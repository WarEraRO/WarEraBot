import asyncio
import logging
import math
import time
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from config import config
from utils.api import (
    get_all_countries,
    get_battle,
    get_game_config,
    get_military_unit,
    get_round,
    get_shared_session,
    get_won_mercenary_auctions,
)
from utils.common import country_flag, get_mu_destination

logger = logging.getLogger(__name__)

MU_CONTRACT_MONITOR_INTERVAL_MINUTES = 5
# won contracts are scanned by createdAt; auctions last 5-25 minutes, so 3h comfortably covers a 5-minute loop
CONTRACT_LOOKBACK = timedelta(hours=3)
# posted contract IDs are forgotten after this long, once the contract's round/battle has finished
POSTED_RETENTION_SECONDS = 18 * 60 * 60
GAME_CONFIG_TTL_SECONDS = 60 * 60
COUNTRY_CACHE_TTL_SECONDS = 60 * 60

# a tick happens every 2 minutes and awards its ground points to one side (not in gameConfig)
TICK_INTERVAL = timedelta(minutes=2)
# fallbacks when gameConfig.battle is unavailable: 300 ground points win a round, and a tick is worth
# 1/2/3/4/5/6 points once the round's total ground points reach 1/100/200/300/400/500
DEFAULT_POINTS_TO_WIN_ROUND = 300
DEFAULT_TICK_POINTS = {1: 1, 100: 2, 200: 3, 300: 4, 400: 5, 500: 6}
DEFAULT_ROUNDS_TO_WIN = 2

SIDE_ICONS = {"attacker": "⚔️", "defender": "🛡️"}


def format_amount(value) -> str:
    """Thousands separators, at most 4 decimals and no trailing zeros (0.08, 400, 5,008,000)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "unknown"
    return f"{number:,.4f}".rstrip("0").rstrip(".")


def format_duration(delta: timedelta) -> str:
    minutes = max(1, math.ceil(delta.total_seconds() / 60))
    hours, minutes = divmod(minutes, 60)
    return f"~{hours}h {minutes}m" if hours else f"~{minutes}m"


def tick_value(total_points: int, tick_points: dict[int, int]) -> int:
    """Ground points the next tick is worth, given the round's total ground points (both sides)."""
    thresholds = sorted(tick_points)
    value = tick_points[thresholds[0]]
    for threshold in thresholds:
        if total_points >= threshold:
            value = tick_points[threshold]
    return value


def ticks_to_win_round(leader_points: int, total_points: int, tick_points: dict[int, int], points_to_win: int) -> int:
    """Ticks until the leading side reaches `points_to_win`, assuming it wins every remaining tick."""
    ticks = 0
    while leader_points < points_to_win:
        points = tick_value(total_points, tick_points)
        leader_points += points
        total_points += points
        ticks += 1
    return ticks


