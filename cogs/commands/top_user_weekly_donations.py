import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils.api import (
    get_all_countries,
    get_country_users,
    get_shared_session,
    get_user_info,
    get_user_transactions,
)


logger = logging.getLogger(__name__)

COUNTRY_CACHE_TTL = 300.0
TOP_LIMIT = 10
TRANSACTION_CONCURRENCY = 5


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


def _week_start(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _weekly_donation_total(
    user_id: str,
    transactions: list[dict],
    start: datetime,
    end: datetime,
) -> float:
    total = 0.0
    for transaction in transactions:
        created_at = _parse_timestamp(transaction.get("createdAt"))
        if (
            transaction.get("transactionType") != "donation"
            or transaction.get("buyerId") != user_id
            or created_at is None
            or not start <= created_at <= end
        ):
            continue

        money = transaction.get("money")
        if isinstance(money, (int, float)) and not isinstance(money, bool):
            total += money
    return total


def _top_donors(
    users: list[dict],
    totals: dict[str, float],
) -> list[tuple[dict, float]]:
    donors = []
    for user in users:
        user_id = user.get("_id") or user.get("userId") or user.get("id")
        total = totals.get(user_id, 0)
        if user_id and total > 0:
            donors.append((user, total))
    donors.sort(
        key=lambda entry: (
            -entry[1],
            str(entry[0].get("username") or "").casefold(),
        )
    )
    return donors[:TOP_LIMIT]


def _format_money(value: float) -> str:
    if value.is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _build_embed(
    country_name: str,
    donors: list[tuple[dict, float]],
    start: datetime,
    end: datetime,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"Weekly Player Donations - {country_name}",
        color=discord.Color.gold(),
    )

    if not donors:
        embed.description = "*No player donations found for this country this week.*"
    else:
        lines = []
        for position, (user, total) in enumerate(donors, start=1):
            user_id = user.get("_id") or user.get("userId") or user.get("id")
            username = user.get("username") or f"Unknown user ({user_id})"
            lines.append(
                f"**{position}. [{username}](https://app.warera.io/user/{user_id})**"
                f" - {_format_money(float(total))} money"
            )
        embed.description = "\n".join(lines)

    embed.set_footer(
        text=(
            f"{start:%Y-%m-%d} to {end:%Y-%m-%d} UTC"
            " | Top 10"
        )
    )
    return embed


class TopUserWeeklyDonations(commands.Cog):
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

    async def _get_donation_total(
        self,
        user: dict,
        session,
        semaphore: asyncio.Semaphore,
        start: datetime,
        end: datetime,
    ) -> tuple[str | None, float]:
        user_id = user.get("_id") or user.get("userId") or user.get("id")
        if not user_id:
            return None, 0.0

        try:
            async with semaphore:
                transactions = await get_user_transactions(
                    user_id,
                    "donation",
                    session,
                )
        except Exception:
            logger.exception("Failed to fetch donations for user %s", user_id)
            return user_id, 0.0

        return user_id, _weekly_donation_total(
            user_id,
            transactions or [],
            start,
            end,
        )

    @app_commands.command(
        name="top_user_weekly_donations",
        description="Show the top 10 player donors from a country this week.",
    )
    @app_commands.describe(
        country="Country to rank (choose one from autocomplete)."
    )
    async def top_user_weekly_donations(
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
        users = await get_country_users(selected_country["_id"], session)
        if users is None:
            await interaction.followup.send(
                "Could not load the country's citizens. Please try again later.",
                ephemeral=True,
            )
            return

        now = datetime.now(timezone.utc)
        start = _week_start(now)
        semaphore = asyncio.Semaphore(TRANSACTION_CONCURRENCY)
        results = await asyncio.gather(
            *(
                self._get_donation_total(
                    user,
                    session,
                    semaphore,
                    start,
                    now,
                )
                for user in users
            )
        )
        totals = {
            user_id: total
            for user_id, total in results
            if user_id is not None
        }

        donors = _top_donors(users, totals)
        resolved_users = await asyncio.gather(
            *(
                get_user_info(
                    user.get("_id") or user.get("userId") or user.get("id"),
                    session,
                )
                for user, _ in donors
            )
        )
        resolved_donors = [
            (resolved_user or user, total)
            for (user, total), resolved_user in zip(donors, resolved_users)
        ]

        embed = _build_embed(
            selected_country["name"],
            resolved_donors,
            start,
            now,
        )
        await interaction.followup.send(embed=embed)

    @top_user_weekly_donations.autocomplete("country")
    async def country_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if self._countries_are_stale():
            self._schedule_country_refresh()
        return _country_choices(self._countries, current)


async def setup(bot: commands.Bot):
    await bot.add_cog(TopUserWeeklyDonations(bot))
