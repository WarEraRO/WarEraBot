"""/player_alignment: each Romanian player's damage since the daily reset, split by Romania's battle orders.

Players are Romania's citizens (the `userWealth` ranking lists every player with their citizenship) plus every
member of the configured military units, so Romanians holding another citizenship are included; the optional
`military_unit` option narrows the list to one configured MU. Damage comes from the per-round, per-side
`battleRanking.getRanking` of every battle active now or ended since the reset (00:00 UTC). Each ranking entry
carries the player's first and last hit in that round (`createdAt` / `updatedAt`), which places the damage in time.

Ended battles lose their `countryOrders` and `battleOrder.getByBattle` returns nothing for them, so the cog keeps
its own in-memory record of when Romania's orders were up: a 5-minute tracker loop reads the active battles and
stores, per battle side, the stretches of time an order was seen, plus the stretches the tracker itself was running
(coverage). Nothing is stored in the database; a restart starts both records again, and damage the records can't
place shows as unknown.

Categories, per ranking entry (one player, one round, one side):

- ordered: a Romanian order on that side overlapped the player's hit window;
- against: a Romanian order on the other side overlapped it;
- free: neither, and the tracker was running for the whole window;
- unknown: neither, but the window falls outside the tracker's coverage (it was not running).

Damage of a round that was already running at the reset is split with a snapshot of that round's rankings taken by
the first tracker run after the reset (at most BASELINE_MAX_DELAY late). Without the snapshot, an entry whose first
hit came before the reset is pro-rated by time and the reply says how much damage was estimated.

Known limits: the category is decided per entry, over the player's whole hit window in that round, so a player who
hit at 01:00 and again at 14:00 in one long round counts all of it as ordered when an order was up at any time in
between. `warera.battles.get_active` returns a partial list when a later page fails, which the cog can't detect:
orders on the missing battles go unseen for that run, and the command misses those battles' damage.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs.commands.damage import _BuildPager
from cogs.commands.mu_order_alignment import COUNTRY_NAME, SIDES, _opposite
from cogs.commands.pills import _unit_ids
from cogs.tasks.military_unit_daily_report import _fmt_short
from utils.api import warera
from utils.common import country_flag, to_local
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

TRACK_MINUTES = 5
# an order or a tracker run seen at time t covers [t - SLACK, t + SLACK]: it was there somewhere between two runs
SLACK = timedelta(minutes=TRACK_MINUTES)
# two sightings further apart than this start a new stretch (an order taken down and put back, a bot restart)
STRETCH_GAP = timedelta(minutes=2 * TRACK_MINUTES)
# a reset snapshot taken later than this would subtract damage dealt after the reset, so it is not taken
BASELINE_MAX_DELAY = timedelta(minutes=10)
# battle.getBattles filters ended battles on createdAt; the longest battle seen lasted 23.3 h
ENDED_LOOKBACK = timedelta(days=2)
MU_NAMES_TTL = 3600
COUNTRIES_TTL = 3600
PLAYERS_PER_PAGE = 20
NAME_LIMIT = 20
PROFILE_LINK = "https://app.warera.io/user/{}"
CATEGORIES = ("ordered", "against", "free", "unknown")
EMOJI = {"ordered": "✅", "against": "❌", "free": "➖", "unknown": "❔"}
FOREIGN_MARKER = "🌐"


def day_start(now: datetime) -> datetime:
    """The last daily reset before `now`: 00:00 UTC (gameConfig `getDates().previousDayAt`)."""
    return now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def parse_time(value) -> datetime | None:
    """An API ISO timestamp ("2026-11-15T14:04:14.227Z") as an aware UTC datetime; None when missing or invalid."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def extend_stretches(stretches: list[list[datetime]], at: datetime) -> None:
    """Record a sighting at `at`: extend the last [first, last] stretch, or open a new one after STRETCH_GAP."""
    if stretches and at - stretches[-1][1] <= STRETCH_GAP:
        stretches[-1][1] = max(stretches[-1][1], at)
    else:
        stretches.append([at, at])


def overlaps(stretches: list[list[datetime]] | None, start: datetime, end: datetime) -> bool:
    """Whether any stretch, widened by SLACK on both sides, overlaps the window [start, end]."""
    return any(first - SLACK <= end and start <= last + SLACK for first, last in stretches or [])


def covered(stretches: list[list[datetime]], start: datetime, end: datetime) -> bool:
    """Whether one stretch, widened by SLACK on both sides, contains the whole window [start, end]."""
    return any(first - SLACK <= start and end <= last + SLACK for first, last in stretches)