def parse_iso(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


class MilitaryUnitContractMonitorJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # contract id -> {"posted_at", "battle", "round"}; contracts seen at startup are stored without posting
        self._posted: dict[str, dict] = {}
        self._seeded = False
        self._game_config: tuple[dict, float] | None = None
        self._country_names: tuple[dict[str, str], float] | None = None
        self.mu_contract_monitor.start()

    def cog_unload(self):
        self.mu_contract_monitor.cancel()

    @tasks.loop(minutes=MU_CONTRACT_MONITOR_INTERVAL_MINUTES)
    async def mu_contract_monitor(self):
        guild = self.bot.get_guild(config["guild"])
        if guild is None:
            return

        # only MUs with a channelId or a contracts thread get contract embeds, posted in the thread when set
        units = {
            str(unit["id"]): unit
            for unit in config.get("military_units", [])
            if unit.get("id") and (unit.get("channelId") or (unit.get("threadIds") or {}).get("contractsId"))
        }
        if not units:
            return

        session = await get_shared_session()
        created_after = (datetime.now(timezone.utc) - CONTRACT_LOOKBACK).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        contracts = await get_won_mercenary_auctions(session, created_after)
        if contracts is None:
            return

        ours = [
            contract for contract in contracts
            if str(contract.get("currentWinner") or "") in units and contract.get("_id")
        ]

        if not self._seeded:
            # after a restart, contracts already won are marked as seen without posting
            for contract in ours:
                self._remember(contract)
            self._seeded = True
            logger.info("MU contract monitor seeded with %d already won contracts", len(ours))
            return

        # oldest first so the channel reads chronologically
        for contract in reversed(ours):
            contract_id = str(contract["_id"])
            if contract_id in self._posted:
                continue
            unit = units[str(contract["currentWinner"])]
            channel = await get_mu_destination(guild, unit, "contractsId")
            if channel is None:
                logger.warning("Contracts channel/thread for MU %s not found", unit.get("friendlyName"))
                continue
            try:
                embed = await self._build_embed(contract, unit, session)
                await channel.send(embed=embed)
            except discord.DiscordException:
                logger.exception("Failed to post contract %s for MU %s", contract_id, unit.get("friendlyName"))
                continue
            self._remember(contract)

        await self._prune_posted(session)

    @mu_contract_monitor.before_loop
    async def before_mu_contract_monitor(self):
        await self.bot.wait_until_ready()

    def _remember(self, contract: dict):
        self._posted[str(contract["_id"])] = {
            "posted_at": time.monotonic(),
            "battle": contract.get("battle"),
            "round": contract.get("round"),
        }

    async def _prune_posted(self, session):
        now = time.monotonic()
        for contract_id, info in list(self._posted.items()):
            if now - info["posted_at"] < POSTED_RETENTION_SECONDS:
                continue
            # round contracts finish with their round, battle contracts with their battle
            if info["round"]:
                target = await get_round(info["round"], session)
            else:
                target = await get_battle(info["battle"], session)
            if target is not None and not target.get("isActive"):
                del self._posted[contract_id]

    async def _build_embed(self, contract: dict, unit: dict, session) -> discord.Embed:
        battle_id = str(contract.get("battle") or "")
        battle_link = f"https://app.warera.io/battle/{battle_id}"
        battle = await get_battle(battle_id, session) if battle_id else None
        battle = battle or {}

        # a round contract carries its round; a battle contract follows the battle's current round
        round_id = contract.get("round") or battle.get("currentRound")
        round_obj, game_config, country_names, military_unit = await asyncio.gather(
            get_round(str(round_id), session) if round_id else asyncio.sleep(0),
            self._get_game_config(session),
            self._get_country_names(session),
            get_military_unit(str(unit["id"]), session),
        )
        military_unit = military_unit if isinstance(military_unit, dict) else {}

        attacker = battle.get("attacker") or {}
        defender = battle.get("defender") or {}
        issuer_name = country_names.get(str(contract.get("country") or contract.get("forCountry") or ""), "unknown")
        attacker_name = country_names.get(str(attacker.get("country") or ""), "unknown")
        defender_name = country_names.get(str(defender.get("country") or ""), "unknown")
        side_icon = SIDE_ICONS.get(contract.get("forCountrySide"), "")

        embed = discord.Embed(
            title=f"{side_icon} {issuer_name} · Mercenary Auction".strip(),
            url=battle_link,
            description=(
                f"{SIDE_ICONS['attacker']} {self._country_label(attacker_name)} vs. "
                f"{SIDE_ICONS['defender']} {self._country_label(defender_name)}"
            ),
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Min. Damage", value=format_amount(contract.get("minimumDamage")), inline=True)
        embed.add_field(name="Per 1k Damage", value=format_amount(contract.get("currentPerK")), inline=True)
        embed.add_field(name="Total Payout", value=format_amount(contract.get("currentPayout")), inline=True)
        embed.add_field(name="Battle ETA", value=self._eta_text(contract, battle, round_obj, game_config), inline=True)
        embed.add_field(name="Score", value=self._score_text(battle, game_config), inline=True)
        # in-game name and avatar make the winner clear; the config's friendlyName is often an abbreviation
        mu_name = military_unit.get("name") or unit.get("friendlyName") or "unknown MU"
        embed.set_footer(text=f"Contract won by {mu_name}")
        if military_unit.get("avatarUrl"):
            embed.set_thumbnail(url=military_unit["avatarUrl"])
        return embed

    def _country_label(self, name: str) -> str:
        flag = country_flag(name)
        return f"{flag} **{name}**" if flag else f"**{name}**"

    def _score_text(self, battle: dict, game_config: dict) -> str:
        if not battle:
            return "unknown"
        attacker_wins = (battle.get("attacker") or {}).get("wonRoundsCount") or 0
        defender_wins = (battle.get("defender") or {}).get("wonRoundsCount") or 0
        rounds_to_win = battle.get("roundsToWin") or game_config["rounds_to_win"]
        round_number = len(battle.get("rounds") or []) or 1
        return (
            f"Round {round_number} · {SIDE_ICONS['attacker']} {attacker_wins} – {defender_wins} "
            f"{SIDE_ICONS['defender']} (first to {rounds_to_win})"
        )

    def _eta_text(self, contract: dict, battle: dict, round_obj, game_config: dict) -> str:
        is_round_contract = bool(contract.get("round"))
        if not battle or not isinstance(round_obj, dict):
            return "unknown"
        if not battle.get("isActive"):
            return "Battle ended"
        if is_round_contract and not round_obj.get("isActive"):
            return "Round ended"

        eta = self._round_eta(round_obj, game_config)
        if is_round_contract:
            return f"{format_duration(eta)} (round {contract.get('roundNumber') or round_obj.get('number')})"

        # battle contract: the side leading this round wins it, then keeps winning full rounds until roundsToWin
        attacker_points = (round_obj.get("attacker") or {}).get("points") or 0
        defender_points = (round_obj.get("defender") or {}).get("points") or 0
        attacker_wins = (battle.get("attacker") or {}).get("wonRoundsCount") or 0
        defender_wins = (battle.get("defender") or {}).get("wonRoundsCount") or 0
        if attacker_points != defender_points:
            leader_wins = attacker_wins if attacker_points > defender_points else defender_wins
        else:
            leader_wins = max(attacker_wins, defender_wins)
        rounds_to_win = battle.get("roundsToWin") or game_config["rounds_to_win"]
        extra_rounds = max(0, rounds_to_win - (leader_wins + 1))
        full_round_ticks = ticks_to_win_round(0, 0, game_config["tick_points"], game_config["points_to_win"])
        return format_duration(eta + extra_rounds * full_round_ticks * TICK_INTERVAL)

    def _round_eta(self, round_obj: dict, game_config: dict) -> timedelta:
        """Time until the leading side wins the round, assuming it wins every remaining tick."""
        attacker_points = (round_obj.get("attacker") or {}).get("points") or 0
        defender_points = (round_obj.get("defender") or {}).get("points") or 0
        ticks = ticks_to_win_round(
            max(attacker_points, defender_points),
            attacker_points + defender_points,
            game_config["tick_points"],
            game_config["points_to_win"],
        )
        if ticks == 0:
            return timedelta(0)
        next_tick_at = parse_iso((round_obj.get("live") or {}).get("nextTickAt"))
        now = datetime.now(timezone.utc)
        until_next_tick = max(next_tick_at - now, timedelta(0)) if next_tick_at else TICK_INTERVAL
        return until_next_tick + (ticks - 1) * TICK_INTERVAL

    async def _get_game_config(self, session) -> dict:
        now = time.monotonic()
        if self._game_config and now - self._game_config[1] < GAME_CONFIG_TTL_SECONDS:
            return self._game_config[0]
        raw = await get_game_config(session)
        battle_config = (raw or {}).get("battle") or {}
        try:
            tick_points = {int(k): int(v) for k, v in (battle_config.get("tickPoints") or {}).items()}
        except (TypeError, ValueError):
            tick_points = {}
        parsed = {
            "tick_points": tick_points or DEFAULT_TICK_POINTS,
            "points_to_win": int(battle_config.get("pointsToWinRound") or DEFAULT_POINTS_TO_WIN_ROUND),
            "rounds_to_win": int(battle_config.get("roundsToWin") or DEFAULT_ROUNDS_TO_WIN),
        }
        # a failed fetch falls back to the defaults now and is retried next time
        if raw is not None:
            self._game_config = (parsed, now)
        return parsed

    async def _get_country_names(self, session) -> dict[str, str]:
        now = time.monotonic()
        if self._country_names and now - self._country_names[1] < COUNTRY_CACHE_TTL_SECONDS:
            return self._country_names[0]
        countries = await get_all_countries(session)
        if not countries:
            return self._country_names[0] if self._country_names else {}
        names = {
            str(country.get("_id") or country.get("id")): str(country.get("name"))
            for country in countries
            if (country.get("_id") or country.get("id")) and country.get("name")
        }
        self._country_names = (names, now)
        return names


async def setup(bot: commands.Bot):
    await bot.add_cog(MilitaryUnitContractMonitorJob(bot))
