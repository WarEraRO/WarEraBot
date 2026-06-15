import asyncio
import json
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands

from utils.api import (
    get_all_countries,
    get_shared_session,
    get_user_info,
    get_rankings
)


logger = logging.getLogger(__name__)

COUNTRY_CACHE_TTL = 300.0
TOP_LIMIT = 10


def _find_country(countries: list[dict], country_name: str) -> dict | None:
    wanted = (country_name or "").strip().casefold()
    for country in countries:
        if str(country.get("name") or "").strip().casefold() == wanted:
            return country
    return None


def _top_country_items(items: list[dict], country_id: str) -> list[dict]:
    matching = [
        item
        for item in items
        if item.get("country") == country_id and item.get("user")
    ]
    matching.sort(key=lambda item: item.get("value") or 0, reverse=True)
    return matching[:TOP_LIMIT]


def _country_choices(
    countries: list[dict],
    current: str,
) -> list[app_commands.Choice[str]]:
    search = (current or "").strip().casefold()
    matches = [
        country["name"]
        for country in countries
        if country.get("name")
        and (not search or search in country["name"].casefold())
    ]
    matches.sort(key=str.casefold)
    return [
        app_commands.Choice(name=name, value=name)
        for name in matches[:25]
    ]


def _build_embed(country_name: str, entries: list[tuple[dict, dict | None]]) -> discord.Embed:
    embed = discord.Embed(
        title=f"Weekly User Damages - {country_name}",
        color=discord.Color.red(),
    )

    if not entries:
        embed.description = "*No weekly damage entries found for this country.*"
        return embed

    lines = []
    for position, (item, user) in enumerate(entries, start=1):
        user_id = item["user"]
        username = (user or {}).get("username") or f"Unknown user ({user_id})"
        damage = item.get("value") or 0
        lines.append(
            f"**{position}. [{username}](https://app.warera.io/user/{user_id})**"
            f" - {damage:,} damage"
        )

    embed.description = "\n".join(lines)
    embed.set_footer(text="Weekly ranking | Top 10")
    return embed


class TopUserWeeklyDamages(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._countries: list[dict] = []
        self._countries_fetched_at = 0.0
        self._country_lock = asyncio.Lock()
        self._country_refresh_task: asyncio.Task | None = None

    async def cog_load(self) -> None:
        self._schedule_country_refresh()

    def cog_unload(self) -> None:
        if self._country_refresh_task and not self._country_refresh_task.done():
            self._country_refresh_task.cancel()

    def _countries_are_stale(self) -> bool:
        return (
            not self._countries
            or time.monotonic() - self._countries_fetched_at >= COUNTRY_CACHE_TTL
        )

    def _schedule_country_refresh(self) -> None:
        if (
            self._country_refresh_task is None
            or self._country_refresh_task.done()
        ):
            self._country_refresh_task = asyncio.create_task(
                self._refresh_countries()
            )

    async def _refresh_countries(self) -> list[dict]:
        try:
            async with self._country_lock:
                if not self._countries_are_stale():
                    return self._countries

                session = await get_shared_session()
                countries = await get_all_countries(session)
                if countries:
                    self._countries = countries
                    self._countries_fetched_at = time.monotonic()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to refresh countries")

        return self._countries

    async def _get_countries(self) -> list[dict]:
        if not self._countries_are_stale():
            return self._countries

        if self._country_refresh_task and not self._country_refresh_task.done():
            return await self._country_refresh_task
        return await self._refresh_countries()

    @app_commands.command(
        name="top_user_weekly_damages",
        description="Show the top 10 weekly damage dealers from a country.",
    )
    @app_commands.describe(country="Country to rank (choose one from autocomplete).")
    async def top_user_weekly_damages(
        self,
        interaction: discord.Interaction,
        country: str,
    ) -> None:
        await interaction.response.defer(thinking=True)

        countries = await self._get_countries()
        if not countries:
            await interaction.followup.send(
                "Could not load the country list. Please try again later.",
                ephemeral=True,
            )
            return

        selected_country = _find_country(countries, country)
        if selected_country is None:
            await interaction.followup.send(
                f"Country `{country}` was not found. Please select a country from autocomplete.",
                ephemeral=True,
            )
            return

        session = await get_shared_session()
        ranking_data = await get_rankings("weeklyUserDamages", session)
        ranking_data = ranking_data or {}
        items = ranking_data.get("items") or []
        top_items = _top_country_items(items, selected_country["_id"])

        try:
            users = await asyncio.gather(
                *(get_user_info(item["user"], session) for item in top_items)
            )
        except Exception:
            logger.exception("Failed to resolve weekly damage ranking users")
            users = [None] * len(top_items)

        embed = _build_embed(
            selected_country["name"],
            list(zip(top_items, users)),
        )
        await interaction.followup.send(embed=embed)

    @top_user_weekly_damages.autocomplete("country")
    async def country_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if self._countries_are_stale():
            self._schedule_country_refresh()
        return _country_choices(self._countries, current)


async def setup(bot: commands.Bot):
    await bot.add_cog(TopUserWeeklyDamages(bot))
