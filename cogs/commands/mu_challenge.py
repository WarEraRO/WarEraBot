"""/gov_challenge: the Romanian government's weekly challenge between the configured Romanian military units.

`/gov_challenge create` opens a private panel: pick the units (all Romanian configured MUs, or some) and up
to five missions from a list, typing only their numbers. Publishing saves it as running and posts the
missions in each MU's contest thread; `cogs/tasks/mu_challenge.py` collects the data and posts the article at
the end of the week. Only members with a government role (config.json roles.government) or the Developer
role can create, cancel or list challenges (user decisions, 2026-11-04): it is created on the Monday after the
weekly reset, one per week, runs until the end of that game week and can't be edited, only cancelled. It is
independent of the points contests (/start_contest): an MU can be in both.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import config
from utils import db
from utils import mu_challenge as mc
from utils.api import warera
from utils.common import get_mu_destination, is_developer, is_government
from utils.contests import split_lines
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

COUNTRY_NAME = "Romania"
THREAD_KEY = "contestId"
PANEL_TIMEOUT = 14 * 60
ALL_UNITS = "__all__"
# Discord limits: select option label/description 100, modal title 45, text input label 45
LABEL_LIMIT = 100
MODAL_LABEL_LIMIT = 45
LIST_WEEKS = 4


def _allowed(member) -> bool:
    return is_government(member) or is_developer(member)


async def romanian_units() -> dict[str, str] | None:
    """{MU id: in-game name} of the configured military units whose country is Romania, in config order.

    None when the MUs or the country list could not be loaded.
    """
    unit_ids = [str(unit["id"]) for unit in config.get("military_units", []) if unit.get("id")]
    mus, countries = await asyncio.gather(warera.mus.get_many(unit_ids), warera.countries.get_all())
    romania = next((c.get("_id") for c in countries or [] if c.get("name") == COUNTRY_NAME), None)
    if romania is None or len(mus) < len(set(unit_ids)):
        return None
    return {mu_id: mus[mu_id].get("name") or mu_id for mu_id in unit_ids if mus[mu_id].get("country") == romania}


def panel_text(challenge: dict, names: dict[str, str], tr: Translator) -> str:
    """The setup panel message: the week, the chosen units and missions."""
    start = mc.start_of(challenge)
    end = mc.reset_of(challenge) - timedelta(days=1)
    lines = [
        tr("mu_challenge.panel_title", start=f"{start:%d.%m}", end=f"{end:%d.%m.%Y}"),
        tr("mu_challenge.announce_units", units=", ".join(
            discord.utils.escape_markdown(str(names.get(m, m))) for m in challenge["mu_ids"]
        ) or tr("common.none")),
        "",
        tr("mu_challenge.announce_missions"),
    ]
    lines += [f"{i}. {mc.mission_text(m, tr)}" for i, m in enumerate(challenge["missions"], start=1)]
    if not challenge["missions"]:
        lines.append(tr("mu_challenge.panel_no_missions"))
    lines += ["", tr("mu_challenge.panel_hint", max=mc.MAX_MISSIONS)]
    return "\n".join(lines)


class _MissionModal(discord.ui.Modal):
    """The numbers of one mission type; a valid submit adds the mission to the panel."""

    def __init__(self, panel: "ChallengePanel", mission_type: str):
        tr = panel.tr
        super().__init__(title=tr(f"mu_challenge.mission.{mission_type}.label")[:MODAL_LABEL_LIMIT])
        self.panel, self.mission_type = panel, mission_type
        self.inputs = {}
        for name, default in mc.MISSIONS[mission_type]["fields"]:
            field = discord.ui.TextInput(
                label=tr(f"mu_challenge.mission.{mission_type}.field.{name}")[:MODAL_LABEL_LIMIT],
                default=mc.compact(default) if name not in mc.MISSIONS[mission_type]["whole"] else str(default),
                max_length=20,
            )
            self.inputs[name] = field
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        """Validate the numbers and add the mission, or say which field is wrong."""
        mission, bad = mc.parse_mission(self.mission_type, {name: f.value for name, f in self.inputs.items()})
        if mission is None:
            return await interaction.response.send_message(
                self.panel.tr("mu_challenge.error_number", value=self.inputs[bad].value), ephemeral=True,
            )
        if len(self.panel.challenge["missions"]) >= mc.MAX_MISSIONS:
            return await interaction.response.send_message(
                self.panel.tr("mu_challenge.error_max_missions", max=mc.MAX_MISSIONS), ephemeral=True,
            )
        self.panel.challenge["missions"].append(mission)
        await self.panel.changed(interaction)


class ChallengePanel(discord.ui.View):
    """The private setup panel of one unpublished challenge, kept in memory until Publish saves it."""

    def __init__(self, challenge: dict, names: dict[str, str], member, tr: Translator):
        super().__init__(timeout=PANEL_TIMEOUT)
        self.challenge, self.names, self.member, self.tr = challenge, names, member, tr
        self._last_interaction: discord.Interaction | None = None
        self.message: discord.Message | None = None
        self.publish_btn.label = tr("mu_challenge.button_publish")
        self.discard_btn.label = tr("mu_challenge.button_discard")
        self._build_selects()

    def text(self) -> str:
        """The panel message."""
        return panel_text(self.challenge, self.names, self.tr)

    def _build_selects(self) -> None:
        for item in [i for i in self.children if isinstance(i, discord.ui.Select)]:
            self.remove_item(item)
        tr = self.tr
        chosen = set(self.challenge["mu_ids"])
        everyone = bool(self.names) and chosen == set(self.names)
        unit_options = [discord.SelectOption(
            label=tr("mu_challenge.all_units")[:LABEL_LIMIT], value=ALL_UNITS, default=everyone,
            description=tr("mu_challenge.all_units_description")[:LABEL_LIMIT],
        )]
        unit_options += [
            discord.SelectOption(label=str(name)[:LABEL_LIMIT], value=mu_id, default=not everyone and mu_id in chosen)
            for mu_id, name in list(self.names.items())[:24]
        ]
        units = discord.ui.Select(
            placeholder=tr("mu_challenge.select_units"), min_values=0, max_values=len(unit_options),
            options=unit_options, row=0,
        )
        units.callback = self._units_selected
        self.add_item(units)

        add = discord.ui.Select(
            placeholder=tr("mu_challenge.select_add_mission"), row=1,
            disabled=len(self.challenge["missions"]) >= mc.MAX_MISSIONS,
            options=[
                discord.SelectOption(
                    label=tr(f"mu_challenge.mission.{kind}.label")[:LABEL_LIMIT], value=kind,
                    description=tr(f"mu_challenge.mission.{kind}.description")[:LABEL_LIMIT],
                )
                for kind in mc.MISSIONS
            ],
        )
        add.callback = self._add_mission
        self.add_item(add)

        missions = self.challenge["missions"]
        remove = discord.ui.Select(
            placeholder=tr("mu_challenge.select_remove_mission"), row=2, disabled=not missions,
            options=[
                discord.SelectOption(label=f"{i}. {mc.mission_text(m, tr)}"[:LABEL_LIMIT], value=str(i - 1))
                for i, m in enumerate(missions, start=1)
            ] or [discord.SelectOption(label=tr("mu_challenge.panel_no_missions")[:LABEL_LIMIT], value="none")],
        )
        remove.callback = self._remove_mission
        self.add_item(remove)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only the member who opened the panel can use it."""
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(self.tr("common.not_authorized"), ephemeral=True)
            return False
        return True

    async def changed(self, interaction: discord.Interaction) -> None:
        """Rebuild the selects and show the new summary."""
        self._last_interaction = interaction
        self._build_selects()
        await interaction.response.edit_message(content=self.text(), view=self)

    async def _units_selected(self, interaction: discord.Interaction):
        values = interaction.data.get("values", [])
        everyone = set(self.challenge["mu_ids"]) == set(self.names)
        if ALL_UNITS in values and everyone and len(values) > 1:
            # "All" was ticked and the member picked units: narrow down to them
            self.challenge["mu_ids"] = [mu_id for mu_id in self.names if mu_id in values]
        elif ALL_UNITS in values:
            self.challenge["mu_ids"] = list(self.names)
        else:
            self.challenge["mu_ids"] = [mu_id for mu_id in self.names if mu_id in values]
        await self.changed(interaction)

    async def _add_mission(self, interaction: discord.Interaction):
        await interaction.response.send_modal(_MissionModal(self, interaction.data["values"][0]))

    async def _remove_mission(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]
        if value.isdigit() and int(value) < len(self.challenge["missions"]):
            del self.challenge["missions"][int(value)]
        await self.changed(interaction)

    @discord.ui.button(label="Publish", style=discord.ButtonStyle.success, row=3)
    async def publish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Check the challenge (Monday, units, missions, one per week), save it as running and announce it."""
        # acknowledge first: the tracker can hold the lock for longer than Discord's 3-second limit
        await interaction.response.defer()
        self._last_interaction = interaction
        tr, challenge = self.tr, self.challenge
        now = datetime.now(timezone.utc)
        error = None
        if not mc.can_create(now) or mc.week_start(now).date().isoformat() != challenge["week"]:
            error = tr("mu_challenge.error_not_monday")
        elif not challenge["mu_ids"]:
            error = tr("mu_challenge.error_no_units")
        elif not challenge["missions"]:
            error = tr("mu_challenge.error_no_missions")
        if error:
            return await interaction.followup.send(error, ephemeral=True)
        async with mc.CHALLENGE_LOCK:
            if mc.same_week(await asyncio.to_thread(db.get_mu_challenges), challenge["week"]):
                return await interaction.followup.send(tr("mu_challenge.error_exists"), ephemeral=True)
            challenge["created_at"] = now.isoformat()
            challenge["mu_names"] = {m: self.names.get(m, m) for m in challenge["mu_ids"]}
            await asyncio.to_thread(db.save_mu_challenge, challenge)
        self.stop()
        posted = await self._announce(interaction.guild)
        await interaction.edit_original_response(
            content=f"{self.text()}\n\n{tr('mu_challenge.published', channels=posted)}", view=None,
        )

    async def _announce(self, guild) -> int:
        """Post the missions once to each participating MU's contest thread (else channel); returns how many."""
        if guild is None:
            return 0
        lines = mc.announcement_lines(self.challenge, self.challenge["mu_names"], self.tr)
        units = {str(unit.get("id")): unit for unit in config.get("military_units", [])}
        seen = set()
        for mu_id in self.challenge["mu_ids"]:
            unit = units.get(mu_id)
            destination = await get_mu_destination(guild, unit, THREAD_KEY) if unit else None
            if destination is None or destination.id in seen:
                continue
            seen.add(destination.id)
            try:
                for message in split_lines(lines):
                    await destination.send(message, allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                logger.exception("MU challenge %s: could not post to %s", self.challenge["id"], destination.id)
        return len(seen)

    @discord.ui.button(label="Discard", style=discord.ButtonStyle.danger, row=3)
    async def discard_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the panel without saving anything."""
        self.stop()
        await interaction.response.edit_message(content=self.tr("mu_challenge.discarded"), view=None)

    async def on_timeout(self):
        """Show the summary without controls: an unpublished challenge is not saved."""
        try:
            if self._last_interaction is not None:
                await self._last_interaction.edit_original_response(
                    content=f"{self.text()}\n\n{self.tr('mu_challenge.panel_expired')}", view=None,
                )
            elif self.message is not None:
                await self.message.edit(content=f"{self.text()}\n\n{self.tr('mu_challenge.panel_expired')}", view=None)
        except discord.HTTPException:
            pass


class MuChallenges(commands.Cog):
    """The /gov_challenge group."""

    gov_challenge = app_commands.Group(
        name="gov_challenge", description="The government's weekly challenge between Romanian military units.",
        guild_only=True,
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @gov_challenge.command(name="create", description="Create this week's MU challenge (government, Mondays UTC only).")
    async def challenge_create(self, interaction: discord.Interaction):
        """Check the role, the day and the week, then open the private setup panel."""
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)
        if not _allowed(interaction.user):
            return await interaction.followup.send(tr("common.not_authorized"), ephemeral=True)
        now = datetime.now(timezone.utc)
        if not mc.can_create(now):
            return await interaction.followup.send(tr("mu_challenge.error_not_monday"), ephemeral=True)
        week = mc.week_start(now).date().isoformat()
        if mc.same_week(await asyncio.to_thread(db.get_mu_challenges), week):
            return await interaction.followup.send(tr("mu_challenge.error_exists"), ephemeral=True)
        names = await romanian_units()
        if names is None:
            return await interaction.followup.send(tr("mu_challenge.error_units_unavailable"), ephemeral=True)
        if not names:
            return await interaction.followup.send(tr("mu_challenge.error_no_romanian_units"), ephemeral=True)
        challenge = mc.new_challenge(interaction.guild_id, interaction.user.id, now)
        challenge["mu_ids"] = list(names)
        view = ChallengePanel(challenge, names, interaction.user, tr)
        view.message = await interaction.followup.send(view.text(), view=view, ephemeral=True, wait=True)

    @gov_challenge.command(name="cancel", description="Cancel the running MU challenge; no article is posted.")
    @app_commands.describe(challenge="The challenge")
    async def challenge_cancel(self, interaction: discord.Interaction, challenge: str):
        """Mark a running challenge cancelled."""
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)
        if not _allowed(interaction.user):
            return await interaction.followup.send(tr("common.not_authorized"), ephemeral=True)
        async with mc.CHALLENGE_LOCK:
            records = {c.get("id"): c for c in await asyncio.to_thread(db.get_mu_challenges)}
            record = records.get(challenge)
            if record is None or record.get("status") != "running":
                return await interaction.followup.send(tr("mu_challenge.error_not_running"), ephemeral=True)
            record["status"] = "cancelled"
            record.setdefault("state", {})["cancelled_by"] = interaction.user.id
            await asyncio.to_thread(db.save_mu_challenge, record)
        await interaction.followup.send(tr("mu_challenge.cancelled", week=record["week"]), ephemeral=True)

    @gov_challenge.command(name="list", description="List the MU challenges of the last weeks.")
    async def challenge_list(self, interaction: discord.Interaction):
        """List the challenges of the last LIST_WEEKS weeks with their status, units and missions."""
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)
        if not _allowed(interaction.user):
            return await interaction.followup.send(tr("common.not_authorized"), ephemeral=True)
        since = (mc.week_start(datetime.now(timezone.utc)) - timedelta(weeks=LIST_WEEKS - 1)).date().isoformat()
        records = sorted(
            (c for c in await asyncio.to_thread(db.get_mu_challenges) if (c.get("week") or "") >= since),
            key=lambda c: c.get("week") or "", reverse=True,
        )
        lines = []
        for record in records:
            names = record.get("mu_names") or {}
            lines.append(tr(
                "mu_challenge.list_line", week=record.get("week"), status=tr(f"mu_challenge.status.{record.get('status')}"),
                units=discord.utils.escape_markdown(", ".join(str(names.get(m) or m) for m in record.get("mu_ids") or [])),
            ))
            lines += [f"   • {mc.mission_text(m, tr)}" for m in record.get("missions") or []]
        for message in split_lines(lines or [tr("mu_challenge.list_empty")]):
            await interaction.followup.send(message, ephemeral=True)

    @challenge_cancel.autocomplete("challenge")
    async def _running_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            records = await asyncio.to_thread(db.get_mu_challenges)
        except Exception:
            return []
        current = (current or "").casefold()
        choices = []
        for record in records:
            if record.get("status") != "running":
                continue
            label = f"{record.get('week')} ({len(record.get('mu_ids') or [])} MU, {len(record.get('missions') or [])})"
            if current in label.casefold():
                choices.append(app_commands.Choice(name=label[:LABEL_LIMIT], value=record["id"]))
        return choices[:25]


async def setup(bot: commands.Bot):
    """Load the /gov_challenge commands."""
    await bot.add_cog(MuChallenges(bot))