def _share_after(first: datetime, end: datetime, reset: datetime) -> float:
    """The share of the time from `first` to `end` that falls after `reset` (1.0 for an empty span)."""
    span = (end - first).total_seconds()
    return max(0.0, min(1.0, (end - reset).total_seconds() / span)) if span > 0 else 1.0


def entry_damage(
    item: dict, reset: datetime, baseline: dict[str, float] | None, taken_at: datetime | None = None
) -> tuple[float, bool, datetime, datetime] | None:
    """The part of one ranking entry dealt since `reset`, as (damage, estimated, window start, window end).

    The window is the player's hits in the round since the reset. Entries whose last hit came before the reset,
    or with no usable timestamps, give None. An entry whose first hit came before the reset subtracts the
    player's value in `baseline` (the round's snapshot for that side, taken at `taken_at`, a few minutes after
    the reset); the snapshot's own post-reset minutes are added back pro rata, so they are not lost. Without a
    snapshot, the damage is pro-rated by the share of the hit window after the reset and `estimated` is True.
    """
    value = float(item.get("value") or 0)
    first, last = parse_time(item.get("createdAt")), parse_time(item.get("updatedAt"))
    if value <= 0 or first is None or last is None or last < reset:
        return None
    if first >= reset:
        return value, False, first, last
    if baseline is not None:
        before = float(baseline.get(str(item.get("user")), 0))
        if taken_at is not None and taken_at > reset:
            before -= before * _share_after(first, taken_at, reset)
        return max(0.0, value - before), False, reset, last
    return value * _share_after(first, last, reset), True, reset, last


def entry_category(
    orders: dict[tuple[str, str], list[list[datetime]]],
    coverage: list[list[datetime]],
    battle_id: str,
    side: str,
    start: datetime,
    end: datetime,
) -> str:
    """The category (see CATEGORIES) of damage dealt on `side` of `battle_id` between `start` and `end`."""
    if overlaps(orders.get((battle_id, side)), start, end):
        return "ordered"
    if overlaps(orders.get((battle_id, _opposite(side))), start, end):
        return "against"
    return "free" if covered(coverage, start, end) else "unknown"


