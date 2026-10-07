import asyncio
import logging
from collections import Counter
from datetime import datetime, time as dt_time, timedelta, timezone

import discord
from discord.ext import commands, tasks

from config import config
from utils.api import (
    get_all_countries,
    get_battle_ranking,
    get_ended_battles,
    get_military_unit,
    get_mu_members,
    get_mu_public_orders,
    get_mu_transactions,
    get_shared_session,
    get_user_info,
    get_won_mercenary_auctions,
)
from utils.common import country_with_flag, get_mu_destination

logger = logging.getLogger(__name__)

MU_BATTLE_TRACKER_INTERVAL_MINUTES = 60
# the game week (and the MU weekly damage ranking) resets on Monday 00:00 UTC, so the report runs just before
REPORT_TIME = dt_time(hour=23, minute=30, tzinfo=timezone.utc)
SUNDAY = 6
# battles last at most ~1 day and are listed newest-created first, so a battle that ended this week
# was created at most this long before the week started
BATTLE_LOOKBACK = timedelta(days=2)
RANKING_CONCURRENCY = 2
TOP_FIGHTERS = 3
IDLE_MEMBERS_SHOWN = 10
NEW_MEMBERS_SHOWN = 10
# MUs with less weekly damage than this get no report
MIN_REPORT_DAMAGE = 10_000_000
# members below this share of the average member damage count as low contributors
LOW_CONTRIBUTOR_PERCENT = 25
# insight thresholds
DAMAGE_CONCENTRATION_PERCENT = 60
UNPAID_DAMAGE_PERCENT = 30
EMBED_FIELD_VALUE_LIMIT = 1024
# Discord rejects embeds over 6000 characters in total
EMBED_TOTAL_LIMIT = 6000
BATTLE_LINK = "https://app.warera.io/battle/{}"


