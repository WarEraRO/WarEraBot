import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
from config import config
from utils.api import get_user, get_shared_session
from utils.i18n import Translator, get_translator

_INACTIVE_THRESHOLD_SECONDS = 3 * 24 * 3600
_PAGE_SIZE = 15


def _build_pages(items: list, tr: Translator) -> list[discord.Embed]:
    title = tr("inactive_players.title")
    if not items:
        embed = discord.Embed(title=title, description=tr("inactive_players.none_found"), color=discord.Color.green())
        embed.set_footer(text=tr("common.page_total", page=1, pages=1, total=0))
        return [embed]
    lines = [
        tr("inactive_players.line", name=name, level=level, last_active=last_active)
        for name, level, last_active in items
    ]
    total = len(lines)
    total_pages = max(1, (total - 1) // _PAGE_SIZE + 1)
    pages = []
    for i in range(0, total, _PAGE_SIZE):
        chunk = lines[i : i + _PAGE_SIZE]
        embed = discord.Embed(title=title, color=discord.Color.red())
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


class InactivePlayers(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="inactive_players",
        description="List players who have been inactive for more than 3 days.",
    )
    async def inactive_players(self, interaction: discord.Interaction):
        await interaction.response.defer()
        tr = await get_translator(interaction.guild_id)

        guild = interaction.guild or self.bot.get_guild(config["guild"])
        if guild is None:
            await interaction.followup.send(tr("common.guild_not_found"), ephemeral=True)
            return

        citizen = guild.get_role(config["roles"]["citizen"])
        newbie = guild.get_role(config["roles"]["newbie"])

        members: set[discord.Member] = set()
        if citizen:
            members.update(citizen.members)
        if newbie:
            members.update(newbie.members)

        session = await get_shared_session()
        inactive = []

        for member in members:
            try:
                user = await get_user(member.display_name, session)
            except Exception:
                user = None
            if not user:
                continue

            try:
                last_conn_str = (user.get("dates") or {}).get("lastConnectionAt")
                if not last_conn_str:
                    continue
                last_conn = datetime.fromisoformat(last_conn_str.replace("Z", "+00:00"))
                delta = datetime.now(timezone.utc) - last_conn
                if delta.total_seconds() >= _INACTIVE_THRESHOLD_SECONDS:
                    leveling = user.get("leveling", {}) or {}
                    level = leveling.get("level") if isinstance(leveling.get("level"), int) else None
                    inactive.append((member.display_name, level, last_conn_str))
            except Exception:
                continue

        inactive.sort(key=lambda x: x[0].lower())
        pages = _build_pages(inactive, tr)

        if len(pages) == 1:
            await interaction.followup.send(embed=pages[0])
        else:
            view = _Paginator(pages, tr)
            msg = await interaction.followup.send(embed=pages[0], view=view, wait=True)
            view.message = msg


async def setup(bot: commands.Bot):
    await bot.add_cog(InactivePlayers(bot))
