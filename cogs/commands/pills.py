import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs.tasks.military_unit_daily_report import PILL_CODE, _parse_iso, _pill_settings
from config import config
from utils.api import get_game_config, get_military_unit, get_mu_members, get_shared_session, get_user_info
from utils.common import to_local
from utils.computational import is_economy_build

logger = logging.getLogger(__name__)

USER_CONCURRENCY = 5
GAME_CONFIG_TTL = 3600
MU_NAMES_TTL = 3600
# per embed, kept below Discord's 4096 description cap; longer lists continue in another embed
EMBED_TOTAL_LIMIT = 4000


def _fmt_left(delta: timedelta) -> str:
    """Time left as `3h05m` or `42m`."""
    minutes = max(0, int(delta.total_seconds() // 60))
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"


def _hour_lines(entries: list[tuple[datetime, datetime, str]], now: datetime) -> list[str]:
    """One line per local hour of the first time: `` `~10` Name1 (3h05m), Name2 (4h12m)``, where the
    parenthesis is the time left until the second time."""
    lines: list[str] = []
    current_hour = None
    for grouped_at, ends_at, name in sorted(entries):
        hour = to_local(grouped_at).replace(minute=0, second=0, microsecond=0)
        item = f"{name} ({_fmt_left(ends_at - now)})"
        if hour != current_hour:
            lines.append(f"`~{hour:%H}` {item}")
            current_hour = hour
        else:
            lines[-1] += f", {item}"
    return lines


def _split(lines: list[str]) -> list[str]:
    """Lines joined into descriptions of at most EMBED_TOTAL_LIMIT characters."""
    chunks: list[str] = []
    current = ""
    for line in lines:
        if current and len(current) + 1 + len(line) > EMBED_TOTAL_LIMIT:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


def _unit_ids() -> list[str]:
    return [str(unit["id"]) for unit in config.get("military_units", []) if unit.get("id")]


class Pills(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._game_config: dict | None = None
        self._game_config_at = 0.0
        # MU id -> in-game name (mu.getById), for the configured military units
        self._mu_names: dict[str, str] = {}
        self._mu_names_at = 0.0
        self._mu_names_task: asyncio.Task | None = None

    async def cog_load(self):
        # warmed in the background so autocomplete has names right away
        self._refresh_mu_names()

    def cog_unload(self):
        if self._mu_names_task and not self._mu_names_task.done():
            self._mu_names_task.cancel()

    def _refresh_mu_names(self) -> None:
        """Start refreshing the MU names unless a refresh is already running."""
        if self._mu_names_task and not self._mu_names_task.done():
            return

        async def _refresh():
            session = await get_shared_session()
            unit_ids = _unit_ids()
            results = await asyncio.gather(*(get_military_unit(mu_id, session) for mu_id in unit_ids))
            for mu_id, military_unit in zip(unit_ids, results):
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

    async def _settings(self, session) -> dict:
        if self._game_config is None or time.monotonic() - self._game_config_at > GAME_CONFIG_TTL:
            game_config = await get_game_config(session)
            if game_config:
                self._game_config, self._game_config_at = game_config, time.monotonic()
        # falls back to the default pill durations when gameConfig could not be fetched
        return _pill_settings(self._game_config)

    async def _fetch_user(self, user_id: str, session, semaphore: asyncio.Semaphore) -> dict | None:
        async with semaphore:
            return await get_user_info(user_id, session)

    @app_commands.command(name="pills", description="Show who is pilled, in debuff or not pilled in a military unit.")
    @app_commands.describe(military_unit="Military unit (one of the units configured for this server)")
    async def pills(self, interaction: discord.Interaction, military_unit: str):
        mu_id = self._find_unit(military_unit)
        if mu_id is None:
            await interaction.response.send_message("Unknown military unit. Pick one from the list.", ephemeral=True)
            return
        await interaction.response.defer()

        session = await get_shared_session()
        # muMember.getByMu is not in the public OpenAPI spec (see utils/api.py)
        settings, members, military_unit_data = await asyncio.gather(
            self._settings(session), get_mu_members(mu_id, session), get_military_unit(mu_id, session)
        )
        if isinstance(military_unit_data, dict) and military_unit_data.get("name"):
            self._mu_names[mu_id] = str(military_unit_data["name"])
        mu_name = discord.utils.escape_markdown(self._mu_names.get(mu_id, mu_id))
        if members is None:
            await interaction.followup.send("Could not fetch the military unit members. Try again later.", ephemeral=True)
            return

        semaphore = asyncio.Semaphore(USER_CONCURRENCY)
        users = await asyncio.gather(
            *(self._fetch_user(str(member.get("user")), session, semaphore) for member in members)
        )
        now = datetime.now(timezone.utc)

        pilled: list[tuple[datetime, datetime, str]] = []
        debuffed: list[tuple[datetime, datetime, str]] = []
        not_pilled: list[str] = []
        economy = 0
        for user in users:
            if not user:
                continue
            name = discord.utils.escape_markdown(str(user.get("username") or "unknown"))
            buffs = user.get("buffs") or {}
            # older responses had no codes, so an end time without codes is taken as a pill
            buff_end = _parse_iso(buffs.get("buffEndAt")) if PILL_CODE in (buffs.get("buffCodes") or [PILL_CODE]) else None
            debuff_end = _parse_iso(buffs.get("debuffEndAt")) if PILL_CODE in (buffs.get("debuffCodes") or [PILL_CODE]) else None
            if buff_end and buff_end > now:
                # grouped by the hour the pill was taken
                pilled.append((buff_end - settings["buff"], buff_end, name))
            elif debuff_end and debuff_end > now:
                # grouped by the hour the debuff ends
                debuffed.append((debuff_end, debuff_end, name))
            elif is_economy_build(user):
                economy += 1
            else:
                not_pilled.append(name)
        missing = len(members) - sum(1 for user in users if user)
        not_pilled.sort(key=str.lower)

        tz_name = to_local(now).tzname()
        lines = [f"💊 **Pilled ({len(pilled)})** · pill hour → time left"]
        lines += _hour_lines(pilled, now) or ["—"]
        lines.append(f"🥴 **Debuff ({len(debuffed)})** · ends at → time left")
        lines += _hour_lines(debuffed, now) or ["—"]
        lines.append(f"⚪ **Not pilled ({len(not_pilled)})**")
        lines.append(", ".join(not_pilled) or "—")

        footer = f"Hours in {tz_name}"
        if economy:
            footer += f" · {economy} economy member{'s' if economy != 1 else ''} not listed"
        if missing:
            footer += f" · {missing} member{'s' if missing != 1 else ''} could not be fetched"

        chunks = _split(lines)
        embeds = []
        for index, chunk in enumerate(chunks, start=1):
            title = f"Pills · {mu_name}"
            if len(chunks) > 1:
                title += f" ({index}/{len(chunks)})"
            embed = discord.Embed(title=title, description=chunk, color=discord.Color.purple(), timestamp=now)
            embed.set_footer(text=footer)
            embeds.append(embed)
        await interaction.followup.send(embeds=embeds)

    @pills.autocomplete("military_unit")
    async def military_unit_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
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
    await bot.add_cog(Pills(bot))
