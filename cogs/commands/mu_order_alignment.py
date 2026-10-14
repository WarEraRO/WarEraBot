"""/mu_order_alignment: whether a configured military unit's battle orders follow Romania's country orders.

Read-only and on demand: the reply is posted in the channel and nobody is pinged. Both order sets come from the live
active-battle list (`countryOrders` / `muOrders` of each side); priority levels come from battleOrder.getByBattle.
The in-game order rank is hidden from the bot's API key, so the national ranking shown is the battle's place
in the bot's /priority list.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs.commands.fight_wealth import _messages, _pack
from cogs.commands.pills import _unit_ids
from utils.api import (
    get_active_battles,
    get_all_countries,
    get_battle_orders,
    get_military_unit,
    get_military_units_by_ids,
    get_regions_by_ids,
    get_shared_session,
)
from utils.common import country_flag, country_with_flag
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

# the country whose orders MU orders must copy; the same country battle-order_monitor tracks
COUNTRY_NAME = "Romania"
BATTLE_LINK = "https://app.warera.io/battle/{}"
TOURNAMENT_BATTLE_TYPE = "tournament"
SIDES = ("attacker", "defender")
MU_NAMES_TTL = 3600
COUNTRIES_TTL = 3600
# per embed, like the reports; a longer list continues in another embed
EMBED_TOTAL_LIMIT = 4000
# battleOrder priority levels, strongest first; the colours are the game's (red / yellow / green)
PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}
PRIORITY_ORDER = {level: index for index, level in enumerate(PRIORITY_EMOJI)}
MU_MARKER = "🎖️"
# report sections in display order: problems first
CATEGORIES = ("opposite", "not_ordered", "missing", "aligned", "tournament")


def _opposite(side: str) -> str:
    """The other side of a battle."""
    return "defender" if side == "attacker" else "attacker"


def _side_ids(battle: dict, side: str, key: str) -> set[str]:
    """The country or MU ids in `countryOrders` / `muOrders` (`key`) of one side of a battle."""
    return {str(item) for item in ((battle.get(side) or {}).get(key) or [])}


def _region_id(battle: dict) -> str | None:
    """The battle's region id, as battle-order_monitor reads it; None for tournament battles."""
    region = battle.get("region")
    if not region:
        region = (battle.get("defender") or {}).get("region") or (battle.get("attacker") or {}).get("region")
    return str(region) if region else None


def classify_orders(battles: list[dict], mu_id: str, country_id: str) -> dict[str, list[tuple[dict, str]]]:
    """Sort the MU's and the country's active orders into the alignment categories.

    Each category holds (battle, side) pairs, where side is the side the MU ordered, except in "missing",
    where it is the side the country ordered:

    - "aligned": the country ordered the same battle and side.
    - "opposite": the country ordered the other side of the battle.
    - "not_ordered": the country ordered neither side (tournament battles excluded).
    - "tournament": a tournament battle the country did not order, such as an MU tournament.
    - "missing": a country order with no MU order on either side of that battle.
    """
    categories: dict[str, list[tuple[dict, str]]] = {category: [] for category in CATEGORIES}
    for battle in battles:
        mu_sides = [side for side in SIDES if mu_id in _side_ids(battle, side, "muOrders")]
        country_sides = [side for side in SIDES if country_id in _side_ids(battle, side, "countryOrders")]
        for side in mu_sides:
            if side in country_sides:
                categories["aligned"].append((battle, side))
            elif _opposite(side) in country_sides:
                categories["opposite"].append((battle, side))
            elif battle.get("type") == TOURNAMENT_BATTLE_TYPE:
                categories["tournament"].append((battle, side))
            else:
                categories["not_ordered"].append((battle, side))
        # a battle the MU ordered on the wrong side is already listed under "opposite"
        if not mu_sides:
            categories["missing"].extend((battle, side) for side in country_sides)
    return categories


