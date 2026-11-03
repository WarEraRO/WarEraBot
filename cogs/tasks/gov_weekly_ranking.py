"""Weekly government rankings: the Romanian government's "Topul săptămânii" article, built from the API.

Shortly before the weekly reset, the job posts two ready-to-paste articles as .txt files in the government channel
(config.json channels.government), in the layout of the government's 2026-10-05 article:

- the Romania top (Romanian citizens only): top damage and top donations to Romania per level bracket, the
  "Built Different" fighter who donated the most, Romanian MUs by their Romanian members' damage, the week's top
  bounty earners, the richest citizens and every citizen who has prestiged;
- the diaspora top: Romanians who are not Romanian citizens, i.e. the server's Citizen/Newbie members and the
  members of the configured MUs with another citizenship, with the same sections except donations, the configured
  MUs by their diaspora members' damage, and each player's citizenship next to their name.

Weekly bounty has no ranking of its own: a separate tracker reads each ended battle's money ranking (everyone paid
there) and the loot summaries of the Romanian and diaspora earners, a few battles per run, so the Sunday report
only fetches what is left.
"""
import asyncio
import io
import logging
import time
from datetime import datetime, time as dt_time, timedelta, timezone

import discord
from discord.ext import commands, tasks

from cogs.commands.mu_positions import _unicode_flag
from config import config
from utils.api import warera
from utils.common import to_local
from utils.computational import fight_percent, is_economy_build
from utils.db import get_api_ids_by_discord_id
from utils.i18n import Translator

logger = logging.getLogger(__name__)

# the weekly rankings reset on Monday 00:00 UTC (gameConfig.getDates().weeklyMissionRegenAt), so the article is
# built REPORT_LEAD before; damage and donations made in those last minutes are not counted
REPORT_LEAD = timedelta(minutes=12)
REPORT_TIME = dt_time(hour=23, minute=48, tzinfo=timezone.utc)
SUNDAY = 6
COUNTRY_NAME = "Romania"
# the article is Romanian government content pasted into the game, whatever the server language
ARTICLE_LANGUAGE = "ro"
USER_URL = "https://app.warera.io/user/{}"
MU_URL = "https://app.warera.io/mu/{}"
DAMAGE_TOP = 5
DONATION_TOP = 3
BOUNTY_TOP = 10
WEALTH_TOP = 10
# (first level, last level or None for no cap, bracket label key), as in the government's 2026-10-05 article; it
# wrote "45+" after "41-45", read as 46+ so that no level is in two brackets
DAMAGE_BRACKETS = (
    (6, 15, "wannabes"),
    (16, 20, "sweaty_beginners"),
    (21, 25, "tryhards"),
    (26, 30, "damage_addicts"),
    (31, 35, "certified_menaces"),
    (36, 40, "no_grass_touched"),
    (41, 45, "war_machines"),
    (46, None, "nuclear_arsenal"),
)
DONATION_BRACKETS = (
    (1, 15, "pocket_money"),
    (16, 30, "tax_evaders"),
    (31, 40, "big_spenders"),
    (41, None, "sugar_daddies"),
)
# one bracket holding every level, for the tops without level brackets
ALL_LEVELS = ((0, None, None),)

