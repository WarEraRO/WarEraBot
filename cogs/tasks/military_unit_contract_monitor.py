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
    get_users_info,
    get_won_mercenary_auctions,
)
from utils.common import country_flag, get_mu_destination
from utils.computational import is_economy_build
from utils.db import get_job_subscribers
from utils.i18n import Translator, get_translator

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

# job name in the job_subscriptions table; the target is the MU id (see cogs/commands/subscriptions.py)
SUBSCRIPTION_JOB = "mu_contracts"
# a subscriber is pinged unless they are on an economy build or cannot fight: below one hit of health (~10)
# with no hunger left to eat food (1 per item), or in a debuff
MIN_HEALTH_TO_FIGHT = 10
MIN_HUNGER_TO_EAT = 1
MESSAGE_CONTENT_LIMIT = 2000


def format_amount(value, unknown: str = "unknown") -> str:
    """Thousands separators, at most 4 decimals and no trailing zeros (0.08, 400, 5,008,000)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return unknown
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


def contract_units() -> dict[str, dict]:
    """MU id -> config entry for the MUs that get contract embeds: those with a channelId or a contracts
    thread (the embed goes to the thread when set)."""
    return {
        str(unit["id"]): unit
        for unit in config.get("military_units", [])
        if unit.get("id") and (unit.get("channelId") or (unit.get("threadIds") or {}).get("contractsId"))
    }


def _bar_value(skill) -> float:
    try:
        return float((skill or {}).get("currentBarValue") or 0)
    except (TypeError, ValueError):
        return 0.0


def can_fight(user: dict, now: datetime) -> bool:
    """False when the player has no stats (health < 10 and hunger < 1) or is in a debuff."""
    skills = user.get("skills") or {}
    if _bar_value(skills.get("health")) < MIN_HEALTH_TO_FIGHT and _bar_value(skills.get("hunger")) < MIN_HUNGER_TO_EAT:
        return False
    debuff_end = parse_iso((user.get("buffs") or {}).get("debuffEndAt"))
    return not (debuff_end and debuff_end > now)


def mention_chunks(mentions: list[str], limit: int = MESSAGE_CONTENT_LIMIT) -> list[str]:
    """Mentions joined by spaces into message contents of at most `limit` characters."""
    chunks: list[str] = []
    current = ""
    for mention in mentions:
        if current and len(current) + 1 + len(mention) > limit:
            chunks.append(current)
            current = mention
        else:
            current = f"{current} {mention}" if current else mention
    if current:
        chunks.append(current)
    return chunks


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

        units = contract_units()
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

        tr = await get_translator(guild)
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
            embed = await self._build_embed(contract, unit, session, tr)
            mentions = mention_chunks(await self._subscriber_mentions(str(unit["id"]), session))
            try:
                await channel.send(
                    content=mentions[0] if mentions else None,
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
                )
            except discord.DiscordException:
                logger.exception("Failed to post contract %s for MU %s", contract_id, unit.get("friendlyName"))
                continue
            self._remember(contract)
            for content in mentions[1:]:
                try:
                    await channel.send(content=content, allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True))
                except discord.DiscordException:
                    logger.exception("Failed to ping subscribers of contract %s", contract_id)

        await self._prune_posted(session)

    @mu_contract_monitor.before_loop
    async def before_mu_contract_monitor(self):
        await self.bot.wait_until_ready()

    async def _subscriber_mentions(self, mu_id: str, session) -> list[str]:
        """Mentions of the MU's subscribers who are still in the MU, not on an economy build and able to fight."""
        try:
            subscriptions = await asyncio.to_thread(get_job_subscribers, SUBSCRIPTION_JOB, mu_id)
        except Exception:
            logger.exception("Could not read contract subscribers of MU %s", mu_id)
            return []
        api_ids = {str(s["discord_id"]): str(s["api_id"]) for s in subscriptions if s.get("api_id")}
        if not api_ids:
            return []
        # one batched request; a subscriber whose stats could not be fetched is not pinged
        users = await get_users_info(api_ids.values(), session)
        now = datetime.now(timezone.utc)
        return [
            f"<@{discord_id}>"
            for discord_id, api_id in api_ids.items()
            if (user := users.get(api_id))
            and str(user.get("mu") or "") == mu_id
            and not is_economy_build(user)
            and can_fight(user, now)
        ]

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

    async def _build_embed(self, contract: dict, unit: dict, session, tr: Translator) -> discord.Embed:
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
        unknown = tr("common.unknown")
        issuer_name = country_names.get(str(contract.get("country") or contract.get("forCountry") or ""), unknown)
        attacker_name = country_names.get(str(attacker.get("country") or ""), unknown)
        defender_name = country_names.get(str(defender.get("country") or ""), unknown)
        side_icon = SIDE_ICONS.get(contract.get("forCountrySide"), "")

        embed = discord.Embed(
            title=f"{side_icon} {tr('mu_contracts.title', country=issuer_name)}".strip(),
            url=battle_link,
            description=(
                f"{SIDE_ICONS['attacker']} {self._country_label(attacker_name)} vs. "
                f"{SIDE_ICONS['defender']} {self._country_label(defender_name)}"
            ),
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name=tr("mu_contracts.min_damage"), value=format_amount(contract.get("minimumDamage"), unknown), inline=True)
        embed.add_field(name=tr("mu_contracts.per_1k"), value=format_amount(contract.get("currentPerK"), unknown), inline=True)
        embed.add_field(name=tr("mu_contracts.total_payout"), value=format_amount(contract.get("currentPayout"), unknown), inline=True)
        embed.add_field(name=tr("mu_contracts.battle_eta"), value=self._eta_text(contract, battle, round_obj, game_config, tr), inline=True)
        embed.add_field(name=tr("mu_contracts.score"), value=self._score_text(battle, game_config, tr), inline=True)
        # in-game name and avatar make the winner clear; the config's friendlyName is often an abbreviation
        mu_name = military_unit.get("name") or unit.get("friendlyName") or tr("mu_contracts.unknown_mu")
        embed.set_footer(text=tr("mu_contracts.won_by", mu=mu_name))
        if military_unit.get("avatarUrl"):
            embed.set_thumbnail(url=military_unit["avatarUrl"])
        return embed

    def _country_label(self, name: str) -> str:
        flag = country_flag(name)
        return f"{flag} **{name}**" if flag else f"**{name}**"

    def _score_text(self, battle: dict, game_config: dict, tr: Translator) -> str:
        if not battle:
            return tr("common.unknown")
        attacker_wins = (battle.get("attacker") or {}).get("wonRoundsCount") or 0
        defender_wins = (battle.get("defender") or {}).get("wonRoundsCount") or 0
        rounds_to_win = battle.get("roundsToWin") or game_config["rounds_to_win"]
        round_number = len(battle.get("rounds") or []) or 1
        return tr(
            "mu_contracts.score_value",
            round=round_number,
            attacker_icon=SIDE_ICONS["attacker"],
            attacker_wins=attacker_wins,
            defender_wins=defender_wins,
            defender_icon=SIDE_ICONS["defender"],
            rounds_to_win=rounds_to_win,
        )

    def _eta_text(self, contract: dict, battle: dict, round_obj, game_config: dict, tr: Translator) -> str:
        is_round_contract = bool(contract.get("round"))
        if not battle or not isinstance(round_obj, dict):
            return tr("common.unknown")
        if not battle.get("isActive"):
            return tr("mu_contracts.battle_ended")
        if is_round_contract and not round_obj.get("isActive"):
            return tr("mu_contracts.round_ended")

        eta = self._round_eta(round_obj, game_config)
        if is_round_contract:
            return tr(
                "mu_contracts.round_eta",
                eta=format_duration(eta),
                round=contract.get("roundNumber") or round_obj.get("number"),
            )

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
