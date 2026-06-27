import asyncio
import logging
import time

import discord
from discord.ext import commands, tasks

from config import config
from utils.api import get_active_battles, get_military_unit, get_shared_session
from utils.db import get_all_naps, init_db


logger = logging.getLogger(__name__)

NAP_MONITOR_INTERVAL_HOURS = 1
MU_COUNTRY_CACHE_TTL_SECONDS = 24 * 60 * 60


class NAPMonitorJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reported_violations: set[str] = set()
        try:
            init_db()
        except Exception:
            pass
        self.naps = get_all_naps()
        self.mu_cache: dict[str, tuple[str | None, str | None, float]] = {}
        self.monitor_nap.start()

    def cog_unload(self):
        self.monitor_nap.cancel()

    def refresh_naps(self):
        self.naps = get_all_naps()
        self.reported_violations.clear()

    def remove_cached_nap(self, country_a_id: str, country_b_id: str):
        pair = frozenset([str(country_a_id), str(country_b_id)])
        self.naps = [
            nap
            for nap in self.naps
            if frozenset([
                str(nap.get("country_a_id") or ""),
                str(nap.get("country_b_id") or ""),
            ]) != pair
        ]
        self.reported_violations.clear()

    @tasks.loop(hours=NAP_MONITOR_INTERVAL_HOURS)
    async def monitor_nap(self):
        """Check active battles for country or MU orders against configured NAPs."""
        guild = self.bot.get_guild(config["guild"])
        if guild is None:
            return

        naps = self.naps
        if not naps:
            self.reported_violations.clear()
            return

        session = await get_shared_session()
        battles = await get_active_battles(session)
        if not battles:
            self.reported_violations.clear()
            return

        nap_pairs: set[frozenset[str]] = set()
        nap_pair_ids: dict[frozenset[str], tuple[str, str]] = {}
        for nap in naps:
            first_id = str(nap.get("country_a_id") or "")
            second_id = str(nap.get("country_b_id") or "")
            if not first_id or not second_id:
                continue
            pair = frozenset([first_id, second_id])
            nap_pairs.add(pair)
            nap_pair_ids[pair] = (first_id, second_id)

        if not nap_pairs:
            return

        country_names: dict[str, str] = {}
        for nap in naps:
            if nap.get("country_a_id"):
                country_names[str(nap["country_a_id"])] = str(nap.get("country_a_name") or nap["country_a_id"])
            if nap.get("country_b_id"):
                country_names[str(nap["country_b_id"])] = str(nap.get("country_b_name") or nap["country_b_id"])

        def country_link(country_id: str) -> str:
            name = country_names.get(country_id, country_id)
            return f"[{name}](https://app.warera.io/country/{country_id})"

        def mu_link(mu_id: str, mu_name: str | None = None) -> str:
            name = mu_name or f"Military Unit {mu_id}"
            return f"[{name}](https://app.warera.io/mu/{mu_id})"

        async def get_mu_info(mu_id: str) -> tuple[str | None, str | None]:
            now = time.monotonic()
            cached = self.mu_cache.get(mu_id)
            if cached:
                country_id, mu_name, fetched_at = cached
                if now - fetched_at < MU_COUNTRY_CACHE_TTL_SECONDS:
                    return country_id, mu_name

            try:
                mu = await get_military_unit(mu_id, session)
            except Exception:
                logger.exception("Failed to fetch MU %s for NAP monitor", mu_id)
                mu = None
            country_id = str(mu.get("country")) if isinstance(mu, dict) and mu.get("country") else None
            mu_name = str(mu.get("name")) if isinstance(mu, dict) and mu.get("name") else None
            self.mu_cache[mu_id] = (country_id, mu_name, now)
            return country_id, mu_name

        violations: list[dict] = []
        active_battle_ids: set[str] = set()

        for battle in battles:
            battle_id = str(battle.get("_id") or "unknown")
            active_battle_ids.add(battle_id)
            attacker = battle.get("attacker") or {}
            defender = battle.get("defender") or {}

            sides = [
                ("attacker", attacker, defender),
                ("defender", defender, attacker),
            ]

            for side_name, side, opponent in sides:
                opponent_country = str(opponent.get("country") or "")
                if not opponent_country:
                    continue

                for ordered_country in side.get("countryOrders") or []:
                    ordered_country = str(ordered_country)
                    pair = frozenset([ordered_country, opponent_country])
                    if pair not in nap_pairs:
                        continue
                    violations.append({
                        "battle_id": battle_id,
                        "side": side_name,
                        "source_type": "country",
                        "source_id": ordered_country,
                        "source_country": ordered_country,
                        "opponent_country": opponent_country,
                        "pair": pair,
                    })

                mu_ids = [str(mu_id) for mu_id in (side.get("muOrders") or []) if mu_id]
                if not mu_ids:
                    continue
                mu_infos = await asyncio.gather(*(get_mu_info(mu_id) for mu_id in mu_ids))
                for mu_id, (mu_country, mu_name) in zip(mu_ids, mu_infos):
                    if not mu_country:
                        continue
                    pair = frozenset([str(mu_country), opponent_country])
                    if pair not in nap_pairs:
                        continue
                    violations.append({
                        "battle_id": battle_id,
                        "side": side_name,
                        "source_type": "military unit",
                        "source_id": mu_id,
                        "source_name": mu_name,
                        "source_country": str(mu_country),
                        "opponent_country": opponent_country,
                        "pair": pair,
                    })

        if not violations:
            self._prune_reported(active_battle_ids)
            return

        channel = guild.get_channel(config.get("channels", {}).get("reports"))
        if channel is None:
            return

        new_violations = []
        for violation in violations:
            token = (
                f"{violation['battle_id']}:{violation['side']}:"
                f"{violation['source_type']}:{violation['source_id']}:"
                f"{violation['opponent_country']}"
            )
            if token in self.reported_violations:
                continue
            violation["token"] = token
            new_violations.append(violation)

        if not new_violations:
            self._prune_reported(active_battle_ids)
            return

        for chunk_start in range(0, len(new_violations), 10):
            chunk = new_violations[chunk_start:chunk_start + 10]
            embed = discord.Embed(
                title="NAP Violation Alert",
                color=discord.Color.red(),
                description="Active battle orders were found against configured NAP partners.",
            )

            for violation in chunk:
                source_country = country_link(violation["source_country"])
                opponent_country = country_link(violation["opponent_country"])
                pair_ids = nap_pair_ids.get(
                    violation["pair"],
                    (violation["source_country"], violation["opponent_country"]),
                )
                pair_name_a, pair_name_b = (country_link(country_id) for country_id in pair_ids)
                battle_link = f"https://app.warera.io/battle/{violation['battle_id']}"
                source = source_country
                if violation["source_type"] == "military unit":
                    source = f"{mu_link(violation['source_id'], violation.get('source_name'))} ({source_country})"
                embed.add_field(
                    name=f"{pair_name_a} - {pair_name_b}",
                    value=(
                        f"{source} has {violation['side']} orders against "
                        f"{opponent_country}.\n[View battle]({battle_link})"
                    ),
                    inline=False,
                )

            try:
                await channel.send(embed=embed)
            except discord.DiscordException:
                logger.exception("Failed to send NAP monitor alert")
                continue

            for violation in chunk:
                self.reported_violations.add(violation["token"])

        self._prune_reported(active_battle_ids)

    def _prune_reported(self, active_battle_ids: set[str]):
        self.reported_violations = {
            token
            for token in self.reported_violations
            if token.split(":", 1)[0] in active_battle_ids
        }

    @monitor_nap.before_loop
    async def before_monitor_nap(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(NAPMonitorJob(bot))
