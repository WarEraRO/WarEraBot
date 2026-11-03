"""Points contests between configured military units (/start_contest): mission registry, dates, scoring and ranking text.

Nothing here does I/O. `cogs/tasks/contests.py` fills each participant record from the WarEra API and
calls `score_player`; `cogs/commands/contests.py` builds and validates contests. A contest record and its
participant records are stored with `utils.db.save_contest`.

Game days run from 00:00 UTC to 00:00 UTC (gameConfig.getDates.nextDayAt). A contest that starts on
day D begins at D 00:00 UTC and ends `days` days later at 00:00 UTC.
"""

import asyncio
import math
import re
import uuid
from datetime import date, datetime, time as dt_time, timedelta, timezone

import discord

# One lock for every read-modify-write of contest records: the tracker job and the commands both take it,
# so a run that started before /contest cancel can't write the old status back.
CONTEST_LOCK = asyncio.Lock()

CATEGORIES = ("fighters", "economists")
STATUSES = ("draft", "scheduled", "running", "ended", "cancelled")
# contests that hold their military units: an MU can be in only one of these at a time
ACTIVE_STATUSES = ("scheduled", "running")

DEFAULT_FIGHTER_MIN_LEVEL = 25
MAX_DAYS = 30
MAX_PRIZE_PLACES = 5
MAX_MISSIONS = 25
# brackets per category, counting the first one
MAX_BRACKETS = 5
# drafts nobody published are deleted after this long
DRAFT_TTL = timedelta(days=7)
# the daily ranking is posted this long before the 00:00 UTC game reset
RANKING_LEAD = timedelta(minutes=15)

# Skills that make a build a fight build (user.skills keys, gameConfig skills). Since v0.27.3 the point-buyable
# skills are these plus energy, companies, production and management (Leadership was merged into Management).
FIGHT_SKILLS = (
    "health", "hunger", "attack", "criticalChance", "criticalDamages", "armor", "precision", "dodge", "lootChance",
)

# Predefined missions; only the bot developer adds types. `fields` are the goal values the creator sets
# (name, default), besides `points`. Category is fixed per type (user decision, 2026-11-01).
MISSIONS = {
    "daily_damage": {"category": "fighters", "fields": (("goal", 1_000_000),), "points": 1},
    "daily_pill": {"category": "fighters", "fields": (), "points": 3},
    "contract_damage": {"category": "fighters", "fields": (("goal", 500_000), ("min_contract", 1_000_000)), "points": 2},
    "contract_money": {"category": "fighters", "fields": (("goal", 100),), "points": 1},
    "company_disabled": {"category": "fighters", "fields": (("keep", 4),), "points": 0.5},
    "eco_skills": {"category": "economists", "fields": (), "points": 5},
    "automated_engine": {"category": "economists", "fields": (), "points": 1},
    "build_company": {"category": "economists", "fields": (), "points": 2},
    "recruit_employee": {"category": "economists", "fields": (), "points": 1},
    "employee_output": {"category": "economists", "fields": (("goal", 3),), "points": 1},
}

MESSAGE_LIMIT = 2000
_SUFFIXES = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}


# ---------------------------------------------------------------------------------------------- dates