BOUNTY_TRACKER_MINUTES = 15
BATTLES_PER_STEP = 30
# battles last at most ~1 day and are listed newest-created first, so a battle that ended in a window was
# created at most this long before the window started
BATTLE_MAX_AGE = timedelta(days=2)
# the tracker stops retrying a battle whose money ranking failed this many times; the Sunday report retries it once
MAX_BATTLE_ATTEMPTS = 4
# Romanian and diaspora ids are re-read this often by the tracker; the report always reads them fresh
PLAYER_SETS_TTL = 3600.0
# loot summaries are read in chunks of this many (battle, player) pairs, so a cancelled sync keeps the chunks
# already read; a tracker run reads at most TRACKER_MAX_PAIRS of them, the report all that are left
SUMMARY_CHUNK = 200
TRACKER_MAX_PAIRS = 1000
# the Sunday report waits at most this long for the remaining battles, then posts with a warning
BOUNTY_SYNC_TIMEOUT = 480.0


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def week_start(now: datetime) -> datetime:
    """Monday 00:00 UTC of the game week that contains `now`."""
    now = now.astimezone(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def bounty_window_start(now: datetime) -> datetime:
    """Start of the bounty window that contains `now`: the previous Sunday report's cut-off (Monday - REPORT_LEAD).

    A battle's bounty counts in the week the battle ends (user decision, 2026-11-03), and each report counts the
    battles that ended up to its own cut-off, so a battle ending between 23:48 and 00:00 goes to the next week.
    """
    return week_start(now + REPORT_LEAD) - REPORT_LEAD


def battles_in_window(battles: list[dict], start: datetime, end: datetime) -> list[dict]:
    """The ended battles whose endedAt is in [start, end)."""
    start_iso, end_iso = _iso(start), _iso(end)
    return [
        battle for battle in battles
        if battle.get("_id") and isinstance(battle.get("endedAt"), str) and start_iso <= battle["endedAt"] < end_iso
    ]


def user_level(user: dict | None) -> int | None:
    """The user's current level, or None when it is unknown."""
    level = ((user or {}).get("leveling") or {}).get("level")
    return level if isinstance(level, int) and not isinstance(level, bool) else None


def country_flag(country: dict | None) -> str:
    """The Unicode flag of a country object, or "" when its code is unknown.

    United Korea ("kp") gets the South Korean flag, the project's choice in utils.common.COUNTRY_FLAGS.
    """
    code = (country or {}).get("code")
    return _unicode_flag("kr" if code == "kp" else code) or ""


def bracket_top(
    values: dict[str, float],
    users: dict[str, dict],
    start: int,
    end: int | None,
    limit: int | None,
) -> list[tuple[str, int, float]]:
    """The `limit` highest positive values (all with None) of players whose level is in [start, end] (end None = no cap).

    Returns (user id, level, value) tuples, highest first; ties are ordered by user id so the article is stable.
    Players missing from `users` (failed to load) are skipped, since their level is unknown.
    """
    entries = []
    for user_id, value in values.items():
        level = user_level(users.get(user_id))
        if level is None or value <= 0 or level < start or (end is not None and level > end):
            continue
        entries.append((user_id, level, value))
    entries.sort(key=lambda entry: (-entry[2], entry[0]))
    return entries[:limit]


def missing_that_matter(
    values: dict[str, float] | None,
    users: dict[str, dict],
    brackets: tuple,
    limit: int,
) -> set[str]:
    """Players missing from `users` whose value could have put them in a shown top.

    Their level is unknown, so a missing player counts when some bracket has a free place or a lowest
    shown value they reach; a missing player who couldn't beat any bracket doesn't change the article.
    """
    if not values:
        return set()
    floors = []
    for start, end, _ in brackets:
        top = bracket_top(values, users, start, end, limit)
        floors.append(top[-1][2] if len(top) == limit else 0)
    lowest = min(floors)
    return {
        user_id for user_id, value in values.items()
        if user_id not in users and value > 0 and value >= lowest
    }


def citizens_only(values: dict[str, float] | None, users: dict[str, dict], country_id: str) -> dict[str, float] | None:
    """`values` without the players whose loaded profile shows another citizenship (user.country).

    Players who failed to load are kept: they never reach a top (their level is unknown), but
    missing_that_matter still has to see them.
    """
    if values is None:
        return None
    return {
        user_id: value for user_id, value in values.items()
        if user_id not in users or users[user_id].get("country") == country_id
    }


def restrict(values: dict[str, float] | None, people: set[str]) -> dict[str, float] | None:
    """`values` limited to the user ids in `people` (None stays None)."""
    if values is None:
        return None
    return {user_id: value for user_id, value in values.items() if user_id in people}


def country_values(ranking: dict, country_id: str) -> dict[str, float]:
    """{user id: value} of a user ranking's items (weeklyUserDamages, userWealth, ...) whose country is `country_id`."""
    return {
        item["user"]: item.get("value") or 0
        for item in ranking.get("items") or []
        if item.get("country") == country_id and item.get("user")
    }


def ranking_values(ranking: dict) -> dict[str, float]:
    """{user id: value} of every item of a user ranking, whatever the country."""
    return {item["user"]: item.get("value") or 0 for item in ranking.get("items") or [] if item.get("user")}


def ranking_mus(ranking: dict, country_id: str) -> dict[str, str]:
    """{user id: MU id} of a user ranking's items whose country is `country_id` and that carry an MU."""
    return {
        item["user"]: item["mu"]
        for item in ranking.get("items") or []
        if item.get("country") == country_id and item.get("user") and item.get("mu")
    }


def donation_totals(transactions: list[dict], country_id: str, since: datetime) -> dict[str, float]:
    """{donor user id: total donated} for the donations to `country_id` created at or after `since`."""
    since_iso = _iso(since)
    totals: dict[str, float] = {}
    for transaction in transactions:
        money = transaction.get("money")
        donor = transaction.get("buyerId")
        if (
            transaction.get("transactionType") != "donation"
            or transaction.get("sellerCountryId") != country_id
            or not donor
            or not isinstance(money, (int, float))
            or isinstance(money, bool)
            or (transaction.get("createdAt") or "") < since_iso
        ):
            continue
        totals[donor] = totals.get(donor, 0) + money
    return totals


def built_different(donations: dict[str, float], users: dict[str, dict]) -> tuple[str, int, float, float] | None:
    """The fight-build donor (is_economy_build is False) who donated the most this week, or None.

    Returns (user id, level, fight percent, total donated); ties go to the higher fight percent, then the user id.
    """
    candidates = []
    for user_id, total in donations.items():
        user = users.get(user_id)
        level = user_level(user)
        if total <= 0 or level is None or is_economy_build(user) is not False:
            continue
        candidates.append((user_id, level, fight_percent(user), total))
    candidates.sort(key=lambda entry: (-entry[3], -entry[2], entry[0]))
    return candidates[0] if candidates else None


def mu_totals(
    damages: dict[str, float],
    user_mus: dict[str, str],
    users: dict[str, dict],
    country_id: str,
) -> dict[str, tuple[float, int]]:
    """{MU id: (summed damage, members counted)} over the loaded Romanian citizens with damage this week.

    Players who failed to load are left out: their citizenship is unknown.
    """
    totals: dict[str, tuple[float, int]] = {}
    for user_id, damage in damages.items():
        user = users.get(user_id)
        mu_id = user_mus.get(user_id)
        if damage <= 0 or not mu_id or user is None or user.get("country") != country_id:
            continue
        total, members = totals.get(mu_id, (0, 0))
        totals[mu_id] = (total + damage, members + 1)
    return totals


def top_mus(
    totals: dict[str, tuple[float, int]],
    mus: dict[str, dict],
    country_id: str,
) -> list[tuple[str, float, int]]:
    """(MU id, damage, members) of the Romanian MUs (mu.country) in `totals`, most damage first."""
    entries = [
        (mu_id, total, members) for mu_id, (total, members) in totals.items()
        if (mus.get(mu_id) or {}).get("country") == country_id
    ]
    entries.sort(key=lambda entry: (-entry[1], entry[0]))
    return entries


def unit_totals(mus: dict[str, dict], damages: dict[str, float], people: set[str]) -> list[tuple[str, float, int]]:
    """(MU id, damage, members) of the given MUs, summed over their members in `people`; most damage first.

    Membership is the MU's current members list; MUs whose counted members did no damage are left out.
    """
    entries = []
    for mu_id, mu in mus.items():
        counted = [
            damages[user_id] for user_id in {str(member) for member in mu.get("members") or []}
            if user_id in people and damages.get(user_id, 0) > 0
        ]
        if counted:
            entries.append((mu_id, sum(counted), len(counted)))
    entries.sort(key=lambda entry: (-entry[1], entry[0]))
    return entries


def prestige_list(users: dict[str, dict], people: set[str]) -> list[tuple[str, int, int]]:
    """(user id, prestige count, level) of every loaded player in `people` who has prestiged; most prestige, then level."""
    entries = []
    for user_id in people:
        user = users.get(user_id)
        prestige = ((user or {}).get("leveling") or {}).get("prestigeLevel") or 0
        level = user_level(user)
        if prestige > 0 and level is not None:
            entries.append((user_id, prestige, level))
    entries.sort(key=lambda entry: (-entry[1], -entry[2], entry[0]))
    return entries


def bounty_totals(
    cache: dict[str, dict],
    battle_ids: list[str],
    people: set[str],
) -> tuple[dict[str, float], int, int]:
    """({user id: bounty}, bounty records, unread battles) for the players in `people` over `battle_ids`.

    `cache` maps a battle id to {"earners": everyone the money ranking paid, "bounty": {user id: bounty}}. A battle
    is unread when its money ranking was never read, or when one of its earners in `people` has no bounty yet.
    """
    totals: dict[str, float] = {}
    records = unread = 0
    for battle_id in battle_ids:
        entry = cache.get(battle_id)
        if entry is None:
            unread += 1
            continue
        wanted = entry["earners"] & people
        if any(user_id not in entry["bounty"] for user_id in wanted):
            unread += 1
        for user_id in wanted:
            bounty = entry["bounty"].get(user_id) or 0
            if bounty > 0:
                totals[user_id] = totals.get(user_id, 0) + bounty
                records += 1
    return totals, records, unread


def format_number(value: float) -> str:
    """Thousands-separated number, with up to 2 decimals when it is not whole (1,234 / 12.5)."""
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _entry(tr: Translator, key: str, places: dict[str, str] | None, user_id: str, **values) -> str:
    """A player line: `key`, or `key_abroad` with the player's citizenship when `places` is given."""
    if places is None:
        return tr(f"gov_weekly_ranking.{key}", url=USER_URL.format(user_id), **values)
    return tr(f"gov_weekly_ranking.{key}_abroad", url=USER_URL.format(user_id), place=places.get(user_id, ""), **values)


def _bracket_header(tr: Translator, start: int, end: int | None, label: str) -> str:
    levels = f"{start}-{end}" if end is not None else f"{start}+"
    return tr("gov_weekly_ranking.bracket", levels=levels, label=tr(f"gov_weekly_ranking.brackets.{label}"))


def _bracket_lines(
    tr: Translator,
    brackets: tuple,
    values: dict[str, float] | None,
    users: dict[str, dict],
    limit: int,
    places: dict[str, str] | None = None,
) -> list[str]:
    lines = []
    for start, end, label in brackets:
        lines.append(_bracket_header(tr, start, end, label))
        if values is None:
            lines.append(tr("gov_weekly_ranking.unavailable"))
        else:
            top = bracket_top(values, users, start, end, limit)
            lines += [
                _entry(tr, "entry", places, user_id, level=level, value=format_number(value))
                for user_id, level, value in top
            ] or [tr("gov_weekly_ranking.nobody")]
        lines.append("")
    return lines


def _simple_top(
    tr: Translator,
    values: dict[str, float] | None,
    users: dict[str, dict],
    limit: int,
    places: dict[str, str] | None = None,
) -> list[str]:
    """`- url → value` lines of the `limit` highest values, or the nobody/unavailable line.

    Values are whole numbers like the government's article, except below 10, which keep 2 decimals so a small
    bounty (0.46) doesn't show as 0.
    """
    if values is None:
        return [tr("gov_weekly_ranking.unavailable")]
    top = bracket_top(values, users, 0, None, limit)
    return [
        _entry(tr, "top_entry", places, user_id, value=format_number(round(value) if value >= 10 else round(value, 2)))
        for user_id, _, value in top
    ] or [tr("gov_weekly_ranking.nobody")]


def _warning_lines(tr: Translator, warnings: dict[str, int]) -> list[str]:
    """The delete-before-publishing warnings for the positive counts in `warnings`, plus a blank line."""
    lines = [
        tr(f"gov_weekly_ranking.incomplete_{name}", count=count)
        for name, count in warnings.items() if count
    ]
    return lines + [""] if lines else []


def _mu_lines(tr: Translator, mus: list[tuple[str, float, int]] | None) -> list[str]:
    if mus is None:
        return [tr("gov_weekly_ranking.unavailable")]
    return [
        tr("gov_weekly_ranking.mu_entry", url=MU_URL.format(mu_id), value=format_number(round(total)),
           members=tr.plural("gov_weekly_ranking.members", members))
        for mu_id, total, members in mus
    ] or [tr("gov_weekly_ranking.nobody")]


def _bounty_lines(tr: Translator, data: dict, users: dict[str, dict], places: dict[str, str] | None) -> list[str]:
    lines = _simple_top(tr, data["bounty"], users, BOUNTY_TOP, places)
    if data["bounty_span"] is not None:
        battles, records, start, end = data["bounty_span"]
        span_format = tr("gov_weekly_ranking.span_format")
        lines.append(tr(
            "gov_weekly_ranking.bounty_note", battles=battles, records=records,
            start=tr.strftime(to_local(start), span_format), end=tr.strftime(to_local(end), span_format),
        ))
    return lines


def _prestige_lines(
    tr: Translator,
    prestige: list[tuple[str, int, int]] | None,
    places: dict[str, str] | None,
) -> list[str]:
    if prestige is None:
        return [tr("gov_weekly_ranking.unavailable")]
    return [
        _entry(tr, "prestige_entry", places, user_id, prestige=count, level=level)
        for user_id, count, level in prestige
    ] or [tr("gov_weekly_ranking.nobody")]


def _footer_lines(tr: Translator, now: datetime, week_span: dict) -> list[str]:
    date_format = tr("gov_weekly_ranking.date_format")
    return [
        tr("gov_weekly_ranking.compiled", date=tr.strftime(to_local(now), date_format), **week_span),
        "",
        tr("gov_weekly_ranking.signature"),
        tr.strftime(to_local(now), date_format),
    ]


def _week_span(week: datetime) -> dict:
    return {"start": f"{week:%d.%m}", "end": f"{week + timedelta(days=6):%d.%m}"}


def build_article(
    tr: Translator,
    week: datetime,
    now: datetime,
    data: dict,
    users: dict[str, dict],
    warnings: dict[str, int],
) -> str:
    """The Romania article text for the week starting `week` (Monday 00:00 UTC), compiled at `now`.

    `data` holds the week's values, each None when it could not be loaded (its section then says so):
    "damages", "donations", "wealth", "bounty" ({user id: value}), "mus" (top_mus entries), "prestige"
    (prestige_list entries, or None) and "bounty_span" ((battles, records, start, end) or None). `warnings`
    maps a warning name ("players": failed to load but could have made a top; "battles": bounty not read
    completely) to a count; each positive count puts a delete-before-publishing warning at the top.
    """
    week_span = _week_span(week)
    lines = _warning_lines(tr, warnings)
    lines += [tr("gov_weekly_ranking.title", **week_span), ""]

    lines += [tr("gov_weekly_ranking.damage_title"), tr("gov_weekly_ranking.damage_subtitle", count=DAMAGE_TOP)]
    lines += _bracket_lines(tr, DAMAGE_BRACKETS, data["damages"], users, DAMAGE_TOP)

    donations = data["donations"]
    lines += [tr("gov_weekly_ranking.donations_title"), tr("gov_weekly_ranking.donations_subtitle", count=DONATION_TOP)]
    lines += _bracket_lines(tr, DONATION_BRACKETS, donations, users, DONATION_TOP)
    lines.append(tr("gov_weekly_ranking.built_different"))
    best = built_different(donations, users) if donations is not None else None
    if donations is None:
        lines.append(tr("gov_weekly_ranking.unavailable"))
    elif best is None:
        lines.append(tr("gov_weekly_ranking.nobody"))
    else:
        user_id, level, percent, total = best
        lines.append(tr(
            "gov_weekly_ranking.built_different_entry",
            url=USER_URL.format(user_id), level=level, percent=round(percent), value=format_number(total),
        ))
    lines.append("")

    lines += [tr("gov_weekly_ranking.mus_title"), tr("gov_weekly_ranking.mus_subtitle")]
    lines += _mu_lines(tr, data["mus"]) + [""]
    lines += [tr("gov_weekly_ranking.bounty_title"), tr("gov_weekly_ranking.bounty_subtitle")]
    lines += _bounty_lines(tr, data, users, None) + [""]
    lines += [tr("gov_weekly_ranking.wealth_title"), tr("gov_weekly_ranking.wealth_subtitle")]
    lines += _simple_top(tr, data["wealth"], users, WEALTH_TOP) + [""]
    lines += [tr("gov_weekly_ranking.prestige_title"), tr("gov_weekly_ranking.prestige_subtitle")]
    lines += _prestige_lines(tr, data["prestige"], None) + [""]
    lines += _footer_lines(tr, now, week_span)
    return "\n".join(lines)


def build_diaspora_article(
    tr: Translator,
    week: datetime,
    now: datetime,
    data: dict,
    users: dict[str, dict],
    places: dict[str, str],
    warnings: dict[str, int],
) -> str:
    """The diaspora article text: like build_article without donations, each player shown with `places[user id]`.

    `data` holds "damages", "wealth", "bounty", "mus" (unit_totals entries of the configured MUs), "prestige" and
    "bounty_span", each None when unavailable. `warnings` may also hold "discord" (the server's member list could
    not be read) and "mus" (configured MUs that failed to load).
    """
    week_span = _week_span(week)
    lines = _warning_lines(tr, warnings)
    lines += [tr("gov_weekly_ranking.diaspora_title", **week_span), tr("gov_weekly_ranking.diaspora_intro"), ""]

    lines += [tr("gov_weekly_ranking.damage_title"), tr("gov_weekly_ranking.damage_subtitle", count=DAMAGE_TOP)]
    lines += _bracket_lines(tr, DAMAGE_BRACKETS, data["damages"], users, DAMAGE_TOP, places)
    lines += [tr("gov_weekly_ranking.mus_title"), tr("gov_weekly_ranking.mus_subtitle_diaspora")]
    lines += _mu_lines(tr, data["mus"]) + [""]
    lines += [tr("gov_weekly_ranking.bounty_title"), tr("gov_weekly_ranking.bounty_subtitle_diaspora")]
    lines += _bounty_lines(tr, data, users, places) + [""]
    lines += [tr("gov_weekly_ranking.wealth_title"), tr("gov_weekly_ranking.wealth_subtitle_diaspora")]
    lines += _simple_top(tr, data["wealth"], users, WEALTH_TOP, places) + [""]
    lines += [tr("gov_weekly_ranking.prestige_title"), tr("gov_weekly_ranking.prestige_subtitle")]
    lines += _prestige_lines(tr, data["prestige"], places) + [""]
    lines += _footer_lines(tr, now, week_span)
    return "\n".join(lines)


async def send_message(destination, content: str, filename: str) -> None:
    """Send `content` to `destination` as a UTF-8 .txt attachment named `filename`."""
    file = discord.File(
        io.BytesIO(content.encode("utf-8")),
        filename=filename,
    )

    await destination.send(file=file)


class GovWeeklyRankingJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._country_id: str | None = None
        self._countries: dict[str, dict] = {}
        # the Romanian ids of the userWealth ranking (it lists every player) and the diaspora candidates, with
        # when each was read; -inf, not 0: time.monotonic() counts from boot, so 0 would look fresh at first
        self._romanians: set[str] = set()
        self._romanians_at = float("-inf")
        self._diaspora: set[str] = set()
        self._diaspora_at = float("-inf")
        # bounty window start -> {battle id: {"earners": set of user ids paid in it, "bounty": {user id: bounty}}}
        self._bounty: dict[datetime, dict[str, dict]] = {}
        # bounty window start -> (time.monotonic() of the last listing, its battle ids), so a report whose sync timed
        # out can still count when that listing was made by the report's own sync
        self._window_battles: dict[datetime, tuple[float, list[str]]] = {}
        # battle id -> failed money-ranking reads
        self._attempts: dict[str, int] = {}
        self._bounty_lock = asyncio.Lock()
        self.gov_weekly_ranking.start()
        self.gov_bounty_tracker.start()

    def cog_unload(self):
        self.gov_weekly_ranking.cancel()
        self.gov_bounty_tracker.cancel()

    async def _load_country_id(self) -> str | None:
        """Romania's country id (the country list is read once), or None while it can't be loaded."""
        if self._country_id is None:
            countries = await warera.countries.get_all()
            self._countries = {c["_id"]: c for c in countries or [] if c.get("_id")}
            country = next((c for c in self._countries.values() if c.get("name") == COUNTRY_NAME), None)
            self._country_id = country["_id"] if country else None
        return self._country_id

    async def _load_romanians(self, country_id: str, wealth_ranking: dict | None = None) -> set[str]:
        """Ids of Romania's citizens in the userWealth ranking, refreshed hourly; the last good set on failure."""
        if wealth_ranking is None and time.monotonic() - self._romanians_at >= PLAYER_SETS_TTL:
            wealth_ranking = await warera.game.get_ranking("userWealth")
        if wealth_ranking is not None:
            self._romanians = set(country_values(wealth_ranking, country_id))
            self._romanians_at = time.monotonic()
        return self._romanians

    async def _discord_romanians(self) -> tuple[set[str], bool]:
        """Player ids of the server's Citizen and Newbie members, and whether the member list could be read.

        Members are matched by their database link, else by nickname (exact username). The list counts as
        unreadable when the guild is missing or its members aren't fully cached (no member would be found).
        """
        guild = self.bot.get_guild(config["guild"])
        if guild is None or not guild.chunked:
            return set(), False
        members = set()
        for role_id in (config["roles"].get("citizen"), config["roles"].get("newbie")):
            role = guild.get_role(role_id) if role_id else None
            if role:
                members.update(role.members)
        try:
            links = await asyncio.to_thread(get_api_ids_by_discord_id)
        except Exception:
            logger.exception("Government ranking: could not read the linked players; matching by nickname")
            links = {}
        ids, names = set(), []
        for member in members:
            api_id = links.get(str(member.id))
            if api_id:
                ids.add(str(api_id))
            else:
                names.append(member.display_name)
        if names:
            found = await warera.users.ids_by_name(names)
            if not found:
                # ids_by_name answers {} when the search failed, so this is a failure, not "nobody matched"
                logger.warning("Government ranking: none of %d unlinked members could be found by name", len(names))
                return ids, False
            ids.update(str(user_id) for user_id in found.values() if user_id)
            if len(found) < len(names):
                # nicknames that aren't a username are the unidentified_members job's concern, not a report warning
                logger.info("Government ranking: %d unlinked members match no username", len(names) - len(found))
        return ids, bool(members)

    async def _load_diaspora(self) -> tuple[set[str], dict[str, dict], dict[str, int]]:
        """Diaspora candidates (Citizen/Newbie members plus configured MU members), the configured MUs, warnings.

        The candidates aren't filtered by citizenship yet. `warnings` counts an unreadable Discord member list
        ("discord") and configured MUs that failed to load ("mus"). Only a complete set refreshes the tracker's copy.
        """
        unit_ids = [str(unit["id"]) for unit in config.get("military_units", []) if unit.get("id")]
        (discord_ids, discord_ok), mus = await asyncio.gather(self._discord_romanians(), warera.mus.get_many(unit_ids))
        candidates = discord_ids | {str(member) for mu in mus.values() for member in mu.get("members") or []}
        warnings = {"discord": 0 if discord_ok else 1, "mus": len(set(unit_ids) - set(mus))}
        # a lasting problem (a deleted MU in config.json) must not make the tracker reload every run
        self._diaspora_at = time.monotonic()
        if not any(warnings.values()):
            self._diaspora = candidates
        else:
            # keep tracking whoever was found before, so a bad read doesn't stop their bounty being prefetched
            self._diaspora |= candidates
        return candidates, mus, warnings

    async def _check_reset(self, week: datetime) -> None:
        """Warn when the game's weekly reset is not the Monday 00:00 UTC this schedule assumes."""
        dates = await warera.game.get_dates()
        expected = (week + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
        regen_at = (dates or {}).get("weeklyMissionRegenAt")
        if isinstance(regen_at, str) and not regen_at.startswith(expected):
            logger.warning("Weekly reset is %s, not %s as REPORT_TIME assumes", regen_at, expected)

    async def _read_rankings(self, window: datetime, battle_ids: list[str]) -> None:
        """Read the money ranking of each battle (everyone paid there) into the window's cache."""
        cache = self._bounty.setdefault(window, {})
        rankings = await asyncio.gather(
            *(warera.battles.get_ranking(battle_id, "money", "user", "merged") for battle_id in battle_ids)
        )
        for battle_id, items in zip(battle_ids, rankings):
            if items is None:
                self._attempts[battle_id] = self._attempts.get(battle_id, 0) + 1
                continue
            self._attempts.pop(battle_id, None)
            cache[battle_id] = {
                "earners": {item["user"] for item in items if item.get("user") and (item.get("value") or 0) > 0},
                "bounty": {},
            }

    async def _fill_bounty(
        self,
        window: datetime,
        battle_ids: list[str],
        people: set[str],
        max_pairs: int | None = None,
    ) -> None:
        """Read the bounty of the earners in `people` that the cached battles don't have yet (at most `max_pairs`).

        The money ranking mixes bounty with contract pay; the loot summary splits them. A summary of None is a 404
        (no hits in that battle, so no bounty); a failed summary stays missing and is retried by the next call.
        Results are saved per SUMMARY_CHUNK, so a cancelled call keeps the chunks already read.
        """
        cache = self._bounty.get(window, {})
        pairs = [
            (battle_id, user_id)
            for battle_id in battle_ids if battle_id in cache
            for user_id in cache[battle_id]["earners"] & people if user_id not in cache[battle_id]["bounty"]
        ][:max_pairs]
        for start in range(0, len(pairs), SUMMARY_CHUNK):
            summaries = await warera.battles.get_loot_summaries_many(pairs[start:start + SUMMARY_CHUNK])
            for (battle_id, user_id), summary in summaries.items():
                cache[battle_id]["bounty"][user_id] = (summary or {}).get("totalMoneyFromBounty") or 0

    async def _sync_bounty(
        self,
        window: datetime,
        end: datetime,
        people: set[str],
        max_steps: int | None = None,
        retry_failed: bool = False,
    ) -> list[str] | None:
        """Read the battles that ended in [window, end) and the bounty of their earners in `people`.

        Reads at most `max_steps` steps of BATTLES_PER_STEP new battles (all with None), saving each step's
        results, so a cancelled sync keeps its progress; the battle list is saved in `_window_battles` first.
        Battles whose ranking failed MAX_BATTLE_ATTEMPTS times are skipped unless `retry_failed`. Returns the ids
        of every battle in [window, end), or None when the battle list could not be loaded.
        """
        async with self._bounty_lock:
            # only this window and the previous one can still be reported
            for stale in [start for start in self._bounty if start < window - timedelta(days=7)]:
                self._bounty.pop(stale, None)
                self._window_battles.pop(stale, None)
            ended = await warera.battles.get_ended_since(_iso(window - BATTLE_MAX_AGE))
            if ended is None:
                return None
            battle_ids = [battle["_id"] for battle in battles_in_window(ended, window, end)]
            self._window_battles[window] = (time.monotonic(), battle_ids)
            # failure counts of battles outside the current listing can't be used again
            self._attempts = {b: n for b, n in self._attempts.items() if b in set(battle_ids)}
            cache = self._bounty.setdefault(window, {})
            todo = [
                battle_id for battle_id in battle_ids
                if battle_id not in cache and (retry_failed or self._attempts.get(battle_id, 0) < MAX_BATTLE_ATTEMPTS)
            ]
            steps = 0
            while todo and (max_steps is None or steps < max_steps):
                step, todo = todo[:BATTLES_PER_STEP], todo[BATTLES_PER_STEP:]
                await self._read_rankings(window, step)
                await self._fill_bounty(window, step, people)
                steps += 1
            # earners added to `people` since a battle was read (new members, a late member list) are read now
            await self._fill_bounty(window, battle_ids, people, None if max_steps is None else TRACKER_MAX_PAIRS)
            return battle_ids

    @tasks.loop(minutes=BOUNTY_TRACKER_MINUTES)
    async def gov_bounty_tracker(self):
        """Read the bounty of a few newly ended battles of the current window, so the Sunday report has little left."""
        try:
            now = datetime.now(timezone.utc)
            country_id = await self._load_country_id()
            if country_id is None:
                return
            romanians = await self._load_romanians(country_id)
            if time.monotonic() - self._diaspora_at >= PLAYER_SETS_TTL:
                await self._load_diaspora()
            await self._sync_bounty(bounty_window_start(now), now, romanians | self._diaspora, max_steps=1)
        except Exception:
            # an uncaught error would stop the loop until the next restart
            logger.exception("Government bounty tracker failed")
            if asyncio.current_task() is not self.gov_bounty_tracker.get_task():
                raise  # /run_job reports the error to whoever forced the run

    @tasks.loop(time=REPORT_TIME)
    async def gov_weekly_ranking(self):
        """Build the week's Romania and diaspora articles and post them as .txt files in the government channel."""
        now = datetime.now(timezone.utc)
        # the loop fires daily but only Sunday's run posts; /run_job calls it from another task and always posts
        if now.weekday() != SUNDAY and asyncio.current_task() is self.gov_weekly_ranking.get_task():
            return
        try:
            await self._post_rankings(now)
        except Exception:
            # an uncaught error would stop the loop until the next restart, skipping every later Sunday
            logger.exception("Government weekly ranking failed")
            if asyncio.current_task() is not self.gov_weekly_ranking.get_task():
                raise  # /run_job reports the error to whoever forced the run

    async def _load_users(self, user_ids: list[str], users: dict[str, dict] | None = None) -> dict[str, dict]:
        """Batched users by id, added to `users` (whose ids aren't fetched again); failed ids are retried once."""
        users = users if users is not None else {}
        wanted = [user_id for user_id in dict.fromkeys(user_ids) if user_id not in users]
        users.update(await warera.users.get_many(wanted))
        missing = [user_id for user_id in wanted if user_id not in users]
        if missing:
            users.update(await warera.users.get_many(missing))
            still = sum(1 for user_id in missing if user_id not in users)
            if still:
                logger.warning("Government ranking: %d players could not be loaded", still)
        return users

    async def _post_rankings(self, now: datetime) -> None:
        """Fetch the week's data, build both articles and send them to the government channel.

        The week is fixed from `now` at the start; the weekly rankings and donations are read first, before the
        bounty sync that may take minutes, so they still describe this week if the sync runs past the reset. The
        diaspora article is built and sent after the Romania one, and its failure never affects that one.
        """
        guild = self.bot.get_guild(config["guild"])
        channel_id = config.get("channels", {}).get("government")
        channel = guild.get_channel_or_thread(channel_id) if guild and channel_id else None
        if channel is None:
            logger.warning("Government channel %s not found; weekly ranking not posted", channel_id)
            return

        week = week_start(now)
        country_id = await self._load_country_id()
        if country_id is None:
            logger.warning("Country %s not found; weekly ranking not posted", COUNTRY_NAME)
            return
        damage_ranking, wealth_ranking, transactions, _ = await asyncio.gather(
            warera.game.get_ranking("weeklyUserDamages"),
            warera.game.get_ranking("userWealth"),
            warera.market.get_country_transactions(country_id, "donation", _iso(week)),
            self._check_reset(week),
        )
        for name, value in (("damage ranking", damage_ranking), ("wealth ranking", wealth_ranking),
                            ("donations", transactions)):
            if value is None:
                logger.warning("Government ranking: %s unavailable", name)
        romanians = await self._load_romanians(country_id, wealth_ranking)
        try:
            diaspora = await self._load_diaspora()
        except Exception:
            logger.exception("Government ranking: diaspora members could not be read")
            diaspora = None
        candidates = diaspora[0] if diaspora else set()

        # this report counts the battles that ended since the previous report's cut-off, up to its own
        window = week - REPORT_LEAD
        bounty_end = min(now, week + timedelta(days=7) - REPORT_LEAD)
        sync_started = time.monotonic()
        try:
            battle_ids = await asyncio.wait_for(
                self._sync_bounty(window, bounty_end, romanians | candidates, retry_failed=True), BOUNTY_SYNC_TIMEOUT,
            )
        except asyncio.TimeoutError:
            # the listing is saved before the reading starts, so the battles not read yet count as unread; a listing
            # older than this sync (it timed out before relisting) could miss battles, so bounty is then unavailable
            listed_at, listed = self._window_battles.get(window, (float("-inf"), None))
            battle_ids = listed if listed_at >= sync_started else None
            logger.warning("Government ranking: bounty sync timed out (%s)",
                           "posting with what was read" if battle_ids is not None else "no fresh battle list")
        bounty_span = None
        if battle_ids is not None:
            bounty_span = (len(battle_ids), window, bounty_end)

        users: dict[str, dict] = {}
        tr = Translator(ARTICLE_LANGUAGE)
        content = await self._romania_article(
            tr, week, now, country_id, damage_ranking, wealth_ranking, transactions, romanians,
            battle_ids, bounty_span, users,
        )
        filename = f"{week + timedelta(days=6):%Y-%m-%d}"
        try:
            await send_message(channel, content, f"{filename}.txt")
        except discord.HTTPException:
            logger.exception("Failed to post the government weekly ranking in channel %s", channel_id)

        if diaspora is None:
            return
        try:
            content = await self._diaspora_article(
                tr, week, now, country_id, damage_ranking, wealth_ranking, diaspora, battle_ids, bounty_span, users,
            )
            await send_message(channel, content, f"{filename}-diaspora.txt")
        except Exception:
            logger.exception("Failed to build or post the government diaspora ranking")

    def _bounty_data(
        self,
        window: datetime,
        battle_ids: list[str] | None,
        bounty_span: tuple | None,
        people: set[str],
    ) -> tuple[dict[str, float] | None, tuple | None, int]:
        """(bounty per player in `people`, the bounty note's (battles, records, start, end), unread battles)."""
        if battle_ids is None:
            return None, None, 0
        bounty, records, unread = bounty_totals(self._bounty.get(window, {}), battle_ids, people)
        battles, start, end = bounty_span
        return bounty, (battles, records, start, end), unread

    async def _romania_article(
        self, tr, week, now, country_id, damage_ranking, wealth_ranking, transactions, romanians,
        battle_ids, bounty_span, users,
    ) -> str:
        """The Romania article; loads its players into `users` for the diaspora article to reuse."""
        damages = country_values(damage_ranking, country_id) if damage_ranking is not None else None
        user_mus = ranking_mus(damage_ranking, country_id) if damage_ranking is not None else {}
        wealth = country_values(wealth_ranking, country_id) if wealth_ranking is not None else None
        donations = donation_totals(transactions, country_id, week) if transactions is not None else None
        bounty, span, unread = self._bounty_data(week - REPORT_LEAD, battle_ids, bounty_span, romanians)

        # only players with something to rank can appear, plus every Romanian in the rankings for Top Prestige
        await self._load_users([
            *(user_id for values in (damages, donations, bounty) for user_id, value in (values or {}).items() if value > 0),
            *(wealth or {}),
        ], users)
        # the Romania top is for Romanian citizens only: donors from other countries are dropped, and so is a
        # ranked player whose citizenship changed after the ranking recorded their country
        damages = citizens_only(damages, users, country_id)
        donations = citizens_only(donations, users, country_id)
        wealth = citizens_only(wealth, users, country_id)
        bounty = citizens_only(bounty, users, country_id)

        mus = None
        if damages is not None:
            totals = mu_totals(damages, user_mus, users, country_id)
            mu_objects = await warera.mus.get_many(list(totals))
            mus = top_mus(totals, mu_objects, country_id)
            if len(mu_objects) < len(totals):
                logger.warning("Government ranking: %d MUs could not be loaded", len(totals) - len(mu_objects))

        citizens = {user_id for user_id, user in users.items() if user.get("country") == country_id}
        missing = (
            missing_that_matter(damages, users, DAMAGE_BRACKETS, DAMAGE_TOP)
            | missing_that_matter(donations, users, DONATION_BRACKETS, DONATION_TOP)
            | missing_that_matter(bounty, users, ALL_LEVELS, BOUNTY_TOP)
            | missing_that_matter(wealth, users, ALL_LEVELS, WEALTH_TOP)
            # any Romanian who failed to load could be missing from Top Prestige
            | {user_id for user_id in wealth or {} if user_id not in users}
        )
        data = {
            "damages": damages,
            "donations": donations,
            "wealth": wealth,
            "bounty": bounty,
            "mus": mus,
            "prestige": prestige_list(users, citizens) if wealth is not None else None,
            "bounty_span": span,
        }
        return build_article(tr, week, now, data, users, {"players": len(missing), "battles": unread})

    async def _diaspora_article(
        self, tr, week, now, country_id, damage_ranking, wealth_ranking, diaspora, battle_ids, bounty_span, users,
    ) -> str:
        """The diaspora article: candidates who aren't Romanian citizens, with their citizenship on each line."""
        candidates, unit_mus, warnings = diaspora
        await self._load_users(list(candidates), users)
        abroad = {
            user_id for user_id in candidates
            if user_id in users and users[user_id].get("country") != country_id
        }
        # players who failed to load stay in the values for missing_that_matter; they never reach a top
        unknown = {user_id for user_id in candidates if user_id not in users}
        damages = restrict(ranking_values(damage_ranking), abroad | unknown) if damage_ranking is not None else None
        wealth = restrict(ranking_values(wealth_ranking), abroad | unknown) if wealth_ranking is not None else None
        bounty, span, unread = self._bounty_data(week - REPORT_LEAD, battle_ids, bounty_span, abroad | unknown)

        places = {}
        for user_id in abroad:
            country = self._countries.get(users[user_id].get("country"))
            if country is None:
                places[user_id] = tr("gov_weekly_ranking.no_citizenship")
            else:
                places[user_id] = f"{country_flag(country)} {country.get('name', '')}".strip()

        missing = (
            missing_that_matter(damages, users, DAMAGE_BRACKETS, DAMAGE_TOP)
            | missing_that_matter(bounty, users, ALL_LEVELS, BOUNTY_TOP)
            | missing_that_matter(wealth, users, ALL_LEVELS, WEALTH_TOP)
            # any candidate who failed to load could be missing from Top Prestige
            | unknown
        )
        data = {
            "damages": damages,
            "wealth": wealth,
            "bounty": bounty,
            "mus": unit_totals(unit_mus, damages, abroad) if damages is not None else None,
            "prestige": prestige_list(users, abroad),
            "bounty_span": span,
        }
        return build_diaspora_article(
            tr, week, now, data, users, places,
            {**warnings, "players": len(missing), "battles": unread},
        )

    @gov_weekly_ranking.before_loop
    async def before_gov_weekly_ranking(self):
        await self.bot.wait_until_ready()

    @gov_bounty_tracker.before_loop
    async def before_gov_bounty_tracker(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(GovWeeklyRankingJob(bot))
