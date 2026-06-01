import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
from config import config
from utils.api import get_user, get_shared_session

_INACTIVE_THRESHOLD_SECONDS = 3 * 24 * 3600
_PAGE_SIZE = 15


def _build_pages(items: list) -> list[discord.Embed]:
    title = "Inactive Players"
    if not items:
        embed = discord.Embed(title=title, description="*No inactive players found.*", color=discord.Color.green())
        embed.set_footer(text="Page 1 of 1 — Total: 0")
        return [embed]
    lines = [f"{name} — Level: {level} — {note}" for name, level, note in items]
    total = len(lines)
    total_pages = max(1, (total - 1) // _PAGE_SIZE + 1)
    pages = []
    for i in range(0, total, _PAGE_SIZE):
        chunk = lines[i : i + _PAGE_SIZE]
        embed = discord.Embed(title=title, color=discord.Color.red())
        embed.description = "\n".join(f"• {l}" for l in chunk)
        embed.set_footer(text=f"Page {i // _PAGE_SIZE + 1} of {total_pages} — Total: {total}")
        pages.append(embed)
    return pages


class _Paginator(discord.ui.View):
    def __init__(self, pages: list[discord.Embed], timeout: int = 180):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current = 0
        self.message: discord.Message | None = None
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

        guild = interaction.guild or self.bot.get_guild(config["guild"])
        if guild is None:
            await interaction.followup.send("Guild not found.", ephemeral=True)
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
                    inactive.append((member.display_name, level, f"Last active: {last_conn_str}"))
            except Exception:
                continue

        inactive.sort(key=lambda x: x[0].lower())
        pages = _build_pages(inactive)

        if len(pages) == 1:
            await interaction.followup.send(embed=pages[0])
        else:
            view = _Paginator(pages)
            msg = await interaction.followup.send(embed=pages[0], view=view, wait=True)
            view.message = msg


async def setup(bot: commands.Bot):
    await bot.add_cog(InactivePlayers(bot))
