import asyncio
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import config
from utils import db
from utils.api import get_all_countries, get_shared_session


class NAPs(commands.Cog):
    nap = app_commands.Group(
        name="nap",
        description="Manage non-aggression pacts.",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._country_cache: dict = {"items": [], "fetched_at": 0.0}
        self._country_ttl = 300.0
        self._country_refresh_task: Optional[asyncio.Task] = None
        try:
            db.init_db()
        except Exception:
            pass

    async def cog_load(self):
        self._schedule_country_refresh()

    def cog_unload(self):
        if self._country_refresh_task and not self._country_refresh_task.done():
            self._country_refresh_task.cancel()

    def _schedule_country_refresh(self):
        if self._country_refresh_task and not self._country_refresh_task.done():
            return

        async def refresh():
            try:
                await self._countries()
            except Exception:
                return

        try:
            self._country_refresh_task = asyncio.create_task(refresh())
        except RuntimeError:
            self._country_refresh_task = None

    def _member_has_government(self, member: discord.Member) -> bool:
        gov_ids = config.get("roles", {}).get("government", [])
        return bool(gov_ids) and any(
            role.id in gov_ids for role in getattr(member, "roles", [])
        )

    async def _countries(self) -> list[dict]:
        now = time.time()
        items = self._country_cache.get("items") or []
        fetched_at = self._country_cache.get("fetched_at") or 0.0
        if items and now - fetched_at <= self._country_ttl:
            return items

        session = await get_shared_session()
        countries = await get_all_countries(session) or []
        if countries:
            countries.sort(key=lambda c: str(c.get("name", "")).lower())
            self._country_cache["items"] = countries
            self._country_cache["fetched_at"] = now
        return countries

    async def _find_country(self, name: str) -> Optional[dict]:
        wanted = (name or "").strip().lower()
        if not wanted:
            return None
        countries = await self._countries()
        for country in countries:
            if str(country.get("name", "")).lower() == wanted:
                return country
        return None

    async def _country_choices(self, current: str) -> list[app_commands.Choice[str]]:
        now = time.time()
        items = self._country_cache.get("items") or []
        fetched_at = self._country_cache.get("fetched_at") or 0.0

        if now - fetched_at > self._country_ttl:
            self._schedule_country_refresh()

        lower = (current or "").strip().lower()
        choices: list[app_commands.Choice[str]] = []
        for country in items:
            name = str(country.get("name") or "")
            if not name:
                continue
            if not lower or lower in name.lower():
                choices.append(app_commands.Choice(name=name, value=name))
            if len(choices) >= 25:
                break
        return choices

    @nap.command(name="add", description="Add a non-aggression pact between two countries.")
    @app_commands.describe(country_a="First country", country_b="Second country")
    async def add(
        self,
        interaction: discord.Interaction,
        country_a: str,
        country_b: str,
    ):
        if not self._member_has_government(interaction.user):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        first = await self._find_country(country_a)
        second = await self._find_country(country_b)

        if not first:
            await interaction.followup.send(f"Country '{country_a}' was not found.")
            return
        if not second:
            await interaction.followup.send(f"Country '{country_b}' was not found.")
            return
        if first.get("_id") == second.get("_id"):
            await interaction.followup.send("A NAP needs two different countries.")
            return

        created_at = interaction.created_at.date().isoformat()
        added = db.add_nap(first, second, created_at)
        first_name = first.get("name")
        second_name = second.get("name")
        if not added:
            await interaction.followup.send(
                f"A NAP between {first_name} and {second_name} already exists."
            )
            return

        await interaction.followup.send(f"Added NAP: {first_name} - {second_name}.")

    @nap.command(name="remove", description="Remove a non-aggression pact.")
    @app_commands.describe(country_a="First country", country_b="Second country")
    async def remove(
        self,
        interaction: discord.Interaction,
        country_a: str,
        country_b: str,
    ):
        if not self._member_has_government(interaction.user):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        first = await self._find_country(country_a)
        second = await self._find_country(country_b)

        if not first or not second:
            await interaction.followup.send("One or both countries were not found.")
            return

        removed = db.remove_nap(first["_id"], second["_id"])
        if not removed:
            await interaction.followup.send(
                f"No NAP exists between {first['name']} and {second['name']}."
            )
            return

        await interaction.followup.send(f"Removed NAP: {first['name']} - {second['name']}.")

    @nap.command(name="list", description="List configured non-aggression pacts.")
    async def list_naps(self, interaction: discord.Interaction):
        if not self._member_has_government(interaction.user):
            await interaction.response.send_message(
                "You are not authorized to use this command.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        naps = db.get_all_naps()
        embed = discord.Embed(title="Configured NAPs", color=discord.Color.blue())
        if not naps:
            embed.description = "No NAPs configured."
        else:
            lines = []
            for index, nap in enumerate(naps, start=1):
                lines.append(
                    f"{index}. {nap.get('country_a_name')} - {nap.get('country_b_name')}"
                )
            embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed)

    @add.autocomplete("country_a")
    @remove.autocomplete("country_a")
    async def country_a_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await self._country_choices(current)

    @add.autocomplete("country_b")
    @remove.autocomplete("country_b")
    async def country_b_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await self._country_choices(current)


async def setup(bot: commands.Bot):
    await bot.add_cog(NAPs(bot))