def parse_iso(value) -> datetime | None:
    """An aware datetime from an API or stored ISO string, or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def parse_start_date(text: str) -> date | None:
    """The date typed for a contest start: YYYY-MM-DD, DD.MM.YYYY or DD/MM/YYYY; None if it is not a date."""
    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def game_day(moment: datetime) -> str:
    """The UTC game day of an aware datetime, as YYYY-MM-DD."""
    return moment.astimezone(timezone.utc).date().isoformat()


def day_start(day: str) -> datetime:
    """00:00 UTC of a YYYY-MM-DD game day."""
    return datetime.combine(date.fromisoformat(day), dt_time(0, tzinfo=timezone.utc))


def start_at(contest: dict) -> datetime:
    """When the contest begins: 00:00 UTC of its start day."""
    return day_start(contest["start_day"])


def end_at(contest: dict) -> datetime:
    """When the contest ends: 00:00 UTC `days` days after it begins."""
    return start_at(contest) + timedelta(days=int(contest["days"]))


def contest_days(contest: dict) -> list[str]:
    """Every game day of the contest, as YYYY-MM-DD."""
    first = date.fromisoformat(contest["start_day"])
    return [(first + timedelta(days=i)).isoformat() for i in range(int(contest["days"]))]


def day_number(contest: dict, now: datetime) -> int:
    """The 1-based contest day `now` falls on (may be outside 1..days)."""
    return (now.astimezone(timezone.utc).date() - date.fromisoformat(contest["start_day"])).days + 1


def overlaps(a: dict, b: dict) -> bool:
    """True when two contests run on at least one common day."""
    return start_at(a) < end_at(b) and start_at(b) < end_at(a)


# ---------------------------------------------------------------------------------------------- records


def new_contest(guild_id: int, creator_id: int, name: str, start_day: date, days: int, now: datetime) -> dict:
    """A draft contest record with the default level limits and no units, missions or prizes."""
    return {
        "id": uuid.uuid4().hex,
        "guild_id": guild_id,
        "creator_id": creator_id,
        "name": name,
        "status": "draft",
        "start_day": start_day.isoformat(),
        "days": days,
        "mu_ids": [],
        "fighter_min_level": DEFAULT_FIGHTER_MIN_LEVEL,
        # extra bracket lower bounds per category; the first bracket starts at the category's lowest level
        "brackets": {"fighters": [], "economists": []},
        "missions": [],
        # "<category>:<bracket index>" -> [{"gems": int, "text": str}] for places 1..n
        "prizes": {},
        "prize_pool": "",
        "created_at": now.isoformat(),
        "state": {},
    }


def bracket_bounds(contest: dict, category: str) -> list[tuple[int, int | None]]:
    """The (lowest, highest) level of each bracket of a category; highest None means no upper limit."""
    min_level = int(contest.get("fighter_min_level") or DEFAULT_FIGHTER_MIN_LEVEL)
    low, high = (min_level, None) if category == "fighters" else (1, min_level - 1)
    starts = [low] + sorted(
        b for b in set(contest.get("brackets", {}).get(category) or []) if low < b and (high is None or b <= high)
    )
    bounds = []
    for i, start in enumerate(starts):
        end = starts[i + 1] - 1 if i + 1 < len(starts) else high
        bounds.append((start, end))
    return bounds


def classify(contest: dict, level: int) -> tuple[str, int]:
    """The (category, bracket index) of a player of `level`: fighters from fighter_min_level up."""
    category = "fighters" if level >= int(contest.get("fighter_min_level") or DEFAULT_FIGHTER_MIN_LEVEL) else "economists"
    index = 0
    for i, (low, _high) in enumerate(bracket_bounds(contest, category)):
        if level >= low:
            index = i
    return category, index


def missions_of(contest: dict, mission_type: str) -> list[dict]:
    """The contest's missions of one type, in the order they were added."""
    return [mission for mission in contest.get("missions") or [] if mission.get("type") == mission_type]


def has_mission(contest: dict, *mission_types: str) -> bool:
    """True when the contest has at least one mission of any of the types."""
    return any(missions_of(contest, mission_type) for mission_type in mission_types)


def parse_number(text: str) -> float | None:
    """A number typed in a form: 1M, 500k, 1,000,000, 0.5 or 0,5. None when it is not a non-negative number."""
    text = (text or "").strip().lower().replace(" ", "").replace("_", "")
    multiplier = 1
    if text and text[-1] in _SUFFIXES:
        multiplier = _SUFFIXES[text[-1]]
        text = text[:-1]
    if re.fullmatch(r"\d{1,3}(,\d{3})+", text):
        text = text.replace(",", "")
    text = text.replace(",", ".")
    try:
        value = float(text) * multiplier
    except ValueError:
        return None
    return value if value >= 0 and math.isfinite(value) else None


def parse_prize(text: str) -> dict | None:
    """One prize place typed as "600" or "600 | banner or premium"; None when the gems are not a whole number."""
    gems_text, _, note = (text or "").partition("|")
    gems = parse_number(gems_text)
    if gems is None or gems != int(gems):
        return None
    return {"gems": int(gems), "text": note.strip()}


# ---------------------------------------------------------------------------------------------- scoring


def _contract_battles(contest: dict) -> dict:
    """{battleId: {"perK", "max_contract"}} from the contest's won contracts (state.contracts)."""
    battles: dict = {}
    for contract in (contest.get("state") or {}).get("contracts", {}).values():
        battle = battles.setdefault(contract["battle"], {"payout": 0.0, "damage": 0.0, "max_contract": 0.0})
        battle["payout"] += float(contract.get("payout") or 0)
        battle["damage"] += float(contract.get("minimumDamage") or 0)
        battle["max_contract"] = max(battle["max_contract"], float(contract.get("minimumDamage") or 0))
    for battle in battles.values():
        # the API pools every contract of a battle, so contract damage is read at the battle's average rate
        battle["perK"] = battle["payout"] / battle["damage"] * 1000 if battle["damage"] else 0.0
    return battles


