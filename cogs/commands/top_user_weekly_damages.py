import asyncio
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
EMBED_FIELD_VALUE_LIMIT = 1024
LEVEL_BRACKETS = [
    (6, 15),
    (15, 20),
    (20, 25),
    (25, 30),
    (30, 35),
    (35, 40),
    (40, 45),
    (45, 50),
]


def _find_country(countries: list[dict], country_name: str) -> dict | None:
    wanted = (country_name or "").strip().casefold()
    for country in countries:
        if str(country.get("name") or "").strip().casefold() == wanted:
            return country
    return None


def _split_country_names(country_names: str) -> list[str]:
    names = [
        name.strip()
        for chunk in (country_names or "").split(";")
        for name in chunk.split(",")
    ]
    return [name for name in names if name]


def _find_countries(
    countries: list[dict],
    country_names: str,
) -> tuple[list[dict], list[str]]:
    selected = []
    missing = []
    seen_ids = set()

    for country_name in _split_country_names(country_names):
        country = _find_country(countries, country_name)
        if country is None:
            missing.append(country_name)
            continue

        country_id = country.get("_id")
        if country_id and country_id not in seen_ids:
            selected.append(country)
            seen_ids.add(country_id)

    return selected, missing


def _country_items(items: list[dict], country_ids: set[str]) -> list[dict]:
    matching = [
        item
        for item in items
        if item.get("country") in country_ids and item.get("user")
    ]
    matching.sort(key=lambda item: item.get("value") or 0, reverse=True)
    return matching


def _country_choices(
    countries: list[dict],
    current: str,
) -> list[app_commands.Choice[str]]:
    raw_current = current or ""
    separator_index = max(raw_current.rfind(","), raw_current.rfind(";"))
    prefix = raw_current[: separator_index + 1] if separator_index >= 0 else ""
    search = raw_current[separator_index + 1 :].strip().casefold()
    matches = [
        country["name"]
        for country in countries
        if country.get("name")
        and (not search or search in country["name"].casefold())
    ]
    matches.sort(key=str.casefold)
    return [
        app_commands.Choice(name=name, value=f"{prefix} {name}".strip())
        for name in matches[:25]
    ]


def _format_country_title(countries: list[dict]) -> str:
    names = [country["name"] for country in countries if country.get("name")]
    if len(names) <= 3:
        return ", ".join(names)
    return f"{', '.join(names[:3])} + {len(names) - 3} more"


def _level_from_user(user: dict | None) -> int | None:
    if not user:
        return None

    leveling = user.get("leveling") or {}
    level = leveling.get("level")
    if isinstance(level, int) and not isinstance(level, bool):
        return level
    return None


def _bracket_title(start: int, end: int) -> str:
    return f"Level [{start}-{end})"


def _bracket_entries(
    entries: list[tuple[dict, dict | None]],
) -> dict[tuple[int, int], list[tuple[dict, dict | None]]]:
    bracketed = {bracket: [] for bracket in LEVEL_BRACKETS}

    for item, user in entries:
        level = _level_from_user(user)
        if level is None:
            continue

        for start, end in LEVEL_BRACKETS:
            if start <= level < end:
                bracketed[(start, end)].append((item, user))
                break

    for bracket_entries in bracketed.values():
        bracket_entries.sort(key=lambda entry: entry[0].get("value") or 0, reverse=True)

    return bracketed


def _fit_field_lines(lines: list[str]) -> str:
    fitted = []
    length = 0

    for line in lines:
        separator_length = 1 if fitted else 0
        next_length = length + separator_length + len(line)
        if next_length > EMBED_FIELD_VALUE_LIMIT:
            break

        fitted.append(line)
        length = next_length

    if not fitted and lines:
        return lines[0][: EMBED_FIELD_VALUE_LIMIT - 3] + "..."

    return "\n".join(fitted)


