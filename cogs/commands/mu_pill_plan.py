"""/mu_pill_plan: when the fighters of a configured military unit can take a Pill together, hour by hour.

Each fighter's current Pill phase (from `pill_state`) is projected forward with the gameConfig buff and debuff
durations, assuming nobody takes a new Pill: buff, then debuff, then able to take one again. The fighters are
also split into squads of SQUAD_SIZE, built from the hours they took their current Pill, that each take the
Pill at their own hour every day.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs.commands.fight_wealth import _pack
from cogs.commands.pills import _unit_ids
from cogs.tasks.military_unit_daily_report import _pill_settings, pill_state
from utils.api import get_game_config, get_military_unit, get_military_units_by_ids, get_mu_members, get_shared_session, get_users_info
from utils.common import to_local
from utils.computational import is_economy_build
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

GAME_CONFIG_TTL = 3600
MU_NAMES_TTL = 3600
# fighters per rotation squad (user request, 2026-10-25)
SQUAD_SIZE = 4
DAY_MINUTES = 24 * 60
PHASES = ("buff", "debuff", "ready")
PHASE_EMOJI = {"buff": "💊", "debuff": "🥴", "ready": "✅"}


def phase_at(state: dict, at: datetime, settings: dict) -> str:
    """Pill phase ("buff", "debuff" or "ready") of a member at `at`, if they take no new Pill before then.

    Args:
        state: The member's `pill_state` taken now.
        at: The time to project to, at or after the time `state` was taken.
        settings: Pill durations from `_pill_settings`.
    """
    if state["pilled_at"] is None or at >= state["ready_at"]:
        return "ready"
    return "buff" if at < state["pilled_at"] + settings["buff"] else "debuff"


def phase_counts(states: list[dict], at: datetime, settings: dict) -> dict[str, int]:
    """How many members are in each phase of PHASES at `at`."""
    counts = dict.fromkeys(PHASES, 0)
    for state in states:
        counts[phase_at(state, at, settings)] += 1
    return counts


def pill_timeline(states: list[dict], now: datetime, settings: dict) -> list[tuple[datetime, dict[str, int]]]:
    """Phase counts now, then at every following full hour where they change, until every member is ready.

    Returns:
        (time, counts) rows; the first row is `now`, and the last one has every member "ready".
    """
    rows = [(now, phase_counts(states, now, settings))]
    at = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    # ends: every ready_at is at most buff + debuff away
    while rows[-1][1]["ready"] < len(states):
        counts = phase_counts(states, at, settings)
        if counts != rows[-1][1]:
            rows.append((at, counts))
        at += timedelta(hours=1)
    return rows


def all_ready_at(states: list[dict], now: datetime) -> datetime:
    """Earliest time every member can take a Pill at once (`now` when they already can)."""
    return max([now] + [state["ready_at"] for state in states])


def all_available_at(states: list[dict], now: datetime, settings: dict) -> datetime:
    """Earliest time no member is in debuff, i.e. each one is in buff or can take a Pill.

    A debuff only ends at a member's ready_at, so the answer is `now` or one of those times.
    """
    candidates = sorted({now} | {state["ready_at"] for state in states if state["ready_at"] > now})
    for at in candidates:
        if phase_counts(states, at, settings)["debuff"] == 0:
            return at
    return candidates[-1]


def _minute_of_day(at: datetime) -> int:
    """Minutes since local midnight of `at`."""
    local = to_local(at)
    return local.hour * 60 + local.minute


def _round_up_hour(minute: int) -> int:
    """A minute of the day rounded up to the next full hour, wrapping past midnight."""
    return -(-minute // 60) * 60 % DAY_MINUTES


def _hhmm(minute: int) -> str:
    """A minute of the day as `HH:MM`."""
    minute %= DAY_MINUTES
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _next_at(minute: int, not_before: datetime) -> datetime:
    """The first local time at minute of the day `minute` that is not before `not_before`."""
    local = to_local(not_before)
    candidate = local.replace(hour=minute // 60, minute=minute % 60, second=0, microsecond=0)
    # wall-clock arithmetic on the zoneinfo datetime, so the hour stays the same across a DST change
    return candidate if candidate >= local else candidate + timedelta(days=1)


def _new_squad_minute(minutes: list[int], now: datetime, buff_minutes: int) -> int:
    """Daily Pill time for a squad with no current Pill: where the day has the most room.

    The first squad starts at the next full hour. Later ones go into the widest gap between two squads' Pill
    times: right where the earlier squad's buff ends when the gap is longer than a buff, else in its middle.
    """
    if not minutes:
        return _round_up_hour(_minute_of_day(now))
    ordered = sorted(set(minutes))
    gap, after = max(((ordered[(index + 1) % len(ordered)] - minute) % DAY_MINUTES or DAY_MINUTES, minute)
                     for index, minute in enumerate(ordered))
    return _round_up_hour(after + (buff_minutes if gap > buff_minutes else gap // 2))


def daily_rotation(
    fighters: list[tuple[str, dict]], now: datetime, settings: dict, size: int = SQUAD_SIZE
) -> list[dict]:
    """Squads of `size` that each take the Pill at their own hour every day, built from the current Pills.

    Fighters on a Pill now are sorted by the local time of day they took it, starting after the widest gap
    between two of those times, and every `size` in a row form a squad. A squad's daily Pill time is its latest
    member's, rounded up to the full hour; the cycle (buff + debuff) is under a day, so each member is ready
    again by then. Fighters without a Pill can take one any time: they first fill squads with free places,
    soonest turn first, and the rest form new squads placed by `_new_squad_minute`.

    Args:
        fighters: (name, `pill_state` taken at `now`) per fighter.
        now: The time the states were taken.
        settings: Pill durations from `_pill_settings`.
        size: Fighters per squad.

    Returns:
        One {"names", "minute", "start", "end"} per squad, soonest turn first: "minute" is the daily Pill time
        (minutes since local midnight), "start" and "end" the first turn every member can make.
    """
    buff_minutes = int(settings["buff"].total_seconds() // 60)
    pilled = sorted(
        ((_minute_of_day(state["pilled_at"]), name, state) for name, state in fighters if state["pilled_at"] is not None),
        key=lambda item: (item[0], item[1].lower()),
    )
    free = sorted(((name, state) for name, state in fighters if state["pilled_at"] is None), key=lambda item: item[0].lower())

    squads: list[dict] = []
    if pilled:
        count = len(pilled)
        # a squad never spans the widest gap, so its members' Pill times stay as close as possible
        first = (max(range(count), key=lambda index: (pilled[(index + 1) % count][0] - pilled[index][0]) % DAY_MINUTES) + 1) % count
        ordered = pilled[first:] + pilled[:first]
        for index in range(0, count, size):
            group = ordered[index:index + size]
            base = group[0][0]
            latest = base + max((minute - base) % DAY_MINUTES for minute, _, _ in group)
            squads.append({"minute": _round_up_hour(latest), "members": [(name, state) for _, name, state in group]})

    def first_start(squad: dict) -> datetime:
        """The squad's first turn at its daily time once every member can take a Pill."""
        return _next_at(squad["minute"], max([now] + [state["ready_at"] for _, state in squad["members"]]))

    # free fighters are ready now, so joining a squad never delays its turn
    for squad in sorted(squads, key=first_start):
        while free and len(squad["members"]) < size:
            squad["members"].append(free.pop(0))
    while free:
        group, free = free[:size], free[size:]
        squads.append({"minute": _new_squad_minute([squad["minute"] for squad in squads], now, buff_minutes), "members": group})

    turns = []
    for squad in squads:
        start = first_start(squad)
        turns.append({
            "names": [name for name, _ in squad["members"]],
            "minute": squad["minute"],
            "start": start,
            "end": start + settings["buff"],
        })
    return sorted(turns, key=lambda turn: (turn["start"], turn["names"]))


