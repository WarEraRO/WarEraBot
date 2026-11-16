"""MU challenge tracker: collects the data of the government MU challenges (/gov_challenge) and posts the article.

One loop ticks every minute and decides from the stored state what is due, so a restart never loses a week:
- a running challenge is refreshed hourly: members seen in each MU with their weekly damage, the day each
  member pilled, the MUs' muWeeklyDamages entry, their won contracts and the contract money paid per battle,
  and the MU money ranking of every battle that ended in the window (for bounty);
- at the cut-off (Sunday 23:48 UTC, REPORT_LEAD before the weekly reset) a final refresh adds the donations
  and the rest of the battles, and the article (utils.mu_challenge.article_text) is posted as a .txt file in
  the government rankings thread (config.json channels.government_rankings).
Everything collected is saved, so the final run after a restart only reads what is missing. If the bot is
down at the cut-off, the article is posted when it is back, with a warning to check it: the weekly counters
(muMember, muWeeklyDamages) are then taken from the last hourly read before the reset.
"""

import asyncio
import io
import json
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from cogs.tasks.gov_rankings import battles_in_window
from cogs.tasks.military_unit_daily_report import _pill_settings, pill_state
from config import config
from utils import db
from utils import mu_challenge as mc
from utils.api import warera
from utils.common import get_government_rankings_channel
from utils.contests import parse_iso
from utils.i18n import Translator

logger = logging.getLogger(__name__)

TICK_MINUTES = 1
REFRESH_EVERY = timedelta(hours=1)
# won contracts turn "won" up to the auction's max duration (25 min) after createdAt, so each scan overlaps the last
CONTRACT_SCAN_OVERLAP = timedelta(hours=2)
# battles last at most ~1 day and are listed by creation, so one that ended in the window was created after this
BATTLE_MAX_AGE = timedelta(days=2)
# MU money rankings read per hourly refresh (~41 battles end per day [observed 2026-11-04]); the final reads all
BATTLES_PER_REFRESH = 60
# a battle whose MU money ranking failed this many times is left for the final run
MAX_BATTLE_ATTEMPTS = 4
# the extra refresh before the cut-off: 23:38 UTC, so the 23:48 final competes less with gov_weekly_ranking
PRE_FINAL_LEAD = timedelta(minutes=10)
MAX_POST_ATTEMPTS = 5
# a battle whose contract money read as 0 after it ended is read again until this long after its end
SETTLE_AFTER = timedelta(hours=1)
ARTICLE_LANGUAGE = "ro"


def _snapshot(record: dict) -> str:
    return json.dumps(record, sort_keys=True)


