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
    get_tournament,
    get_tournament_team,
)
from utils.common import country_flag, country_with_flag


logger = logging.getLogger(__name__)

BATTLE_ORDER_MONITOR_INTERVAL_MINUTES = 5
ROMANIA_NAME = "Romania"
BATTLE_LINK_RE = re.compile(r"https?://app\.warera\.io/battle/([A-Za-z0-9]+)")
REGION_CACHE_TTL_SECONDS = 60 * 60
TOURNAMENT_CACHE_TTL_SECONDS = 60 * 60
# battle.type of tournament battles; they have no region or side country, only a tournamentTeam per side
TOURNAMENT_BATTLE_TYPE = "tournament"
# tournament.type of country tournaments ("mu" tournaments are not reported)
COUNTRY_TOURNAMENT_TYPE = "country"


class BattleOrderMonitorJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.priority_cache: list[dict] = []
        self._removed_auto_tokens: set[str] = set()
        self._country_cache: dict[str, str] = {}
        self._country_id_cache: dict[str, tuple[str | None, float]] = {}
        self._regions_cache: dict[str, tuple[str, float]] = {}
        self._tournaments_cache: dict[str, tuple[dict, float]] = {}
        self._tournament_teams_cache: dict[str, tuple[dict, float]] = {}
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

                tournament = await self._tournament_context(battle, session)
                if tournament is not None and tournament["type"] != COUNTRY_TOURNAMENT_TYPE:
                    # MU tournaments are not reported; a failed tournament lookup is retried next cycle
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
                    tournament=tournament,
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

        tournament = await self._tournament_context(battle, session)
        if tournament is not None and tournament["type"] != COUNTRY_TOURNAMENT_TYPE:
            if tournament["type"] is None:
                return False, "Could not fetch the tournament for this battle.", None
            return False, "Only country tournament battles can be added as priorities.", None

        await self._get_country_id(ROMANIA_NAME, session)
        side_name, side, opponent_side_name, opponent = self._preferred_side_for_manual_entry(battle, tournament)
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
            tournament=tournament,
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
            f"Order Description: {description}\n"
            f"Battle Link: {entry.get('battle_link')}"
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
        if entry.get("tournament_name"):
            return (
                f"{country_with_flag(ROMANIA_NAME, left=True)} put an order in the "
                f"[tournament]({entry.get('battle_link')}) against "
                f"{self._format_team(entry.get('opponent_team_names'))}"
            )
        side_country = country_with_flag(entry.get("side_country_name"), left=True)
        opponent_country = country_with_flag(entry.get("opponent_country_name"), left=False)
        return (
            f"{ROMANIA_NAME} placed an order for the {entry.get('side_name')} "
            f"{side_country} against {entry.get('opponent_side_name')} "
            f"{opponent_country} in "
            f"[{entry.get('region_name')}]({entry.get('battle_link')})"
        )

    def format_priority_title(self, entry: dict) -> str:
        if entry.get("tournament_name"):
            return (
                f"Tournament: {entry.get('side_name').capitalize()} "
                f"{self._format_team(entry.get('side_team_names'), compact=True)} - "
                f"{self._format_team(entry.get('opponent_team_names'), compact=True)} "
                f"{entry.get('opponent_side_name').capitalize()}"
            )
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
        tournament: dict | None = None,
    ) -> dict:
        battle_id = self._battle_id(battle) or "unknown"
        if tournament is not None:
            side_team_names, opponent_team_names = await asyncio.gather(
                self._country_names(tournament["teams"].get(side_name, []), session),
                self._country_names(tournament["teams"].get(opponent_side_name, []), session),
            )
            return {
                "token": self._entry_token(battle_id, side_name, source),
                "source": source,
                "battle_id": battle_id,
                "battle_link": f"https://app.warera.io/battle/{battle_id}",
                "side_name": side_name,
                "opponent_side_name": opponent_side_name,
                "side_team_names": side_team_names,
                "opponent_team_names": opponent_team_names,
                "tournament_name": tournament["name"],
                # read by the manual-priority message ("... in [region](link)")
                "region_name": tournament["name"],
                "description": description or "",
            }

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

    def _preferred_side_for_manual_entry(
        self, battle: dict, tournament: dict | None = None
    ) -> tuple[str, dict, str, dict]:
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
        if tournament is not None:
            # in a country tournament Romania fights as one country of a team
            teams = tournament["teams"]
            if romania_id and str(romania_id) in teams.get("defender", []):
                return "defender", defender, "attacker", attacker
            return "attacker", attacker, "defender", defender
        if romania_id and str(romania_id) == str(attacker.get("country") or ""):
            return "attacker", attacker, "defender", defender
        if romania_id and str(romania_id) == str(defender.get("country") or ""):
            return "defender", defender, "attacker", attacker
        return "attacker", attacker, "defender", defender

    async def _tournament_context(self, battle: dict, session) -> dict | None:
        """None for regular battles. For tournament battles: {"type", "name", "teams": {side: [country ids]}};
        "type" is None when the tournament could not be fetched."""
        if battle.get("type") != TOURNAMENT_BATTLE_TYPE:
            return None
        context = {"type": None, "name": "Tournament", "teams": {}}
        tournament = await self._cached_lookup(
            self._tournaments_cache, str(battle.get("tournament") or ""), get_tournament, session
        )
        if tournament is None:
            return context
        context["type"] = tournament.get("type")
        context["name"] = str(tournament.get("name") or "Tournament")
        if context["type"] != COUNTRY_TOURNAMENT_TYPE:
            return context

        side_names = ("attacker", "defender")
        teams = await asyncio.gather(
            *(
                self._cached_lookup(
                    self._tournament_teams_cache,
                    str((battle.get(side_name) or {}).get("tournamentTeam") or ""),
                    get_tournament_team,
                    session,
                )
                for side_name in side_names
            )
        )
        for side_name, team in zip(side_names, teams):
            context["teams"][side_name] = [str(country_id) for country_id in (team or {}).get("countries") or []]
        return context

    async def _cached_lookup(self, cache: dict[str, tuple[dict, float]], key: str, fetch, session) -> dict | None:
        if not key:
            return None
        now = time.monotonic()
        cached = cache.get(key)
        if cached and now - cached[1] < TOURNAMENT_CACHE_TTL_SECONDS:
            return cached[0]
        value = await fetch(key, session)
        # failures are not cached so the next cycle retries
        if value is not None:
            cache[key] = (value, now)
        return value

    async def _country_names(self, country_ids: list[str], session) -> list[str]:
        return list(await asyncio.gather(*(self._country_name(country_id, session) for country_id in country_ids)))

    def _format_team(self, country_names: list[str] | None, compact: bool = False) -> str:
        if not country_names:
            return "unknown"
        if compact:
            return ", ".join(country_flag(name) or name for name in country_names)
        return ", ".join(country_with_flag(name, left=True) for name in country_names)

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
