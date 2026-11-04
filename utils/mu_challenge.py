"""Government MU challenges (/gov_challenge): mission registry, week window, scoring and the article text.

A challenge is a Romanian-government weekly challenge between the configured Romanian military units: up to
MAX_MISSIONS pass/fail missions per MU. It is created on the Monday of a game week (the weekly reset is Monday
00:00 UTC, gameConfig.getDates.weeklyMissionRegenAt) and covers that week up to REPORT_LEAD before the next
reset, when `cogs/tasks/mu_challenge.py` posts the ready-to-paste article (winners only) in the government
channel. Nothing here does I/O.

Storage (utils.db.save_mu_challenge): the challenge record, and one record per participating MU holding
what the tracker collected:
- "members": {user id: highest weekly damage seen while in the MU} (muMember.getByMu weeklyDamagesCount);
  everyone seen in the MU during the week stays in it; "members_read" is set once muMember was read;
- "pills_read": set once the members' pill timers were read;
- "member_count": the MU's current member count;
- "pills": {YYYY-MM-DD: [user ids pilled that UTC day while in the MU]};
- "contracts": {auction id: {"battle", "minimumDamage", "payout", "createdAt"}}: the MU's won contracts,
  also those created up to CONTRACT_LOOKBACK before the week (their pay can land in a battle of the week);
- "contract_paid": {battle id: contract money paid to the MU's members and takers in that battle};
- "battle_money": {battle id: the MU's money ranking value} for the battles that ended in the window
  (bounty plus contract pay, per the MU the player was in during the battle);
- "weekly_damage" / "weekly_rank": the MU's muWeeklyDamages entry at the last read before the reset;
- "donations": the money donated to the MU in the window.
A value that was never read is missing, and a mission that needs it is reported as unavailable.
"""

import asyncio
import uuid
from datetime import date, datetime, time as dt_time, timedelta, timezone

from utils.contests import parse_iso, parse_number

# Every read-modify-write of challenge records holds this (tracker and commands), like contests.CONTEST_LOCK.
CHALLENGE_LOCK = asyncio.Lock()

STATUSES = ("running", "ended", "cancelled")
MAX_MISSIONS = 5
WEEK = timedelta(days=7)
# results are built this long before the weekly reset, when the weekly counters (muMember, muWeeklyDamages)
# still describe the week; the same cut-off as the government's weekly ranking (cogs/tasks/gov_rankings.py)
REPORT_LEAD = timedelta(minutes=12)
# won contracts created this long before the week are kept, so their pay is not counted as bounty
CONTRACT_LOOKBACK = timedelta(days=2)
# paid at least this share of the payouts counts as fully paid (rounding in the API's money values)
PAID_SHARE = 0.999
MU_URL = "https://app.warera.io/mu/{}"

# Mission types (user decision, 2026-11-04: only these, more will be requested). `fields` are the numbers the
# creator types (name, default); `whole` the fields that must be whole numbers of at least 1. Locale keys:
# mu_challenge.mission.<type>.label / description (dropdown), .text (article sentence), .field.<name>.
MISSIONS = {
    "mu_donations": {"fields": (("amount", 300),), "whole": ()},
    "members_damage": {"fields": (("members", 2), ("damage", 10_000_000)), "whole": ("members",)},
    "mu_damage": {"fields": (("damage", 100_000_000),), "whole": ()},
    "mu_top": {"fields": (("rank", 100),), "whole": ("rank",)},
    "bounty": {"fields": (("amount", 2_000),), "whole": ()},
    "contracts": {"fields": (("count", 1), ("min_damage", 5_000_000)), "whole": ("count",)},
    "contract_streak": {"fields": (("days", 5), ("min_damage", 1_000_000)), "whole": ("days",)},
    "pill_streak": {"fields": (("members", 8), ("days", 3)), "whole": ("members", "days")},
}
# fields counted in days can't exceed the week
DAY_FIELDS = ("days",)

# data each mission needs from the tracker
NEEDS_MEMBERS = ("members_damage", "bounty", "contracts", "contract_streak")
NEEDS_RANKING = ("mu_damage", "mu_top")
NEEDS_CONTRACTS = ("contracts", "contract_streak", "bounty")


# ---------------------------------------------------------------------------------------------- dates


