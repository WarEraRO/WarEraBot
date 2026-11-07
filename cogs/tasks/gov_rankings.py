"""Government rankings: the Romanian government's weekly and monthly top articles, built from the API.

Shortly before the weekly reset (Sunday) and the monthly reset (the last day of the month), a job posts
ready-to-paste articles as .txt files in the government rankings thread (config.json channels.government_rankings), in the layout of
the government's articles of 2026-10-05 (weekly) and 2026-10-06 ("TOP LUNA SEPTEMBRIE", monthly; the monthly report
has no diaspora article, user decision 2026-11-04):

- the Romania top (Romanian citizens only): top damage and top donations to Romania per level bracket, the
  "Built Different" fighter who donated the most, Romanian MUs by their Romanian members' damage, the period's top
  bounty earners, the richest citizens and every citizen who has prestiged;
- the diaspora top: Romanians who are not Romanian citizens, i.e. the server's Citizen/Newbie members and the
  members of the configured MUs with another citizenship, with the same sections except donations, the configured
  MUs by their diaspora members' damage, and each player's citizenship next to their name.

Weekly damage comes from the weeklyUserDamages ranking. The API has no monthly damage or bounty ranking, so the
monthly article sums every battle that ended in the month (battleRanking damage per player, and per MU for the
MU section, so damage counts for the MU the player was in when fighting; user decisions 2026-11-04), and both
reports read bounty per ended battle (money ranking, then the earners' loot summaries).
A tracker reads newly ended battles every 15 minutes into an in-memory cache, so a report only fetches what is
left; after a restart the tracker catches up, or the report reads the rest itself.
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
from utils.common import get_government_rankings_channel, to_local
from utils.computational import fight_percent, is_economy_build
from utils.db import get_api_ids_by_discord_id
from utils.i18n import Translator

logger = logging.getLogger(__name__)

# the weekly rankings reset on Monday 00:00 UTC (gameConfig.getDates().weeklyMissionRegenAt) and the monthly missions
# on the 1st 00:00 UTC (monthlyMissionRegenAt), so each article is built REPORT_LEAD before its reset; battles that
# end in those last minutes count in the next period
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

TRACKER_MINUTES = 15
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
# a cold month (after a restart) is ~1,250 battles, read in ~3 minutes [observed 2026-11-04]; nothing the monthly
# report reads is reset-sensitive (battles count by end time, donations from the window start), so it waits longer
MONTH_SYNC_TIMEOUT = 900.0
# tracker steps per run: 2 x 30 battles every 15 minutes (~41 battles end per day) catch up a month in ~5 hours
TRACKER_STEPS = 2
# locale namespaces: shared strings always come from WEEKLY_TEXTS, the period-specific ones (PERIOD_KEYS) from the
# article's own namespace
WEEKLY_TEXTS = "gov_weekly_ranking"
MONTHLY_TEXTS = "gov_monthly_ranking"


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


def month_start(now: datetime) -> datetime:
    """The 1st 00:00 UTC of the month that contains `now`."""
    return now.astimezone(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def next_month(start: datetime) -> datetime:
    """The 1st 00:00 UTC of the month after the one that starts at `start`."""
    return (start + timedelta(days=32)).replace(day=1)


def month_window_start(now: datetime) -> datetime:
    """Start of the monthly battle window that contains `now`: the previous monthly report's cut-off.

    Like bounty_window_start, a battle counts in the month it ends, up to each report's cut-off (1st - REPORT_LEAD).
    """
    return month_start(now + REPORT_LEAD) - REPORT_LEAD


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


def battle_mu_top(
    mu_damage: dict[str, float],
    mus: dict[str, dict],
    members: dict[str, int],
    country_id: str,
) -> list[tuple[str, float, int]]:
    """(MU id, damage, members) of the loaded MUs of `country_id` (mu.country) with battle damage, most damage first.

    `mu_damage` is the period's damage per MU summed from the battles' MU rankings: every member's damage counts,
    for the MU they were in when they fought (user decision 2026-11-04). `members` gives the count shown next to
    each MU (MUs missing from it show 0).
    """
    entries = [
        (mu_id, damage, members.get(mu_id, 0)) for mu_id, damage in mu_damage.items()
        if damage > 0 and (mus.get(mu_id) or {}).get("country") == country_id
    ]
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
    records = 0
    for battle_id in battle_ids:
        entry = cache.get(battle_id)
        if entry is None:
            continue
        for user_id in entry["earners"] & people:
            bounty = entry["bounty"].get(user_id) or 0
            if bounty > 0:
                totals[user_id] = totals.get(user_id, 0) + bounty
                records += 1
    return totals, records, len(unread_battles(cache, battle_ids, people))


def unread_battles(cache: dict[str, dict], battle_ids: list[str], people: set[str]) -> set[str]:
    """The battles of `battle_ids` whose bounty is not fully read for `people` (see bounty_totals)."""
    return {
        battle_id for battle_id in battle_ids
        if battle_id not in cache
        or any(user_id not in cache[battle_id]["bounty"] for user_id in cache[battle_id]["earners"] & people)
    }


def bounty_data(
    snapshot: dict | None,
    bounty_span: tuple[datetime, datetime],
    people: set[str],
) -> tuple[dict[str, float] | None, tuple | None, int]:
    """(bounty per player in `people`, the bounty note's (battles, records, start, end), unread battles).

    `snapshot` is a report's copy of the battle cache (GovRankingsJob._snapshot) or None when the battle list could
    not be loaded; `bounty_span` is the (start, end) of its window. Unread battles count a battle once, whether its
    bounty or (monthly) its damage is missing.
    """
    if snapshot is None:
        return None, None, 0
    bounty, records, _ = bounty_totals(snapshot["bounty"], snapshot["ids"], people)
    unread = unread_battles(snapshot["bounty"], snapshot["ids"], people) | snapshot["damage_unread"]
    start, end = bounty_span
    return bounty, (len(snapshot["ids"]), records, start, end), len(unread)


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


def _warning_lines(tr: Translator, texts: str, warnings: dict[str, int]) -> list[str]:
    """The delete-before-publishing warnings (from the `texts` namespace) for the positive counts, plus a blank line."""
    lines = [
        tr(f"{texts}.incomplete_{name}", count=count)
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


def _bounty_lines(
    tr: Translator,
    texts: str,
    data: dict,
    users: dict[str, dict],
    places: dict[str, str] | None,
) -> list[str]:
    lines = _simple_top(tr, data["bounty"], users, BOUNTY_TOP, places)
    if data["bounty_span"] is not None:
        battles, records, start, end = data["bounty_span"]
        span_format = tr("gov_weekly_ranking.span_format")
        lines.append(tr(
            f"{texts}.bounty_note", battles=battles, records=records,
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


def _footer_lines(tr: Translator, texts: str, now: datetime, span: dict) -> list[str]:
    date_format = tr("gov_weekly_ranking.date_format")
    return [
        tr(f"{texts}.compiled", date=tr.strftime(to_local(now), date_format), **span),
        "",
        tr("gov_weekly_ranking.signature"),
        tr.strftime(to_local(now), date_format),
    ]


def _week_span(week: datetime) -> dict:
    """The weekly article's title and footer placeholders: the week's first and last day (dd.mm)."""
    return {"start": f"{week:%d.%m}", "end": f"{week + timedelta(days=6):%d.%m}"}


def month_span(tr: Translator, month: datetime) -> dict:
    """The monthly article's title and footer placeholders for the month starting at `month`.

    "month" is the localized month name ("octombrie"), "month_upper" the same in capitals for the title, "year"
    the year, and "start"/"end" the month's first (dd.mm) and last (dd.mm.yyyy) day.
    """
    last = next_month(month) - timedelta(days=1)
    name = tr.strftime(month, "%B")
    return {
        "month": name, "month_upper": name.upper(), "year": month.year,
        "start": f"{month:%d.%m}", "end": f"{last:%d.%m.%Y}",
    }


def build_article(
    tr: Translator,
    texts: str,
    span: dict,
    now: datetime,
    data: dict,
    users: dict[str, dict],
    warnings: dict[str, int],
) -> str:
    """The Romania article text of one period, compiled at `now`.

    `texts` is the period's locale namespace (WEEKLY_TEXTS or MONTHLY_TEXTS) for the title, subtitles, notes,
    warnings and footer, and `span` its placeholders (_week_span or month_span). `data` holds the period's
    values, each None when it could not be loaded (its section then says so):
    "damages", "donations", "wealth", "bounty" ({user id: value}), "mus" (top_mus or battle_mu_top entries), "prestige"
    (prestige_list entries, or None) and "bounty_span" ((battles, records, start, end) or None). `warnings`
    maps a warning name ("players": failed to load but could have made a top; "battles": bounty or damage not read
    completely) to a count; each positive count puts a delete-before-publishing warning at the top.
    """
    lines = _warning_lines(tr, texts, warnings)
    lines += [tr(f"{texts}.title", **span), ""]

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

    lines += [tr("gov_weekly_ranking.mus_title"), tr(f"{texts}.mus_subtitle")]
    lines += _mu_lines(tr, data["mus"]) + [""]
    lines += [tr(f"{texts}.bounty_title"), tr(f"{texts}.bounty_subtitle")]
    lines += _bounty_lines(tr, texts, data, users, None) + [""]
    lines += [tr("gov_weekly_ranking.wealth_title"), tr("gov_weekly_ranking.wealth_subtitle")]
    lines += _simple_top(tr, data["wealth"], users, WEALTH_TOP) + [""]
    lines += [tr("gov_weekly_ranking.prestige_title"), tr("gov_weekly_ranking.prestige_subtitle")]
    lines += _prestige_lines(tr, data["prestige"], None) + [""]
    lines += _footer_lines(tr, texts, now, span)
    return "\n".join(lines)


def build_diaspora_article(
    tr: Translator,
    texts: str,
    span: dict,
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
    lines = _warning_lines(tr, texts, warnings)
    lines += [tr(f"{texts}.diaspora_title", **span), tr("gov_weekly_ranking.diaspora_intro"), ""]

    lines += [tr("gov_weekly_ranking.damage_title"), tr("gov_weekly_ranking.damage_subtitle", count=DAMAGE_TOP)]
    lines += _bracket_lines(tr, DAMAGE_BRACKETS, data["damages"], users, DAMAGE_TOP, places)
    lines += [tr("gov_weekly_ranking.mus_title"), tr(f"{texts}.mus_subtitle_diaspora")]
    lines += _mu_lines(tr, data["mus"]) + [""]
    lines += [tr(f"{texts}.bounty_title"), tr(f"{texts}.bounty_subtitle_diaspora")]
    lines += _bounty_lines(tr, texts, data, users, places) + [""]
    lines += [tr("gov_weekly_ranking.wealth_title"), tr("gov_weekly_ranking.wealth_subtitle_diaspora")]
    lines += _simple_top(tr, data["wealth"], users, WEALTH_TOP, places) + [""]
    lines += [tr("gov_weekly_ranking.prestige_title"), tr("gov_weekly_ranking.prestige_subtitle")]
    lines += _prestige_lines(tr, data["prestige"], places) + [""]
    lines += _footer_lines(tr, texts, now, span)
    return "\n".join(lines)


async def send_message(destination, content: str, filename: str) -> None:
    """Send `content` to `destination` as a UTF-8 .txt attachment named `filename`."""
    file = discord.File(
        io.BytesIO(content.encode("utf-8")),
        filename=filename,
    )

    await destination.send(file=file)


class GovRankingsJob(commands.Cog):
    """The government's weekly and monthly articles, and the battle tracker that prefetches their battles."""

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
        # battle id -> {"ended": its endedAt, "earners": user ids paid in its money ranking (None until read),
        # "bounty": {user id: bounty}, "damage": whether its damage ranking was added to its month's totals}
        self._battles: dict[str, dict] = {}
        # month window start -> {user id: damage summed over the window's battles with "damage" True}, every player
        self._damage: dict[datetime, dict[str, float]] = {}
        # month window start -> {MU id: damage of the same battles' MU rankings}, every MU
        self._mu_damage: dict[datetime, dict[str, float]] = {}
        # window start -> (time.monotonic() of the last listing, its battle ids), so a report whose sync timed out
        # can still count when that listing was made by the report's own sync
        self._window_battles: dict[datetime, tuple[float, list[str]]] = {}
        # battle id -> failed ranking reads
        self._attempts: dict[str, int] = {}
        # every read or write of the battle caches holds this; a report takes it before its sync timeout starts,
        # so a weekly report queued behind the monthly sync (a month-end Sunday) still gets its full timeout
        self._battle_lock = asyncio.Lock()
        self.gov_weekly_ranking.start()
        self.gov_monthly_ranking.start()
        self.gov_battle_tracker.start()

    def cog_unload(self):
        """Stop the three loops when the cog is unloaded."""
        self.gov_weekly_ranking.cancel()
        self.gov_monthly_ranking.cancel()
        self.gov_battle_tracker.cancel()

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

    async def _check_reset(self, key: str, expected: datetime) -> None:
        """Warn when the game's `key` reset (gameConfig.getDates) is not at `expected`, as REPORT_TIME assumes."""
        dates = await warera.game.get_dates()
        regen_at = (dates or {}).get(key)
        if isinstance(regen_at, str) and not regen_at.startswith(expected.strftime("%Y-%m-%dT%H:%M:%S")):
            logger.warning("%s is %s, not %s as REPORT_TIME assumes", key, regen_at, _iso(expected))

    def _prune(self, now: datetime) -> None:
        """Drop the battles and windows older than the previous week and month windows.

        The previous windows are kept because a report starts at its own cut-off, the moment the current windows
        (bounty_window_start, month_window_start) switch to the next period, and still reads the finished one. A
        kept battle whose month totals were dropped is marked unread, so its damage could never go missing silently.
        """
        week = bounty_window_start(now)
        month = month_window_start(now)
        cut = min(week - timedelta(days=7), month_window_start(month - timedelta(seconds=1)))
        cut_iso = _iso(cut)
        self._battles = {battle_id: entry for battle_id, entry in self._battles.items() if entry["ended"] >= cut_iso}
        for cache in (self._damage, self._mu_damage, self._window_battles):
            for start in [start for start in cache if start < cut]:
                cache.pop(start, None)
        oldest_totals = _iso(min(self._damage)) if self._damage else None
        for entry in self._battles.values():
            if entry["damage"] and (oldest_totals is None or entry["ended"] < oldest_totals):
                entry["damage"] = False

    async def _read_battles(self, battle_ids: list[str], damage_windows: dict[str, datetime]) -> None:
        """Read the missing money rankings of `battle_ids`, and the user and MU damage rankings in `damage_windows`.

        `damage_windows` maps a battle id to the month window its damage counts in. A battle's user and MU damage
        are added to that window's totals together, only after both whole rankings came back (get_ranking answers
        None when any page fails), with no await in between, so a cancelled or failed read never counts a battle
        partly or twice.
        """
        money_ids = [battle_id for battle_id in battle_ids if self._battles[battle_id]["earners"] is None]
        damage_ids = [
            battle_id for battle_id in battle_ids
            if battle_id in damage_windows and not self._battles[battle_id]["damage"]
        ]
        rankings = await asyncio.gather(
            *(warera.battles.get_ranking(battle_id, "money", "user", "merged") for battle_id in money_ids),
            *(warera.battles.get_ranking(battle_id, "damage", "user", "merged") for battle_id in damage_ids),
            *(warera.battles.get_ranking(battle_id, "damage", "mu", "merged") for battle_id in damage_ids),
        )
        failed = set()
        for battle_id, items in zip(money_ids, rankings[:len(money_ids)]):
            if items is None:
                failed.add(battle_id)
                continue
            self._battles[battle_id]["earners"] = {
                item["user"] for item in items if item.get("user") and (item.get("value") or 0) > 0
            }
        user_rankings = rankings[len(money_ids):len(money_ids) + len(damage_ids)]
        mu_rankings = rankings[len(money_ids) + len(damage_ids):]
        for battle_id, user_items, mu_items in zip(damage_ids, user_rankings, mu_rankings):
            if user_items is None or mu_items is None:
                failed.add(battle_id)
                continue
            window = damage_windows[battle_id]
            for totals, items, key in ((self._damage.setdefault(window, {}), user_items, "user"),
                                       (self._mu_damage.setdefault(window, {}), mu_items, "mu")):
                for item in items:
                    value = item.get("value") or 0
                    if item.get(key) and value > 0:
                        totals[item[key]] = totals.get(item[key], 0) + value
            self._battles[battle_id]["damage"] = True
        for battle_id in battle_ids:
            if battle_id in failed:
                self._attempts[battle_id] = self._attempts.get(battle_id, 0) + 1
            else:
                self._attempts.pop(battle_id, None)

    async def _fill_bounty(self, battle_ids: list[str], people: set[str], max_pairs: int | None = None) -> None:
        """Read the bounty of the earners in `people` that the read battles don't have yet (at most `max_pairs`).

        The money ranking mixes bounty with contract pay; the loot summary splits them. A summary of None is a 404
        (no hits in that battle, so no bounty); a failed summary stays missing and is retried by the next call.
        Results are saved per SUMMARY_CHUNK, so a cancelled call keeps the chunks already read.
        """
        pairs = [
            (battle_id, user_id)
            for battle_id in battle_ids if (self._battles.get(battle_id) or {}).get("earners")
            for user_id in self._battles[battle_id]["earners"] & people
            if user_id not in self._battles[battle_id]["bounty"]
        ][:max_pairs]
        for start in range(0, len(pairs), SUMMARY_CHUNK):
            summaries = await warera.battles.get_loot_summaries_many(pairs[start:start + SUMMARY_CHUNK])
            for (battle_id, user_id), summary in summaries.items():
                self._battles[battle_id]["bounty"][user_id] = (summary or {}).get("totalMoneyFromBounty") or 0

    async def _sync_battles(
        self,
        ranges: list[tuple[datetime, datetime, bool]],
        people: set[str],
        max_steps: int | None = None,
        retry_failed: bool = False,
    ) -> dict[datetime, list[str]] | None:
        """Read the battles that ended in each (start, end, with damage) range and the bounty of their earners.

        The caller holds `_battle_lock`. Every battle's money ranking is read; the damage ranking only for ranges
        with damage (the month). Reads at most `max_steps` steps of BATTLES_PER_STEP battles (all with None),
        saving each step's results, so a cancelled sync keeps its progress; each range's battle list is saved in
        `_window_battles` first. Battles whose rankings failed MAX_BATTLE_ATTEMPTS times are skipped unless
        `retry_failed`. Returns {range start: ids of the battles in that range}, or None when the battle list
        could not be loaded.
        """
        self._prune(datetime.now(timezone.utc))
        oldest = min(start for start, _, _ in ranges)
        ended = await warera.battles.get_ended_since(_iso(oldest - BATTLE_MAX_AGE))
        if ended is None:
            return None
        listed: dict[datetime, list[str]] = {}
        damage_windows: dict[str, datetime] = {}
        for start, end, with_damage in ranges:
            battles = battles_in_window(ended, start, end)
            for battle in battles:
                self._battles.setdefault(
                    battle["_id"], {"ended": battle["endedAt"], "earners": None, "bounty": {}, "damage": False},
                )
                if with_damage:
                    damage_windows[battle["_id"]] = start
            if with_damage:
                self._damage.setdefault(start, {})
                self._mu_damage.setdefault(start, {})
            listed[start] = [battle["_id"] for battle in battles]
            self._window_battles[start] = (time.monotonic(), listed[start])
        battle_ids = list(dict.fromkeys(battle_id for ids in listed.values() for battle_id in ids))
        # failure counts of battles outside the current listing can't be used again
        self._attempts = {b: n for b, n in self._attempts.items() if b in set(battle_ids)}
        todo = [
            battle_id for battle_id in battle_ids
            if (
                self._battles[battle_id]["earners"] is None
                or (battle_id in damage_windows and not self._battles[battle_id]["damage"])
            )
            and (retry_failed or self._attempts.get(battle_id, 0) < MAX_BATTLE_ATTEMPTS)
        ]
        steps = 0
        while todo and (max_steps is None or steps < max_steps):
            step, todo = todo[:BATTLES_PER_STEP], todo[BATTLES_PER_STEP:]
            await self._read_battles(step, damage_windows)
            await self._fill_bounty(step, people)
            steps += 1
        # earners added to `people` since a battle was read (new members, a late member list) are read now
        await self._fill_bounty(battle_ids, people, None if max_steps is None else TRACKER_MAX_PAIRS)
        return listed

    def _snapshot(self, start: datetime, battle_ids: list[str], with_damage: bool) -> dict:
        """A report's copy of the battle cache for one window, so later tracker runs can't change it.

        {"ids": the window's battle ids, "bounty": {battle id: {"earners", "bounty"}} of the battles whose money
        ranking was read (the bounty_totals cache shape), "damage": the window's {user id: damage} and
        "mu_damage" its {MU id: damage} (each None without damage), "damage_unread": the battles whose damage
        rankings were not read (empty without damage)}.
        """
        entries = [(battle_id, self._battles.get(battle_id)) for battle_id in battle_ids]
        return {
            "ids": list(battle_ids),
            "bounty": {
                battle_id: {"earners": set(entry["earners"]), "bounty": dict(entry["bounty"])}
                for battle_id, entry in entries if entry and entry["earners"] is not None
            },
            "damage": dict(self._damage.get(start, {})) if with_damage else None,
            "mu_damage": dict(self._mu_damage.get(start, {})) if with_damage else None,
            "damage_unread": (
                {battle_id for battle_id, entry in entries if not (entry and entry["damage"])} if with_damage else set()
            ),
        }

    async def _battle_snapshot(
        self,
        start: datetime,
        end: datetime,
        people: set[str],
        with_damage: bool,
        timeout: float,
    ) -> dict | None:
        """Sync the battles that ended in [start, end) (at most `timeout` seconds) and return their _snapshot.

        The timeout starts once the lock is held. When the sync times out, the battles not read yet count as unread;
        a listing older than this sync (it timed out before relisting) could miss battles, so the result is then
        None, like a battle list that could not be loaded.
        """
        async with self._battle_lock:
            sync_started = time.monotonic()
            try:
                listed = await asyncio.wait_for(
                    self._sync_battles([(start, end, with_damage)], people, retry_failed=True), timeout,
                )
                battle_ids = listed[start] if listed is not None else None
            except asyncio.TimeoutError:
                listed_at, battle_ids = self._window_battles.get(start, (float("-inf"), None))
                if listed_at < sync_started:
                    battle_ids = None
                logger.warning("Government ranking: battle sync timed out (%s)",
                               "posting with what was read" if battle_ids is not None else "no fresh battle list")
            if battle_ids is None:
                return None
            return self._snapshot(start, battle_ids, with_damage)

    @tasks.loop(minutes=TRACKER_MINUTES)
    async def gov_battle_tracker(self):
        """Read a few newly ended battles of the current week and month, so the reports have little left."""
        try:
            now = datetime.now(timezone.utc)
            country_id = await self._load_country_id()
            if country_id is None:
                return
            romanians = await self._load_romanians(country_id)
            if time.monotonic() - self._diaspora_at >= PLAYER_SETS_TTL:
                await self._load_diaspora()
            ranges = [(bounty_window_start(now), now, False), (month_window_start(now), now, True)]
            async with self._battle_lock:
                await self._sync_battles(ranges, romanians | self._diaspora, max_steps=TRACKER_STEPS)
        except Exception:
            # an uncaught error would stop the loop until the next restart
            logger.exception("Government battle tracker failed")
            if asyncio.current_task() is not self.gov_battle_tracker.get_task():
                raise  # /run_job reports the error to whoever forced the run

    @tasks.loop(time=REPORT_TIME)
    async def gov_weekly_ranking(self):
        """Build the week's Romania and diaspora articles and post them as .txt files in the government rankings thread."""
        now = datetime.now(timezone.utc)
        # the loop fires daily but only Sunday's run posts; /run_job calls it from another task and always posts
        if now.weekday() != SUNDAY and asyncio.current_task() is self.gov_weekly_ranking.get_task():
            return
        try:
            await self._post_weekly(now)
        except Exception:
            # an uncaught error would stop the loop until the next restart, skipping every later Sunday
            logger.exception("Government weekly ranking failed")
            if asyncio.current_task() is not self.gov_weekly_ranking.get_task():
                raise  # /run_job reports the error to whoever forced the run

    @tasks.loop(time=REPORT_TIME)
    async def gov_monthly_ranking(self):
        """Build the month's Romania article and post it as a .txt file in the government rankings thread (no diaspora)."""
        now = datetime.now(timezone.utc)
        # the loop fires daily but only the month's last day posts; /run_job always posts (the month so far)
        if (now + timedelta(days=1)).day != 1 and asyncio.current_task() is self.gov_monthly_ranking.get_task():
            return
        try:
            await self._post_monthly(now)
        except Exception:
            logger.exception("Government monthly ranking failed")
            if asyncio.current_task() is not self.gov_monthly_ranking.get_task():
                raise  # /run_job reports the error to whoever forced the run

    async def _load_users(self, user_ids: list[str], users: dict[str, dict] | None = None) -> dict[str, dict]:
        """Batched users by id, added to `users` (whose ids aren't fetched again); failed ids are retried once.

        Full users (user.getUserById): the build split reads `skills`, which getUserLite stopped
        returning in v0.28.1 (2026-11-07).
        """
        users = users if users is not None else {}
        wanted = [user_id for user_id in dict.fromkeys(user_ids) if user_id not in users]
        users.update(await warera.users.get_full_many(wanted))
        missing = [user_id for user_id in wanted if user_id not in users]
        if missing:
            users.update(await warera.users.get_full_many(missing))
            still = sum(1 for user_id in missing if user_id not in users)
            if still:
                logger.warning("Government ranking: %d players could not be loaded", still)
        return users

    async def _government_channel(self):
        """The government rankings thread (utils.common.get_government_rankings_channel), or None with a warning."""
        channel = await get_government_rankings_channel(self.bot.get_guild(config["guild"]))
        if channel is None:
            logger.warning("Government rankings channel %s not found; government ranking not posted",
                           config.get("channels", {}).get("government_rankings"))
        return channel

    async def _read_diaspora(self) -> tuple[set[str], dict[str, dict], dict[str, int]] | None:
        """_load_diaspora, or None (logged) when it fails, so the Romania article is posted anyway."""
        try:
            return await self._load_diaspora()
        except Exception:
            logger.exception("Government ranking: diaspora members could not be read")
            return None

    async def _post_weekly(self, now: datetime) -> None:
        """Fetch the week's data, build both articles and send them to the government rankings thread.

        The week is fixed from `now` at the start; the weekly rankings and donations are read first, before the
        battle sync that may take minutes, so they still describe this week if the sync runs past the reset.
        """
        channel = await self._government_channel()
        if channel is None:
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
            self._check_reset("weeklyMissionRegenAt", week + timedelta(days=7)),
        )
        for name, value in (("damage ranking", damage_ranking), ("wealth ranking", wealth_ranking),
                            ("donations", transactions)):
            if value is None:
                logger.warning("Government ranking: %s unavailable", name)
        romanians = await self._load_romanians(country_id, wealth_ranking)
        diaspora = await self._read_diaspora()

        # this report counts the battles that ended since the previous report's cut-off, up to its own
        window = week - REPORT_LEAD
        bounty_end = min(now, week + timedelta(days=7) - REPORT_LEAD)
        snapshot = await self._battle_snapshot(
            window, bounty_end, romanians | (diaspora[0] if diaspora else set()), False, BOUNTY_SYNC_TIMEOUT,
        )
        has_damage = damage_ranking is not None
        await self._post_articles(
            channel, f"{week + timedelta(days=6):%Y-%m-%d}", WEEKLY_TEXTS, _week_span(week), now, country_id,
            damages=country_values(damage_ranking, country_id) if has_damage else None,
            user_mus=ranking_mus(damage_ranking, country_id) if has_damage else {},
            all_damages=ranking_values(damage_ranking) if has_damage else None,
            wealth_ranking=wealth_ranking,
            donations=donation_totals(transactions, country_id, week) if transactions is not None else None,
            romanians=romanians, diaspora=diaspora, snapshot=snapshot, bounty_span=(window, bounty_end),
        )

    async def _post_monthly(self, now: datetime) -> None:
        """Fetch the month's data, build the Romania article and send it to the government rankings thread.

        Damage (players and MUs) and bounty come from every battle that ended in the month window [previous
        cut-off, this cut-off), donations from the window start, wealth and prestige as they are now. There is no
        diaspora article (user decision 2026-11-04).
        """
        channel = await self._government_channel()
        if channel is None:
            return
        month = month_start(now)
        country_id = await self._load_country_id()
        if country_id is None:
            logger.warning("Country %s not found; monthly ranking not posted", COUNTRY_NAME)
            return
        window = month - REPORT_LEAD
        end = min(now, next_month(month) - REPORT_LEAD)
        wealth_ranking, transactions, _ = await asyncio.gather(
            warera.game.get_ranking("userWealth"),
            warera.market.get_country_transactions(country_id, "donation", _iso(window)),
            self._check_reset("monthlyMissionRegenAt", next_month(month)),
        )
        for name, value in (("wealth ranking", wealth_ranking), ("donations", transactions)):
            if value is None:
                logger.warning("Government ranking: %s unavailable", name)
        romanians = await self._load_romanians(country_id, wealth_ranking)
        snapshot = await self._battle_snapshot(window, end, romanians, True, MONTH_SYNC_TIMEOUT)
        totals = snapshot["damage"] if snapshot is not None else None
        await self._post_articles(
            channel, f"{month:%Y-%m}", MONTHLY_TEXTS, month_span(Translator(ARTICLE_LANGUAGE), month), now,
            country_id,
            # the totals hold every player; the wealth ranking's Romanians are the citizens to load and check
            damages=restrict(totals, romanians), user_mus=None, all_damages=totals,
            wealth_ranking=wealth_ranking,
            donations=donation_totals(transactions, country_id, window) if transactions is not None else None,
            romanians=romanians, diaspora=None, snapshot=snapshot, bounty_span=(window, end),
            mu_damage=snapshot["mu_damage"] if snapshot is not None else None,
        )

    async def _post_articles(
        self, channel, filename: str, texts: str, span: dict, now: datetime, country_id: str, *,
        damages, user_mus, all_damages, wealth_ranking, donations, romanians, diaspora, snapshot, bounty_span,
        mu_damage=None,
    ) -> None:
        """Build and send the Romania article, then the diaspora one, as `filename`.txt and `filename`-diaspora.txt.

        `diaspora` (_load_diaspora's result) None skips the diaspora article. `mu_damage` ({MU id: damage} from the
        battles' MU rankings, monthly) ranks the Romanian MUs instead of their members' summed damage.

        `damages` are the period's damages of the Romanian candidates and `all_damages` every player's (each None
        when unavailable); `user_mus` maps a player to the MU their damage counts for (None: their current MU,
        read from the loaded users). The diaspora article's failure never affects the Romania one.
        """
        users: dict[str, dict] = {}
        tr = Translator(ARTICLE_LANGUAGE)
        content = await self._romania_article(
            tr, texts, span, now, country_id, damages, user_mus, wealth_ranking, donations, romanians,
            snapshot, bounty_span, users, mu_damage,
        )
        try:
            await send_message(channel, content, f"{filename}.txt")
        except discord.HTTPException:
            logger.exception("Failed to post the government ranking %s in channel %s", filename, channel.id)

        if diaspora is None:
            return
        try:
            content = await self._diaspora_article(
                tr, texts, span, now, country_id, all_damages, wealth_ranking, diaspora, snapshot, bounty_span, users,
            )
            await send_message(channel, content, f"{filename}-diaspora.txt")
        except Exception:
            logger.exception("Failed to build or post the government diaspora ranking %s", filename)

    async def _romania_article(
        self, tr, texts, span, now, country_id, damages, user_mus, wealth_ranking, donations, romanians,
        snapshot, bounty_span, users, mu_damage=None,
    ) -> str:
        """The Romania article; loads its players into `users` for the diaspora article to reuse.

        With `mu_damage` (monthly) the Romanian MUs are ranked by their battle damage, each showing how many of
        its current members are citizens who did damage this period; without it, by their loaded Romanian
        members' damage.
        """
        wealth = country_values(wealth_ranking, country_id) if wealth_ranking is not None else None
        bounty, span_note, unread = bounty_data(snapshot, bounty_span, romanians)

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
        if user_mus is None:
            user_mus = {user_id: str(user["mu"]) for user_id, user in users.items() if user.get("mu")}

        mus = None
        if mu_damage is not None and damages is not None:
            wanted = [mu_id for mu_id, value in mu_damage.items() if value > 0]
            mu_objects = await warera.mus.get_many(wanted)
            members = {mu_id: count for mu_id, (_, count) in mu_totals(damages, user_mus, users, country_id).items()}
            mus = battle_mu_top(mu_damage, mu_objects, members, country_id)
            if len(mu_objects) < len(wanted):
                # an unloaded MU's country is unknown, so it can't be shown even if it is Romanian
                logger.warning("Government ranking: %d MUs could not be loaded", len(wanted) - len(mu_objects))
        elif damages is not None:
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
            "bounty_span": span_note,
        }
        return build_article(tr, texts, span, now, data, users, {"players": len(missing), "battles": unread})

    async def _diaspora_article(
        self, tr, texts, span, now, country_id, all_damages, wealth_ranking, diaspora, snapshot, bounty_span, users,
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
        damages = restrict(all_damages, abroad | unknown)
        wealth = restrict(ranking_values(wealth_ranking), abroad | unknown) if wealth_ranking is not None else None
        bounty, span_note, unread = bounty_data(snapshot, bounty_span, abroad | unknown)

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
            "bounty_span": span_note,
        }
        return build_diaspora_article(
            tr, texts, span, now, data, users, places,
            {**warnings, "players": len(missing), "battles": unread},
        )

    @gov_weekly_ranking.before_loop
    async def before_gov_weekly_ranking(self):
        """Wait until the bot is ready before the first weekly run."""
        await self.bot.wait_until_ready()

    @gov_monthly_ranking.before_loop
    async def before_gov_monthly_ranking(self):
        """Wait until the bot is ready before the first monthly run."""
        await self.bot.wait_until_ready()

    @gov_battle_tracker.before_loop
    async def before_gov_battle_tracker(self):
        """Wait until the bot is ready before the first tracker run."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    """Load the government rankings cog (discord.py extension entry point)."""
    await bot.add_cog(GovRankingsJob(bot))
