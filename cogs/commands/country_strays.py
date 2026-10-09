import discord
from discord import app_commands
from discord.ext import commands
from config import config
from utils.api import get_user, get_shared_session, get_all_countries, get_country
from utils.i18n import Translator, get_translator

_PAGE_SIZE = 15


def _build_pages(items: list[tuple], tr: Translator) -> list[discord.Embed]:
    title = tr("country_strays.title")
    if not items:
        embed = discord.Embed(title=title, description=tr("country_strays.none_found"), color=discord.Color.green())
        embed.set_footer(text=tr("common.page_total", page=1, pages=1, total=0))
        return [embed]
    lines = [f"{name} — {country}" for name, country in items]
    total = len(lines)
    total_pages = max(1, (total - 1) // _PAGE_SIZE + 1)
    pages = []
    for i in range(0, total, _PAGE_SIZE):
        chunk = lines[i : i + _PAGE_SIZE]
        embed = discord.Embed(title=title, color=discord.Color.orange())
        embed.description = "\n".join(f"• {l}" for l in chunk)
        embed.set_footer(text=tr("common.page_total", page=i // _PAGE_SIZE + 1, pages=total_pages, total=total))
        pages.append(embed)
    return pages


class _Paginator(discord.ui.View):
    def __init__(self, pages: list[discord.Embed], tr: Translator, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current = 0
        self.message: discord.Message | None = None
        self.prev_btn.label = tr("common.prev")
        self.next_btn.label = tr("common.next")
        self._sync()

    def _sync(self):
        self.prev_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current == len(self.pages) - 1

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.primary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = max(0, self.current - 1)
        self._sync()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = min(len(self.pages) - 1, self.current + 1)
        self._sync()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)


class CountryStrays(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._countries_cache: list | None = None

    @app_commands.command(
        name="country_strays",
        description="List players whose in-game citizenship is not in the configured allowed countries.",
    )
    async def country_strays(self, interaction: discord.Interaction):
        await interaction.response.defer()
        tr = await get_translator(interaction.guild_id)

        guild = interaction.guild or self.bot.get_guild(config["guild"])
        if guild is None:
            await interaction.followup.send(tr("common.guild_not_found"), ephemeral=True)
            return

        allowed = set(config.get("citizenship_countries", []) or [])
        citizen_role = guild.get_role(config["roles"].get("citizen"))
        newbie_role = guild.get_role(config["roles"].get("newbie"))

        members: set[discord.Member] = set()
        if citizen_role:
            members.update(citizen_role.members)
        if newbie_role:
            members.update(newbie_role.members)

        session = await get_shared_session()

        if self._countries_cache is None:
            try:
                self._countries_cache = await get_all_countries(session) or []
            except Exception:
                self._countries_cache = []

        issues: list[tuple] = []

        for member in members:
            try:
                user = await get_user(member.display_name, session)
            except Exception:
                user = None
            if not user:
                continue

            country_id = user.get("country")
            country_name = None
            for c in (self._countries_cache or []):
                if c.get("_id") == country_id:
                    country_name = c.get("name")
                    break

            if country_name is None:
                try:
                    country = await get_country(country_id, session)
                    if country:
                        country_name = country.get("name")
                        if self._countries_cache is not None:
                            self._countries_cache.append({"_id": country_id, "name": country_name})
                except Exception:
                    country_name = None

            if country_name not in allowed:
                issues.append((member.display_name, country_name or tr("common.unknown_title")))

        issues.sort(key=lambda x: x[0].lower())
        pages = _build_pages(issues, tr)

        if len(pages) == 1:
            await interaction.followup.send(embed=pages[0])
        else:
            view = _Paginator(pages, tr)
            msg = await interaction.followup.send(embed=pages[0], view=view, wait=True)
            view.message = msg


async def setup(bot: commands.Bot):
    await bot.add_cog(CountryStrays(bot))