def _iso(value: datetime) -> str:
    """Same format as API timestamps, so ISO strings compare chronologically."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _week_start(now: datetime) -> datetime:
    now = now.astimezone(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def _fmt_int(value) -> str:
    return f"{round(value or 0):,}"


def _fmt_money(value) -> str:
    return f"{value or 0:,.2f}"


def _fmt_short(value) -> str:
    """Compact damage figures: 950, 12.3K, 4.5M."""
    value = value or 0
    for divisor, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(value) >= divisor:
            return f"{value / divisor:.1f}{suffix}"
    return f"{round(value)}"


def _shorten(name: str, limit: int = 14) -> str:
    """Keeps names short enough for one line of a 3-column field row."""
    return name if len(name) <= limit else name[: limit - 1] + "…"


def _fmt_perk(value) -> str:
    return f"{value or 0:.3f}"


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _truncate(text: str) -> str:
    if len(text) <= EMBED_FIELD_VALUE_LIMIT:
        return text
    return text[: EMBED_FIELD_VALUE_LIMIT - 1] + "…"


class MilitaryUnitWeeklyReportJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # battle id -> {"ended_at", "won_by", "mus": {mu id: {"side", "damage", "money"}}} for battles that ended this week
        self._battles: dict[str, dict] = {}
        self._battle_lock = asyncio.Lock()
        self.mu_battle_tracker.start()
        self.mu_weekly_report.start()

    def cog_unload(self):
        self.mu_battle_tracker.cancel()
        self.mu_weekly_report.cancel()

    def _units(self) -> dict[str, dict]:
        return {str(unit["id"]): unit for unit in config.get("military_units", []) if unit.get("id")}

    # ------------------------------------------------------------------
    # Battles: MU damage and money per battle, collected as battles end
    # ------------------------------------------------------------------

    @tasks.loop(minutes=MU_BATTLE_TRACKER_INTERVAL_MINUTES)
    async def mu_battle_tracker(self):
        session = await get_shared_session()
        await self._collect_battles(session, _week_start(datetime.now(timezone.utc)))

    @mu_battle_tracker.before_loop
    async def before_mu_battle_tracker(self):
        await self.bot.wait_until_ready()

    async def _collect_battles(self, session, week_start: datetime) -> bool:
        """Fetch the MU rankings of battles that ended this week and are not cached yet.

        After a restart the cache is empty and the whole week is backfilled. Returns False when
        some battles could not be fetched (they are retried on the next run).
        """
        async with self._battle_lock:
            units = self._units()
            battles = await get_ended_battles(session, _iso(week_start - BATTLE_LOOKBACK))
            if battles is None:
                return False
            week_start_iso = _iso(week_start)
            self._battles = {
                battle_id: result
                for battle_id, result in self._battles.items()
                if result["ended_at"] >= week_start_iso
            }
            pending = [
                battle for battle in battles
                if battle.get("_id")
                and str(battle.get("endedAt") or "") >= week_start_iso
                and str(battle["_id"]) not in self._battles
            ]
            semaphore = asyncio.Semaphore(RANKING_CONCURRENCY)
            results = await asyncio.gather(
                *(self._battle_result(battle, units, session, semaphore) for battle in pending)
            )
            complete = True
            for battle, result in zip(pending, results):
                if result is None:
                    complete = False
                    continue
                self._battles[str(battle["_id"])] = result
            if pending:
                logger.info("MU weekly report: collected %d ended battles (%d failed)", len(pending), results.count(None))
            return complete

    async def _battle_result(self, battle: dict, units: dict[str, dict], session, semaphore) -> dict | None:
        battle_id = str(battle["_id"])
        async with semaphore:
            # per-side rankings tell which side each MU fought for, so wins and losses can be counted
            attacker, defender = await asyncio.gather(
                get_battle_ranking(battle_id, "damage", "mu", "attacker", session),
                get_battle_ranking(battle_id, "damage", "mu", "defender", session),
            )
            if attacker is None or defender is None:
                return None
            side_damage: dict[str, dict[str, float]] = {}
            for side, items in (("attacker", attacker), ("defender", defender)):
                for item in items:
                    mu_id = str(item.get("mu") or "")
                    if mu_id in units and item.get("value"):
                        side_damage.setdefault(mu_id, {})[side] = item["value"]
            money_by_mu: dict[str, float] = {}
            if side_damage:
                # money = bounty plus mercenary contract payouts earned in this battle
                money = await get_battle_ranking(battle_id, "money", "mu", "merged", session)
                if money is None:
                    return None
                money_by_mu = {str(item.get("mu") or ""): item.get("value") or 0 for item in money}
        return {
            "ended_at": str(battle.get("endedAt")),
            "won_by": battle.get("wonBy"),
            # tournament battles have no side country
            "countries": {
                side: str((battle.get(side) or {}).get("country") or "") for side in ("attacker", "defender")
            },
            "mus": {
                mu_id: {
                    # an MU that fought on both sides is credited to the side it did most damage for
                    "side": max(sides, key=sides.get),
                    "damage": sum(sides.values()),
                    "money": money_by_mu.get(mu_id, 0),
                }
                for mu_id, sides in side_damage.items()
            },
        }

    # ------------------------------------------------------------------
    # Weekly report
    # ------------------------------------------------------------------

    @tasks.loop(time=REPORT_TIME)
    async def mu_weekly_report(self):
        now = datetime.now(timezone.utc)
        # the loop fires daily but only Sunday's run reports; /run_job calls it from another task and always reports
        if now.weekday() != SUNDAY and asyncio.current_task() is self.mu_weekly_report.get_task():
            return

        guild = self.bot.get_guild(config["guild"])
        if guild is None:
            return
        # only MUs with a channelId or a weekly report thread get a report, posted in the thread when set
        units = {
            mu_id: unit for mu_id, unit in self._units().items()
            if unit.get("channelId") or (unit.get("threadIds") or {}).get("weeklyReportId")
        }
        if not units:
            return

        session = await get_shared_session()
        week_start = _week_start(now)
        battles_complete = await self._collect_battles(session, week_start)
        # contracts for battles that ended this week may have been won before it started
        contracts = await get_won_mercenary_auctions(session, _iso(week_start - BATTLE_LOOKBACK))
        country_names = {
            str(country.get("_id")): str(country.get("name"))
            for country in await get_all_countries(session) or []
            if country.get("_id") and country.get("name")
        }

        names: dict[str, str] = {}
        for mu_id, unit in units.items():
            try:
                embed = await self._build_embed(
                    mu_id, unit, session, week_start, now, contracts, battles_complete, names, country_names
                )
                if embed is None:
                    continue
                channel = await get_mu_destination(guild, unit, "weeklyReportId")
                if channel is None:
                    logger.warning("Weekly report channel/thread for MU %s not found", unit.get("friendlyName"))
                    continue
                await channel.send(embed=embed)
            except discord.DiscordException:
                logger.exception("Failed to post weekly report for MU %s", unit.get("friendlyName"))

    @mu_weekly_report.before_loop
    async def before_mu_weekly_report(self):
        await self.bot.wait_until_ready()

    async def _build_embed(
        self,
        mu_id: str,
        unit: dict,
        session,
        week_start: datetime,
        now: datetime,
        contracts: list[dict] | None,
        battles_complete: bool,
        names: dict[str, str],
        country_names: dict[str, str],
    ) -> discord.Embed | None:
        """The MU's weekly report, or None when it has no members or dealt less than MIN_REPORT_DAMAGE."""
        week_start_iso = _iso(week_start)
        military_unit, members = await asyncio.gather(
            get_military_unit(mu_id, session),
            get_mu_members(mu_id, session),
        )
        if military_unit is None and members is None:
            logger.warning("Skipping weekly report for MU %s: MU could not be fetched", unit.get("friendlyName"))
            return None
        military_unit = military_unit if isinstance(military_unit, dict) else {}
        mu_name = military_unit.get("name") or unit.get("friendlyName") or mu_id

        # battles that ended this week
        fought = {
            battle_id: battle["mus"][mu_id] | {"won_by": battle["won_by"], "countries": battle.get("countries") or {}}
            for battle_id, battle in self._battles.items()
            if mu_id in battle["mus"]
        }
        won = sum(1 for result in fought.values() if result["won_by"] == result["side"])
        battle_damage = sum(result["damage"] for result in fought.values())
        battle_money = sum(result["money"] for result in fought.values())

        weekly = (military_unit.get("rankings") or {}).get("muWeeklyDamages") or {}
        total_damage = weekly.get("value") if weekly.get("value") is not None else battle_damage
        member_count = len(members) if members is not None else len(military_unit.get("members") or [])
        if member_count == 0 or total_damage < MIN_REPORT_DAMAGE:
            logger.info(
                "Skipping weekly report for MU %s: %d members, %s damage", mu_name, member_count, _fmt_int(total_damage)
            )
            return None

        transactions, open_orders = await asyncio.gather(
            get_mu_transactions(mu_id, ["donation", "trading"], week_start_iso, session),
            get_mu_public_orders(mu_id, session),
        )

        # contracts: won this week, plus any won earlier for battles that ended this week
        contracts_available = contracts is not None
        contracts = contracts or []
        won_contracts = [
            contract for contract in contracts
            if str(contract.get("currentWinner") or "") == mu_id and str(contract.get("createdAt") or "") >= week_start_iso
        ]
        lost_auctions = [
            contract for contract in contracts
            if str(contract.get("createdAt") or "") >= week_start_iso
            and str(contract.get("currentWinner") or "") != mu_id
            and any(str(bid.get("mu") or "") == mu_id for bid in contract.get("bids") or [])
        ]
        contract_value = sum(contract.get("currentPayout") or 0 for contract in won_contracts)
        payout_by_battle = Counter()
        for contract in contracts:
            if str(contract.get("currentWinner") or "") == mu_id:
                payout_by_battle[str(contract.get("battle") or "")] += contract.get("currentPayout") or 0
        # battle money includes contract payouts; what is left is free bounty
        bounty = sum(max(0.0, result["money"] - payout_by_battle[battle_id]) for battle_id, result in fought.items())
        unpaid = [result for result in fought.values() if not result["money"]]
        unpaid_damage = sum(result["damage"] for result in unpaid)
        unpaid_percent = unpaid_damage / battle_damage * 100 if battle_damage else 0.0

        # auction pricing: auctions go down in price per 1k damage and the lowest bid wins
        won_perk = _average([contract.get("currentPerK") or 0 for contract in won_contracts])
        won_start_perk = _average([contract.get("initialPerK") or 0 for contract in won_contracts])
        lost_winner_perk = _average([contract.get("currentPerK") or 0 for contract in lost_auctions])
        lost_our_perk = _average([
            min(bid.get("perK") or 0 for bid in contract.get("bids") or [] if str(bid.get("mu") or "") == mu_id)
            for contract in lost_auctions
        ])

        # members
        members = members or []
        member_damage = sorted(members, key=lambda member: member.get("weeklyDamagesCount") or 0, reverse=True)
        damages = [member.get("weeklyDamagesCount") or 0 for member in member_damage]
        average_damage = _average(damages)
        median_damage = (damages[(len(damages) - 1) // 2] + damages[len(damages) // 2]) / 2 if damages else 0
        active_members = [member for member in members if member.get("weeklyDamagesCount")]
        idle_members = [member for member in members if not member.get("weeklyDamagesCount")]
        low_contributors = [
            member for member in active_members
            if member["weeklyDamagesCount"] < average_damage * LOW_CONTRIBUTOR_PERCENT / 100
        ]
        help_count = sum(member.get("weeklyHelpCount") or 0 for member in members)
        no_help = [member for member in members if not member.get("weeklyHelpCount")]
        # createdAt of the membership record, i.e. when the member joined
        new_members = [member for member in members if str(member.get("createdAt") or "") >= week_start_iso]
        top_fighters = member_damage[:TOP_FIGHTERS]
        await self._resolve_names(
            [
                str(member.get("user"))
                for member in top_fighters + idle_members[:IDLE_MEMBERS_SHOWN] + new_members[:NEW_MEMBERS_SHOWN]
            ],
            session,
            names,
        )

        # Discord does not allow a wider embed, so the avatar goes in the author line instead of a thumbnail
        # (which takes a column from every field row) and lines in the 3-column rows stay ~22 characters
        embed = discord.Embed(
            description=f"Game week **{week_start:%b %d} – {now:%b %d}** (resets Monday 00:00 UTC)",
            color=discord.Color.gold(),
            timestamp=now,
        )
        embed.set_author(name=f"📊 {mu_name} · Weekly Report", icon_url=military_unit.get("avatarUrl") or None)

        # row 1: damage, battles, earnings
        damage_text = f"**{_fmt_int(total_damage)}**"
        if weekly.get("rank"):
            damage_text += f"\nRank #{weekly['rank']}" + (f" · {weekly['tier']}" if weekly.get("tier") else "")
        embed.add_field(name="⚔️ Damage", value=damage_text, inline=True)

        battles_text = f"**{len(fought)}** ended\n{won} won · {len(fought) - won} lost"
        if unpaid:
            share = "<1" if unpaid_percent < 1 else f"{unpaid_percent:.0f}"
            battles_text += f"\n{len(unpaid)} unpaid · {share}% dmg"
        embed.add_field(name="🗺️ Battles", value=battles_text, inline=True)

        earnings_text = (
            f"**{_fmt_int(battle_money)}**\n"
            f"Bounty ~{_fmt_int(bounty)}\n"
            f"Contracts ~{_fmt_int(battle_money - bounty)}"
        )
        if battle_damage:
            earnings_text += f"\n{_fmt_money(battle_money / battle_damage * 1000)} per 1k dmg"
        embed.add_field(name="💰 Earned", value=earnings_text, inline=True)

        # row 2: contracts, reputation, treasury
        if contracts_available:
            contracts_text = f"**{len(won_contracts)}** won · {_fmt_int(contract_value)}"
            if won_contracts:
                contracts_text += f"\n{_fmt_perk(won_perk)} (start {_fmt_perk(won_start_perk)})"
            if lost_auctions:
                contracts_text += (
                    f"\n{len(lost_auctions)} lost · ours {_fmt_perk(lost_our_perk)}"
                    f"\nWinners {_fmt_perk(lost_winner_perk)}"
                )
        else:
            contracts_text = "unavailable"
        embed.add_field(name="📜 Contracts (per 1k)", value=contracts_text, inline=True)

        reputation = (military_unit.get("rankings") or {}).get("muReputation") or {}
        reputation_value = military_unit.get("mercenaryReputation", reputation.get("value"))
        if reputation_value is not None:
            reputation_text = f"**{reputation_value:.2f}**"
            if reputation.get("rank"):
                reputation_text += f"\nRank #{reputation['rank']}" + (f" · {reputation['tier']}" if reputation.get("tier") else "")
            embed.add_field(name="🎖️ Reputation", value=reputation_text, inline=True)

        embed.add_field(name="🏦 Treasury", value=self._treasury_text(mu_id, military_unit, transactions, open_orders), inline=True)

        # row 3: activity, damage spread, top fighters
        if members:
            activity_text = f"**{len(active_members)}/{len(members)}** fought"
            if new_members:
                activity_text += f" · {len(new_members)} new"
            activity_text += (
                f"\n{_fmt_int(help_count)} help · {help_count / len(members):.0f}/member"
                f"\n{len(no_help)} gave no help"
            )
            embed.add_field(name="👥 Activity", value=activity_text, inline=True)
            spread_text = (
                f"Median {_fmt_short(median_damage)}\n"
                f"Avg {_fmt_short(average_damage)}\n"
                f"{len(low_contributors)} below {LOW_CONTRIBUTOR_PERCENT}% of avg"
            )
            embed.add_field(name="📈 Damage spread", value=spread_text, inline=True)
            fighters_text = "\n".join(
                f"{index}. {_shorten(names.get(str(member.get('user')), 'unknown'))} {_fmt_short(member.get('weeklyDamagesCount'))}"
                for index, member in enumerate(top_fighters, start=1)
                if member.get("weeklyDamagesCount")
            )
            embed.add_field(name="🏅 Top fighters", value=fighters_text or "nobody fought", inline=True)

        if fought:
            battle_id, result = max(fought.items(), key=lambda item: item[1]["damage"])
            embed.add_field(name="🔥 Biggest battle", value=self._battle_text(battle_id, result, country_names), inline=False)

        if new_members:
            embed.add_field(
                name=f"🆕 New members ({len(new_members)})",
                value=_truncate(self._name_list(new_members, NEW_MEMBERS_SHOWN, names)),
                inline=False,
            )

        if idle_members:
            embed.add_field(
                name=f"💤 No damage this week ({len(idle_members)})",
                value=_truncate(self._name_list(idle_members, IDLE_MEMBERS_SHOWN, names)),
                inline=False,
            )

        insights = self._insights(
            members, top_fighters, idle_members, lost_auctions, won_contracts,
            fought, won, unpaid_percent, lost_winner_perk,
        )
        if insights:
            embed.add_field(name="💡 Focus for next week", value=_truncate("\n".join(f"• {tip}" for tip in insights)), inline=False)

        footer = "Battles count once they end · bounty is estimated as battle money minus contract payouts"
        if not battles_complete:
            footer = "⚠️ Some battles could not be fetched, battle numbers may be low · " + footer
        embed.set_footer(text=footer)

        # every field is capped at 1024 characters, so only the name lists can push the embed over the limit
        while len(embed) > EMBED_TOTAL_LIMIT and len(embed.fields) > 1:
            logger.warning("Weekly report for MU %s is %d characters, dropping a field", mu_name, len(embed))
            embed.remove_field(len(embed.fields) - 1)
        return embed

    def _treasury_text(self, mu_id: str, military_unit: dict, transactions: list[dict] | None, open_orders: dict | None) -> str:
        lines = []
        wealth = (military_unit.get("rankings") or {}).get("muWealth") or {}
        if wealth.get("value") is not None:
            lines.append(f"Wealth **{_fmt_int(wealth['value'])}**" + (f" (#{wealth['rank']})" if wealth.get("rank") else ""))
        if transactions is None:
            lines.append("Transactions unavailable")
        else:
            donations = [item for item in transactions if item.get("transactionType") == "donation"]
            bought = [item for item in transactions if item.get("transactionType") == "trading" and str(item.get("buyerMuId") or "") == mu_id]
            sold = [item for item in transactions if item.get("transactionType") == "trading" and str(item.get("sellerMuId") or "") == mu_id]
            donors = {str(item.get("buyerId")) for item in donations if item.get("buyerId")}
            lines.append(f"+{_fmt_int(sum(item.get('money') or 0 for item in donations))} from {len(donors)} donors")
            if bought:
                spent_by_item = Counter()
                for item in bought:
                    spent_by_item[str(item.get("itemCode") or "items")] += item.get("money") or 0
                lines.append(f"−{_fmt_int(sum(spent_by_item.values()))} bought ({spent_by_item.most_common(1)[0][0]})")
            if sold:
                lines.append(f"+{_fmt_int(sum(item.get('money') or 0 for item in sold))} sold")
        if open_orders and open_orders.get("allOrders"):
            lines.append(
                f"{len(open_orders['allOrders'])} orders · "
                f"{_fmt_int(open_orders.get('totalBuyMoneyInvested'))} invested"
            )
        return "\n".join(lines) or "unavailable"

    def _battle_text(self, battle_id: str, result: dict, country_names: dict[str, str]) -> str:
        countries = result.get("countries") or {}
        if countries.get("attacker") and countries.get("defender"):
            title = (
                f"{country_with_flag(country_names.get(countries['attacker']), left=True)} vs "
                f"{country_with_flag(country_names.get(countries['defender']), left=False)}"
            )
        else:
            title = "Tournament battle"
        outcome = "won" if result["won_by"] == result["side"] else "lost"
        return (
            f"[{title}]({BATTLE_LINK.format(battle_id)}) · {_fmt_short(result['damage'])} damage · "
            f"{_fmt_money(result['money'])} earned · {outcome}"
        )

    def _name_list(self, members: list[dict], limit: int, names: dict[str, str]) -> str:
        shown = ", ".join(names.get(str(member.get("user")), "unknown") for member in members[:limit])
        if len(members) > limit:
            shown += f" and {len(members) - limit} more"
        return shown

    def _insights(
        self,
        members: list[dict],
        top_fighters: list[dict],
        idle_members: list[dict],
        lost_auctions: list[dict],
        won_contracts: list[dict],
        fought: dict[str, dict],
        won: int,
        unpaid_percent: float,
        lost_winner_perk: float,
    ) -> list[str]:
        tips = []
        if idle_members:
            tips.append(f"{len(idle_members)} member(s) dealt no damage; check in with them or free up their slots.")
        if unpaid_percent >= UNPAID_DAMAGE_PERCENT:
            tips.append(f"{unpaid_percent:.0f}% of damage earned nothing; prefer battles with a bounty or a contract.")
        total_member_damage = sum(member.get("weeklyDamagesCount") or 0 for member in members)
        top_damage = sum(member.get("weeklyDamagesCount") or 0 for member in top_fighters)
        if total_member_damage and len(members) > len(top_fighters):
            share = top_damage / total_member_damage * 100
            if share >= DAMAGE_CONCENTRATION_PERCENT:
                tips.append(f"Top {len(top_fighters)} fighters did {share:.0f}% of the damage; the rest of the MU can add a lot more.")
        if lost_auctions and len(lost_auctions) >= len(won_contracts):
            tips.append(
                f"Lost {len(lost_auctions)} contract auctions vs {len(won_contracts)} won; "
                f"winners went down to {_fmt_perk(lost_winner_perk)}/1k."
            )
        if fought and won * 2 < len(fought):
            tips.append(f"Only {won} of {len(fought)} battles were won; focus damage on fewer, winnable battles.")
        return tips

    async def _resolve_names(self, user_ids: list[str], session, names: dict[str, str]):
        missing = [user_id for user_id in dict.fromkeys(user_ids) if user_id and user_id not in names]
        users = await asyncio.gather(*(get_user_info(user_id, session) for user_id in missing))
        for user_id, user in zip(missing, users):
            names[user_id] = str((user or {}).get("username") or "unknown")


async def setup(bot: commands.Bot):
    await bot.add_cog(MilitaryUnitWeeklyReportJob(bot))