class MuOrderAlignment(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # MU id -> in-game name (mu.getById), for the configured military units
        self._mu_names: dict[str, str] = {}
        self._mu_names_at = 0.0
        self._mu_names_task: asyncio.Task | None = None
        # country id -> name, and the id of COUNTRY_NAME; refreshed every COUNTRIES_TTL seconds
        self._country_names: dict[str, str] = {}
        self._country_id: str | None = None
        self._countries_at = 0.0
        # region id -> name; region names do not change
        self._region_names: dict[str, str] = {}

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

    async def _load_countries(self, session) -> bool:
        """Refresh the country names and COUNTRY_NAME's id when stale; False when the id is unknown."""
        if self._country_id and time.monotonic() - self._countries_at < COUNTRIES_TTL:
            return True
        countries = await get_all_countries(session)
        if not countries:
            # a failed refresh keeps the previous list
            return self._country_id is not None
        for country in countries:
            country_id = str(country.get("_id") or country.get("id") or "")
            name = str(country.get("name") or "")
            if not country_id or not name:
                continue
            self._country_names[country_id] = name
            if name.lower() == COUNTRY_NAME.lower():
                self._country_id = country_id
        self._countries_at = time.monotonic()
        return self._country_id is not None

    async def _load_region_names(self, region_ids: set[str], session) -> None:
        """Fetch the names of the regions not cached yet; regions that fail are shown without a name."""
        missing = [region_id for region_id in region_ids if region_id not in self._region_names]
        if not missing:
            return
        regions = await get_regions_by_ids(missing, session)
        for region_id, region in regions.items():
            if isinstance(region, dict) and region.get("name"):
                self._region_names[region_id] = str(region["name"])

    async def _priority_numbers(self) -> dict[str, int]:
        """Battle id -> its 1-based place in the bot's /priority list; empty when the monitor is not loaded."""
        monitor = self.bot.get_cog("BattleOrderMonitorJob") if self.bot else None
        if monitor is None:
            return {}
        numbers: dict[str, int] = {}
        for number, entry in enumerate(await monitor.get_priorities(), start=1):
            numbers.setdefault(str(entry.get("battle_id")), number)
        return numbers

    @app_commands.command(
        name="mu_order_alignment",
        description="Check whether a military unit's battle orders follow Romania's country orders.",
    )
    @app_commands.describe(military_unit="Military unit (one of the units configured for this server)")
    async def mu_order_alignment_command(self, interaction: discord.Interaction, military_unit: str):
        tr = await get_translator(interaction.guild_id)
        mu_id = self._find_unit(military_unit)
        if mu_id is None:
            await interaction.response.send_message(tr("mu_alignment.unknown_unit"), ephemeral=True)
            return
        await interaction.response.defer()

        session = await get_shared_session()
        battles, military_unit_data, countries_loaded = await asyncio.gather(
            get_active_battles(session), get_military_unit(mu_id, session), self._load_countries(session)
        )
        if isinstance(military_unit_data, dict) and military_unit_data.get("name"):
            self._mu_names[mu_id] = str(military_unit_data["name"])
        if battles is None or not countries_loaded:
            await interaction.followup.send(tr("mu_alignment.fetch_failed"), ephemeral=True)
            return

        categories = classify_orders(battles, mu_id, self._country_id)
        listed = [(battle, side) for pairs in categories.values() for battle, side in pairs]
        # levels are read from both sides: an "opposite" line shows the country's level on the other side
        order_sides = [(str(battle.get("_id")), side) for battle, _ in listed for side in SIDES]
        region_ids = {region_id for battle, _ in listed if (region_id := _region_id(battle))}
        orders, _, numbers = await asyncio.gather(
            get_battle_orders(order_sides, session) if order_sides else asyncio.sleep(0, result={}),
            self._load_region_names(region_ids, session),
            self._priority_numbers(),
        )

        mu_name = discord.utils.escape_markdown(self._mu_names.get(mu_id, mu_id))
        embeds = self._build_embeds(mu_name, mu_id, categories, orders, numbers, datetime.now(timezone.utc), tr)
        for message_embeds in _messages(embeds):
            await interaction.followup.send(embeds=message_embeds)

    def _level(self, orders: dict, battle: dict, side: str, key: str, owner_id: str, tr: Translator) -> str:
        """The level of `owner_id`'s order (an MU or country id under `key`) as " 🔴 High"; "" when unknown."""
        for order in orders.get((str(battle.get("_id")), side)) or []:
            level = str(order.get("priority") or "")
            if str(order.get(key) or "") == owner_id and level in PRIORITY_EMOJI:
                return f" {PRIORITY_EMOJI[level]} {tr(f'mu_alignment.priority.{level}')}"
        return ""

    def _level_rank(self, orders: dict, battle: dict, side: str, key: str, owner_id: str) -> int:
        """Sort key of an order's priority level: high first, unknown last."""
        for order in orders.get((str(battle.get("_id")), side)) or []:
            if str(order.get(key) or "") == owner_id:
                return PRIORITY_ORDER.get(str(order.get("priority") or ""), len(PRIORITY_ORDER))
        return len(PRIORITY_ORDER)

    def _side_label(self, battle: dict, side: str, tr: Translator) -> str:
        """The country fighting on `side` with its flag; the side's name in tournament battles."""
        country_id = str((battle.get(side) or {}).get("country") or "")
        if not country_id:
            return tr(f"common.side_title.{side}")
        return country_with_flag(self._country_names.get(country_id), left=True, unknown=tr("common.unknown"))

    def _battle_title(self, battle: dict, numbers: dict[str, int], tr: Translator) -> str:
        """Linked "A vs B", then the region and the battle's /priority number when known."""
        attacker = str((battle.get("attacker") or {}).get("country") or "")
        defender = str((battle.get("defender") or {}).get("country") or "")
        unknown = tr("common.unknown")
        if attacker and defender:
            title = (
                f"{country_with_flag(self._country_names.get(attacker), left=True, unknown=unknown)} vs "
                f"{country_with_flag(self._country_names.get(defender), left=False, unknown=unknown)}"
            )
        else:
            title = tr("common.tournament_battle")
        line = f"[{title}]({BATTLE_LINK.format(battle.get('_id'))})"
        region_name = self._region_names.get(_region_id(battle) or "")
        if region_name:
            line += f" · {discord.utils.escape_markdown(region_name)}"
        number = numbers.get(str(battle.get("_id")))
        if number:
            line += " · " + tr("mu_alignment.priority_number", number=number)
        return line

    def _entry(
        self, category: str, battle: dict, side: str, mu_id: str, orders: dict, numbers: dict[str, int], tr: Translator
    ) -> str:
        """Two lines for one order: the battle, then who fights for whom and at which priority level."""
        country_marker = country_flag(COUNTRY_NAME) or COUNTRY_NAME
        country_id = self._country_id or ""
        if category == "missing":
            details = tr("mu_alignment.ordered_for", who=country_marker, side=self._side_label(battle, side, tr))
            details += self._level(orders, battle, side, "country", country_id, tr)
        elif category == "aligned":
            parts = [tr("mu_alignment.for_side", side=self._side_label(battle, side, tr))]
            # a level that could not be fetched is left out rather than shown as unknown
            for marker, key, owner_id in ((country_marker, "country", country_id), (MU_MARKER, "mu", mu_id)):
                level = self._level(orders, battle, side, key, owner_id, tr)
                if level:
                    parts.append(marker + level)
            details = " · ".join(parts)
        else:
            details = tr("mu_alignment.ordered_for", who=MU_MARKER, side=self._side_label(battle, side, tr))
            details += self._level(orders, battle, side, "mu", mu_id, tr)
            if category == "opposite":
                other = _opposite(side)
                details += " · " + tr("mu_alignment.ordered_for", who=country_marker, side=self._side_label(battle, other, tr))
                details += self._level(orders, battle, other, "country", country_id, tr)
        return f"{self._battle_title(battle, numbers, tr)}\n{details}"

    def _build_embeds(
        self,
        mu_name: str,
        mu_id: str,
        categories: dict[str, list[tuple[dict, str]]],
        orders: dict,
        numbers: dict[str, int],
        now: datetime,
        tr: Translator,
    ) -> list[discord.Embed]:
        """The verdict and order counts, then one section per non-empty category, problems first.

        Within a section, battles in the /priority list come first in its order, then by priority level.
        Content over EMBED_TOTAL_LIMIT continues in more embeds numbered "(i/N)".
        """
        country = country_with_flag(COUNTRY_NAME, left=True)
        mu_orders = sum(len(categories[category]) for category in CATEGORIES if category != "missing")
        country_orders = len(categories["aligned"]) + len(categories["opposite"]) + len(categories["missing"])
        issues = len(categories["opposite"]) + len(categories["not_ordered"])
        if issues:
            verdict, color = tr("mu_alignment.verdict_issues", count=issues, total=mu_orders, country=country), discord.Color.orange()
        elif categories["aligned"]:
            verdict, color = tr("mu_alignment.verdict_aligned", country=country), discord.Color.green()
        elif mu_orders:
            # only tournament orders, which the country does not set
            verdict, color = tr("mu_alignment.verdict_tournament_only"), discord.Color.blurple()
        elif country_orders:
            verdict, color = tr("mu_alignment.verdict_no_mu_orders", country=country), discord.Color.greyple()
        else:
            verdict, color = tr("mu_alignment.verdict_none", country=country), discord.Color.greyple()
        description = verdict + "\n" + tr(
            "mu_alignment.counts", country=country, country_count=country_orders, mu_count=mu_orders
        )

        fields: list[tuple[str, str]] = []
        for category in CATEGORIES:
            pairs = categories[category]
            if not pairs:
                continue
            # the country's level ranks "missing" orders, the MU's level ranks the rest
            key, owner_id = ("country", self._country_id or "") if category == "missing" else ("mu", mu_id)
            pairs = sorted(
                pairs,
                key=lambda pair: (
                    numbers.get(str(pair[0].get("_id")), len(numbers) + 1),
                    self._level_rank(orders, pair[0], pair[1], key, owner_id),
                ),
            )
            # field names get the plain name: the flag is only needed once, in the description
            title = tr(f"mu_alignment.{category}_title", count=len(pairs), country=COUNTRY_NAME)
            fields += _pack(title, [self._entry(category, battle, side, mu_id, orders, numbers, tr) for battle, side in pairs])

        title = tr("mu_alignment.title", mu=mu_name)
        footer = tr("mu_alignment.footer", mu=MU_MARKER)

        def new_embed(first: bool) -> discord.Embed:
            embed = discord.Embed(title=title, description=description if first else None, color=color, timestamp=now)
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

    @mu_order_alignment_command.autocomplete("military_unit")
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
    await bot.add_cog(MuOrderAlignment(bot))
