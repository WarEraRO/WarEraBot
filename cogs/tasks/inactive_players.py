from discord.ext import commands, tasks
from utils.api import get_user, get_shared_session
from config import config
import discord
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class InactivePlayersJob(commands.Cog):
    """Checks all server members for inactivity (lastConnectionAt > 3 days)

    Sends a red, button-paginated embed listing inactive players (10 per page).
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_loop.start()

    def cog_unload(self):
        self.check_loop.cancel()

    @tasks.loop(hours=24)
    async def check_loop(self):
        guild = self.bot.get_guild(config['guild'])
        if guild is None:
            return

        citizen = guild.get_role(config['roles']['citizen'])
        newbie = guild.get_role(config['roles']['newbie'])

        members = set()
        if citizen:
            members.update(citizen.members)
        if newbie:
            members.update(newbie.members)
        inactive = []

        session = await get_shared_session()
        for member in members:
            try:
                user = await get_user(member.display_name, session)
            except Exception:
                user = None

            if not user:
                # treat as missing data; skip here
                continue

            try:
                last_conn_str = (user.get('dates') or {}).get('lastConnectionAt')
                if not last_conn_str:
                    continue
                last_conn = datetime.fromisoformat(last_conn_str.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                delta = now - last_conn
                if delta.total_seconds() >= 3 * 24 * 3600:
                    leveling = user.get('leveling', {}) or {}
                    level = leveling.get('level') if isinstance(leveling.get('level'), int) else None
                    inactive.append((member.display_name, level, f'Last active: {last_conn_str}'))
            except Exception:
                continue

        if not inactive:
            return

        embeds = build_paginated_embeds('Inactive Players', inactive, page_size=10, color=discord.Color.red())
        channel = guild.get_channel(config.get('channels', {}).get('reports')) if guild else None
        if channel:
            await send_paginated_buttons(channel, self.bot, embeds)

    @check_loop.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


def build_paginated_embeds(title: str, items: list, page_size: int = 10, color: discord.Color = discord.Color.red()) -> list:
    pages = []
    lines = []
    for it in items:
        if isinstance(it, tuple):
            if len(it) == 3:
                lines.append(f"{it[0]} — Level: {it[1]} — {it[2]}")
            elif len(it) == 2:
                lines.append(f"{it[0]} — {it[1]}")
            else:
                lines.append(str(it))
        else:
            lines.append(str(it))

    for i in range(0, len(lines), page_size):
        chunk = lines[i:i + page_size]
        embed = discord.Embed(title=title, color=color)
        desc = "\n".join(f"* {l}" for l in chunk)
        embed.description = desc or 'None'
        embed.set_footer(text=f"Page {i // page_size + 1} of {((len(lines)-1)//page_size)+1} — Total: {len(lines)}")
        pages.append(embed)

    return pages


async def send_paginated_buttons(channel: discord.TextChannel, bot: commands.Bot, embeds: list, timeout: int = 120):
    if not embeds:
        return

    class Paginator(discord.ui.View):
        def __init__(self, embeds, timeout):
            super().__init__(timeout=timeout)
            self.embeds = embeds
            self.current = 0

        async def on_timeout(self):
            try:
                for item in self.children:
                    item.disabled = True
                if hasattr(self, "message") and self.message:
                    await self.message.edit(view=self)
            except Exception:
                pass

        def _update_button_states(self):
            last_index = len(self.embeds) - 1
            if len(self.children) >= 4:
                self.children[0].disabled = self.current == 0
                self.children[1].disabled = self.current == 0
                self.children[2].disabled = self.current == last_index
                self.children[3].disabled = self.current == last_index

        @discord.ui.button(label='First', style=discord.ButtonStyle.secondary)
        async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.bot:
                return
            self.current = 0
            self._update_button_states()
            await interaction.response.edit_message(embed=self.embeds[self.current], view=self)

        @discord.ui.button(label='Prev', style=discord.ButtonStyle.primary)
        async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.bot:
                return
            self.current = max(0, self.current - 1)
            self._update_button_states()
            await interaction.response.edit_message(embed=self.embeds[self.current], view=self)

        @discord.ui.button(label='Next', style=discord.ButtonStyle.primary)
        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.bot:
                return
            self.current = min(len(self.embeds) - 1, self.current + 1)
            self._update_button_states()
            await interaction.response.edit_message(embed=self.embeds[self.current], view=self)

        @discord.ui.button(label='Last', style=discord.ButtonStyle.secondary)
        async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.bot:
                return
            self.current = len(self.embeds) - 1
            self._update_button_states()
            await interaction.response.edit_message(embed=self.embeds[self.current], view=self)

    view = Paginator(embeds, timeout)
    msg = await channel.send(embed=embeds[0], view=view)
    view.message = msg
    view._update_button_states()
    try:
        await msg.edit(view=view)
    except Exception:
        pass

async def setup(bot: commands.Bot):
    await bot.add_cog(InactivePlayersJob(bot))
