"""Contest tracker: starts, scores, ranks and ends the points contests created with /start_contest.

One loop ticks every minute and decides from the stored state what is due, so a restart or a missed run
never skips a start, a day rollover, a daily ranking or the end:
- a scheduled contest starts at 00:00 UTC of its start day: participants are registered with their baselines
  and the announcement is posted to each participating MU's `threadIds.contestId` thread (else `channelId`),
  once per destination;
- a running contest is refreshed hourly, right after each game reset (closing the previous day's damage),
  and just before it, when the daily ranking is posted; a ranking missed while the bot was down is posted late;
- after its last day the final refresh scores the daily pill and freezes contract money, and the final
  results are posted.
A tick only reads the contest records; participant records are read when a contest has work due. Damage near
a reset lands on the right day to within about a minute (the tick plus the refresh time).
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from cogs.tasks.military_unit_daily_report import _pill_settings, pill_state
from config import config
from utils import contests as cx
from utils import db
from utils.api import (
    get_battle_loot_summaries,
    get_companies_by_ids,
    get_company_rosters,
    get_employees_work_stats,
    get_game_config,
    get_military_units_by_ids,
    get_pp_money_value,
    get_shared_session,
    get_users_company_ids,
    get_users_full,
    get_won_mercenary_auctions,
)
from utils.common import get_mu_destination, to_local
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

TICK_MINUTES = 1
REFRESH_EVERY = timedelta(hours=1)
# a start or day rollover whose refresh missed some units or members is retried this often, for at most RETRY_FOR
RETRY_EVERY = timedelta(minutes=5)
RETRY_FOR = timedelta(hours=1)
THREAD_KEY = "contestId"
# won contracts turn "won" up to the auction's max duration (25 min) after createdAt, so each scan overlaps the last
CONTRACT_SCAN_OVERLAP = timedelta(hours=2)
# a battle's contract money is re-read until it is fully paid, or until this long after its last contract
CONTRACT_SETTLE_AFTER = timedelta(hours=48)
ECONOMY_COMPANY_MISSIONS = ("automated_engine", "build_company", "recruit_employee", "employee_output")


def _lifetime_damage(user: dict) -> float | None:
    """All-time damage of a player (user.rankings.userDamages, updated within minutes [observed 2026-11-01])."""
    value = ((user.get("rankings") or {}).get("userDamages") or {}).get("value")
    return float(value) if isinstance(value, (int, float)) else None


def _skill(user: dict, name: str, key: str):
    return ((user.get("skills") or {}).get(name) or {}).get(key)


def _snapshot(record: dict) -> str:
    return json.dumps(record, sort_keys=True)


class ContestTrackerJob(commands.Cog):
    """Runs the `contest_tracker` loop; `/contest end` calls `finish_now`."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.contest_tracker.start()

    def cog_unload(self):
        """Stop the loop."""
        self.contest_tracker.cancel()

    @tasks.loop(minutes=TICK_MINUTES)
    async def contest_tracker(self):
        """Do whatever each stored contest is due for (see the module docstring)."""
        async with cx.CONTEST_LOCK:
            contests = await asyncio.to_thread(db.get_contests)
            now = datetime.now(timezone.utc)
            for contest in contests:
                try:
                    await self._tick(contest, now)
                except Exception:
                    logger.exception("Contest %s (%s) failed this run", contest.get("id"), contest.get("name"))

    @contest_tracker.before_loop
    async def before_contest_tracker(self):
        """Wait until the bot is ready."""
        await self.bot.wait_until_ready()

    async def _tick(self, contest: dict, now: datetime) -> None:
        status = contest.get("status")
        state = contest.setdefault("state", {})
        if status == "draft":
            created = cx.parse_iso(contest.get("created_at"))
            if created and now - created > cx.DRAFT_TTL:
                await asyncio.to_thread(db.delete_contest, contest["id"])
                logger.info("Deleted unpublished contest draft %s", contest["id"])
            return
        if status == "scheduled":
            attempted = cx.parse_iso(state.get("start_attempt_at"))
            if now >= cx.start_at(contest) and (attempted is None or now - attempted >= RETRY_EVERY):
                await self._start(contest, now)
            return
        if status == "ended" and not state.get("results_posted"):
            await self._post_results(contest, await asyncio.to_thread(db.get_contest_players, contest["id"]))
            return
        if status != "running":
            return

        if not state.get("announced"):
            await self._announce(contest, len(await asyncio.to_thread(db.get_contest_players, contest["id"])))
        if now >= cx.end_at(contest):
            await self._finish(contest, await asyncio.to_thread(db.get_contest_players, contest["id"]), now)
            return

        today = cx.game_day(now)
        day_begin = cx.day_start(today)
        # the latest day whose ranking time has passed; a ranking missed while the bot was down is posted late
        ranking_day = today if now >= day_begin + timedelta(days=1) - cx.RANKING_LEAD else cx.game_day(day_begin - timedelta(days=1))
        ranking_due = ranking_day in cx.contest_days(contest) and (state.get("last_ranking_day") or "") < ranking_day
        last_refresh = cx.parse_iso(state.get("last_refresh_at"))
        since_refresh = now - last_refresh if last_refresh else None
        rollover_due = state.get("last_rollover_day") != today and (
            last_refresh is None or last_refresh < day_begin or since_refresh >= RETRY_EVERY
        )
        if not (ranking_due or rollover_due or since_refresh is None or since_refresh >= REFRESH_EVERY):
            return

        players = await asyncio.to_thread(db.get_contest_players, contest["id"])
        changed, complete = await self._refresh(contest, players, now)
        if complete or now - day_begin >= RETRY_FOR:
            state["last_rollover_day"] = today
        if not ranking_due:
            await self._save(contest, players, changed)
            return
        tr = await get_translator(contest.get("guild_id"))
        header = tr(
            "contest.ranking_title",
            name=discord.utils.escape_markdown(contest["name"]),
            day=cx.day_number(contest, cx.day_start(ranking_day)),
            days=contest["days"],
        )
        lines = [header, ""] + cx.ranking_lines(contest, list(players.values()), tr)
        # saved before posting: if the save fails, the ranking is not posted again every minute
        state["last_ranking_day"] = ranking_day
        await self._save(contest, players, changed)
        await self._post(contest, lines)

    async def _start(self, contest: dict, now: datetime) -> None:
        """Register the members with their baselines and mark the contest running.

        When some unit or member did not load, the contest stays scheduled and is retried every RETRY_EVERY,
        for at most RETRY_FOR after the start, so nobody starts with a late baseline because of one failed request.
        """
        contest["state"] = {
            "last_rollover_day": contest["start_day"],
            "contracts": {},
            "battles": {},
            "contracts_scanned_at": cx.start_at(contest).isoformat(),
        }
        players: dict = {}
        changed, complete = await self._refresh(contest, players, now)
        if not complete and now - cx.start_at(contest) < RETRY_FOR:
            logger.warning("Contest %s: not every unit or member loaded, the start is retried", contest["id"])
            stored = {key: contest[key] for key in contest if key != "state"}
            stored["state"] = {"start_attempt_at": now.isoformat()}
            await asyncio.to_thread(db.save_contest, stored)
            return
        contest["status"] = "running"
        await self._save(contest, players, changed)
        logger.info("Contest %s started with %d participants", contest["id"], len(players))
        await self._announce(contest, len(players))

    async def _announce(self, contest: dict, player_count: int) -> None:
        """Post the start announcement once and DM the creator."""
        tr = await get_translator(contest.get("guild_id"))
        lines = announcement_lines(contest, contest.get("mu_names") or {}, tr)
        # marked before posting, so a failed save can't repeat the announcement
        contest["state"]["announced"] = True
        await asyncio.to_thread(db.save_contest, contest)
        posted = await self._post(contest, lines)
        await self._notify_creator(contest, tr("contest.started_dm", name=contest["name"], players=player_count, channels=posted))

    async def _finish(self, contest: dict, players: dict, now: datetime) -> None:
        # an early end (/contest end) makes today the last day the daily pill needs
        contest.setdefault("state", {})["last_day"] = min(cx.game_day(now), cx.contest_days(contest)[-1])
        changed, _complete = await self._refresh(contest, players, now, final=True)
        contest["status"] = "ended"
        contest["state"]["ended_at"] = now.isoformat()
        await self._save(contest, players, changed)
        logger.info("Contest %s ended", contest["id"])
        await self._post_results(contest, players)

    async def _post_results(self, contest: dict, players: dict) -> None:
        """Post the winners and the final ranking once."""
        tr = await get_translator(contest.get("guild_id"))
        lines = [tr("contest.final_title", name=discord.utils.escape_markdown(contest["name"])), ""]
        lines += cx.winners_lines(contest, list(players.values()), tr)
        lines += [tr("contest.final_ranking"), ""] + cx.ranking_lines(contest, list(players.values()), tr)
        contest["state"]["results_posted"] = True
        await asyncio.to_thread(db.save_contest, contest)
        await self._post(contest, lines)

    async def finish_now(self, contest: dict) -> None:
        """End a running contest early (/contest end): final refresh, status ended and the final results.

        The caller holds `CONTEST_LOCK`.
        """
        players = await asyncio.to_thread(db.get_contest_players, contest["id"])
        await self._finish(contest, players, datetime.now(timezone.utc))

    async def _save(self, contest: dict, players: dict, changed: set) -> None:
        await asyncio.to_thread(db.save_contest, contest, {uid: players[uid] for uid in changed if uid in players})

    # ------------------------------------------------------------------------------------------ refresh

    async def _refresh(self, contest: dict, players: dict, now: datetime, final: bool = False) -> tuple[set, bool]:
        """Update every participant record from the API, register new members and rescore.

        Returns the ids of the records that changed, and whether every unit and every member loaded. Data that
        failed to load leaves the affected values as they were, so a failed request never takes points away or
        marks a member as gone.
        """
        session = await get_shared_session()
        state = contest.setdefault("state", {})
        before = {uid: _snapshot(rec) for uid, rec in players.items()}
        today = cx.game_day(now)
        days = cx.contest_days(contest)
        start = cx.start_at(contest)
        # a final refresh long after the end (bot down at the reset) would book post-contest damage on the last day
        count_damage = not final or now - cx.end_at(contest) <= RETRY_EVERY

        mus = await get_military_units_by_ids(contest["mu_ids"], session)
        contest["mu_names"] = {mu_id: mu.get("name") or mu_id for mu_id, mu in mus.items()} or contest.get("mu_names", {})
        member_mu = {str(uid): mu_id for mu_id, mu in mus.items() for uid in mu.get("members") or []}
        for uid, player in players.items():
            if uid in member_mu:
                player["mu_id"] = member_mu[uid]
            elif player.get("mu_id") in mus:
                # their MU loaded and no participating MU lists them: they left, and keep what they earned
                player["active"] = False

        wanted = [uid for uid, p in players.items() if uid in member_mu]
        if not final:
            wanted += [uid for uid in member_mu if uid not in players]
        users = await get_users_full(wanted, session) if wanted else {}
        game_config = await get_game_config(session)
        pill_settings = _pill_settings(game_config)

        for uid in wanted:
            user = users.get(uid)
            if not user:
                continue
            damage = _lifetime_damage(user)
            player = players.get(uid)
            if player is None:
                level = int((user.get("leveling") or {}).get("level") or 0)
                category, bracket = cx.classify(contest, level)
                player = players[uid] = {
                    "user_id": uid, "category": category, "bracket": bracket, "level": level,
                    "joined_at": now.isoformat(), "joined_day": max(today, contest["start_day"]),
                    "damage_base": damage, "damage_day": max(today, contest["start_day"]), "day_damage": {},
                    "pill_days": [], "points": 0, "reached_at": now.isoformat(), "active": True,
                }
            elif not player.get("active", True):
                # back in a participating MU: the damage done while away doesn't count
                player["active"] = True
                if damage is not None:
                    counted = player["day_damage"].get(today, 0) if player.get("damage_day") == today else 0
                    player["damage_base"], player["damage_day"] = damage - counted, max(today, contest["start_day"])
            player["username"] = user.get("username") or player.get("username")
            player["mu_id"] = member_mu.get(uid, player.get("mu_id"))
            if count_damage:
                self._update_damage(player, damage, today, days, final)
            if player["category"] == "fighters" and cx.has_mission(contest, "daily_pill"):
                pilled_at = pill_state(user, now, pill_settings).get("pilled_at")
                day = cx.game_day(pilled_at) if pilled_at else None
                if day and day in days and day >= player["joined_day"] and day not in player["pill_days"]:
                    player["pill_days"].append(day)
            fight_levels = [_skill(user, name, "level") for name in cx.FIGHT_SKILLS]
            if all(isinstance(level, int) for level in fight_levels):
                player["fight_skill_levels"] = sum(fight_levels)
            limit = _skill(user, "companies", "value")
            if isinstance(limit, (int, float)):
                player["company_limit"] = int(limit)

        active = {uid: p for uid, p in players.items() if p.get("active", True) and uid in users}
        await self._refresh_companies(contest, active, start, days)
        if cx.has_mission(contest, "contract_damage", "contract_money"):
            await self._refresh_contracts(contest, players, now, final)

        for player in players.values():
            points, breakdown = cx.score_player(contest, player, final=final)
            if abs(points - float(player.get("points") or 0)) > 1e-9:
                player["points"], player["reached_at"] = points, now.isoformat()
            player["breakdown"] = breakdown
        state["last_refresh_at"] = now.isoformat()
        complete = len(mus) == len(set(contest["mu_ids"])) and all(uid in users for uid in wanted)
        return {uid for uid, rec in players.items() if before.get(uid) != _snapshot(rec)}, complete

    @staticmethod
    def _update_damage(player: dict, damage: float | None, today: str, days: list[str], final: bool) -> None:
        """Book the damage since the day's baseline on the player's current contest day.

        On the first refresh of a new game day the previous day is closed with everything done since its
        baseline (including the minutes between the reset and this refresh) and a new baseline is taken.
        """
        if damage is None or player.get("damage_base") is None:
            if damage is not None:
                player["damage_base"] = damage
            return
        day = player.get("damage_day")
        if day in days:
            player["day_damage"][day] = max(0.0, damage - float(player["damage_base"]))
        if day != today and not final and today in days:
            player["damage_base"], player["damage_day"] = damage, today
            player["day_damage"].setdefault(today, 0.0)

    async def _refresh_companies(self, contest: dict, players: dict, start: datetime, days: list[str]) -> None:
        """Companies, Automated Engine levels, hires and employee output of the players that have such missions."""
        fighters = [uid for uid, p in players.items() if p["category"] == "fighters"] if cx.has_mission(contest, "company_disabled") else []
        economists = (
            [uid for uid, p in players.items() if p["category"] == "economists"]
            if cx.has_mission(contest, *ECONOMY_COMPANY_MISSIONS)
            else []
        )
        owners = fighters + economists
        if not owners:
            return
        session = await get_shared_session()
        listings = await get_users_company_ids(owners, session)
        companies = await get_companies_by_ids([cid for ids in listings.values() for cid in ids if cid], session)
        end = cx.end_at(contest)

        def owned(uid):
            ids = listings.get(uid)
            if ids is None or not all(cid in companies for cid in ids):
                return None
            return [companies[cid] for cid in ids]

        for uid in fighters:
            player, items = players[uid], owned(uid)
            if items is None or player.get("company_limit") is None:
                continue
            player["active_now"] = min(len(items), player["company_limit"])
            if player.get("active_base") is None:
                player["active_base"] = player["active_now"]

        economy_companies = {}
        for uid in economists:
            player, items = players[uid], owned(uid)
            if items is None:
                continue
            since = max(start, cx.parse_iso(player["joined_at"]) or start)
            ae_now = {c["_id"]: int((c.get("activeUpgradeLevels") or {}).get("automatedEngine") or 0) for c in items}
            if player.get("ae_base") is None:
                player["ae_base"] = dict(ae_now)
            player["ae_now"] = ae_now
            built = set(player.get("built") or [])
            built.update(c["_id"] for c in items if since <= (cx.parse_iso(c.get("createdAt")) or start - timedelta(1)) < end)
            player["built"] = sorted(built)
            economy_companies.update({c["_id"]: uid for c in items})

        if not economy_companies or not cx.has_mission(contest, "recruit_employee", "employee_output"):
            return
        rosters = await get_company_rosters(list(economy_companies), session)
        employees = {}
        for company_id, roster in rosters.items():
            uid = economy_companies[company_id]
            player = players[uid]
            since = max(start, cx.parse_iso(player["joined_at"]) or start)
            hired = set(player.get("hired") or [])
            for employee in roster.get("employees") or []:
                employees[employee["_id"]] = uid
                if since <= (cx.parse_iso(employee.get("createdAt")) or start - timedelta(1)) < end:
                    hired.add(employee["_id"])
            player["hired"] = sorted(hired)

        output_missions = [
            (index, m) for index, m in enumerate(contest["missions"]) if m.get("type") == "employee_output"
        ]
        if not employees or not output_missions:
            return
        pp_value = await get_pp_money_value(session)
        state = contest.setdefault("state", {})
        if pp_value:
            state["pp_value"] = pp_value
        pp_value = state.get("pp_value")
        if not pp_value:
            return
        stats = await get_employees_work_stats(list(employees), session)
        for employee_id, rows in stats.items():
            player = players[employees[employee_id]]
            produced = sum(float(row.get("employeeProd") or 0) for row in rows if row.get("dailyDate") in days) * pp_value
            producers = player.setdefault("producers", {})
            for index, mission in output_missions:
                # once awarded an employee stays counted, so a lower money value later takes nothing back
                awarded = producers.setdefault(str(index), [])
                if produced >= float(mission.get("goal") or 0) and employee_id not in awarded:
                    awarded.append(employee_id)

    async def _refresh_contracts(self, contest: dict, players: dict, now: datetime, final: bool) -> None:
        """Record the contest MUs' won contracts and each fighter's contract money per battle."""
        session = await get_shared_session()
        state = contest.setdefault("state", {})
        start, end = cx.start_at(contest), cx.end_at(contest)
        scanned = cx.parse_iso(state.get("contracts_scanned_at")) or start
        auctions = await get_won_mercenary_auctions(session, max(start, scanned - CONTRACT_SCAN_OVERLAP).isoformat())
        if auctions is not None:
            for auction in auctions:
                created = cx.parse_iso(auction.get("createdAt"))
                if auction.get("currentWinner") in contest["mu_ids"] and created and start <= created < end and auction.get("battle"):
                    state.setdefault("contracts", {})[auction["_id"]] = {
                        "battle": auction["battle"],
                        "minimumDamage": auction.get("minimumDamage"),
                        "payout": auction.get("currentPayout"),
                        "createdAt": auction.get("createdAt"),
                    }
            state["contracts_scanned_at"] = now.isoformat()

        fighters = [uid for uid, p in players.items() if p["category"] == "fighters"]
        battles = state.setdefault("battles", {})
        expected: dict = {}
        latest: dict = {}
        for contract in state.get("contracts", {}).values():
            expected[contract["battle"]] = expected.get(contract["battle"], 0.0) + float(contract.get("payout") or 0)
            latest[contract["battle"]] = max(latest.get(contract["battle"], ""), contract.get("createdAt") or "")
        for battle_id, payout in expected.items():
            if battles.get(battle_id, {}).get("done") or not fighters:
                continue
            summaries = await get_battle_loot_summaries(battle_id, fighters, session)
            paid = 0.0
            for uid, summary in summaries.items():
                money = float(summary.get("totalMoneyFromContract") or 0)
                if money > 0:
                    players[uid].setdefault("contract_money", {})[battle_id] = money
                    paid += money
            last_contract = cx.parse_iso(latest[battle_id]) or now
            settled = paid >= payout * 0.999 or now - last_contract > CONTRACT_SETTLE_AFTER
            # contract money is frozen at the end, paid or not
            battles[battle_id] = {"done": bool(settled or final)}

    # ------------------------------------------------------------------------------------------ posting

    async def _post(self, contest: dict, lines: list[str]) -> int:
        """Send `lines` (split into messages) once to each destination of the participating MUs; returns how many."""
        guild = self.bot.get_guild(int(contest.get("guild_id") or config["guild"]))
        if guild is None:
            logger.warning("Contest %s: guild %s not found", contest["id"], contest.get("guild_id"))
            return 0
        units = {str(unit.get("id")): unit for unit in config.get("military_units", [])}
        seen = set()
        for mu_id in contest["mu_ids"]:
            unit = units.get(mu_id)
            destination = await get_mu_destination(guild, unit, THREAD_KEY) if unit else None
            if destination is None or destination.id in seen:
                continue
            seen.add(destination.id)
            try:
                for message in cx.split_lines(lines):
                    await destination.send(message, allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                logger.exception("Contest %s: could not post to %s", contest["id"], destination.id)
        return len(seen)

    async def _notify_creator(self, contest: dict, text: str) -> None:
        try:
            user = self.bot.get_user(int(contest["creator_id"])) or await self.bot.fetch_user(int(contest["creator_id"]))
            await user.send(text)
        except discord.HTTPException:
            logger.warning("Contest %s: could not DM the creator %s", contest["id"], contest.get("creator_id"))


def announcement_lines(contest: dict, mu_names: dict, tr: Translator) -> list[str]:
    """The start announcement: dates, units, missions per category, prizes and when rankings are posted."""
    start, end = to_local(cx.start_at(contest)), to_local(cx.end_at(contest))
    ranking_time = to_local(cx.end_at(contest) - cx.RANKING_LEAD)
    lines = [
        tr("contest.announce_title", name=discord.utils.escape_markdown(contest["name"])),
        tr(
            "contest.announce_dates",
            start=tr.strftime(start, tr("contest.datetime_format")),
            end=tr.strftime(end, tr("contest.datetime_format")),
            days=contest["days"],
        ),
        tr("contest.announce_units", units=", ".join(
            discord.utils.escape_markdown(str(mu_names.get(mu_id) or mu_id)) for mu_id in contest["mu_ids"]
        )),
    ]
    if contest.get("prize_pool"):
        lines.append(tr("contest.announce_pool", pool=contest["prize_pool"]))
    for category in cx.CATEGORIES:
        missions = [m for m in contest["missions"] if cx.MISSIONS[m["type"]]["category"] == category]
        if not missions:
            continue
        lines += ["", f"**{bracket_header(contest, category, tr)}**"]
        lines += [f"• {cx.mission_text(m, tr)}" for m in missions]
        for index in range(len(cx.bracket_bounds(contest, category))):
            prizes = contest.get("prizes", {}).get(f"{category}:{index}") or []
            if prizes:
                places = " · ".join(f"{place}. {cx.prize_text(p, tr)}" for place, p in enumerate(prizes, start=1))
                lines.append(tr("contest.announce_prizes", bracket=cx.bracket_label(contest, category, index, tr), prizes=places))
    lines += ["", tr("contest.announce_rankings", time=f"{ranking_time:%H:%M} {ranking_time.tzname()}")]
    return lines


def bracket_header(contest: dict, category: str, tr: Translator) -> str:
    """'Fighters (level 25+)': the category with the level range of all its brackets."""
    bounds = cx.bracket_bounds(contest, category)
    low, high = bounds[0][0], bounds[-1][1]
    levels = tr("contest.levels_open", low=low) if high is None else tr("contest.levels_range", low=low, high=high)
    return f"{tr(f'contest.category.{category}')} ({levels})"


async def setup(bot: commands.Bot):
    """Load the contest tracker."""
    await bot.add_cog(ContestTrackerJob(bot))
