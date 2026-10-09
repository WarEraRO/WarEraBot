import discord
from discord import app_commands
from discord.ext import commands
from typing import List

from utils.i18n import Translator, get_translator

# ---------------------------------------------------------------------------
# Static data: help.commands.<id> and help.jobs.<id> in the locale files hold
# the field name ("name") and field value ("desc") of each entry, in this order
# ---------------------------------------------------------------------------

_COMMAND_IDS: List[str] = [
    "diplomacy",
    "update_diplomacy",
    "add_diplomacy",
    "remove_diplomacy",
    "delete_diplomacy",
    "nap",
    "priority",
    "fightstatus",
    "country_strays",
    "discorless",
    "inactive_players",
    "mu_stray",
    "pills",
    "promotions",
    "top_user_weekly_damages",
    "top_user_weekly_donations",
    "get_region_upgrade_cost",
    "run_job",
    "setlang",
]

_JOB_IDS: List[str] = [
    "skill_roles",
    "military_unit_roles",
    "commander_roles",
    "unidentified_members",
    "takeover_countries",
    "buff_monitor",
    "bounty_monitor",
    "mercenary_contracts",
    "mu_contract_monitor",
    "monitor_nap",
    "battle_order_monitor",
    "reddit_monitor",
]

_COMMANDS_PER_PAGE = 3
_JOBS_PER_PAGE = 4


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def _build_command_pages(tr: Translator) -> List[discord.Embed]:
    pages: List[discord.Embed] = []
    total = len(_COMMAND_IDS)
    total_pages = max(1, (total - 1) // _COMMANDS_PER_PAGE + 1)
    for i in range(0, total, _COMMANDS_PER_PAGE):
        chunk = _COMMAND_IDS[i : i + _COMMANDS_PER_PAGE]
        embed = discord.Embed(title=tr("help.commands_title"), color=discord.Color.blurple())
        embed.description = tr("help.commands_description")
        for command_id in chunk:
            embed.add_field(name=tr(f"help.commands.{command_id}.name"), value=tr(f"help.commands.{command_id}.desc"), inline=False)
        embed.set_footer(text=tr("help.commands_footer", page=i // _COMMANDS_PER_PAGE + 1, pages=total_pages))
        pages.append(embed)
    return pages


def _build_job_pages(tr: Translator) -> List[discord.Embed]:
    pages: List[discord.Embed] = []
    total = len(_JOB_IDS)
    total_pages = max(1, (total - 1) // _JOBS_PER_PAGE + 1)
    for i in range(0, total, _JOBS_PER_PAGE):
        chunk = _JOB_IDS[i : i + _JOBS_PER_PAGE]
        embed = discord.Embed(title=tr("help.jobs_title"), color=discord.Color.dark_gold())
        embed.description = tr("help.jobs_description")
        for job_id in chunk:
            embed.add_field(name=tr(f"help.jobs.{job_id}.name"), value=tr(f"help.jobs.{job_id}.desc"), inline=False)
        embed.set_footer(text=tr("help.jobs_footer", page=i // _JOBS_PER_PAGE + 1, pages=total_pages))
        pages.append(embed)
    return pages


# ---------------------------------------------------------------------------
# Paginator view
# ---------------------------------------------------------------------------

class _HelpPaginator(discord.ui.View):
    def __init__(self, tr: Translator, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self._commands_pages = _build_command_pages(tr)
        self._jobs_pages = _build_job_pages(tr)
        self.active_section: str = "commands"  # "commands" | "jobs"
        self.page_index: dict[str, int] = {"commands": 0, "jobs": 0}
        self.message: discord.Message | None = None
        self.prev_btn.label = tr("common.prev")
        self.next_btn.label = tr("common.next")
        self.btn_commands.label = tr("help.commands_button")
        self.btn_jobs.label = tr("help.jobs_button")
        self._sync()

    # ------------------------------------------------------------------ helpers

    @property
    def _current_pages(self) -> List[discord.Embed]:
        return self._commands_pages if self.active_section == "commands" else self._jobs_pages

    @property
    def _current_page(self) -> int:
        return self.page_index[self.active_section]

    @_current_page.setter
    def _current_page(self, value: int) -> None:
        self.page_index[self.active_section] = value

    def _sync(self) -> None:
        last = len(self._current_pages) - 1
        cur = self._current_page
        self.prev_btn.disabled = cur == 0
        self.next_btn.disabled = cur == last
        self.btn_commands.style = (
            discord.ButtonStyle.success if self.active_section == "commands" else discord.ButtonStyle.secondary
        )
        self.btn_jobs.style = (
            discord.ButtonStyle.success if self.active_section == "jobs" else discord.ButtonStyle.secondary
        )

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self._sync()
        await interaction.response.edit_message(embed=self._current_pages[self._current_page], view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    # ------------------------------------------------------------------ row 0: navigation

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.primary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._current_page = max(0, self._current_page - 1)
        await self._refresh(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._current_page = min(len(self._current_pages) - 1, self._current_page + 1)
        await self._refresh(interaction)

    # ------------------------------------------------------------------ row 1: section filters

    @discord.ui.button(label="Commands", style=discord.ButtonStyle.success, custom_id="help_commands", row=1)
    async def btn_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_section = "commands"
        await self._refresh(interaction)

    @discord.ui.button(label="Jobs", style=discord.ButtonStyle.secondary, custom_id="help_jobs", row=1)
    async def btn_jobs(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.active_section = "jobs"
        await self._refresh(interaction)


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show bot commands and background jobs (paginated).")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer()
        tr = await get_translator(interaction.guild_id)
        view = _HelpPaginator(tr)
        embed = view._current_pages[view._current_page]
        try:
            msg = await interaction.followup.send(embed=embed, view=view, wait=True)
            view.message = msg
        except Exception:
            channel = getattr(interaction, "channel", None)
            if channel:
                msg = await channel.send(embed=embed, view=view)
                view.message = msg
            else:
                await interaction.followup.send(tr("help.unavailable"))


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