def contract_damage(contest: dict, player: dict) -> dict:
    """{battleId: damage} the player did for the contest's contracts: contract money / perK x 1000."""
    battles = _contract_battles(contest)
    result = {}
    for battle_id, money in (player.get("contract_money") or {}).items():
        perk = battles.get(battle_id, {}).get("perK")
        if perk:
            result[battle_id] = float(money) / perk * 1000
    return result


def score_player(contest: dict, player: dict, final: bool = False) -> tuple[float, dict]:
    """The player's points and {mission index: points} from the data the tracker stored on the record.

    Only missions of the player's category score. The daily pill scores only when `final` is True, since
    it needs every day from the start (or the player's join day) to the last day, which is
    `state.last_day` when the contest was ended early.
    """
    category = player.get("category")
    breakdown: dict = {}
    days = contest_days(contest)
    tiers = missions_of(contest, "daily_damage")
    first_tier = next((i for i, m in enumerate(contest.get("missions") or []) if m.get("type") == "daily_damage"), None)
    for index, mission in enumerate(contest.get("missions") or []):
        kind = mission.get("type")
        if MISSIONS.get(kind, {}).get("category") != category:
            continue
        points = float(mission.get("points") or 0)
        earned = 0.0
        if kind == "daily_damage":
            # tiers don't add up: each day only the highest daily_damage mission reached counts, booked on the first tier
            if index != first_tier:
                continue
            for damage in (player.get("day_damage") or {}).values():
                reached = [float(t.get("points") or 0) for t in tiers if damage >= float(t.get("goal") or 0)]
                earned += max(reached, default=0.0)
        elif kind == "daily_pill":
            last_day = (contest.get("state") or {}).get("last_day") or days[-1]
            needed = [day for day in days if (player.get("joined_day") or days[0]) <= day <= last_day]
            pilled = set(player.get("pill_days") or [])
            if final and needed and all(day in pilled for day in needed):
                earned = points
        elif kind == "contract_damage":
            battles = _contract_battles(contest)
            goal = float(mission.get("goal") or 0)
            min_contract = float(mission.get("min_contract") or 0)
            for battle_id, damage in contract_damage(contest, player).items():
                if damage >= goal and battles[battle_id]["max_contract"] >= min_contract:
                    earned += points
        elif kind == "contract_money":
            goal = float(mission.get("goal") or 0)
            money = sum(float(value) for value in (player.get("contract_money") or {}).values())
            if goal > 0:
                earned = math.floor(money / goal) * points
        elif kind == "company_disabled":
            # companies already disabled at the start count too; companies built during the contest don't
            if player.get("owned_base") is not None and player.get("owned_now") is not None and player.get("active_now") is not None:
                keep = int(mission.get("keep") or 0)
                owned = min(int(player["owned_now"]), int(player["owned_base"]))
                earned = max(0, owned - max(int(player["active_now"]), keep)) * points
        elif kind == "eco_skills":
            if player.get("fight_skill_levels") == 0:
                earned = points
        elif kind == "automated_engine":
            base = player.get("ae_base") or {}
            gained = sum(
                max(0, int(level) - int(base.get(company_id, 1)))
                for company_id, level in (player.get("ae_now") or {}).items()
            )
            earned = gained * points
        elif kind == "build_company":
            earned = len(player.get("built") or []) * points
        elif kind == "recruit_employee":
            earned = len(player.get("hired") or []) * points
        elif kind == "employee_output":
            earned = len((player.get("producers") or {}).get(str(index)) or []) * points
        if earned:
            breakdown[str(index)] = earned
    return sum(breakdown.values()), breakdown


def rank_players(players: list[dict]) -> list[dict]:
    """Players by points, highest first; ties go to whoever reached their score first."""
    return sorted(players, key=lambda p: (-float(p.get("points") or 0), p.get("reached_at") or "", p.get("username") or ""))


# ---------------------------------------------------------------------------------------------- text


def format_points(value) -> str:
    """Points without a trailing .0 (12, 12.5)."""
    value = round(float(value or 0), 2)
    return f"{value:g}"