def _build_embeds(
    countries: list[dict],
    entries: list[tuple[dict, dict | None]],
) -> list[discord.Embed]:
    title = f"Weekly User Damages - {_format_country_title(countries)}"
    embed = discord.Embed(
        title=title,
        color=discord.Color.red(),
    )

    if not entries:
        embed.description = "*No weekly damage entries found for the selected countries.*"
        return [embed]

    countries_by_id = {
        country["_id"]: country["name"]
        for country in countries
        if country.get("_id") and country.get("name")
    }
    bracketed = _bracket_entries(entries)
    embeds = []

    for bracket in LEVEL_BRACKETS:
        bracket_items = bracketed[bracket][:TOP_LIMIT]
        if not bracket_items:
            continue

        lines = []
        for position, (item, user) in enumerate(bracket_items, start=1):
            user_id = item["user"]
            username = (user or {}).get("username") or f"Unknown user ({user_id})"
            country_name = countries_by_id.get(item.get("country"), "Unknown country")
            damage = item.get("value") or 0
            lines.append(
                f"**{position}. [{username}](https://app.warera.io/user/{user_id})**"
                f" ({country_name}) - {damage:,} damage"
            )

        embed = discord.Embed(
            title=title,
            color=discord.Color.red(),
        )
        embed.add_field(
            name=_bracket_title(*bracket),
            value=_fit_field_lines(lines),
            inline=False,
        )
        embeds.append(embed)

    if not embeds:
        embed = discord.Embed(
            title=title,
            color=discord.Color.red(),
        )
        embed.description = "*No weekly damage entries found in the configured level brackets.*"
        embeds.append(embed)

    return embeds


class _BracketPaginator(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed], timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.current = 0
        self.message: discord.Message | None = None
        self._sync()

    def _sync(self) -> None:
        self.prev_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current == len(self.embeds) - 1
        for index, embed in enumerate(self.embeds, start=1):
            embed.set_footer(
                text=(
                    f"Bracket {index}/{len(self.embeds)}"
                    " | Weekly ranking | Top 10 per bracket"
                )
            )

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.primary)
    async def prev_btn(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.current = max(0, self.current - 1)
        self._sync()
        await interaction.response.edit_message(
            embed=self.embeds[self.current],
            view=self,
        )

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_btn(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.current = min(len(self.embeds) - 1, self.current + 1)
        self._sync()
        await interaction.response.edit_message(
            embed=self.embeds[self.current],
            view=self,
        )


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
        description="Show the top 10 weekly damage dealers from one or more countries.",
    )
    @app_commands.describe(
        country="Country/countries to rank. Separate multiple countries with commas."
    )
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

        selected_countries, missing_countries = _find_countries(countries, country)
        if missing_countries:
            await interaction.followup.send(
                (
                    "Could not find: "
                    + ", ".join(f"`{name}`" for name in missing_countries)
                    + ". Please select countries from autocomplete."
                ),
                ephemeral=True,
            )
            return
        if not selected_countries:
            await interaction.followup.send(
                "Please provide at least one country.",
                ephemeral=True,
            )
            return

        session = await get_shared_session()
        ranking_data = await get_rankings("weeklyUserDamages", session)
        ranking_data = ranking_data or {}
        items = ranking_data.get("items") or []
        country_ids = {
            country["_id"]
            for country in selected_countries
            if country.get("_id")
        }
        country_items = _country_items(items, country_ids)

        try:
            users = await asyncio.gather(
                *(get_user_info(item["user"], session) for item in country_items)
            )
        except Exception:
            logger.exception("Failed to resolve weekly damage ranking users")
            users = [None] * len(country_items)

        embeds = _build_embeds(
            selected_countries,
            list(zip(country_items, users)),
        )
        if len(embeds) == 1:
            embeds[0].set_footer(text="Weekly ranking | Top 10 per bracket")
            await interaction.followup.send(embed=embeds[0])
            return

        view = _BracketPaginator(embeds)
        message = await interaction.followup.send(
            embed=embeds[0],
            view=view,
            wait=True,
        )
        view.message = message

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
