"""War priority alerts: warn the government before the priority in one of Romania's wars runs out.

A war's priority lasts 24 h from the war's latest event: its declaration (held by the declaring
country) or its latest ended battle, war or resistance (held by the winner). Every 2 minutes the job
reads, in one batch, Romania's war declarations and peace treaties of the last 24 h, Romania's battles
that ended in the last 24 h and its active battles, and works out each war's holder and end from them.
Whichever side holds the priority, Romania or the enemy, it posts to `channels.government_mod_cabinet`
once when the end is 3 h away, once at 1 h and once at 10 min. Nothing is posted while Romania and that
enemy fight a battle in the war: the battle's winner gets a fresh priority, which starts a new series.

Before an alert is posted, the war is read with `war.getById` (one batched request, only when an alert
is due). The alert shows the API's holder and end; a war that ended, or a mismatch with the derived
values (for instance after a game patch changes the rule), is logged.

State is in memory only. The first time a war is seen after a restart, the alerts already due for it
are recorded without being posted (unless the threshold was crossed in the last few minutes), so a
restart doesn't repeat them; a threshold crossed while the bot was down is not posted.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from config import config
from utils.api import warera
from utils.common import country_with_flag, to_local
from utils.i18n import get_translator

logger = logging.getLogger(__name__)

COUNTRY_NAME = "Romania"
SCAN_MINUTES = 2
# How long a war's priority lasts after its declaration or latest ended battle [observed 2026-11-10:
# exact to the second on 6 of 6 wars, battles of type war and resistance alike].
PRIORITY_DURATION = timedelta(hours=24)
# Ended battles are listed by creation time; the longest of 300 lasted 24.2 h, so a battle that ended in
# the last 24 h was created within this window.
ENDED_LOOKBACK = timedelta(hours=50)
# Alert thresholds, longest first: stage i means the i-th threshold has been reached.
THRESHOLDS = (timedelta(hours=3), timedelta(hours=1), timedelta(minutes=10))
COUNTRIES_TTL = timedelta(hours=1)
# On the first sighting of a war after a restart, an alert whose threshold was crossed less than this
# long ago is still posted: a quick restart must not swallow it.
RESTART_GRACE = timedelta(minutes=5)
# The ended-battle listing can lag behind the active one when a battle ends, so a war stays quiet this
# long after its last active battle was seen.
BATTLE_SETTLE = timedelta(minutes=5)
# A derived end this close to war.getById's priorityEndAt counts as the same.
END_TOLERANCE = timedelta(minutes=1)
COLOR_OURS = discord.Color.orange()   # Romania's priority runs out
COLOR_THEIRS = discord.Color.blue()   # the enemy's priority runs out


def parse_iso(value) -> datetime | None:
    """An API ISO timestamp as an aware UTC datetime; None when missing or malformed."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def iso(value: datetime) -> str:
    """`value` as the API's ISO format (UTC, milliseconds, Z), so string comparisons with createdAt work."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


def alert_stage(remaining: timedelta) -> int | None:
    """Index in THRESHOLDS of the deepest threshold `remaining` has reached; None while more is left than the first."""
    stage = None
    for index, threshold in enumerate(THRESHOLDS):
        if remaining <= threshold:
            stage = index
    return stage


def derive_priorities(country_id: str, events, ended_battles, now: datetime) -> dict[str, dict]:
    """{war id: {"holder", "enemy", "end"}} for the wars of `country_id` whose priority is still running.

    A war's priority ends PRIORITY_DURATION after its latest event: a warDeclared event (held by the
    declaring country) or an ended battle with a winner (held by the winner). Only battles fought by
    `country_id` itself count, and a war with a peaceMade event after its latest event is left out.
    """
    cutoff = now - PRIORITY_DURATION
    latest: dict[str, dict] = {}

    def offer(war_id, start, holder, attacker, defender):
        if not war_id or start is None or start <= cutoff or country_id not in (attacker, defender) or attacker == defender:
            return
        if war_id not in latest or start > latest[war_id]["start"]:
            enemy = defender if attacker == country_id else attacker
            latest[war_id] = {"start": start, "holder": holder, "enemy": enemy}

    for event in events or []:
        data = event.get("data") or {}
        if data.get("type") == "warDeclared":
            attacker, defender = data.get("attackerCountry"), data.get("defenderCountry")
            offer(data.get("war"), parse_iso(event.get("createdAt")), attacker, attacker, defender)
    for battle in ended_battles or []:
        attacker = (battle.get("attacker") or {}).get("country")
        defender = (battle.get("defender") or {}).get("country")
        won_by = battle.get("wonBy")
        if won_by not in ("attacker", "defender"):
            continue
        holder = attacker if won_by == "attacker" else defender
        offer(battle.get("war"), parse_iso(battle.get("endedAt")), holder, attacker, defender)
    for event in events or []:
        data = event.get("data") or {}
        made_at = parse_iso(event.get("createdAt"))
        if data.get("type") != "peaceMade" or made_at is None:
            continue
        for war_id in data.get("wars") or []:
            if war_id in latest and made_at >= latest[war_id]["start"]:
                del latest[war_id]
    return {
        war_id: {"holder": info["holder"], "enemy": info["enemy"], "end": info["start"] + PRIORITY_DURATION}
        for war_id, info in latest.items()
    }


def war_matches(war: dict, country_id: str, enemy_id: str) -> bool:
    """True when `war` is active and fought between exactly `country_id` and `enemy_id`."""
    sides = {(war.get("attacker") or {}).get("country"), (war.get("defender") or {}).get("country")}
    return bool(war.get("isActive")) and sides == {country_id, enemy_id}


def format_remaining(delta: timedelta) -> str:
    """A countdown such as "2h 58m" or "9m", rounded up to the minute."""
    minutes = max(1, -(-int(delta.total_seconds()) // 60))
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


class WarPriorityJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._country_id: str | None = None
        self._countries: dict[str, dict] = {}
        self._countries_at: datetime | None = None
        self._seeded_wars: set[str] = set()
        self._notified: dict[tuple, int] = {}          # (war id, holder, end ISO) -> deepest stage done
        self._battle_seen: dict[str, datetime] = {}    # war id -> last run it had an active battle
        self._send_failed: set[tuple] = set()
        self._mismatch_logged: set[tuple] = set()
        self._channel_warned = False
        self._lock = asyncio.Lock()
        self.war_priority.start()

    def cog_unload(self):
        """Stop the loop when the cog is unloaded."""
        self.war_priority.cancel()

    async def _load_countries(self, now: datetime) -> bool:
        """Refresh the country list (names, codes) and Romania's id hourly; False while Romania's id is unknown."""
        if self._country_id and self._countries_at and now - self._countries_at < COUNTRIES_TTL:
            return True
        countries = await warera.countries.get_all()
        if not countries:
            return self._country_id is not None
        romania = next((country for country in countries if country.get("name") == COUNTRY_NAME), None)
        if romania is None:
            logger.error("war_priority: country %s not found in country.getAllCountries", COUNTRY_NAME)
            return self._country_id is not None
        self._countries = {country["_id"]: country for country in countries if country.get("_id")}
        self._country_id = romania["_id"]
        self._countries_at = now
        return True

    def _country_label(self, country_id: str | None, unknown: str) -> str:
        """The country's name with its flag, in bold; `unknown` when the id isn't in the country list."""
        name = (self._countries.get(country_id) or {}).get("name")
        return f"**{country_with_flag(name, left=True, unknown=unknown)}**"

    def _build_embed(self, tr, holder: str, other: str, end: datetime, now: datetime) -> discord.Embed:
        """The alert for one war: who holds the priority over whom and when it ends (local time)."""
        ours = holder == self._country_id
        unknown = tr("common.unknown")
        local_end = to_local(end)
        embed = discord.Embed(
            title=tr("war_priority.title_ours" if ours else "war_priority.title_theirs"),
            description=tr(
                "war_priority.description",
                holder=self._country_label(holder, unknown),
                other=self._country_label(other, unknown),
                remaining=format_remaining(end - now),
                time=f"{local_end:%H:%M} {local_end.tzname()}",
            ),
            color=COLOR_OURS if ours else COLOR_THEIRS,
            timestamp=now,
        )
        embed.set_footer(text=tr("war_priority.footer"))
        return embed

    @tasks.loop(minutes=SCAN_MINUTES)
    async def war_priority(self):
        """Post the war priority alerts that are due (see the module docstring); about 1 request a run.

        Runs are serialized, so a forced /run_job overlapping a scheduled run can't post an alert twice,
        and an error is logged instead of stopping the loop for good.
        """
        async with self._lock:
            try:
                await self._run()
            except Exception:
                logger.exception("war_priority: run failed")

    async def _run(self) -> None:
        """One check of Romania's wars; posts the alerts that became due."""
        guild = self.bot.get_guild(config["guild"])
        if guild is None:
            return
        channel_id = config.get("channels", {}).get("government_mod_cabinet")
        channel = guild.get_channel_or_thread(int(channel_id)) if channel_id else None
        if channel is None:
            if not self._channel_warned:
                logger.warning("war_priority: channels.government_mod_cabinet (%s) not found", channel_id)
                self._channel_warned = True
            return
        self._channel_warned = False

        now = datetime.now(timezone.utc)
        if not await self._load_countries(now):
            return
        events, ended, active = await asyncio.gather(
            warera.countries.get_war_events_since(self._country_id, iso(now - PRIORITY_DURATION)),
            warera.battles.get_ended_for_country_since(self._country_id, iso(now - ENDED_LOOKBACK)),
            warera.battles.get_active_for_country(self._country_id),
        )
        if events is None or ended is None or active is None:
            # A missing list could hide a battle or a newer priority; a false alert is worse than a delay.
            logger.warning("war_priority: war events or battles unavailable, run skipped")
            return
        for battle in active:
            if battle.get("war"):
                self._battle_seen[battle["war"]] = now
            # Also by enemy country, so a battle listed without its war id still holds the alerts back.
            sides = ((battle.get("attacker") or {}).get("country"), (battle.get("defender") or {}).get("country"))
            if self._country_id in sides:
                enemy = sides[1] if sides[0] == self._country_id else sides[0]
                self._battle_seen[("country", enemy)] = now

        derived = derive_priorities(self._country_id, events, ended, now)
        candidates = []
        for war_id, info in derived.items():
            key = (war_id, info["holder"], iso(info["end"]))
            if war_id not in self._seeded_wars:
                self._seeded_wars.add(war_id)
                seeded = alert_stage(info["end"] - now + RESTART_GRACE)
                if seeded is not None:
                    self._notified[key] = max(seeded, self._notified.get(key, -1))
            seen = max(self._battle_seen.get(war_id, now - BATTLE_SETTLE),
                       self._battle_seen.get(("country", info["enemy"]), now - BATTLE_SETTLE))
            if now - seen < BATTLE_SETTLE:
                continue
            stage = alert_stage(info["end"] - now)
            if stage is None or stage <= self._notified.get(key, -1):
                continue
            candidates.append((war_id, info, key, stage))

        if candidates:
            await self._confirm_and_post(guild, channel, candidates, now)
        self._prune(now, derived)

    async def _confirm_and_post(self, guild, channel, candidates, now: datetime) -> None:
        """Re-read the candidate wars with war.getById and post the alerts the API confirms.

        The alert uses the API's holder and priorityEndAt. A war that is over (or between other
        countries) is muted for this priority; a derived holder or end the API doesn't confirm is logged
        once and the API's values decide whether an alert is due. When the API says no alert is due, the
        derived stage is recorded as handled, so each derived threshold costs at most one confirmation.
        """
        wars = await warera.countries.get_wars_many([candidate[0] for candidate in candidates])
        tr = None
        for war_id, info, key, derived_stage in candidates:
            war = wars.get(war_id)
            if war is None:
                continue
            if not war_matches(war, self._country_id, info["enemy"]):
                logger.info("war_priority: war %s is no longer Romania's war with %s", war_id, info["enemy"])
                self._notified[key] = len(THRESHOLDS) - 1
                continue
            holder, end = war.get("priority"), parse_iso(war.get("priorityEndAt"))
            if holder != info["holder"] or end is None or abs(end - info["end"]) > END_TOLERANCE:
                if key not in self._mismatch_logged:
                    logger.warning("war_priority: war %s: derived priority %s until %s, war.getById says %s until %s",
                                   war_id, info["holder"], iso(info["end"]), holder, war.get("priorityEndAt"))
                    self._mismatch_logged.add(key)
            stage = alert_stage(end - now) if holder and end is not None and end > now else None
            if stage is None or stage <= self._notified.get(key, -1):
                self._notified[key] = max(derived_stage, self._notified.get(key, -1))
                continue
            if tr is None:
                tr = await get_translator(guild)
            other = info["enemy"] if holder == self._country_id else self._country_id
            try:
                await channel.send(embed=self._build_embed(tr, holder, other, end, now))
            except discord.DiscordException as error:
                if key not in self._send_failed:
                    logger.warning("war_priority: could not post the alert for war %s: %s", war_id, error)
                    self._send_failed.add(key)
                continue
            self._notified[key] = stage
            self._send_failed.discard(key)

    def _prune(self, now: datetime, derived: dict) -> None:
        """Forget alerts whose priority has ended, battle sightings older than BATTLE_SETTLE and unseen wars."""
        for key in list(self._notified):
            end = parse_iso(key[2])
            if end is None or end <= now:
                del self._notified[key]
                self._send_failed.discard(key)
                self._mismatch_logged.discard(key)
        for war_id, seen in list(self._battle_seen.items()):
            if now - seen >= BATTLE_SETTLE:
                del self._battle_seen[war_id]
        self._seeded_wars &= set(derived)

    @war_priority.before_loop
    async def before_war_priority(self):
        """Wait until the bot is connected before the first run."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    """Load the war priority job."""
    await bot.add_cog(WarPriorityJob(bot))