def format_amount(value) -> str:
    """A goal amount the way it is typed: 1M, 500k, 100."""
    value = float(value or 0)
    for suffix, size in (("B", 1_000_000_000), ("M", 1_000_000), ("k", 1_000)):
        if value >= size and value % (size / 100) == 0:
            return f"{value / size:g}{suffix}"
    return f"{value:g}"


def bracket_label(contest: dict, category: str, index: int, tr) -> str:
    """'Fighters · level 25–39' style header of one bracket."""
    bounds = bracket_bounds(contest, category)
    low, high = bounds[min(index, len(bounds) - 1)]
    levels = tr("contest.levels_open", low=low) if high is None else tr("contest.levels_range", low=low, high=high)
    return f"{tr(f'contest.category.{category}')} · {levels}"


def mission_text(mission: dict, tr) -> str:
    """One mission as shown in the setup panel and the announcement."""
    values = {name: format_amount(mission.get(name, default)) for name, default in MISSIONS[mission["type"]]["fields"]}
    return tr(f"contest.mission.{mission['type']}.text", points=format_points(mission.get("points")), **values)


def split_lines(lines: list[str], limit: int = MESSAGE_LIMIT) -> list[str]:
    """Pack whole lines into messages of at most `limit` characters; a longer line is cut at `limit`."""
    messages, current = [], ""
    for line in lines:
        line = line[:limit]
        if current and len(current) + 1 + len(line) > limit:
            messages.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        messages.append(current)
    return messages


def _name_lines(prefix: str, names: list[str], limit: int = MESSAGE_LIMIT) -> list[str]:
    """`prefix` followed by comma-separated names, wrapped into lines of at most `limit` characters."""
    lines, current = [], prefix
    for name in names:
        piece = name if current == prefix else f", {name}"
        if len(current) + len(piece) > limit:
            lines.append(current)
            current, piece = prefix, name
        current += piece
    lines.append(current)
    return lines


def ranking_lines(contest: dict, players: list[dict], tr) -> list[str]:
    """Ranking lines per category and bracket: header once, `rank. name points`, then every 0-point player on one line.

    Categories without missions are left out, and so are brackets nobody is in.
    """
    lines = []
    for category in CATEGORIES:
        if not any(MISSIONS.get(m.get("type"), {}).get("category") == category for m in contest.get("missions") or []):
            continue
        for index in range(len(bracket_bounds(contest, category))):
            group = [p for p in players if p.get("category") == category and int(p.get("bracket") or 0) == index]
            if not group:
                continue
            lines.append(f"**{bracket_label(contest, category, index, tr)}**")
            scored = [p for p in rank_players(group) if float(p.get("points") or 0) > 0]
            for rank, player in enumerate(scored, start=1):
                lines.append(f"{rank}. {discord.utils.escape_markdown(player.get('username') or '?')} — {format_points(player.get('points'))}")
            zero = sorted(discord.utils.escape_markdown(p.get("username") or "?") for p in group if float(p.get("points") or 0) <= 0)
            if zero:
                lines.extend(_name_lines(tr("contest.zero_points"), zero))
            lines.append("")
    return lines or [tr("contest.no_participants")]


def winners_lines(contest: dict, players: list[dict], tr) -> list[str]:
    """The prize winners of every bracket that has prizes, place by place."""
    lines = []
    for category in CATEGORIES:
        for index in range(len(bracket_bounds(contest, category))):
            prizes = contest.get("prizes", {}).get(f"{category}:{index}") or []
            if not prizes:
                continue
            group = [
                p for p in rank_players(players)
                if p.get("category") == category and int(p.get("bracket") or 0) == index and float(p.get("points") or 0) > 0
            ]
            lines.append(f"**{bracket_label(contest, category, index, tr)}**")
            for place, prize in enumerate(prizes, start=1):
                winner = group[place - 1] if place <= len(group) else None
                name = discord.utils.escape_markdown(winner.get("username") or "?") if winner else tr("contest.no_winner")
                lines.append(tr("contest.winner_line", place=place, name=name, prize=prize_text(prize, tr)))
            lines.append("")
    return lines


def prize_text(prize: dict, tr) -> str:
    """'600 gems (banner or premium)'."""
    text = tr("contest.gems", gems=prize.get("gems", 0))
    return f"{text} ({prize['text']})" if prize.get("text") else text