def week_start(now: datetime) -> datetime:
    """Monday 00:00 UTC of the game week that contains `now`."""
    now = now.astimezone(timezone.utc)
    return datetime.combine(now.date() - timedelta(days=now.weekday()), dt_time(0, tzinfo=timezone.utc))


def can_create(now: datetime) -> bool:
    """True on a Monday (UTC), the only day a challenge can be created (user decision, 2026-11-04)."""
    return now.astimezone(timezone.utc).weekday() == 0


def start_of(challenge: dict) -> datetime:
    """Monday 00:00 UTC of the challenge's week."""
    return datetime.combine(date.fromisoformat(challenge["week"]), dt_time(0, tzinfo=timezone.utc))


def reset_of(challenge: dict) -> datetime:
    """The weekly reset that ends the challenge's week (the next Monday 00:00 UTC)."""
    return start_of(challenge) + WEEK


def cutoff_of(challenge: dict) -> datetime:
    """When the results are built: REPORT_LEAD before the reset. Battles and contracts after it don't count."""
    return reset_of(challenge) - REPORT_LEAD


def week_days(challenge: dict) -> list[str]:
    """The seven UTC days of the challenge's week, as YYYY-MM-DD."""
    first = date.fromisoformat(challenge["week"])
    return [(first + timedelta(days=i)).isoformat() for i in range(7)]


def utc_day(moment: datetime) -> str:
    """The UTC day of an aware datetime, as YYYY-MM-DD."""
    return moment.astimezone(timezone.utc).date().isoformat()


# ---------------------------------------------------------------------------------------------- records


def new_challenge(guild_id: int, creator_id: int, now: datetime) -> dict:
    """An unsaved challenge of the week that contains `now`, with no units or missions yet."""
    return {
        "id": uuid.uuid4().hex,
        "guild_id": guild_id,
        "creator_id": creator_id,
        "status": "running",
        "week": week_start(now).date().isoformat(),
        "mu_ids": [],
        "missions": [],
        "created_at": now.isoformat(),
        "state": {},
    }


def has_mission(challenge: dict, *types: str) -> bool:
    """True when the challenge has a mission of any of the types."""
    return any(mission.get("type") in types for mission in challenge.get("missions") or [])


def parse_mission(mission_type: str, values: dict[str, str]) -> tuple[dict | None, str | None]:
    """(mission, None) from the typed field values, or (None, the first invalid field name).

    Amounts accept 1M / 500k / 1,000,000; whole-number fields must be at least 1, and day counts at most 7.
    """
    mission = {"type": mission_type}
    spec = MISSIONS[mission_type]
    for name, _default in spec["fields"]:
        value = parse_number(values.get(name, ""))
        if value is None:
            return None, name
        if name in spec["whole"]:
            if value != int(value) or value < 1 or (name in DAY_FIELDS and value > 7):
                return None, name
            value = int(value)
        mission[name] = value
    return mission, None


def same_week(challenges: list[dict], week: str) -> dict | None:
    """A running or ended challenge of `week` (only one is allowed per week), or None."""
    return next(
        (c for c in challenges if c.get("week") == week and c.get("status") in ("running", "ended")), None,
    )


# ---------------------------------------------------------------------------------------------- formatting


def compact(value: float) -> str:
    """A short number for the article: 630, 2k, 14.97k, 80M, 1.5M (up to 2 decimals, trailing zeros dropped)."""
    value = float(value)
    for limit, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "k")):
        if abs(value) >= limit:
            return f"{value / limit:.2f}".rstrip("0").rstrip(".") + suffix
    return str(round(value)) if abs(value) >= 10 or value == int(value) else f"{value:.2f}".rstrip("0").rstrip(".")


def mission_values(mission: dict) -> dict[str, str]:
    """The mission's field values formatted for its sentence (amounts compact, counts as whole numbers)."""
    return {
        name: str(int(mission[name])) if name in MISSIONS[mission["type"]]["whole"] else compact(mission[name])
        for name, _default in MISSIONS[mission["type"]]["fields"]
    }


def mission_text(mission: dict, tr) -> str:
    """The mission sentence (mu_challenge.mission.<type>.text, or .text_any for contracts with no minimum)."""
    kind = mission["type"]
    values = mission_values(mission)
    if kind == "contracts":
        key = "text_any" if not mission.get("min_damage") else "text"
        return tr(f"mu_challenge.mission.contracts.{key}",
                  contracts=tr.plural("mu_challenge.contracts_word", int(mission["count"])), **values)
    return tr(f"mu_challenge.mission.{kind}.text", **values)