class PlayerAlignment(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # (battle id, side) -> [[first seen, last seen], ...] of Romania's country order on that side
        self._orders: dict[tuple[str, str], list[list[datetime]]] = {}
        # [[first, last], ...] of successful active-battle reads, by the tracker or the command
        self._coverage: list[list[datetime]] = []
        # the reset the state below belongs to
        self._day: datetime | None = None
        # round id -> side -> {user id: damage} at the reset, for the rounds running across it
        self._baseline: dict[str, dict[str, dict[str, float]]] = {}
        # (round id, side) -> when that snapshot was read
        self._baseline_at: dict[tuple[str, str], datetime] = {}
        self._baseline_done = False
        # MU id -> in-game name (mu.getById), for the configured military units
        self._mu_names: dict[str, str] = {}
        self._mu_names_at = 0.0
        self._mu_names_task: asyncio.Task | None = None
        # country id -> name, and the id of COUNTRY_NAME; refreshed every COUNTRIES_TTL seconds
        self._country_names: dict[str, str] = {}
        self._country_id: str | None = None
        self._countries_at = 0.0

    async def cog_load(self):
        """Warm the MU name cache for autocomplete and start the order tracker."""
        self._refresh_mu_names()
        if self.bot is not None:
            self.order_tracker.start()

    def cog_unload(self):
        """Stop the order tracker and cancel a running MU name refresh."""
        self.order_tracker.cancel()
        if self._mu_names_task and not self._mu_names_task.done():
            self._mu_names_task.cancel()

    @tasks.loop(minutes=TRACK_MINUTES)
    async def order_tracker(self):
        """Record Romania's current orders and, right after the reset, snapshot the rounds running across it."""
        try:
            now = datetime.now(timezone.utc)
            battles, countries_loaded = await asyncio.gather(warera.battles.get_active(), self._load_countries())
            if battles is None or not countries_loaded:
                return
            self._observe(battles, now)
            if not self._baseline_done and now - self._day <= BASELINE_MAX_DELAY:
                await self._take_baseline(battles, self._day)
        except Exception:
            # an unhandled exception would stop the loop until the bot restarts
            logger.exception("player_alignment order tracker failed")

    @order_tracker.before_loop
    async def before_order_tracker(self):
        """Wait until the bot is connected."""
        await self.bot.wait_until_ready()

    def _roll_day(self, reset: datetime) -> None:
        """Start a new day's state at a new reset: drop the old snapshot and stretches that ended before the reset.

        An older reset is ignored: a command started just before midnight observes after the tracker has
        already moved to the new day, and rolling back would wipe the new day's snapshot.
        """
        if self._day is not None and reset <= self._day:
            return
        self._day = reset
        self._baseline = {}
        self._baseline_at = {}
        self._baseline_done = False
        horizon = reset - SLACK
        self._orders = {
            key: kept for key, stretches in self._orders.items()
            if (kept := [stretch for stretch in stretches if stretch[1] >= horizon])
        }
        self._coverage = [stretch for stretch in self._coverage if stretch[1] >= horizon]

    def _observe(self, battles: list[dict], now: datetime) -> None:
        """Record one successful read of the active battles: coverage at `now` and the sides Romania ordered.

        Has no await, so the tracker and the command never interleave inside it.
        """
        self._roll_day(day_start(now))
        extend_stretches(self._coverage, now)
        for battle in battles:
            battle_id = str(battle.get("_id") or "")
            if not battle_id:
                continue
            for side in SIDES:
                ordered_by = {str(item) for item in ((battle.get(side) or {}).get("countryOrders") or [])}
                if self._country_id in ordered_by:
                    extend_stretches(self._orders.setdefault((battle_id, side), []), now)

    async def _take_baseline(self, battles: list[dict], reset: datetime) -> None:
        """Snapshot both side rankings of every round that started before `reset` and is still running.

        Rounds already snapshotted are kept; a ranking that fails or comes back partial is retried by the next
        tracker run, until BASELINE_MAX_DELAY has passed.
        """
        todo = []
        for battle in battles:
            current = battle.get("currentRound")
            if not isinstance(current, dict) or not current.get("_id"):
                continue
            started = parse_time(current.get("createdAt"))
            round_id = str(current["_id"])
            if started is None or started >= reset:
                continue
            todo += [(round_id, side) for side in SIDES if side not in self._baseline.get(round_id, {})]
        results = await asyncio.gather(*(
            warera.battles.get_ranking_pages({"roundId": round_id}, "damage", "user", side) for round_id, side in todo
        ))
        taken_at = datetime.now(timezone.utc)
        if self._day != reset:
            return
        failed = 0
        for (round_id, side), result in zip(todo, results):
            if not result or not result[1]:
                failed += 1
                continue
            self._baseline.setdefault(round_id, {})[side] = {
                str(item["user"]): float(item.get("value") or 0) for item in result[0] if item.get("user")
            }
            self._baseline_at[(round_id, side)] = taken_at
        self._baseline_done = failed == 0
        logger.info("player_alignment reset snapshot: %d round sides, %d failed", len(todo) - failed, failed)

    def _refresh_mu_names(self) -> None:
        """Start refreshing the MU names unless a refresh is already running."""
        if self._mu_names_task and not self._mu_names_task.done():
            return

        async def _refresh():
            unit_ids = _unit_ids()
            military_units = await warera.mus.get_many(unit_ids)
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
        if not value:
            # an empty name would match every MU whose name is not cached yet
            return None
        for mu_id in _unit_ids():
            if value == mu_id or value.lower() == self._mu_names.get(mu_id, "").lower():
                return mu_id
        return None

    async def _load_countries(self) -> bool:
        """Refresh the country names and COUNTRY_NAME's id when stale; False when the id is unknown."""
        if self._country_id and time.monotonic() - self._countries_at < COUNTRIES_TTL:
            return True
        countries = await warera.countries.get_all()
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

    async def _load_players(self, mu_id: str | None) -> tuple[set[str], set[str], list[str]] | None:
        """The players to report as (every player id, member ids of configured MUs, names of MUs that failed).

        With `mu_id`, that MU's members only. Otherwise Romania's citizens (userWealth, which lists every
        player) plus the members of every configured MU. None when the list itself could not be read.
        """
        if mu_id is not None:
            military_unit = await warera.mus.get(mu_id)
            if not isinstance(military_unit, dict):
                return None
            if military_unit.get("name"):
                self._mu_names[mu_id] = str(military_unit["name"])
            members = {str(member) for member in military_unit.get("members") or []}
            return members, members, []
        unit_ids = _unit_ids()
        ranking, military_units = await asyncio.gather(
            warera.game.get_ranking("userWealth"), warera.mus.get_many(unit_ids)
        )
        if not isinstance(ranking, dict) or not ranking.get("items"):
            return None
        citizens = {
            str(item["user"]) for item in ranking["items"]
            if item.get("user") and str(item.get("country") or "") == self._country_id
        }
        members: set[str] = set()
        failed = []
        for unit_id in unit_ids:
            military_unit = military_units.get(unit_id)
            if not isinstance(military_unit, dict):
                failed.append(self._mu_names.get(unit_id, unit_id))
                continue
            if military_unit.get("name"):
                self._mu_names[unit_id] = str(military_unit["name"])
            members |= {str(member) for member in military_unit.get("members") or []}
        return citizens | members, members, failed

    @app_commands.command(
        name="player_alignment",
        description="Damage of Romania's players since the daily reset, split by Romania's battle orders.",
    )
    @app_commands.describe(military_unit="Only this military unit (one of the units configured for this server)")
    async def player_alignment_command(self, interaction: discord.Interaction, military_unit: str | None = None):
        mu_id = self._find_unit(military_unit) if military_unit else None
        if military_unit and mu_id is None:
            await interaction.response.defer(ephemeral=True)
            tr = await get_translator(interaction.guild_id)
            await interaction.followup.send(tr("player_alignment.unknown_unit"), ephemeral=True)
            return
        # the whole reply is ephemeral (user request): every followup below must pass ephemeral=True too
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)

        now = datetime.now(timezone.utc)
        reset = day_start(now)
        battles, ended, countries_loaded = await asyncio.gather(
            warera.battles.get_active(),
            # compared as a string with the API's createdAt, so in the same format
            warera.battles.get_ended_since((reset - ENDED_LOOKBACK).strftime("%Y-%m-%dT%H:%M:%S.000Z")),
            self._load_countries(),
        )
        if battles is None or ended is None or not countries_loaded:
            await interaction.followup.send(tr("player_alignment.fetch_failed"), ephemeral=True)
            return
        # the command's own read counts as a tracker sighting, so orders are known even before the first loop run
        self._observe(battles, now)
        players = await self._load_players(mu_id)
        if players is None:
            await interaction.followup.send(tr("player_alignment.players_failed"), ephemeral=True)
            return
        people, mu_members, failed_units = players

        report = await self._collect(battles, ended, people, reset)
        users = await warera.users.get_many(list(report["damage"]))
        # the wealth ranking's citizenship can be stale: drop players who left Romania and are in no configured MU
        for user_id, user in users.items():
            if user_id not in mu_members and str(user.get("country") or "") != self._country_id:
                report["damage"].pop(user_id, None)
                people.discard(user_id)

        # titles get the plain name, like mu_order_alignment: flag shortcodes are only used in descriptions
        title = tr("player_alignment.title_mu", mu=self._mu_names.get(mu_id, mu_id)) if mu_id else tr(
            "player_alignment.title", country=COUNTRY_NAME
        )
        embeds = self._build_embeds(title, report, users, len(people), failed_units, reset, now, tr)
        if len(embeds) == 1:
            await interaction.followup.send(embed=embeds[0], ephemeral=True)
            return
        # the pager's 600 s timeout ends well before the interaction token (15 min), so its final edit still works
        view = _BuildPager(embeds, tr)
        view.message = await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True, wait=True)

    async def _collect(self, battles: list[dict], ended: list[dict], people: set[str], reset: datetime) -> dict:
        """Read the round rankings of every battle fought since `reset` and sum `people`'s damage per category.

        Returns {"damage": {user id: {category: damage}}, "estimated": damage pro-rated without a reset
        snapshot, "failed": round sides whose ranking was not read in full}.
        """
        fought = {str(battle.get("_id")): battle for battle in battles if battle.get("_id")}
        for battle in ended:
            ended_at = parse_time(battle.get("endedAt"))
            if battle.get("_id") and ended_at is not None and ended_at >= reset:
                fought.setdefault(str(battle["_id"]), battle)
        todo = [
            (battle_id, str(round_id), side)
            for battle_id, battle in fought.items()
            for round_id in battle.get("rounds") or []
            for side in SIDES
        ]
        results = await asyncio.gather(*(
            warera.battles.get_ranking_pages({"roundId": round_id}, "damage", "user", side) for _, round_id, side in todo
        ))
        damage: dict[str, dict[str, float]] = {}
        estimated = 0.0
        failed = 0
        # the snapshot belongs to one reset; after a rollover without a new one, none applies
        baseline, baseline_at = (self._baseline, self._baseline_at) if self._day == reset else ({}, {})
        for (battle_id, round_id, side), result in zip(todo, results):
            if not result or not result[1]:
                failed += 1
            for item in (result[0] if result else []):
                user_id = str(item.get("user") or "")
                if user_id not in people:
                    continue
                part = entry_damage(
                    item, reset, baseline.get(round_id, {}).get(side), baseline_at.get((round_id, side))
                )
                if part is None or part[0] <= 0:
                    continue
                value, guessed, start, end = part
                category = entry_category(self._orders, self._coverage, battle_id, side, start, end)
                totals = damage.setdefault(user_id, dict.fromkeys(CATEGORIES, 0.0))
                totals[category] += value
                if guessed:
                    estimated += value
        return {"damage": damage, "estimated": estimated, "failed": failed}

    def _player_line(self, rank: int, user_id: str, totals: dict[str, float], user: dict | None, tr: Translator) -> str:
        """`rank. [name](profile) 🇩🇯 — **total** · ✅ … · ❌ … · ➖ … · ❔ …`, zero categories left out."""
        name = str((user or {}).get("username") or "") or tr("common.unknown_user", id=user_id)
        if len(name) > NAME_LIMIT:
            name = name[: NAME_LIMIT - 1] + "…"
        name = discord.utils.escape_markdown(name).replace("[", "\\[").replace("]", "\\]")
        flag = ""
        country_id = str((user or {}).get("country") or "")
        if user is not None and country_id != self._country_id:
            flag = " " + (country_flag(self._country_names.get(country_id)) or FOREIGN_MARKER)
        parts = [f"{EMOJI[category]} {_fmt_short(totals[category])}" for category in CATEGORIES if totals[category] >= 0.5]
        line = f"{rank}. [{name}]({PROFILE_LINK.format(user_id)}){flag} — **{_fmt_short(sum(totals.values()))}**"
        return " · ".join([line] + parts)

    def _build_embeds(
        self,
        title: str,
        report: dict,
        users: dict[str, dict],
        player_count: int,
        failed_units: list[str],
        reset: datetime,
        now: datetime,
        tr: Translator,
    ) -> list[discord.Embed]:
        """The summary and the first PLAYERS_PER_PAGE players on page 1, the other players on the next pages."""
        damage = report["damage"]
        totals = {category: sum(player[category] for player in damage.values()) for category in CATEGORIES}
        grand_total = sum(totals.values())

        def percent(value: float) -> int:
            return round(100 * value / grand_total) if grand_total else 0

        local_reset, local_now = to_local(reset), to_local(now)
        summary = [
            tr("player_alignment.since", reset=f"{local_reset:%H:%M %Z}", now=f"{local_now:%H:%M %Z}"),
            "",
        ]
        for category in CATEGORIES:
            if category == "unknown" and not totals["unknown"]:
                continue
            summary.append(tr(
                f"player_alignment.total_{category}", value=_fmt_short(totals[category]), percent=percent(totals[category])
            ))
        summary.append(tr(
            "player_alignment.players", total=player_count, active=len(damage), idle=max(0, player_count - len(damage))
        ))

        warnings = []
        # one unbroken stretch from before the reset means every order of the day was seen; otherwise the bot
        # was not watching for part of the day (a restart), and the latest stretch says since when it is
        today = [first for first, last in self._coverage if last >= reset]
        if today and (len(today) > 1 or today[0] - SLACK > reset):
            warnings.append(tr("player_alignment.warn_tracking", time=f"{to_local(today[-1]):%H:%M %Z}"))
        if report["estimated"] >= 0.5:
            warnings.append(tr("player_alignment.warn_baseline", value=_fmt_short(report["estimated"])))
        if report["failed"]:
            warnings.append(tr("player_alignment.warn_rankings", count=report["failed"]))
        if failed_units:
            names = ", ".join(discord.utils.escape_markdown(name) for name in failed_units)
            warnings.append(tr("player_alignment.warn_units", names=names))
        missing = sum(1 for user_id in damage if user_id not in users)
        if missing:
            warnings.append(tr("player_alignment.warn_users", count=missing))
        if warnings:
            summary += [""] + warnings

        ranked = sorted(damage.items(), key=lambda pair: (-sum(pair[1].values()), pair[0]))
        lines = [
            self._player_line(rank, user_id, player, users.get(user_id), tr)
            for rank, (user_id, player) in enumerate(ranked, start=1)
        ]
        pages = [lines[index:index + PLAYERS_PER_PAGE] for index in range(0, len(lines), PLAYERS_PER_PAGE)] or [[]]
        embeds = []
        for number, page in enumerate(pages):
            body = page if page else [tr("player_alignment.no_damage")]
            description = "\n".join((summary + [""] if number == 0 else []) + body)
            embed = discord.Embed(title=title, description=description, color=discord.Color.orange(), timestamp=now)
            embed.set_footer(text=tr("player_alignment.footer"))
            embeds.append(embed)
        return embeds

    @player_alignment_command.autocomplete("military_unit")
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
    await bot.add_cog(PlayerAlignment(bot))
