import asyncio
import logging
import re
import time

import discord
from discord.ext import commands, tasks

from config import config
from utils.api import (
    get_active_battles,
    get_all_countries,
    get_country,
    get_shared_session,
    get_region,
)
from utils.common import country_with_flag


logger = logging.getLogger(__name__)

BATTLE_ORDER_MONITOR_INTERVAL_MINUTES = 5
ROMANIA_NAME = "Romania"
BATTLE_LINK_RE = re.compile(r"https?://app\.warera\.io/battle/([A-Za-z0-9]+)")
REGION_CACHE_TTL_SECONDS = 60 * 60


class BattleOrderMonitorJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.priority_cache: list[dict] = []
        self._removed_auto_tokens: set[str] = set()
        self._country_cache: dict[str, str] = {}
        self._country_id_cache: dict[str, tuple[str | None, float]] = {}
        self._regions_cache: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()
        self.battle_order_monitor.start()

    def cog_unload(self):
        self.battle_order_monitor.cancel()

    @tasks.loop(minutes=BATTLE_ORDER_MONITOR_INTERVAL_MINUTES)
    async def battle_order_monitor(self):
        await self.check_orders(notify=True)

    @battle_order_monitor.before_loop
    async def before_battle_order_monitor(self):
        await self.bot.wait_until_ready()

    async def check_orders(self, notify: bool = True) -> int:
        guild = self.bot.get_guild(config["guild"])
        if guild is None:
            return 0

        session = await get_shared_session()
        battles = await get_active_battles(session)
        if battles is None:
            return 0
        romania_id = await self._get_country_id(ROMANIA_NAME, session)
        if not romania_id:
            return 0

        active_battle_ids: set[str] = set()
        found_tokens: set[str] = set()
        new_entries: list[dict] = []

        for battle in battles:
            battle_id = self._battle_id(battle)
            if not battle_id:
                continue
            active_battle_ids.add(battle_id)

            attacker = battle.get("attacker") or {}
            defender = battle.get("defender") or {}
            sides = [
                ("attacker", attacker, "defender", defender),
                ("defender", defender, "attacker", attacker),
            ]

            for side_name, side, opponent_side_name, opponent in sides:
                country_orders = [str(item) for item in (side.get("countryOrders") or [])]
                if str(romania_id) not in country_orders:
                    continue

                token = self._entry_token(battle_id, side_name, "romania")
                found_tokens.add(token)
                async with self._lock:
                    exists = any(
                        entry.get("token") == token or entry.get("battle_id") == battle_id
                        for entry in self.priority_cache
                    )
                    removed = token in self._removed_auto_tokens
                if removed:
                    continue
                if exists:
                    continue

                entry = await self._build_entry(
                    battle,
                    side_name,
                    side,
                    opponent_side_name,
                    opponent,
                    source="romania",
                    description="",
                    session=session,
                )
                new_entries.append(entry)

        async with self._lock:
            self.priority_cache = [
                entry
                for entry in self.priority_cache
                if entry.get("battle_id") in active_battle_ids
                and (entry.get("source") != "romania" or entry.get("token") in found_tokens)
            ]
            for entry in new_entries:
                if not any(existing.get("token") == entry.get("token") for existing in self.priority_cache):
                    self.priority_cache.append(entry)
            self._removed_auto_tokens = {
                token
                for token in self._removed_auto_tokens
                if token.split(":", 1)[0] in active_battle_ids
            }

        if notify:
            for entry in new_entries:
                await self.notify_priority(entry)

        return len(new_entries)

    async def add_priority_from_link(self, link: str, description: str = "") -> tuple[bool, str, dict | None]:
        battle_id = self._parse_battle_id(link)
        if not battle_id:
            return False, "Invalid battle link.", None

        session = await get_shared_session()
        battles = await get_active_battles(session)
        if battles is None:
            return False, "Could not fetch active battles.", None
        battle = next((item for item in battles if self._battle_id(item) == battle_id), None)
        if not battle:
            return False, "Battle is not active or could not be found.", None

        await self._get_country_id(ROMANIA_NAME, session)
        side_name, side, opponent_side_name, opponent = self._preferred_side_for_manual_entry(battle)
        token = self._entry_token(battle_id, side_name, "manual")

        entry = await self._build_entry(
            battle,
            side_name,
            side,
            opponent_side_name,
            opponent,
            source="manual",
            description=description,
            session=session,
        )
        entry["token"] = token

        async with self._lock:
            if any(existing.get("battle_id") == battle_id for existing in self.priority_cache):
                return False, "That battle is already in the priority list.", None
            self._removed_auto_tokens = {
                removed_token
                for removed_token in self._removed_auto_tokens
                if removed_token.split(":", 1)[0] != battle_id
            }
            self.priority_cache.append(entry)

        await self.notify_manual_priority(entry)
        return True, "Priority added.", entry

    async def set_description(self, entry_number: int, description: str) -> bool:
        async with self._lock:
            if entry_number < 1 or entry_number > len(self.priority_cache):
                return False
            self.priority_cache[entry_number - 1]["description"] = description
            return True

    async def remove_priority(self, entry_number: int) -> dict | None:
        async with self._lock:
            if entry_number < 1 or entry_number > len(self.priority_cache):
                return None
            entry = self.priority_cache.pop(entry_number - 1)
            if entry.get("battle_id") and entry.get("side_name"):
                self._removed_auto_tokens.add(
                    self._entry_token(entry["battle_id"], entry["side_name"], "romania")
                )
            return entry

    async def move_priorities(self, entry_number_a: int, entry_number_b: int) -> bool:
        async with self._lock:
            if (
                entry_number_a < 1
                or entry_number_b < 1
                or entry_number_a > len(self.priority_cache)
                or entry_number_b > len(self.priority_cache)
            ):
                return False
            index_a = entry_number_a - 1
            index_b = entry_number_b - 1
            self.priority_cache[index_a], self.priority_cache[index_b] = (
                self.priority_cache[index_b],
                self.priority_cache[index_a],
            )
            return True

    async def get_priorities(self) -> list[dict]:
        async with self._lock:
            return [dict(entry) for entry in self.priority_cache]

    async def notify_priority(self, entry: dict):
        guild = self.bot.get_guild(config["guild"])
        if guild is None:
            return
        channel = guild.get_channel(config.get("channels", {}).get("battle-orders"))
        if channel is None:
            return

        message = self.format_priority_message(entry)
        description = entry.get("description")
        if description:
            message += f"\nOrder Description: {description}"

        await self._send_priority_message(channel, message)

    async def notify_manual_priority(self, entry: dict):
        guild = self.bot.get_guild(config["guild"])
        if guild is None:
            return
        channel = guild.get_channel(config.get("channels", {}).get("battle-orders"))
        if channel is None:
            return

        description = entry.get("description") or "No description."
        message = (
            f"A new priority was added: {self.format_priority_title(entry)} "
            f"in [{entry.get('region_name')}]({entry.get('battle_link')})\n"
            f"Order Description: {description}"
        )

        await self._send_priority_message(channel, message)

    async def _send_priority_message(self, channel: discord.TextChannel, message: str):
        try:
            sent = await channel.send(
                message,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            await sent.edit(suppress=True)
        except discord.DiscordException:
            logger.exception("Failed to send battle order priority alert")

    def format_priority_message(self, entry: dict) -> str:
        side_country = country_with_flag(entry.get("side_country_name"), left=True)
        opponent_country = country_with_flag(entry.get("opponent_country_name"), left=False)
        return (
            f"{ROMANIA_NAME} placed an order for the {entry.get('side_name')} "
            f"{side_country} against {entry.get('opponent_side_name')} "
            f"{opponent_country} in "
            f"[{entry.get('region_name')}]({entry.get('battle_link')})"
        )

    def format_priority_title(self, entry: dict) -> str:
        side_country = country_with_flag(entry.get("side_country_name"), left=True)
        opponent_country = country_with_flag(entry.get("opponent_country_name"), left=False)
        return (
            f"{entry.get('side_name').capitalize()} {side_country} - "
            f"{opponent_country} {entry.get('opponent_side_name').capitalize()}"
        )

    async def _build_entry(
        self,
        battle: dict,
        side_name: str,
        side: dict,
        opponent_side_name: str,
        opponent: dict,
        source: str,
        description: str,
        session,
    ) -> dict:
        battle_id = self._battle_id(battle) or "unknown"
        side_country_id = str(side.get("country") or "")
        opponent_country_id = str(opponent.get("country") or "")
        side_country_name, opponent_country_name = await asyncio.gather(
            self._country_name(side_country_id, session),
            self._country_name(opponent_country_id, session),
        )
        region_name = await self._region_name(battle, session)

        return {
            "token": self._entry_token(battle_id, side_name, source),
            "source": source,
            "battle_id": battle_id,
            "battle_link": f"https://app.warera.io/battle/{battle_id}",
            "side_name": side_name,
            "opponent_side_name": opponent_side_name,
            "side_country_id": side_country_id,
            "opponent_country_id": opponent_country_id,
            "side_country_name": side_country_name,
            "opponent_country_name": opponent_country_name,
            "region_name": region_name,
            "description": description or "",
        }

    def _preferred_side_for_manual_entry(self, battle: dict) -> tuple[str, dict, str, dict]:
        attacker = battle.get("attacker") or {}
        defender = battle.get("defender") or {}
        romania_id = next(
            (
                country_id
                for country_id, name in self._country_cache.items()
                if name.lower() == ROMANIA_NAME.lower()
            ),
            None,
        )
        if romania_id and str(romania_id) == str(attacker.get("country") or ""):
            return "attacker", attacker, "defender", defender
        if romania_id and str(romania_id) == str(defender.get("country") or ""):
            return "defender", defender, "attacker", attacker
        return "attacker", attacker, "defender", defender

    async def _get_country_id(self, country_name: str, session) -> str | None:
        now = time.monotonic()
        cache_key = country_name.lower()
        cached = self._country_id_cache.get(cache_key)
        if cached and now - cached[1] < 24 * 60 * 60:
            return cached[0]

        countries = await get_all_countries(session) or []
        for country in countries:
            name = str(country.get("name") or "")
            country_id = str(country.get("_id") or country.get("id") or "")
            if not name or not country_id:
                continue
            self._country_cache[country_id] = name
            if name.lower() == country_name.lower():
                self._country_id_cache[cache_key] = (country_id, now)
                return country_id
        self._country_id_cache[cache_key] = (None, now)
        return None

    async def _country_name(self, country_id: str, session) -> str:
        if not country_id:
            return "unknown"
        if country_id in self._country_cache:
            return self._country_cache[country_id]
        country = await get_country(country_id, session)
        name = country.get("name") if isinstance(country, dict) else None
        self._country_cache[country_id] = str(name or country_id)
        return self._country_cache[country_id]

    async def _region_name(self, battle: dict, session) -> str:
        region_id = self._region_id(battle)
        if not region_id:
            return "Unknown region"

        now = time.monotonic()
        cached = self._regions_cache.get(region_id)
        if cached and now - cached[1] < REGION_CACHE_TTL_SECONDS:
            return cached[0]

        region_obj = await get_region(session, region_id)
        if isinstance(region_obj, dict):
            name = str(region_obj.get("name") or region_id)
        else:
            name = region_id

        self._regions_cache[region_id] = (name, now)
        return name

    def _region_id(self, battle: dict) -> str | None:
        region = battle.get("region")
        if not region:
            defender = battle.get("defender") or {}
            attacker = battle.get("attacker") or {}
            region = defender.get("region") or attacker.get("region")
        return str(region) if region else None

    def _battle_id(self, battle: dict) -> str | None:
        battle_id = battle.get("_id") or battle.get("id") or battle.get("battleId")
        return str(battle_id) if battle_id else None

    def _entry_token(self, battle_id: str, side_name: str, source: str) -> str:
        return f"{battle_id}:{side_name}:{source}"

    def _parse_battle_id(self, link: str) -> str | None:
        match = BATTLE_LINK_RE.search(link or "")
        return match.group(1) if match else None


async def setup(bot: commands.Bot):
    await bot.add_cog(BattleOrderMonitorJob(bot))