class MuChallengeJob(commands.Cog):
    """Runs the `mu_challenge_tracker` loop."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mu_challenge_tracker.start()

    def cog_unload(self):
        """Stop the loop."""
        self.mu_challenge_tracker.cancel()

    @tasks.loop(minutes=TICK_MINUTES)
    async def mu_challenge_tracker(self):
        """Refresh each running challenge when due and post its article at the cut-off (see the module docstring)."""
        async with mc.CHALLENGE_LOCK:
            challenges = await asyncio.to_thread(db.get_mu_challenges)
            now = datetime.now(timezone.utc)
            for challenge in challenges:
                try:
                    await self._tick(challenge, now)
                except Exception:
                    logger.exception("MU challenge %s failed this run", challenge.get("id"))
                    if asyncio.current_task() is not self.mu_challenge_tracker.get_task():
                        raise  # /run_job reports the error to whoever forced the run

    @mu_challenge_tracker.before_loop
    async def before_mu_challenge_tracker(self):
        """Wait until the bot is ready."""
        await self.bot.wait_until_ready()

    async def _tick(self, challenge: dict, now: datetime) -> None:
        state = challenge.setdefault("state", {})
        if challenge.get("status") == "ended" and not state.get("results_posted"):
            await self._post_article(challenge, await asyncio.to_thread(db.get_mu_challenge_units, challenge["id"]))
            return
        if challenge.get("status") != "running":
            return
        cutoff = mc.cutoff_of(challenge)
        if now >= cutoff:
            await self._finish(challenge, now)
            return
        last = parse_iso(state.get("last_refresh_at"))
        # one extra refresh shortly before the cut-off, so the final run only reads what is left
        pre_final = now >= cutoff - PRE_FINAL_LEAD and (last is None or last < cutoff - PRE_FINAL_LEAD)
        if not pre_final and last is not None and now - last < REFRESH_EVERY:
            return
        units = await asyncio.to_thread(db.get_mu_challenge_units, challenge["id"])
        changed = await self._refresh(challenge, units, now)
        await self._save(challenge, units, changed)

    async def _finish(self, challenge: dict, now: datetime) -> None:
        """Final refresh, mark the challenge ended with the article's warnings, then post the article."""
        if await self._government_channel() is None:
            return  # retried every tick until the channel is configured
        units = await asyncio.to_thread(db.get_mu_challenge_units, challenge["id"])
        changed = await self._refresh(challenge, units, now, final=True)
        state = challenge["state"]
        warnings = []
        if now >= mc.reset_of(challenge):
            warnings.append("warning_late")
        unread = len(state.get("battles_unread") or [])
        if unread and mc.has_mission(challenge, "bounty"):
            warnings.append("warning_battles")
        challenge["status"] = "ended"
        state.update(ended_at=now.isoformat(), warnings=warnings, unread_count=unread)
        # the per-battle bookkeeping is only needed while collecting; the article is built from the MU records
        for key in ("battles_read", "battle_attempts", "settled_battles", "battles_unread"):
            state.pop(key, None)
        await self._save(challenge, units, changed)
        logger.info("MU challenge %s ended", challenge["id"])
        await self._post_article(challenge, units)

    async def _post_article(self, challenge: dict, units: dict) -> None:
        """Build the article from the stored records and post it in the government rankings thread.

        `results_posted` is saved before sending, so a failed save can't repeat the post every minute; a failed
        send clears it again, for at most MAX_POST_ATTEMPTS tries.
        """
        channel = await self._government_channel()
        if channel is None:
            return
        state = challenge["state"]
        tr = Translator(ARTICLE_LANGUAGE)
        warnings = [
            tr(f"mu_challenge.article.{key}", count=state.get("unread_count") or 0) for key in state.get("warnings") or []
        ]
        content = mc.article_text(challenge, units, parse_iso(state.get("ended_at")), tr, warnings)
        state["results_posted"] = True
        await asyncio.to_thread(db.save_mu_challenge, challenge)
        file = discord.File(io.BytesIO(content.encode("utf-8")), filename=f"mu-challenge-{challenge['week']}.txt")
        try:
            await channel.send(file=file)
        except discord.HTTPException:
            attempts = int(state.get("post_attempts") or 0) + 1
            logger.exception("MU challenge %s: could not post the article in %s (try %d of %d)",
                             challenge["id"], channel.id, attempts, MAX_POST_ATTEMPTS)
            if attempts < MAX_POST_ATTEMPTS:
                state.update(results_posted=False, post_attempts=attempts)
                await asyncio.to_thread(db.save_mu_challenge, challenge)

    async def _government_channel(self):
        """The government rankings thread (utils.common.get_government_rankings_channel), or None with a warning."""
        channel = await get_government_rankings_channel(self.bot.get_guild(config["guild"]))
        if channel is None:
            logger.warning("Government rankings channel %s not found; MU challenge article not posted",
                           config.get("channels", {}).get("government_rankings"))
        return channel

    async def _save(self, challenge: dict, units: dict, changed: set) -> None:
        await asyncio.to_thread(db.save_mu_challenge, challenge, {m: units[m] for m in changed if m in units})

    # ------------------------------------------------------------------------------------------ refresh

    async def _refresh(self, challenge: dict, units: dict, now: datetime, final: bool = False) -> set:
        """Update every MU record from the API; returns the ids of the MU records that changed.

        Weekly counters are only read before the reset (after it they describe the next week). Data that
        failed to load leaves the stored values as they were.
        """
        state = challenge.setdefault("state", {})
        before = {mu_id: _snapshot(unit) for mu_id, unit in units.items()}
        for mu_id in challenge["mu_ids"]:
            units.setdefault(mu_id, {"mu_id": mu_id})
        weekly_ok = now < mc.reset_of(challenge)

        mus = await warera.mus.get_many(challenge["mu_ids"])
        challenge["mu_names"] = {m: mu.get("name") or m for m, mu in mus.items()} or challenge.get("mu_names", {})
        current = {m: [str(uid) for uid in mu.get("members") or []] for m, mu in mus.items()}
        for mu_id, members in current.items():
            units[mu_id]["member_count"] = len(members)
            seen = units[mu_id].setdefault("members", {})
            for uid in members:
                seen.setdefault(uid, 0)

        if weekly_ok and mc.has_mission(challenge, *mc.NEEDS_MEMBERS):
            await self._refresh_member_damage(challenge, units)
        if mc.has_mission(challenge, "pill_streak"):
            await self._refresh_pills(challenge, units, current, now)
        if weekly_ok and mc.has_mission(challenge, *mc.NEEDS_RANKING):
            self._refresh_ranking(challenge, units, mus)
        ended_ids = None
        if mc.has_mission(challenge, "bounty") or mc.has_mission(challenge, *mc.NEEDS_CONTRACTS):
            ended_ids = await self._refresh_battles(challenge, units, now, final)
        if mc.has_mission(challenge, *mc.NEEDS_CONTRACTS):
            await self._refresh_contracts(challenge, units, now, ended_ids, final)
        if final and mc.has_mission(challenge, "mu_donations"):
            await self._refresh_donations(challenge, units)

        state["last_refresh_at"] = now.isoformat()
        return {mu_id for mu_id, unit in units.items() if before.get(mu_id) != _snapshot(unit)}

    async def _refresh_member_damage(self, challenge: dict, units: dict) -> None:
        """Keep the highest weekly damage seen for everyone who was in the MU (muMember weeklyDamagesCount)."""
        mu_ids = challenge["mu_ids"]
        listings = await asyncio.gather(*(warera.mus.get_members(mu_id) for mu_id in mu_ids))
        for mu_id, records in zip(mu_ids, listings):
            if records is None:
                continue
            # without one good read the 0 defaults would look like real damage (members_damage needs this flag)
            units[mu_id]["members_read"] = True
            seen = units[mu_id].setdefault("members", {})
            for record in records:
                uid = str(record.get("user") or "")
                damage = record.get("weeklyDamagesCount")
                if uid and isinstance(damage, (int, float)):
                    seen[uid] = max(float(seen.get(uid) or 0), float(damage))

    async def _refresh_pills(self, challenge: dict, units: dict, current: dict, now: datetime) -> None:
        """Add each current member to the UTC day of their latest pill, when it was taken in the window.

        The pill buff lasts 8 h and its debuff 15.5 h (gameConfig), so an hourly read sees every pill.
        """
        wanted = [uid for members in current.values() for uid in members]
        users = await warera.users.get_many(wanted)
        if wanted and not users:
            return  # the batch failed (get_many answers {}); nothing read this hour
        settings = _pill_settings(await warera.game.get_config())
        start, cutoff, days = mc.start_of(challenge), mc.cutoff_of(challenge), mc.week_days(challenge)
        for mu_id, members in current.items():
            units[mu_id]["pills_read"] = True
            pills = units[mu_id].setdefault("pills", {})
            for uid in members:
                user = users.get(uid)
                pilled_at = pill_state(user, now, settings).get("pilled_at") if user else None
                if pilled_at is None or not start <= pilled_at < cutoff:
                    continue
                day = mc.utc_day(pilled_at)
                if day in days and uid not in pills.setdefault(day, []):
                    pills[day].append(uid)

    def _refresh_ranking(self, challenge: dict, units: dict, mus: dict) -> None:
        """The MUs' muWeeklyDamages value and rank, from the `rankings` of their loaded mu.getById objects (`mus`).

        ranking.getRanking lists only the top 100 of ~900 MUs since 2026-11-16, so it can't be used. An MU
        whose object didn't load keeps its stored values; one without a muWeeklyDamages entry has 0 damage and
        no rank.
        """
        for mu_id in challenge["mu_ids"]:
            mu = mus.get(mu_id)
            if not isinstance(mu, dict):
                continue
            entry = (mu.get("rankings") or {}).get("muWeeklyDamages") or {}
            units[mu_id]["weekly_damage"] = float(entry.get("value") or 0)
            units[mu_id]["weekly_rank"] = entry.get("rank")

    async def _refresh_battles(self, challenge: dict, units: dict, now: datetime, final: bool) -> dict | None:
        """Read the MU money ranking of the battles that ended in the window; returns {ended battle id: endedAt}.

        Hourly refreshes read at most BATTLES_PER_REFRESH new battles; the final run reads the rest and retries
        failed ones. Battles still unread are kept in state["battles_unread"] for the article warning.
        """
        state = challenge["state"]
        start, cutoff = mc.start_of(challenge), mc.cutoff_of(challenge)
        listed = await warera.battles.get_ended_since((start - BATTLE_MAX_AGE).isoformat())
        if listed is None:
            return None
        window = [b["_id"] for b in battles_in_window(listed, start, min(now, cutoff))]
        read = set(state.get("battles_read") or [])
        attempts = state.setdefault("battle_attempts", {})
        todo = [b for b in window if b not in read and (final or attempts.get(b, 0) < MAX_BATTLE_ATTEMPTS)]
        if not mc.has_mission(challenge, "bounty"):
            todo = []  # contracts only need the listing (which battles ended)
        elif not final:
            todo = todo[:BATTLES_PER_REFRESH]
        rankings = await asyncio.gather(*(warera.battles.get_ranking(b, "money", "mu", "merged") for b in todo))
        mu_ids = set(challenge["mu_ids"])
        for battle_id, items in zip(todo, rankings):
            if items is None:
                attempts[battle_id] = attempts.get(battle_id, 0) + 1
                continue
            for item in items:
                if item.get("mu") in mu_ids and (item.get("value") or 0) > 0:
                    units[item["mu"]].setdefault("battle_money", {})[battle_id] = float(item["value"])
            read.add(battle_id)
            attempts.pop(battle_id, None)
        for mu_id in mu_ids:
            units[mu_id].setdefault("battle_money", {})
        state["battles_read"] = sorted(read)
        state["battles_unread"] = [b for b in window if b not in read]
        return {b["_id"]: parse_iso(b.get("endedAt")) or now for b in listed if b.get("_id")}

    async def _refresh_contracts(
        self, challenge: dict, units: dict, now: datetime, ended_ids: dict | None, final: bool,
    ) -> None:
        """Record the MUs' won contracts and the contract money paid to their members per battle.

        Only status "won" is scanned: "expiredBattle" auctions ended with their battle and were never paid
        [observed 2026-11-04]. A battle's contract money is read once after the battle ended (it can't change
        after that, and the MU can't win another contract in it); the final run also reads the battles still
        running at the cut-off. Reading earlier could miss a contract won later in the same battle, whose pay
        would then count as bounty. A read that finds nothing paid is repeated until SETTLE_AFTER past the
        battle's end, in case the pay is credited a little after the battle ends.
        """
        state = challenge["state"]
        start, cutoff = mc.start_of(challenge), mc.cutoff_of(challenge)
        earliest = start - mc.CONTRACT_LOOKBACK
        scanned = parse_iso(state.get("contracts_scanned_at")) or earliest
        auctions = await warera.contracts.get_won_since(max(earliest, scanned - CONTRACT_SCAN_OVERLAP).isoformat())
        takers: dict[tuple[str, str], set[str]] = {}
        for unit in units.values():
            unit.setdefault("contracts", {})
        if auctions is not None:
            for auction in auctions:
                mu_id, created = auction.get("currentWinner"), parse_iso(auction.get("createdAt"))
                if mu_id in units and auction.get("battle") and created and earliest <= created < cutoff:
                    units[mu_id]["contracts"][auction["_id"]] = {
                        "battle": auction["battle"],
                        "minimumDamage": auction.get("minimumDamage"),
                        "payout": auction.get("currentPayout"),
                        "createdAt": auction.get("createdAt"),
                        "taker": auction.get("currentWinnerUser"),
                    }
            state["contracts_scanned_at"] = now.isoformat()

        settled = set(state.get("settled_battles") or [])
        pending = []
        for mu_id, unit in units.items():
            payouts: dict[str, float] = {}
            for contract in unit["contracts"].values():
                payouts[contract["battle"]] = payouts.get(contract["battle"], 0.0) + float(contract.get("payout") or 0)
                if contract.get("taker"):
                    takers.setdefault((mu_id, contract["battle"]), set()).add(contract["taker"])
            for battle_id, payout in payouts.items():
                ended = ended_ids is not None and battle_id in ended_ids
                if f"{mu_id}:{battle_id}" not in settled and (ended or final):
                    pending.append((mu_id, battle_id, payout, ended))
        people = {
            (mu_id, battle_id): sorted(set(units[mu_id].get("members") or {}) | takers.get((mu_id, battle_id), set()))
            for mu_id, battle_id, _payout, _ended in pending
        }
        summaries = await asyncio.gather(*(
            warera.battles.get_loot_summaries(battle_id, people[(mu_id, battle_id)]) for mu_id, battle_id, _, _ in pending
        ))
        for (mu_id, battle_id, _payout, ended), found in zip(pending, summaries):
            paid = sum(float((s or {}).get("totalMoneyFromContract") or 0) for s in found.values())
            units[mu_id].setdefault("contract_paid", {})[battle_id] = paid
            if ended and (paid > 0 or now - ended_ids[battle_id] >= SETTLE_AFTER):
                settled.add(f"{mu_id}:{battle_id}")
        state["settled_battles"] = sorted(settled)

    async def _refresh_donations(self, challenge: dict, units: dict) -> None:
        """Money donated to each MU in the window, from any donor (MU ledger, needs the API key)."""
        start, cutoff = mc.start_of(challenge), mc.cutoff_of(challenge)
        mu_ids = challenge["mu_ids"]
        ledgers = await asyncio.gather(*(
            warera.market.get_mu_transactions(mu_id, "donation", start.isoformat()) for mu_id in mu_ids
        ))
        for mu_id, transactions in zip(mu_ids, ledgers):
            if transactions is None:
                continue
            units[mu_id]["donations"] = sum(
                float(t.get("money") or 0) for t in transactions
                if t.get("transactionType") == "donation" and t.get("sellerMuId") == mu_id
                and (created := parse_iso(t.get("createdAt"))) is not None and start <= created < cutoff
            )


async def setup(bot: commands.Bot):
    """Load the MU challenge tracker."""
    await bot.add_cog(MuChallengeJob(bot))
