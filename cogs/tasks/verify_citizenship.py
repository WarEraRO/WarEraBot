from discord.ext import commands, tasks
import discord
import logging
from config import config
from utils.api import get_shared_session, get_user, get_all_countries, get_country

logger = logging.getLogger(__name__)


class VerifyCitizenshipJob(commands.Cog):
    """Checks newbies and citizens to ensure their WarEra country matches
    the configured list of allowed citizenship countries.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.countries = None
        self.verify_loop.start()

    def cog_unload(self):
        self.verify_loop.cancel()

    async def get_countries(self):
        session = await get_shared_session()
        return await get_all_countries(session)

    @tasks.loop(hours=12)
    async def verify_loop(self):
        guild = self.bot.get_guild(config['guild'])
        if guild is None:
            return

        allowed = set(config.get('citizenship_countries', []) or [])

        citizen_role = guild.get_role(config['roles'].get('citizen'))
        newbie_role = guild.get_role(config['roles'].get('newbie'))

        members = set()
        if citizen_role:
            members.update(citizen_role.members)
        if newbie_role:
            members.update(newbie_role.members)

        if not members:
            return

        # Ensure cache of countries
        if self.countries is None:
            try:
                self.countries = await self.get_countries() or []
            except Exception:
                self.countries = []

        session = await get_shared_session()
        issues = []

        for member in members:
            try:
                user = await get_user(member.display_name, session)
            except Exception:
                user = None

            if not user:
                continue

            country_id = user.get('country')
            country_name = None
            for c in (self.countries or []):
                if c.get('_id') == country_id:
                    country_name = c.get('name')
                    break

            if country_name is None:
                try:
                    country = await get_country(country_id, session)
                    if country:
                        country_name = country.get('name')
                except Exception:
                    country_name = None

            if country_name not in allowed:
                issues.append((member.display_name, country_name))

        if not issues:
            return

        # Build embed(s) and send to reports channel
        channel = guild.get_channel(config.get('channels', {}).get('reports')) if guild else None
        if not channel:
            return

        # Build paginated embeds and send using button paginator
        embeds = build_paginated_embeds('Citizenship Issues', issues, page_size=10, color=discord.Color.orange())
        try:
            await send_paginated_buttons(channel, self.bot, embeds)
        except Exception:
            logger.exception('Failed sending citizenship report')

    @verify_loop.before_loop
    async def before_verify(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(VerifyCitizenshipJob(bot))


def build_paginated_embeds(title: str, items: list, page_size: int = 10, color: discord.Color = discord.Color.orange()) -> list:
    pages = []
    lines = []
    for it in items:
        if isinstance(it, tuple):
            if len(it) == 2:
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