# ---------------------------------------------------------------------------------------------- scoring


def longest_run(days: list[str], good: set[str]) -> int:
    """The longest run of consecutive `days` that are all in `good`."""
    best = run = 0
    for day in days:
        run = run + 1 if day in good else 0
        best = max(best, run)
    return best


def counted_contracts(challenge: dict, unit: dict) -> list[dict]:
    """The MU's contracts created in the window that count as fulfilled.

    The API pools a player's contract money per battle, so fulfilment is decided per battle: a battle's
    contracts count when the money paid to the MU's members and takers reaches their summed payouts, and,
    when the battle holds several contracts of the MU, as soon as any of it was paid (user decision,
    2026-11-04: count all of them). Every contract of the MU in the battle is in the sum, also those created
    before the week.
    """
    start, cutoff = start_of(challenge), cutoff_of(challenge)
    by_battle: dict[str, list[dict]] = {}
    for contract in (unit.get("contracts") or {}).values():
        by_battle.setdefault(contract["battle"], []).append(contract)
    counted = []
    for battle_id, contracts in by_battle.items():
        paid = (unit.get("contract_paid") or {}).get(battle_id)
        if paid is None or paid <= 0:
            continue
        payout = sum(float(c.get("payout") or 0) for c in contracts)
        if len(contracts) == 1 and paid < payout * PAID_SHARE:
            continue
        counted += [
            c for c in contracts
            if (created := parse_iso(c.get("createdAt"))) is not None and start <= created < cutoff
        ]
    return counted


def unit_bounty(unit: dict) -> float | None:
    """The MU's bounty: its battle money (bounty + contract pay) minus its contract pay, over the window's battles.

    A battle whose contract pay was never read but where the MU had contracts takes off their payouts (at
    most the battle's money). None when no battle money was read yet.
    """
    money = unit.get("battle_money")
    if money is None:
        return None
    payouts: dict[str, float] = {}
    for contract in (unit.get("contracts") or {}).values():
        payouts[contract["battle"]] = payouts.get(contract["battle"], 0.0) + float(contract.get("payout") or 0)
    paid = unit.get("contract_paid") or {}
    total = 0.0
    for battle_id, value in money.items():
        contract_pay = paid.get(battle_id, payouts.get(battle_id, 0.0))
        total += max(0.0, float(value) - float(contract_pay))
    return total


def score(challenge: dict, mission: dict, unit: dict) -> dict | None:
    """One MU's result for one mission: {"passed", "sort" (higher is better), "value"}, or None if unavailable.

    "value" holds what the article shows (see `value_text`).
    """
    kind = mission["type"]
    if kind == "mu_donations":
        total = unit.get("donations")
        return None if total is None else {"passed": total >= mission["amount"], "sort": total, "value": total}
    if kind == "members_damage":
        members = unit.get("members")
        if members is None or not unit.get("members_read"):
            return None
        count = sum(1 for damage in members.values() if damage >= mission["damage"])
        return {"passed": count >= mission["members"], "sort": count, "value": count}
    if kind == "mu_damage":
        damage = unit.get("weekly_damage")
        return None if damage is None else {"passed": damage >= mission["damage"], "sort": damage, "value": damage}
    if kind == "mu_top":
        if "weekly_rank" not in unit:
            return None
        rank = unit["weekly_rank"]
        return {"passed": rank is not None and rank <= mission["rank"], "sort": -(rank or 10**9), "value": rank}
    if kind == "bounty":
        bounty = unit_bounty(unit)
        return None if bounty is None else {"passed": bounty >= mission["amount"], "sort": bounty, "value": bounty}
    if kind == "contracts":
        if unit.get("contracts") is None:
            return None
        contracts = [c for c in counted_contracts(challenge, unit) if float(c.get("minimumDamage") or 0) >= mission["min_damage"]]
        damage = sum(float(c.get("minimumDamage") or 0) for c in contracts)
        return {"passed": len(contracts) >= mission["count"], "sort": (len(contracts), damage),
                "value": (len(contracts), damage)}
    if kind == "contract_streak":
        if unit.get("contracts") is None:
            return None
        days = {
            utc_day(parse_iso(c["createdAt"])) for c in counted_contracts(challenge, unit)
            if float(c.get("minimumDamage") or 0) >= mission["min_damage"]
        }
        run = longest_run(week_days(challenge), days)
        return {"passed": run >= mission["days"], "sort": run, "value": run}
    if kind == "pill_streak":
        pills = unit.get("pills")
        if pills is None or not unit.get("pills_read"):
            return None
        days = week_days(challenge)
        good = {day for day in days if len(pills.get(day) or []) >= mission["members"]}
        best = max((len(pills.get(day) or []) for day in days), default=0)
        run = longest_run(days, good)
        return {"passed": run >= mission["days"], "sort": (run, best), "value": (best, unit.get("member_count") or 0)}
    raise ValueError(f"unknown mission type {kind}")


