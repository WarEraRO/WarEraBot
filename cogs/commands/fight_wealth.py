"""/fight_wealth: members of a configured military unit ranked by fight wealth (all wealth but companies)."""
import asyncio
import logging
import time
from datetime import datetime, timezone
from statistics import mean, median

import discord
from discord import app_commands
from discord.ext import commands

from cogs.commands.pills import _unit_ids
from cogs.tasks.military_unit_daily_report import _fmt_short, _wealth_tier_counts, _wealth_tier_label
from utils.api import get_military_unit, get_military_units_by_ids, get_mu_members, get_shared_session, get_users_full
from utils.computational import FIGHT_WEALTH_PARTS, FIGHT_WEALTH_TIERS, fight_wealth, fight_wealth_tier, is_economy_build
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

MU_NAMES_TTL = 3600
EMBED_FIELD_VALUE_LIMIT = 1024
# per embed, like the reports; a longer list continues in another embed
EMBED_TOTAL_LIMIT = 4000
# Discord caps a message at 10 embeds and 6000 characters across all of them
MESSAGE_EMBED_LIMIT = 10
MESSAGE_TOTAL_LIMIT = 6000
PART_EMOJI = {"money": "💵", "items": "📦", "equipments": "🛡️", "weapons": "🔫"}


def _pack(title: str, lines: list[str]) -> list[tuple[str, str]]:
    """Whole lines packed into (name, value) fields of at most EMBED_FIELD_VALUE_LIMIT characters.

    Only the first field carries `title`; the rest are untitled continuations.
    """
    fields: list[tuple[str, str]] = []
    value = ""
    for line in lines:
        if value and len(value) + 1 + len(line) > EMBED_FIELD_VALUE_LIMIT:
            fields.append((title if not fields else "​", value))
            value = line
        else:
            value = f"{value}\n{line}" if value else line
    if value:
        fields.append((title if not fields else "​", value))
    return fields


def _messages(embeds: list[discord.Embed]) -> list[list[discord.Embed]]:
    """Group the embeds into as few messages as Discord's per-message limits allow."""
    messages: list[list[discord.Embed]] = []
    for embed in embeds:
        if (
            messages
            and len(messages[-1]) < MESSAGE_EMBED_LIMIT
            and sum(len(item) for item in messages[-1]) + len(embed) <= MESSAGE_TOTAL_LIMIT
        ):
            messages[-1].append(embed)
        else:
            messages.append([embed])
    return messages


