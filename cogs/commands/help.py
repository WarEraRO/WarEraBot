import discord
from discord import app_commands
from discord.ext import commands
from typing import List

# ---------------------------------------------------------------------------
# Static data: (field_name, field_value) for each entry
# ---------------------------------------------------------------------------

_COMMANDS_DATA: List[tuple[str, str]] = [
    (
        "/diplomacy [country_name]",
        "Show diplomacy info for countries. If `country_name` is provided, shows details for that country; "
        "otherwise shows a paginated list of countries with diplomacy records (3 per page). Government-only fields "
        "(diplomacy list) are shown when you have the government role.",
    ),
    (
        "/update_diplomacy country_name [status] [diplomacy] [description]",
        "Government-only. Update an existing diplomacy record: set `status`, append a `diplomacy` entry, or update "
        "`description`. New diplomacy entries are automatically dated. Status must be one of the predefined options "
        "and autocomplete is available.",
    ),
    (
        "/add_diplomacy country_name [status] [description]",
        "Government-only. Create a new diplomacy record for a country. If a record already exists, use `/update_diplomacy`.",
    ),
    (
        "/remove_diplomacy country_name position",
        "Government-only. Remove the diplomacy list entry at the provided 1-based `position`.",
    ),
    (
        "/delete_diplomacy country_name",
        "Government-only. Delete the diplomacy record for the specified country.",
    ),
    (
        "/nap add country_a country_b | /nap remove country_a country_b | /nap list",
        "Government-only. Manage the internal NAP list used by the hourly battle monitor. Country fields support "
        "autocomplete from the current WarEra country list.",
    ),
    (
        "/fightstatus [military_unit]",
        "Fetch fight status for fighters. Without `military_unit`, operates on members with the configured 'fight' role; "
        "with `military_unit` fetches members of that unit. Results are paginated (10 per page) and include "
        "buff/debuff status, health/hunger, level, and online state. Filters for Buffed/Neutral/Debuffed available.",
    ),
    (
        "/country_strays",
        "List players whose in-game citizenship is not in the configured allowed countries. Results are paginated.",
    ),
    (
        "/inactive_players",
        "List players who have been inactive for more than 3 days. Results are paginated.",
    ),
    (
        "/mu_stray",
        "List MU strays categorised as Wrong MU, No MU, or Inactive Strays. "
        "Filter buttons on the result view switch between categories.",
    ),
    (
        "/promotions",
        "Check newbie members for promotion eligibility. Shows Promotion Candidates, Fight Issues, Inactive, "
        "and Data Issues — filter buttons on the result view switch between categories.",
    ),
    (
        "/top_user_weekly_damages country",
        "Show the top 10 weekly damage dealers from the selected country. The required country field supports "
        "autocomplete using the current country list from WarEra.",
    ),
    (
        "/top_user_weekly_donations country",
        "Show the top 10 citizens by money donated since Monday at 00:00 UTC. The required country field supports "
        "autocomplete using the current country list from WarEra.",
    ),
    (
        "/get_region_upgrade_cost country",
        "Calculate daily oil upkeep and market cost for active bunkers, military bases, and pacification centers "
        "in regions held by the selected country. The required country field supports autocomplete.",
    ),
]

_JOBS_DATA: List[tuple[str, str]] = [
    (
        "skill_roles — every 1 hour",
        "Scans server members with the Citizen role and assigns/removes Economy or Fighter roles based on their "
        "in-game skill distribution. Sends a summary to the reports channel when changes occur.",
    ),
    (
        "military_unit_roles — every 3 hours",
        "Assigns Military Unit roles to members based on their in-game MU membership and removes conflicting MU roles. "
        "Sends a summary to the reports channel when changes occur.",
    ),
    (
        "commander_roles — every 3 hours",
        "Syncs the Discord commander role with the commanders configured across all military units.",
    ),
    (
        "unidentified_members — every 6 hours",
        "Checks Citizen/Newbie members to see if their nickname maps to a known game user. Records mappings when "
        "found and reports unidentified players to the reports channel.",
    ),
    (
        "takeover_countries — every 5 minutes",
        "Scans countries and reports those that appear empty (no government/congress members), posting takeover "
        "opportunities to the public channel.",
    ),
    (
        "buff_monitor — every 10 minutes",
        "Monitors fighter buffs and notifies users when their active pill buff is nearing expiration "
        "(uses an internal cache to avoid repeated notifications).",
    ),
    (
        "bounty_monitor — configurable interval",
        "Checks active battles for money pools/bounties and posts a summary to the public channel when relevant "
        "(interval set by `BOUNTY_MONITOR_INTERVAL_MINUTES` in config).",
    ),
    (
        "mercenary_contracts — every 1 minute",
        "Checks active mercenary contract auctions and posts new or updated contracts to the public channel.",
    ),
    (
        "monitor_nap - every 1 hour",
        "Checks active battle country orders and MU-order nationalities against configured NAPs, then reports "
        "new violations to the reports channel.",
    ),
]

_COMMANDS_PER_PAGE = 3
_JOBS_PER_PAGE = 4


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def _build_command_pages() -> List[discord.Embed]:
    pages: List[discord.Embed] = []
    total = len(_COMMANDS_DATA)
    total_pages = max(1, (total - 1) // _COMMANDS_PER_PAGE + 1)
    for i in range(0, total, _COMMANDS_PER_PAGE):
        chunk = _COMMANDS_DATA[i : i + _COMMANDS_PER_PAGE]
        embed = discord.Embed(title="Bot Commands", color=discord.Color.blurple())
        embed.description = "Use the slash commands below. Autocomplete is available where applicable."
        for name, desc in chunk:
            embed.add_field(name=name, value=desc, inline=False)
        embed.set_footer(text=f"Commands — Page {i // _COMMANDS_PER_PAGE + 1} of {total_pages}")
        pages.append(embed)
    return pages


def _build_job_pages() -> List[discord.Embed]:
    pages: List[discord.Embed] = []
    total = len(_JOBS_DATA)
    total_pages = max(1, (total - 1) // _JOBS_PER_PAGE + 1)
    for i in range(0, total, _JOBS_PER_PAGE):
        chunk = _JOBS_DATA[i : i + _JOBS_PER_PAGE]
        embed = discord.Embed(title="Background Jobs / Tasks", color=discord.Color.dark_gold())
        embed.description = "Active background tasks and how often they run."
        for name, desc in chunk:
            embed.add_field(name=name, value=desc, inline=False)
        embed.set_footer(text=f"Jobs — Page {i // _JOBS_PER_PAGE + 1} of {total_pages}")
        pages.append(embed)
    return pages


# ---------------------------------------------------------------------------
# Paginator view
# ---------------------------------------------------------------------------

class _HelpPaginator(discord.ui.View):
    def __init__(self, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self._commands_pages = _build_command_pages()
        self._jobs_pages = _build_job_pages()
        self.active_section: str = "commands"  # "commands" | "jobs"
        self.page_index: dict[str, int] = {"commands": 0, "jobs": 0}
        self.message: discord.Message | None = None
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
        view = _HelpPaginator()
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
                await interaction.followup.send("Unable to display help at this time.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
