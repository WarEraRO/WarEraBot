import asyncio
import json
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands

from utils.api import (
    get_all_countries,
    get_market_prices,
    get_shared_session,
    get_country,
    get_regions_object,
)


logger = logging.getLogger(__name__)

COUNTRY_CACHE_TTL = 300.0
UPKEEP_UPGRADES = {
    "bunker": "Bunker",
    "base": "Military Base",
    "pacificationCenter": "Pacification Center",
}
UPKEEP_PCTS = {
    "bunker": {1: 0.04, 2: 0.08, 3: 0.16, 4: 0.32, 5: 0.64},
    "base": {1: 0.04, 2: 0.08, 3: 0.16, 4: 0.32, 5: 0.64},
    "pacificationCenter": {1: 0.05, 2: 0.10, 3: 0.20, 4: 0.40, 5: 0.80},
}


def _find_country(countries: list[dict], country_name: str) -> dict | None:
    wanted = (country_name or "").strip().casefold()
    for country in countries:
        if str(country.get("name") or "").strip().casefold() == wanted:
            return country
    return None


def _country_choices(
    countries: list[dict],
    current: str,
) -> list[app_commands.Choice[str]]:
    search = (current or "").strip().casefold()
    names = [
        country["name"]
        for country in countries
        if country.get("name")
        and (not search or search in country["name"].casefold())
    ]
    names.sort(key=str.casefold)
    return [
        app_commands.Choice(name=name, value=name)
        for name in names[:25]
    ]


def _format_number(value: float, suffix: str = "") -> str:
    if abs(value - round(value)) < 0.005:
        return f"{round(value):,}{suffix}"
    return f"{value:,.2f}{suffix}"


def _format_money(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    return _format_number(value)

def _number_or_none(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None

def _extract_price_from_oil_entry(value: object) -> float | None:
    number = _number_or_none(value)
    if number is not None:
        return number

    if isinstance(value, dict):
        for price_key in ("price", "value", "cost", "averagePrice"):
            price = _number_or_none(value.get(price_key))
            if price is not None:
                return price

    return None

def _extract_oil_price(value: object) -> float | None:
    if isinstance(value, dict):
        if "oil" in value:
            price = _extract_price_from_oil_entry(value.get("oil"))
            if price is not None:
                return price

        item_code = str(
            value.get("itemCode")
            or value.get("code")
            or value.get("item")
            or value.get("name")
            or ""
        ).casefold()
        if item_code == "oil":
            price = _extract_price_from_oil_entry(value)
            if price is not None:
                return price

        for nested in value.values():
            price = _extract_oil_price(nested)
            if price is not None:
                return price

    if isinstance(value, list):
        for item in value:
            price = _extract_oil_price(item)
            if price is not None:
                return price

    return None


def _iter_country_regions(regions_object: dict, country_id: str) -> list[dict]:
    regions = []
    for region in regions_object.values():
        if isinstance(region, dict) and region.get("country") == country_id:
            regions.append(region)
    regions.sort(key=lambda item: str(item.get("name") or "").casefold())
    return regions


def _region_active_upkeep(
    region: dict,
    average_development: float,
) -> list[tuple[str, int, float]]:
    upgrades = (
        region.get("activeUpgradeLevels") or {}
    )
    active = []
    for upgrade_key, display_name in UPKEEP_UPGRADES.items():
        try:
            level = int(upgrades.get(upgrade_key, 0))
        except (TypeError, ValueError):
            continue

        pct = UPKEEP_PCTS.get(upgrade_key, {}).get(level)
        if pct is None:
            continue
        active.append((display_name, level, average_development * pct * 24))
    return active


def _build_embed(
    country_name: str,
    average_development: float,
    region_count: int,
    active_entries: list[tuple[str, str, int, float]],
    oil_price: float | None,
) -> discord.Embed:
    total_oil = sum(entry[3] for entry in active_entries)
    total_cost = total_oil * oil_price if oil_price is not None else None

    embed = discord.Embed(
        title=f"Region Upgrade Upkeep - {country_name}",
        color=discord.Color.dark_gold(),
    )
    embed.add_field(
        name="Summary",
        value=(
            f"Regions held: **{region_count:,}**\n"
            f"Average development: **{_format_number(average_development)}**\n"
            f"Active paid upgrades: **{len(active_entries):,}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Oil",
        value=(
            f"Daily oil upkeep: **{_format_number(total_oil, ' oil')}**\n"
            f"Market oil price: **{_format_money(oil_price)}**\n"
            f"Daily market cost: **{_format_money(total_cost)}**"
        ),
        inline=False,
    )

    if not active_entries:
        embed.description = "*No active bunkers, military bases, or pacification centers found.*"
        return embed

    field_lines = []
    used_chars = 0
    lines = []
    hidden_count = 0
    for region_name, upgrade_name, level, oil_amount in active_entries:
        line = (
            f"**{region_name}** - {upgrade_name} lvl {level}: "
            f"{_format_number(oil_amount, ' oil')}"
        )
        extra_chars = len(line) + (1 if field_lines else 0)
        if used_chars + extra_chars > 950:
            hidden_count += 1
            continue
        field_lines.append(line)
        used_chars += extra_chars

    if hidden_count:
        lines.append(f"...and {hidden_count:,} more active upgrades.")

    embed.add_field(
        name="Active Upgrades",
        value="\n".join(field_lines + lines),
        inline=False,
    )
    embed.set_footer(text="Daily upkeep estimate uses active upgrades only.")
    return embed


class GetRegionUpgradeCost(commands.Cog):
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
        name="get_region_upgrade_cost",
        description="Calculate daily oil upkeep for active country region upgrades.",
    )
    @app_commands.describe(
        country="Country to calculate (choose one from autocomplete)."
    )
    async def get_region_upgrade_cost(
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
        country_id = selected_country["_id"]
        regions_object, country_info, market_prices = await asyncio.gather(
            get_regions_object(session),
            get_country(country_id, session),
            get_market_prices(session),
        )

        if not regions_object:
            await interaction.followup.send(
                "Could not load region data. Please try again later.",
                ephemeral=True,
            )
            return
        if not country_info:
            await interaction.followup.send(
                "Could not load country development data. Please try again later.",
                ephemeral=True,
            )
            return

        try:
            average_development = float(country_info.get("averageDevelopment"))
        except (TypeError, ValueError):
            await interaction.followup.send(
                "Country average development is unavailable.",
                ephemeral=True,
            )
            return

        regions = _iter_country_regions(regions_object, country_id)
        active_entries = []
        for region in regions:
            region_name = str(region.get("name") or region.get("_id") or "Unknown region")
            for upgrade_name, level, oil_amount in _region_active_upkeep(
                region,
                average_development,
            ):
                active_entries.append((region_name, upgrade_name, level, oil_amount))

        oil_price = _extract_oil_price(market_prices)
        embed = _build_embed(
            selected_country["name"],
            average_development,
            len(regions),
            active_entries,
            oil_price,
        )
        await interaction.followup.send(embed=embed)

    @get_region_upgrade_cost.autocomplete("country")
    async def country_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if self._countries_are_stale():
            self._schedule_country_refresh()
        return _country_choices(self._countries, current)


async def setup(bot: commands.Bot):
    await bot.add_cog(GetRegionUpgradeCost(bot))