class FightWealth(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # MU id -> in-game name (mu.getById), for the configured military units
        self._mu_names: dict[str, str] = {}
        self._mu_names_at = 0.0
        self._mu_names_task: asyncio.Task | None = None

    async def cog_load(self):
        """Start fetching the configured MUs' names; warmed in the background so autocomplete has them right away."""
        self._refresh_mu_names()

    def cog_unload(self):
        """Cancel a running MU name refresh."""
        if self._mu_names_task and not self._mu_names_task.done():
            self._mu_names_task.cancel()

    def _refresh_mu_names(self) -> None:
        """Start refreshing the MU names unless a refresh is already running."""
        if self._mu_names_task and not self._mu_names_task.done():
            return

        async def _refresh():
            session = await get_shared_session()
            unit_ids = _unit_ids()
            military_units = await get_military_units_by_ids(unit_ids, session)
            for mu_id in unit_ids:
                military_unit = military_units.get(mu_id)
                # a failed fetch keeps the name already known
                if isinstance(military_unit, dict) and military_unit.get("name"):
                    self._mu_names[mu_id] = str(military_unit["name"])
            self._mu_names_at = time.monotonic()

        self._mu_names_task = asyncio.create_task(_refresh())

    def _find_unit(self, value: str) -> str | None:
        """The configured MU id matching an MU id (autocomplete value) or in-game MU name (typed by hand)."""
        value = (value or "").strip()
        for mu_id in _unit_ids():
            if value == mu_id or value.lower() == self._mu_names.get(mu_id, "").lower():
                return mu_id
        return None

    @app_commands.command(
        name="fight_wealth",
        description="Show the fight wealth (all wealth except companies) and tier of every member of a military unit.",
    )
    @app_commands.describe(military_unit="Military unit (one of the units configured for this server)")
    async def fight_wealth_command(self, interaction: discord.Interaction, military_unit: str):
        tr = await get_translator(interaction.guild_id)
        mu_id = self._find_unit(military_unit)
        if mu_id is None:
            await interaction.response.send_message(tr("fight_wealth.unknown_unit"), ephemeral=True)
            return
        await interaction.response.defer()

        session = await get_shared_session()
        # muMember.getByMu is not in the public OpenAPI spec (see utils/api.py)
        members, military_unit_data = await asyncio.gather(get_mu_members(mu_id, session), get_military_unit(mu_id, session))
        if isinstance(military_unit_data, dict) and military_unit_data.get("name"):
            self._mu_names[mu_id] = str(military_unit_data["name"])
        mu_name = discord.utils.escape_markdown(self._mu_names.get(mu_id, mu_id))
        if members is None:
            await interaction.followup.send(tr("fight_wealth.members_unavailable"), ephemeral=True)
            return

        # one batched request for every member; only the full user carries stats.wealth
        users_by_id = await get_users_full([str(member.get("user")) for member in members], session)
        rows = []
        for member in members:
            user = users_by_id.get(str(member.get("user")))
            wealth = fight_wealth(user) if user else None
            if wealth is None:
                continue
            rows.append({
                "name": discord.utils.escape_markdown(str(user.get("username") or tr("common.unknown"))),
                "wealth": wealth,
                # fighters are members with a fight build, as in the daily report
                "economy": is_economy_build(user) is not False,
            })
        rows.sort(key=lambda row: row["wealth"]["total"], reverse=True)

        embeds = self._build_embeds(mu_name, rows, len(members) - len(rows), datetime.now(timezone.utc), tr)
        for message_embeds in _messages(embeds):
            await interaction.followup.send(embeds=message_embeds)

    def _build_embeds(
        self, mu_name: str, rows: list[dict], missing: int, now: datetime, tr: Translator
    ) -> list[discord.Embed]:
        """Every member ranked by fight wealth, grouped by tier, with the MU totals in the description.

        `rows` must already be sorted richest first; `missing` counts members without wealth data.
        Content over EMBED_TOTAL_LIMIT continues in more embeds numbered "(i/N)".
        """
        title = tr("fight_wealth.title", mu=mu_name)
        footer = tr("fight_wealth.footer")
        if missing:
            footer += " · " + tr.plural("fight_wealth.footer_missing", missing)

        if not rows:
            embed = discord.Embed(title=title, description=tr("fight_wealth.no_data"), color=discord.Color.gold(), timestamp=now)
            embed.set_footer(text=footer)
            return [embed]

        totals = [row["wealth"]["total"] for row in rows]
        by_tier = {
            tier: [(rank, row) for rank, row in enumerate(rows, start=1) if fight_wealth_tier(row["wealth"]["total"]) == tier]
            for tier, _ in FIGHT_WEALTH_TIERS
        }
        description = tr(
            "fight_wealth.summary",
            total=_fmt_short(sum(totals)),
            average=_fmt_short(mean(totals)),
            median=_fmt_short(median(totals)),
        ) + "\n" + _wealth_tier_counts(by_tier, tr)

        fields: list[tuple[str, str]] = []
        for tier, tier_rows in by_tier.items():
            if not tier_rows:
                continue
            lines = [
                f"`{rank}.` **{row['name']}**{' 🏭' if row['economy'] else ''} · **{_fmt_short(row['wealth']['total'])}** · "
                + " ".join(f"{PART_EMOJI[part]} {_fmt_short(row['wealth'][part])}" for part in FIGHT_WEALTH_PARTS)
                for rank, row in tier_rows
            ]
            fields += _pack(f"{_wealth_tier_label(tier, tr)} ({len(tier_rows)})", lines)

        def new_embed(first: bool) -> discord.Embed:
            embed = discord.Embed(
                title=title, description=description if first else None, color=discord.Color.gold(), timestamp=now
            )
            embed.set_footer(text=footer)
            return embed

        embeds = [new_embed(first=True)]
        for name, value in fields:
            # room is kept for the " (i/N)" added to the titles below
            if embeds[-1].fields and len(embeds[-1]) + len(name) + len(value) + len(" (10/10)") > EMBED_TOTAL_LIMIT:
                embeds.append(new_embed(first=False))
            embeds[-1].add_field(name=name, value=value, inline=False)
        if len(embeds) > 1:
            for index, embed in enumerate(embeds, start=1):
                embed.title = f"{title} ({index}/{len(embeds)})"
        return embeds

    @fight_wealth_command.autocomplete("military_unit")
    async def military_unit_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Configured MUs whose in-game name contains `current`, from the cache only (Discord waits about 3 s)."""
        if time.monotonic() - self._mu_names_at > MU_NAMES_TTL:
            self._refresh_mu_names()
        current = (current or "").lower()
        # an MU whose name has not been fetched yet is offered by its id
        names = sorted(((self._mu_names.get(mu_id, mu_id), mu_id) for mu_id in _unit_ids()), key=lambda item: item[0].lower())
        return [
            app_commands.Choice(name=name[:100], value=mu_id)
            for name, mu_id in names
            if current in name.lower()
        ][:25]


async def setup(bot: commands.Bot):
    """Extension entry point for bot.load_extension."""
    await bot.add_cog(FightWealth(bot))
