import unicodedata

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
    "subscriptions",
    "subscriptions_loot",
    "subscriptions_bounty",
    "pills",
    "mu_pill_plan",
    "fight_wealth",
    "progression",
    "economy",
    "mu_order_alignment",
    "mu_positions",
    "mu_readiness",
    "loot_targets",
    "promotions",
    "top_user_weekly_damages",
    "top_user_weekly_donations",
    "get_region_upgrade_cost",
    "run_job",
    "setlang",
    "server_ids",
]

_JOB_IDS: List[str] = [
    "skill_roles",
    "military_unit_roles",
    "commander_roles",
    "unidentified_members",
    "takeover_countries",
    "buff_monitor",
    "bounty_monitor",
    "bounty_alerts",
    "mercenary_contracts",
    "mu_contract_monitor",
    "loot_alerts",
    "monitor_nap",
    "battle_order_monitor",
    "reddit_monitor",
    "article_mention",
    "newbie_welcome",
]

_COMMANDS_PER_PAGE = 3
_JOBS_PER_PAGE = 4

# /help topic values are "<section>:<id>"; the section picks the locale block and the embed colour
_SECTIONS = {"command": ("commands", _COMMAND_IDS), "job": ("jobs", _JOB_IDS)}
_SECTION_ICONS = {"command": "⌨️", "job": "⚙️"}
_SECTION_COLORS = {"command": discord.Color.blurple(), "job": discord.Color.dark_gold()}
# Discord's limits for one autocomplete choice label and the number of choices
_CHOICE_NAME_LIMIT = 100
_MAX_CHOICES = 25


# ---------------------------------------------------------------------------
# Single topic (/help topic:<...>)
# ---------------------------------------------------------------------------

def _topic_entries(tr: Translator) -> List[tuple[str, str, str]]:
    """List every help topic, commands first, in the order the paginated help shows them.

    Args:
        tr: Translator used for the topic labels.

    Returns:
        ``(value, section, label)`` tuples, where ``value`` is ``"<section>:<id>"`` and ``label`` is the entry's
        icon plus its translated field name.
    """
    entries = []
    for section, (block, ids) in _SECTIONS.items():
        for entry_id in ids:
            label = f"{_SECTION_ICONS[section]} {tr(f'help.{block}.{entry_id}.name')}"
            entries.append((f"{section}:{entry_id}", section, label))
    return entries


def _resolve_topic(topic: str) -> tuple[str, str] | None:
    """Find the help entry a /help ``topic`` value refers to.

    Accepts an autocomplete value (``"job:skill_roles"``), a bare entry id (``"skill_roles"``) or a typed command
    name (``"/nap"``, ``"nap list"``), case-insensitively. Matching uses ids and the English field names only, so it
    needs no translator.

    Args:
        topic: Text the member picked or typed.

    Returns:
        ``(section, id)``, or None when nothing matches.
    """
    wanted = topic.strip().lower()
    section, _, entry_id = wanted.partition(":")
    if section in _SECTIONS and entry_id in _SECTIONS[section][1]:
        return section, entry_id
    bare = wanted.lstrip("/")
    for section, (_, ids) in _SECTIONS.items():
        if bare in ids:
            return section, bare
    # A typed command name, matched against each " | "-separated usage in the English field names, so
    # "subscribe loot" finds "/subscribe loot | /unsubscribe loot" and "nap" finds "/nap add ... | /nap list"
    usages = [
        (section, value.split(":", 1)[1], usage.strip().lstrip("/").lower())
        for value, section, label in _topic_entries(Translator("en"))
        for usage in label.split(" ", 1)[1].split(" | ")
    ]
    for section, entry_id, usage in usages:
        if usage == bare or usage.startswith(bare + " "):
            return section, entry_id
    return None


def _fold(text: str) -> str:
    """Lowercase ``text`` and drop diacritics, so "ora" matches "oră" in autocomplete."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _build_topic_embed(tr: Translator, section: str, entry_id: str) -> discord.Embed:
    """Build the embed for one command or job.

    Args:
        tr: Translator for the server's language.
        section: ``"command"`` or ``"job"``.
        entry_id: Id from ``_COMMAND_IDS`` or ``_JOB_IDS``.

    Returns:
        An embed titled with the entry's field name and described by its text.
    """
    block = _SECTIONS[section][0]
    embed = discord.Embed(
        title=tr(f"help.{block}.{entry_id}.name"),
        description=tr(f"help.{block}.{entry_id}.desc"),
        color=_SECTION_COLORS[section],
    )
    embed.set_footer(text=tr(f"help.topic_footer_{section}"))
    return embed


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

    async def topic_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Suggest commands and jobs whose id or name contains the typed text.

        Labels follow the member's Discord client language rather than the server's, because the server
        language is a database read and Discord drops autocomplete answers after about 3 seconds.

        Args:
            interaction: The autocomplete interaction.
            current: Text typed so far.

        Returns:
            Up to 25 choices whose value is ``"<section>:<id>"``.
        """
        tr = Translator("ro" if interaction.locale == discord.Locale.romanian else "en")
        wanted = _fold((current or "").strip())
        choices = []
        for value, _, label in _topic_entries(tr):
            if wanted and wanted not in value and wanted not in _fold(label):
                continue
            if len(label) > _CHOICE_NAME_LIMIT:
                label = label[: _CHOICE_NAME_LIMIT - 1] + "…"
            choices.append(app_commands.Choice(name=label, value=value))
            if len(choices) >= _MAX_CHOICES:
                break
        return choices

    @app_commands.command(name="help", description="Show bot commands and background jobs, or one of them in detail.")
    @app_commands.describe(topic="A single command or background job to show (leave empty to browse all)")
    @app_commands.autocomplete(topic=topic_autocomplete)
    async def help(self, interaction: discord.Interaction, topic: str | None = None):
        if topic:
            resolved = _resolve_topic(topic)
            if resolved is None:
                await interaction.response.defer(ephemeral=True)
                tr = await get_translator(interaction.guild_id)
                await interaction.followup.send(tr("help.unknown_topic", topic=topic[:100]), ephemeral=True)
                return
            await interaction.response.defer()
            tr = await get_translator(interaction.guild_id)
            await interaction.followup.send(embed=_build_topic_embed(tr, *resolved))
            return
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
