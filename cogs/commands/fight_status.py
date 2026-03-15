import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from utils.api import get_user, get_fight_status
from config import config

HEADERS = {'X-API-Key': config['api']}

class FightStatus(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="fightstatus", description="Fetch fight status for all members with the fight role and paginate results.")
    async def fightstatus(self, interaction: discord.Interaction):
        """Fetch fight status for all members with the fight role and paginate results."""
        guild = interaction.guild or self.bot.get_guild(config['guild'])
        if guild is None:
            await interaction.response.send_message("Guild not found.")
            return

        fight_role = guild.get_role(config['roles']['fight'])
        if fight_role is None:
            await interaction.response.send_message("Fight role not configured.")
            return

        members = fight_role.members
        if not members:
            await interaction.response.send_message("No fighters found.")
            return

        # defer because we will likely make network requests
        await interaction.response.defer()

        infos: list[dict] = []
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for member in members:
                # attempt to resolve WarEra user and fetch info; always include a fallback
                warera_user = None
                try:
                    warera_user = await get_user(member.display_name, session)
                except Exception:
                    warera_user = None

                info = None
                if warera_user:
                    warera_id = warera_user.get('_id') or warera_user.get('id')
                    if warera_id:
                        try:
                            info = await get_fight_status(str(warera_id), session, member)
                        except Exception:
                            info = None

                # if we couldn't fetch WarEra data, use Discord fallback so every fighter appears
                if not info:
                    info = {
                        'userId': str(member.id),
                        'warera_name': None,
                        'display_name': member.display_name,
                        'avatar_url': None,
                        'level': 'N/A',
                        'is_active': False,
                        'health_curr': None,
                        'health_total': None,
                        'hunger_curr': None,
                        'hunger_total': None,
                        'buff_text': '',
                        'buff_type': None,
                        'buff_end_at': None,
                        'buff_active': False,
                    }
                infos.append(info)

        if not infos:
            await interaction.followup.send("No fighter information available.")
            return

        # Sort fighters: buffed (active) first, neutral/expired second, debuffed (active) last
        def _sort_key(info):
            bt = info.get('buff_type')
            active = info.get('buff_active')
            if bt == 'Buff' and active:
                rank = 0
            elif bt == 'Debuff' and active:
                rank = 2
            else:
                rank = 1
            name = (info.get('display_name') or info.get('warera_name') or "").lower()
            return (rank, name)

        infos.sort(key=_sort_key)

        paginator = self.FightEmbedPaginator(infos, interaction.user, per_page=10)
        await paginator.start(interaction)

    class FightEmbedPaginator(discord.ui.View):
        def __init__(self, infos: list[dict], author, per_page: int = 10, timeout: float = 120.0):
            super().__init__(timeout=timeout)
            self.raw_infos = infos
            self.author = author
            self.per_page = per_page
            self.index = 0
            self.message: discord.Message | None = None
            self.embeds: list[discord.Embed] = []
            self.current_filter: str | None = None
            self.build_embeds()

        def _update_footer(self):
            if not self.embeds:
                return
            embed = self.embeds[self.index]
            embed.set_footer(text=f"Page {self.index+1}/{len(self.embeds)}")

        def build_embeds(self, filter_mode: str | None = None):
            # allow explicit None to clear filters
            self.current_filter = filter_mode

            def _stat_key(info):
                try:
                    health = float(info.get('health_curr') or 0)
                except Exception:
                    health = 0.0
                try:
                    hunger = float(info.get('hunger_curr') or 0)
                except Exception:
                    hunger = 0.0
                name = (info.get('display_name') or info.get('warera_name') or "").lower()
                return (-health, -hunger, name)

            # Build filtered list and sort groups by health then hunger (desc)
            if self.current_filter == 'buffed':
                group = [i for i in self.raw_infos if i.get('buff_type') == 'Buff' and i.get('buff_active')]
                filtered = sorted(group, key=_stat_key)
            elif self.current_filter == 'debuffed':
                group = [i for i in self.raw_infos if i.get('buff_type') == 'Debuff' and i.get('buff_active')]
                filtered = sorted(group, key=_stat_key)
            elif self.current_filter == 'neutral':
                group = [i for i in self.raw_infos if not i.get('buff_type') or not i.get('buff_active')]
                filtered = sorted(group, key=_stat_key)
            else:
                # 'All' view — keep buffed first, neutral second, debuffed last
                buffed = [i for i in self.raw_infos if i.get('buff_type') == 'Buff' and i.get('buff_active')]
                neutral = [i for i in self.raw_infos if not i.get('buff_type') or not i.get('buff_active')]
                debuffed = [i for i in self.raw_infos if i.get('buff_type') == 'Debuff' and i.get('buff_active')]
                buffed_sorted = sorted(buffed, key=_stat_key)
                neutral_sorted = sorted(neutral, key=_stat_key)
                debuffed_sorted = sorted(debuffed, key=_stat_key)
                filtered = buffed_sorted + neutral_sorted + debuffed_sorted

            pages: list[discord.Embed] = []
            per_page = self.per_page
            total_pages = max(1, (len(filtered) + per_page - 1) // per_page)

            for p in range(total_pages):
                chunk = filtered[p * per_page:(p + 1) * per_page]
                embed = discord.Embed(title="Fighters Status", color=discord.Color.blurple())
                lines: list[str] = []
                for i, info in enumerate(chunk):
                    name_display = info.get('display_name') or info.get('warera_name') or f"User {info.get('userId')}"
                    buff_type = info.get('buff_type')
                    buff_active = info.get('buff_active')
                    if buff_type == 'Buff':
                        status_label = '🟢 Buffed' if buff_active else '🟡 Buff expired'
                    elif buff_type == 'Debuff':
                        status_label = '🔴 Debuffed' if buff_active else '🟡 Debuff expired'
                    else:
                        status_label = '⚪ No status'

                    level = info.get('level', 'N/A')
                    online = 'Yes' if info.get('is_active') else 'No'
                    health_curr = info.get('health_curr')
                    health_total = info.get('health_total')
                    hunger_curr = info.get('hunger_curr')
                    hunger_total = info.get('hunger_total')

                    def fmt_curr(val):
                        try:
                            return f"{round(float(val), 1):.1f}"
                        except Exception:
                            return 'N/A'

                    health_curr_fmt = fmt_curr(health_curr)
                    hunger_curr_fmt = fmt_curr(hunger_curr)
                    health_str = f"{health_curr_fmt}/{health_total if health_total is not None else 'N/A'}"
                    hunger_str = f"{hunger_curr_fmt}/{hunger_total if hunger_total is not None else 'N/A'}"

                    flag = '🇷🇴'
                    line1 = f"{flag} {name_display} — Level: {level} • Online: {online}"
                    line2 = f"❤️ {health_str} • 🍔 {hunger_str}"
                    buff_text = (info.get('buff_text') or '').strip()
                    if buff_type:
                        if buff_text and buff_text.lower() != 'no buff/debuff':
                            status_line = f"{status_label} • 🕒 {buff_text}"
                        else:
                            status_line = f"{status_label}"
                    else:
                        status_line = status_label

                    player_block = f"{line1}\n{line2}\n{status_line}"
                    lines.append(player_block)

                chunk_text = "\n\n".join(lines) or "No data"
                embed.add_field(name="Players", value=chunk_text, inline=False)
                embed.set_footer(text=f"Page {p+1}/{total_pages}")
                pages.append(embed)

            self.embeds = pages

        async def start(self, interaction: discord.Interaction):
            self._update_footer()
            try:
                # we've deferred earlier in the command, so use followup
                self.message = await interaction.followup.send(embed=self.embeds[self.index], view=self)
            except Exception:
                # fallback to channel send if followup is unavailable
                channel = getattr(interaction, 'channel', None)
                if channel:
                    self.message = await channel.send(embed=self.embeds[self.index], view=self)
                else:
                    raise
            return self.message

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            # allow anyone to interact with the paginator
            return True

        @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary)
        async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.index = 0
            self._update_footer()
            await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

        @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
        async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.index = (self.index - 1) % len(self.embeds)
            self._update_footer()
            await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

        @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
        async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            # stop the view and remove buttons
            try:
                self.stop()
            except Exception:
                try:
                    discord.ui.View.stop(self)
                except Exception:
                    pass
            await interaction.response.edit_message(view=None)

        @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.index = (self.index + 1) % len(self.embeds)
            self._update_footer()
            await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

        @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
        async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.index = len(self.embeds) - 1
            self._update_footer()
            await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

        @discord.ui.button(label="Buffed", style=discord.ButtonStyle.primary)
        async def buffed_filter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.build_embeds(filter_mode='buffed')
            self.index = 0
            self._update_footer()
            await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

        @discord.ui.button(label="Neutral", style=discord.ButtonStyle.secondary)
        async def neutral_filter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.build_embeds(filter_mode='neutral')
            self.index = 0
            self._update_footer()
            await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

        @discord.ui.button(label="Debuffed", style=discord.ButtonStyle.danger)
        async def debuffed_filter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.build_embeds(filter_mode='debuffed')
            self.index = 0
            self._update_footer()
            await interaction.response.edit_message(embed=self.embeds[self.index], view=self)
        
        @discord.ui.button(label="All", style=discord.ButtonStyle.secondary)
        async def all_filter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            # clear any filter and rebuild pages (show all groups)
            self.build_embeds(filter_mode=None)
            self.index = 0
            self._update_footer()
            await interaction.response.edit_message(embed=self.embeds[self.index], view=self)


async def setup(bot: commands.Bot):
    await bot.add_cog(FightStatus(bot))
