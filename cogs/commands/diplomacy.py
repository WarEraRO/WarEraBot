import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
from config import config
from utils import db
from utils.api import get_all_country_names
import math
import time
import asyncio


STATUS_OPTIONS = [
    "Neutral",
    "Enemy",
    "Friend",
    "Proxy",
    "Neutral Proxy",
    "Enemy Proxy",
    "Proxy Friend",
    "Mercenary",
    "Mixed Proxy",
]

# priority for sorting (lower == higher priority)
STATUS_PRIORITY = {
    'Friend': 0,
    'Proxy Friend': 1,
    'Neutral': 2,
    'Neutral Proxy': 3,
    'Proxy': 4,
    'Mixed Proxy': 5,
    'Mercenary': 6,
    'Enemy Proxy': 7,
    'Enemy': 8,
}


class Diplomacy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # cached list of countries for autocomplete
        self._country_cache: dict = {'items': [], 'fetched_at': 0.0}
        self._country_ttl: float = 300.0
        self._country_refresh_task: asyncio.Task | None = None

    async def _get_guild(self, interaction: discord.Interaction) -> Optional[discord.Guild]:
        return interaction.guild or self.bot.get_guild(config.get('guild'))

    def _member_has_government(self, member: discord.Member) -> bool:
        gov_ids = config.get('roles', {}).get('government', [])
        if not gov_ids:
            return False
        return any(r.id in gov_ids for r in getattr(member, 'roles', []))

    def _normalize_status(self, s: str) -> str:
        # Normalize to Title Case so it matches entries in STATUS_OPTIONS
        return (s or '').strip().title()

    def _build_country_record(self, country: str, record: Optional[dict]) -> dict:
        if not record:
            return {'country_name': country, 'status': None, 'description': None, 'diplomacy': []}
        return {'country_name': country, 'status': record.get('status'), 'description': record.get('description'), 'diplomacy': record.get('diplomacy') or []}

    @app_commands.command(name="diplomacy", description="Show diplomacy info for countries (paginated).")
    @app_commands.describe(country_name="Optional country name to show details for")
    async def diplomacy(self, interaction: discord.Interaction, country_name: Optional[str] = None):
        await interaction.response.defer()
        guild = await self._get_guild(interaction)

        active = await get_all_country_names()
        if country_name:
            # show specific country details
            # find best match from config
            match = None
            for c in active:
                if c.lower() == country_name.strip().lower():
                    match = c
                    break
            if not match:
                # attempt substring match
                for c in active:
                    if country_name.strip().lower() in c.lower():
                        match = c
                        break

            if not match:
                await interaction.followup.send(f"Country '{country_name}' not found.")
                return

            rec = db.get_diplomacy(match) or {}
            has_gov = False
            try:
                has_gov = self._member_has_government(interaction.user)
            except Exception:
                has_gov = False

            embed = discord.Embed(title=f"Diplomacy — {match}", color=discord.Color.green())
            status = rec.get('status') or 'Unknown'
            desc = rec.get('description') or 'No description.'
            embed.add_field(name="Status", value=status, inline=False)
            embed.add_field(name="Description", value=desc or 'No description.', inline=False)
            if has_gov:
                entries = rec.get('diplomacy') or []
                if entries:
                    lines = [f"{i+1}. {e}" for i, e in enumerate(entries)]
                    embed.add_field(name="Diplomacy List", value="\n".join(lines), inline=False)
                else:
                    embed.add_field(name="Diplomacy List", value="(empty)", inline=False)
            await interaction.followup.send(embed=embed)
            return

        # show only countries that have diplomacies created (paginated, 3 per page)
        all_recs = db.get_all_diplomacies()
        if not all_recs:
            await interaction.followup.send("No diplomacies have been created.")
            return

        countries = [self._build_country_record(c, rec) for c, rec in all_recs.items()]

        # default sort: alphabetical
        countries.sort(key=lambda x: x['country_name'].lower())

        paginator = self.DiplomacyPaginator(countries, interaction.user, per_page=3)
        await paginator.start(interaction)

    async def _generate_country_choices(self, current: str) -> List[app_commands.Choice[str]]:
        # Provide up-to-date autocomplete using a cached fetch of get_all_country_names().
        now = time.time()
        items = self._country_cache.get('items') or []
        fetched = self._country_cache.get('fetched_at') or 0.0

        # If cache expired and no refresh task running, start a background refresh
        if now - fetched > self._country_ttl:
            if not self._country_refresh_task or self._country_refresh_task.done():
                async def _refresh():
                    try:
                        new_items = await get_all_country_names()
                        if new_items:
                            self._country_cache['items'] = new_items
                            self._country_cache['fetched_at'] = time.time()
                    except Exception:
                        return

                try:
                    self._country_refresh_task = asyncio.create_task(_refresh())
                except RuntimeError:
                    self._country_refresh_task = None

        lower = (current or '').strip().lower()
        choices: List[app_commands.Choice[str]] = []
        for c in items:
            if not c:
                continue
            if not lower or lower in c.lower():
                choices.append(app_commands.Choice(name=c, value=c))
            if len(choices) >= 25:
                break
        return choices
    

    @app_commands.command(name="update_diplomacy", description="Update diplomacy status/description/entries for a country (government only).")
    @app_commands.describe(country_name="Country name", status="Diplomacy status (optional)", diplomacy="Diplomacy entry to append (optional)", description="Optional description")
    async def update_diplomacy(self, interaction: discord.Interaction, country_name: str, status: Optional[str] = None, diplomacy: Optional[str] = None, description: Optional[str] = None):
        # permission check
        if not self._member_has_government(interaction.user):
            await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
            return

        # defer because we may do DB work
        await interaction.response.defer()

        # validate provided status (if any)
        status_n = None
        if status is not None:
            status_n = self._normalize_status(status)
            if status_n not in STATUS_OPTIONS:
                await interaction.followup.send(f"Invalid status. Allowed: {', '.join(STATUS_OPTIONS)}", ephemeral=True)
                return

        # ensure country exists
        active = await get_all_country_names()
        match = None
        for c in active:
            if c.lower() == country_name.strip().lower():
                match = c
                break
        if not match:
            await interaction.followup.send(f"Country '{country_name}' not found.", ephemeral=True)
            return

        # If nothing provided to update, inform the user
        if status_n is None and diplomacy is None and description is None:
            await interaction.followup.send("No updates provided. Specify at least one of `status`, `diplomacy`, or `description`.", ephemeral=True)
            return

        # Apply updates: append diplomacy entry if provided, update status/description if provided
        if diplomacy is not None:
            # create row if missing and then append
            existing = db.get_diplomacy(match)
            if not existing:
                db.update_diplomacy(match, status=None, description=None)
            db.add_diplomacy_entry(match, diplomacy)

        if status_n is not None or description is not None:
            db.update_diplomacy(match, status=status_n, description=description)

        parts: list[str] = []
        if status_n is not None:
            parts.append(f"status: {status_n}")
        if diplomacy is not None:
            parts.append("diplomacy entry added")
        if description is not None:
            parts.append("description updated")

        await interaction.followup.send(f"Updated '{match}' ({', '.join(parts)}).")

    @app_commands.command(name="add_diplomacy", description="Create a diplomacy record for a country (government only).")
    @app_commands.describe(country_name="Country name", status="Optional status", description="Optional description")
    async def add_diplomacy(self, interaction: discord.Interaction, country_name: str, status: Optional[str] = None, description: Optional[str] = None):
        # permission check
        if not self._member_has_government(interaction.user):
            await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
            return

        # defer for DB/network operations
        await interaction.response.defer()

        # validate status if provided
        status_n = None
        if status is not None:
            status_n = self._normalize_status(status)
            if status_n not in STATUS_OPTIONS:
                await interaction.followup.send(f"Invalid status. Allowed: {', '.join(STATUS_OPTIONS)}", ephemeral=True)
                return

        # ensure country exists
        active = await get_all_country_names()
        match = None
        for c in active:
            if c.lower() == country_name.strip().lower():
                match = c
                break
        if not match:
            await interaction.followup.send(f"Country '{country_name}' not found.", ephemeral=True)
            return

        # if a diplomacy already exists for this country, ignore and instruct to use update_diplomacy
        existing = db.get_diplomacy(match)
        if existing:
            await interaction.followup.send(f"Diplomacy for '{match}' already exists. Use `/update_diplomacy` to modify it.", ephemeral=True)
            return

        # create new diplomacy record (diplomacy list empty)
        db.update_diplomacy(match, status=status_n, description=description)
        await interaction.followup.send(f"Diplomacy for '{match}' created.")

    @app_commands.command(name="remove_diplomacy", description="Remove an entry from a country's diplomacy list (government only).")
    @app_commands.describe(country_name="Country name", position="1-based position to remove")
    async def remove_diplomacy(self, interaction: discord.Interaction, country_name: str, position: int):
        if not self._member_has_government(interaction.user):
            await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
            return

        active = await get_all_country_names()
        match = None
        for c in active:
            if c.lower() == country_name.strip().lower():
                match = c
                break
        if not match:
            await interaction.response.send_message(f"Country '{country_name}' not found.", ephemeral=True)
            return

        ok = db.remove_diplomacy_entry(match, position)
        if not ok:
            await interaction.response.send_message(f"Could not remove entry {position} for '{match}'.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Removed entry {position} for '{match}'.")

    @app_commands.command(name="delete_diplomacy", description="Delete the diplomacy record for a country (government only).")
    @app_commands.describe(country_name="Country name")
    async def delete_diplomacy(self, interaction: discord.Interaction, country_name: str):
        if not self._member_has_government(interaction.user):
            await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
            return
        # defer because fetching country list may take time
        await interaction.response.defer()

        active = await get_all_country_names()
        match = None
        for c in active:
            if c.lower() == country_name.strip().lower():
                match = c
                break
        if not match:
            await interaction.followup.send(f"Country '{country_name}' not found.", ephemeral=True)
            return

        ok = db.delete_diplomacy(match)
        if not ok:
            await interaction.followup.send(f"No diplomacy record found for '{match}'.", ephemeral=True)
        else:
            await interaction.followup.send(f"Diplomacy for '{match}' deleted.")

    @diplomacy.autocomplete('country_name')
    async def diplomacy_country_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return await self._generate_country_choices(current)

    @update_diplomacy.autocomplete('country_name')
    async def update_country_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return await self._generate_country_choices(current)

    @add_diplomacy.autocomplete('country_name')
    async def add_country_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return await self._generate_country_choices(current)

    @add_diplomacy.autocomplete('status')
    async def add_status_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        lower = (current or '').strip().lower()
        choices: List[app_commands.Choice[str]] = []
        for s in STATUS_OPTIONS:
            if not lower or lower in s.lower():
                choices.append(app_commands.Choice(name=s, value=s))
            if len(choices) >= 25:
                break
        return choices


    @remove_diplomacy.autocomplete('country_name')
    async def remove_country_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return await self._generate_country_choices(current)

    @update_diplomacy.autocomplete('status')
    async def update_status_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        lower = (current or '').strip().lower()
        choices: List[app_commands.Choice[str]] = []
        for s in STATUS_OPTIONS:
            if not lower or lower in s.lower():
                choices.append(app_commands.Choice(name=s, value=s))
            if len(choices) >= 25:
                break
        return choices

    class DiplomacyPaginator(discord.ui.View):
        def __init__(self, countries: List[dict], author, per_page: int = 3, timeout: float = 120.0):
            super().__init__(timeout=timeout)
            self.countries = countries
            self.author = author
            self.per_page = per_page
            self.index = 0
            self.embeds: List[discord.Embed] = []
            self.current_sort = 'alpha'  # or 'status'
            self.build_embeds()

        def build_embeds(self):
            items = list(self.countries)
            if self.current_sort == 'status':
                def key_fn(c):
                    pri = STATUS_PRIORITY.get(c.get('status') or '', 999)
                    return (pri, c.get('country_name').lower())
                items.sort(key=key_fn)
            else:
                items.sort(key=lambda x: x.get('country_name').lower())

            per = self.per_page
            pages = max(1, math.ceil(len(items) / per))
            embeds: List[discord.Embed] = []
            for p in range(pages):
                chunk = items[p*per:(p+1)*per]
                embed = discord.Embed(title="Diplomacies", color=discord.Color.blue())
                for c in chunk:
                    name = c.get('country_name')
                    status = c.get('status') or 'Unknown'
                    desc = c.get('description') or ''
                    short = desc if len(desc) < 200 else desc[:197] + '...'
                    embed.add_field(name=f"{name} — {status}", value=short or '(no description)', inline=False)
                embed.set_footer(text=f"Page {p+1}/{pages} — Sorted: {self.current_sort}")
                embeds.append(embed)
            self.embeds = embeds

        async def start(self, interaction: discord.Interaction):
            try:
                self.message = await interaction.followup.send(embed=self.embeds[self.index], view=self)
            except Exception:
                channel = getattr(interaction, 'channel', None)
                if channel:
                    self.message = await channel.send(embed=self.embeds[self.index], view=self)
                else:
                    raise
            return self.message

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            return True

        @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.index = (self.index - 1) % len(self.embeds)
            await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

        @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.index = (self.index + 1) % len(self.embeds)
            await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

        @discord.ui.button(emoji="🔀", label="Sort by status", style=discord.ButtonStyle.primary)
        async def toggle_sort(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_sort = 'status' if self.current_sort == 'alpha' else 'alpha'
            self.build_embeds()
            self.index = 0
            await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

        @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
        async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                self.stop()
            except Exception:
                pass
            await interaction.response.edit_message(view=None)


async def setup(bot: commands.Bot):
    await bot.add_cog(Diplomacy(bot))