def value_text(mission: dict, value, tr) -> str:
    """The value shown after a winner's MU link (630, 14, #12, 14.97k, '11 contracte în valoare de 80M', 23/25)."""
    kind = mission["type"]
    if kind == "members_damage":
        return str(value)
    if kind == "mu_top":
        return tr("mu_challenge.value.rank", rank=value)
    if kind == "contracts":
        count, damage = value
        return tr("mu_challenge.value.contracts", contracts=tr.plural("mu_challenge.contracts_word", count),
                  damage=compact(damage))
    if kind == "contract_streak":
        return tr.plural("mu_challenge.days_word", value)
    if kind == "pill_streak":
        return f"{value[0]}/{value[1]}"
    return compact(value)


# ---------------------------------------------------------------------------------------------- article


def article_text(challenge: dict, units: dict[str, dict], now: datetime, tr, warnings: list[str]) -> str:
    """The ready-to-paste article (always Romanian, `tr` = Translator("ro")): each mission with its winners.

    Winners are sorted best first (ties by MU id, so the text is stable); MUs that missed a mission are not
    listed (user decision, 2026-11-04). "Misiunile săptămânii" is left empty for the government member to
    write. `warnings` are delete-before-publishing lines put at the top.
    """
    next_week = reset_of(challenge)
    lines = [*warnings, *([""] if warnings else [])]
    lines += [
        tr("mu_challenge.article.title", date=f"{next_week:%d/%m/%y}"), "",
        tr("mu_challenge.article.greeting"), "",
        tr("mu_challenge.article.intro"), "",
        "---", "",
        tr("mu_challenge.article.past_title"), "",
    ]
    for index, mission in enumerate(challenge["missions"], start=1):
        lines.append(f"{index}. **{mission_text(mission, tr)}**")
        results = [(mu_id, score(challenge, mission, units.get(mu_id) or {})) for mu_id in challenge["mu_ids"]]
        if any(result is None for _mu_id, result in results):
            lines.append("   - " + tr("mu_challenge.article.unavailable"))
        winners = sorted(
            ((mu_id, r) for mu_id, r in results if r is not None and r["passed"]),
            key=lambda item: (_negate(item[1]["sort"]), item[0]),
        )
        if winners:
            lines.append("   - " + tr("mu_challenge.article.winners"))
            lines += [
                f"     - {MU_URL.format(mu_id)} - {value_text(mission, r['value'], tr)}" for mu_id, r in winners
            ]
        else:
            lines.append("   - " + tr("mu_challenge.article.no_winners"))
        lines.append("")
    lines += [
        "---", "",
        tr("mu_challenge.article.next_title"), "", "",
        "---", "",
        tr("mu_challenge.article.signature"),
        tr("mu_challenge.article.government"), "",
        tr.strftime(now, tr("mu_challenge.article.date_format")),
    ]
    return "\n".join(lines)


def _negate(sort):
    return tuple(-x for x in sort) if isinstance(sort, tuple) else -sort


def announcement_lines(challenge: dict, mu_names: dict[str, str], tr) -> list[str]:
    """The start announcement for the MUs' contest threads: the week, the units and the missions."""
    start = start_of(challenge)
    end = reset_of(challenge) - timedelta(days=1)
    lines = [
        tr("mu_challenge.announce_title", start=f"{start:%d.%m}", end=f"{end:%d.%m.%Y}"),
        tr("mu_challenge.announce_units", units=", ".join(str(mu_names.get(m) or m) for m in challenge["mu_ids"])),
        "",
        tr("mu_challenge.announce_missions"),
    ]
    lines += [f"{index}. {mission_text(m, tr)}" for index, m in enumerate(challenge["missions"], start=1)]
    lines += ["", tr("mu_challenge.announce_footer")]
    return lines