def coverage_gaps(minutes: list[int], buff_minutes: int) -> list[tuple[int, int]]:
    """Daily (start, end) minute ranges when no squad is in buff, given each squad's daily Pill time."""
    if not minutes or buff_minutes <= 0:
        return []
    covered = [False] * DAY_MINUTES
    for minute in minutes:
        for offset in range(min(buff_minutes, DAY_MINUTES)):
            covered[(minute + offset) % DAY_MINUTES] = True
    if all(covered):
        return []
    # walk the day once from a covered minute, so a gap across midnight stays one range
    begin = covered.index(True)
    gaps, gap_start = [], None
    for offset in range(1, DAY_MINUTES + 1):
        minute = (begin + offset) % DAY_MINUTES
        if not covered[minute] and gap_start is None:
            gap_start = minute
        elif covered[minute] and gap_start is not None:
            gaps.append((gap_start, minute))
            gap_start = None
    return gaps


def _clock(at: datetime, now: datetime, tr: Translator) -> str:
    """Local `HH:MM`, prefixed with the weekday when it is not today (local date)."""
    local = to_local(at)
    if local.date() == to_local(now).date():
        return f"{local:%H:%M}"
    return tr.strftime(local, tr("mu_pill_plan.day_time_format"))


class MuPillPlan(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._game_config: dict | None = None
        self._game_config_at = 0.0
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

    async def _settings(self, session) -> dict:
        """Pill durations from gameConfig (cached for GAME_CONFIG_TTL), or the defaults when it can't be fetched."""
        if self._game_config is None or time.monotonic() - self._game_config_at > GAME_CONFIG_TTL:
            game_config = await get_game_config(session)
            if game_config:
                self._game_config, self._game_config_at = game_config, time.monotonic()
        return _pill_settings(self._game_config)

    @app_commands.command(
        name="mu_pill_plan",
        description="Plan when the fighters of a military unit can take a Pill together, hour by hour.",
    )
    @app_commands.describe(military_unit="Military unit (one of the units configured for this server)")
    async def mu_pill_plan_command(self, interaction: discord.Interaction, military_unit: str):
        tr = await get_translator(interaction.guild_id)
        mu_id = self._find_unit(military_unit)
        if mu_id is None:
            await interaction.response.send_message(tr("mu_pill_plan.unknown_unit"), ephemeral=True)
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
            await interaction.followup.send(tr("mu_pill_plan.members_unavailable"), ephemeral=True)
            return

        # one batched request for every member
        users_by_id = await get_users_info([str(member.get("user")) for member in members], session)
        now = datetime.now(timezone.utc)
        fighters: list[tuple[str, dict]] = []
        economy = missing = 0
        for member in members:
            user = users_by_id.get(str(member.get("user")))
            if not user:
                missing += 1
                continue
            state = pill_state(user, now, settings)
            # a fight build, as for contract pings (no skill points counts as economy), or anyone already on a Pill
            if state["phase"] is None and is_economy_build(user) is not False:
                economy += 1
                continue
            fighters.append((discord.utils.escape_markdown(str(user.get("username") or tr("common.unknown"))), state))

        embed = self._build_embed(mu_name, fighters, economy, missing, now, settings, tr)
        await interaction.followup.send(embed=embed)

    def _build_embed(
        self,
        mu_name: str,
        fighters: list[tuple[str, dict]],
        economy: int,
        missing: int,
        now: datetime,
        settings: dict,
        tr: Translator,
    ) -> discord.Embed:
        """The plan embed: counts now, when all can take a Pill together, timeline, rotation squads, who is not ready.

        One embed is enough: an MU has at most 25 members (dormitories level 5), so the timeline has at most
        about 25 rows, the rotation at most 7 squads and the waiting list at most 25 lines.

        Args:
            mu_name: The MU's in-game name, already markdown-escaped.
            fighters: (escaped name, `pill_state` taken at `now`) per fighter.
            economy: Members left out for an economy build.
            missing: Members whose player could not be fetched.
            now: The time the states were taken.
            settings: Pill durations from `_pill_settings`.
            tr: Translator for the server's language.
        """
        embed = discord.Embed(title=tr("mu_pill_plan.title", mu=mu_name), color=discord.Color.purple(), timestamp=now)
        footer = tr(
            "mu_pill_plan.footer",
            tz=to_local(now).tzname(),
            buff=f"{settings['buff'].total_seconds() / 3600:g}",
            debuff=f"{settings['debuff'].total_seconds() / 3600:g}",
        )
        if economy:
            footer += " · " + tr.plural("mu_pill_plan.footer_economy", economy)
        if missing:
            footer += " · " + tr.plural("mu_pill_plan.footer_missing", missing)
        embed.set_footer(text=footer)
        if not fighters:
            embed.description = tr("mu_pill_plan.no_fighters")
            return embed

        states = [state for _, state in fighters]
        counts = phase_counts(states, now, settings)
        ready_at = all_ready_at(states, now)
        available_at = all_available_at(states, now, settings)
        lines = [tr("mu_pill_plan.now_line", total=len(states), **counts)]
        if ready_at <= now:
            lines.append(tr("mu_pill_plan.all_ready_now"))
        else:
            lines.append(tr("mu_pill_plan.all_ready", time=_clock(ready_at, now, tr)))
            # only worth a line when fighting together starts before everyone can take a Pill
            if available_at < ready_at:
                lines.append(
                    tr("mu_pill_plan.all_available_now")
                    if available_at <= now
                    else tr("mu_pill_plan.all_available", time=_clock(available_at, now, tr))
                )
        embed.description = "\n".join(lines)

        timeline: list[str] = []
        day = to_local(now).date()
        for index, (at, row) in enumerate(pill_timeline(states, now, settings)):
            local = to_local(at)
            if local.date() != day:
                day = local.date()
                timeline.append(f"**{tr.strftime(local, '%A').capitalize()}**")
            label = tr("mu_pill_plan.now") if index == 0 else f"{local:%H:%M}"
            timeline.append(f"`{label}` " + " · ".join(f"{PHASE_EMOJI[phase]} {row[phase]}" for phase in PHASES))
        if len(timeline) > 1:
            for name, value in _pack(tr("mu_pill_plan.timeline_title"), timeline):
                embed.add_field(name=name, value=value, inline=False)

        buff_minutes = int(settings["buff"].total_seconds() // 60)
        turns = daily_rotation(fighters, now, settings)
        squads = [
            f"`{index}.` **{_hhmm(turn['minute'])} – {_hhmm(turn['minute'] + buff_minutes)}** · "
            f"▶ {_clock(turn['start'], now, tr)} · {', '.join(turn['names'])}"
            for index, turn in enumerate(turns, start=1)
        ]
        squads += [
            tr("mu_pill_plan.rotation_gap", start=_hhmm(start), end=_hhmm(end))
            for start, end in coverage_gaps([turn["minute"] for turn in turns], buff_minutes)
        ]
        for name, value in _pack(tr("mu_pill_plan.rotation_title", size=SQUAD_SIZE), squads):
            embed.add_field(name=name, value=value, inline=False)

        waiting = sorted(
            ((state["ready_at"], name, phase_at(state, now, settings)) for name, state in fighters if state["ready_at"] > now),
            key=lambda item: (item[0], item[1].lower()),
        )
        if waiting:
            lines = [f"{PHASE_EMOJI[phase]} **{name}** · {_clock(at, now, tr)}" for at, name, phase in waiting]
            for name, value in _pack(tr("mu_pill_plan.waiting_title", count=len(waiting)), lines):
                embed.add_field(name=name, value=value, inline=False)
        return embed

    @mu_pill_plan_command.autocomplete("military_unit")
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
    await bot.add_cog(MuPillPlan(bot))
