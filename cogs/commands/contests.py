"""/start_contest and /contest: create and manage points contests between configured military units.

`/start_contest` saves a draft and opens a private setup panel (units, level brackets, missions, prizes,
prize pool). Publishing schedules the contest; nothing is posted to the units until it starts, which
`cogs/tasks/contests.py` handles. Only a commander (or the owner) in-game of one of the selected MUs, or a
member with the Developer role, can create one; only its creator or a Developer can edit, cancel or end it.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import config
from utils import contests as cx
from utils import db
from utils.api import warera
from utils.common import is_developer, to_local
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

PANEL_TIMEOUT = 14 * 60
# Discord limits: select option label/description 100, modal title 45, text input label 45
LABEL_LIMIT = 100
MODAL_LABEL_LIMIT = 45


def _units() -> dict[str, dict]:
    """Configured military units by id, in config order."""
    return {str(unit["id"]): unit for unit in config.get("military_units", []) if unit.get("id")}


async def _caller_api_id(member) -> str | None:
    """The caller's WarEra user id: the linked record first, then their server nickname as username."""
    api_id = await asyncio.to_thread(db.find_api_id_by_discord_id, member.id)
    if api_id:
        return api_id
    user = await warera.users.find_by_name(getattr(member, "display_name", None) or member.name)
    return (user or {}).get("_id")


async def _load_units() -> dict[str, dict]:
    """mu.getById of every configured MU, {muId: mu}, for the ids that resolved."""
    return await warera.mus.get_many(list(_units()))


def _commanded(mus: dict[str, dict], api_id: str | None) -> set[str]:
    """Ids of the MUs whose owner or in-game commander is `api_id`."""
    if not api_id:
        return set()
    return {
        mu_id for mu_id, mu in mus.items()
        if mu.get("user") == api_id or api_id in ((mu.get("roles") or {}).get("commanders") or [])
    }


def _can_manage(member, contest: dict) -> bool:
    return is_developer(member) or int(contest.get("creator_id") or 0) == member.id


def _summary(contest: dict, mu_names: dict, tr: Translator) -> str:
    """The setup panel text: everything the contest has so far."""
    start, end = to_local(cx.start_at(contest)), to_local(cx.end_at(contest))
    fmt = tr("contest.datetime_format")
    lines = [
        tr("contest.panel_title", name=discord.utils.escape_markdown(contest["name"]), status=tr(f"contest.status.{contest['status']}")),
        tr("contest.announce_dates", start=tr.strftime(start, fmt), end=tr.strftime(end, fmt), days=contest["days"]),
        tr("contest.announce_units", units=", ".join(
            discord.utils.escape_markdown(str(mu_names.get(m, m))) for m in contest["mu_ids"]
        ) or tr("common.none")),
    ]
    for category in cx.CATEGORIES:
        brackets = ", ".join(
            tr("contest.levels_open", low=low) if high is None else tr("contest.levels_range", low=low, high=high)
            for low, high in cx.bracket_bounds(contest, category)
        )
        lines.append(tr("contest.panel_brackets", category=tr(f"contest.category.{category}"), brackets=brackets))
    lines += ["", tr("contest.panel_missions")]
    for index, mission in enumerate(contest["missions"], start=1):
        category = tr(f"contest.category.{cx.MISSIONS[mission['type']]['category']}")
        lines.append(f"{index}. [{category}] {cx.mission_text(mission, tr)}")
    if not contest["missions"]:
        lines.append(tr("contest.panel_no_missions"))
    lines += ["", tr("contest.panel_prizes")]
    prize_lines = []
    for category in cx.CATEGORIES:
        for index in range(len(cx.bracket_bounds(contest, category))):
            prizes = contest["prizes"].get(f"{category}:{index}") or []
            if prizes:
                places = " · ".join(f"{place}. {cx.prize_text(p, tr)}" for place, p in enumerate(prizes, start=1))
                prize_lines.append(f"{cx.bracket_label(contest, category, index, tr)}: {places}")
    lines += prize_lines or [tr("contest.panel_no_prizes")]
    if contest.get("prize_pool"):
        lines.append(tr("contest.announce_pool", pool=contest["prize_pool"]))
    text = "\n".join(lines)
    return text if len(text) <= cx.MESSAGE_LIMIT else text[: cx.MESSAGE_LIMIT - 1] + "…"


def _validate_dates(start_text: str, days: int, now: datetime, tr: Translator) -> tuple[str | None, object]:
    """(error, start date): the start must be a date from tomorrow (UTC) on and the duration 1..MAX_DAYS days."""
    start_day = cx.parse_start_date(start_text)
    if start_day is None:
        return tr("contest.error_date"), None
    if start_day <= now.date():
        return tr("contest.error_date_past"), None
    if not 1 <= days <= cx.MAX_DAYS:
        return tr("contest.error_days", max=cx.MAX_DAYS), None
    return None, start_day


async def _conflict(contest: dict) -> dict | None:
    """Another scheduled or running contest that shares an MU with `contest` on a common day."""
    for other in await asyncio.to_thread(db.get_contests):
        if (
            other.get("id") != contest["id"]
            and other.get("status") in cx.ACTIVE_STATUSES
            and set(other.get("mu_ids") or []) & set(contest["mu_ids"])
            and cx.overlaps(other, contest)
        ):
            return other
    return None


# ------------------------------------------------------------------------------------------------ modals


class _DetailsModal(discord.ui.Modal):
    def __init__(self, panel: "SetupView"):
        tr, contest = panel.tr, panel.contest
        super().__init__(title=tr("contest.details_title")[:MODAL_LABEL_LIMIT])
        self.panel = panel
        self.name = discord.ui.TextInput(label=tr("contest.field.name")[:MODAL_LABEL_LIMIT], default=contest["name"], max_length=100)
        self.start = discord.ui.TextInput(label=tr("contest.field.start_date")[:MODAL_LABEL_LIMIT], default=contest["start_day"], max_length=10)
        self.days = discord.ui.TextInput(label=tr("contest.field.duration")[:MODAL_LABEL_LIMIT], default=str(contest["days"]), max_length=2)
        for item in (self.name, self.start, self.days):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        tr = self.panel.tr
        days = cx.parse_number(self.days.value)
        # 0 fails the duration check, like any value that is not a whole number
        days = int(days) if days is not None and days == int(days) else 0
        error, start_day = _validate_dates(self.start.value, days, datetime.now(timezone.utc), tr)
        if error:
            return await interaction.response.send_message(error, ephemeral=True)
        self.panel.contest.update(name=self.name.value.strip() or self.panel.contest["name"], start_day=start_day.isoformat(), days=days)
        await self.panel.changed(interaction)


class _LevelsModal(discord.ui.Modal):
    def __init__(self, panel: "SetupView"):
        tr, contest = panel.tr, panel.contest
        super().__init__(title=tr("contest.levels_title")[:MODAL_LABEL_LIMIT])
        self.panel = panel
        self.min_level = discord.ui.TextInput(
            label=tr("contest.field.fighter_min_level")[:MODAL_LABEL_LIMIT], default=str(contest["fighter_min_level"]), max_length=3
        )
        self.fighters = discord.ui.TextInput(
            label=tr("contest.field.fighter_brackets")[:MODAL_LABEL_LIMIT], required=False, max_length=100,
            default=", ".join(str(b) for b in contest["brackets"]["fighters"]), placeholder="40",
        )
        self.economists = discord.ui.TextInput(
            label=tr("contest.field.economist_brackets")[:MODAL_LABEL_LIMIT], required=False, max_length=100,
            default=", ".join(str(b) for b in contest["brackets"]["economists"]), placeholder="10",
        )
        for item in (self.min_level, self.fighters, self.economists):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        tr = self.panel.tr
        min_level = cx.parse_number(self.min_level.value)
        if min_level is None or min_level != int(min_level) or not 2 <= min_level <= 1000:
            return await interaction.response.send_message(tr("contest.error_levels"), ephemeral=True)
        brackets = {}
        for category, field in (("fighters", self.fighters), ("economists", self.economists)):
            parts = [part for part in field.value.replace(";", ",").split(",") if part.strip()]
            parsed = [cx.parse_number(part) for part in parts]
            if len(parsed) >= cx.MAX_BRACKETS or any(value is None or value != int(value) for value in parsed):
                return await interaction.response.send_message(tr("contest.error_levels"), ephemeral=True)
            brackets[category] = sorted({int(value) for value in parsed})
        old_bounds = {c: cx.bracket_bounds(self.panel.contest, c) for c in cx.CATEGORIES}
        self.panel.contest["fighter_min_level"] = int(min_level)
        self.panel.contest["brackets"] = brackets
        # prizes are set per bracket, so different level ranges drop them
        for category in cx.CATEGORIES:
            if cx.bracket_bounds(self.panel.contest, category) != old_bounds[category]:
                self.panel.contest["prizes"] = {k: v for k, v in self.panel.contest["prizes"].items() if not k.startswith(f"{category}:")}
        await self.panel.changed(interaction)


class _MissionModal(discord.ui.Modal):
    def __init__(self, panel: "SetupView", mission_type: str):
        tr = panel.tr
        super().__init__(title=tr(f"contest.mission.{mission_type}.label")[:MODAL_LABEL_LIMIT])
        self.panel, self.mission_type = panel, mission_type
        spec = cx.MISSIONS[mission_type]
        self.inputs = {}
        for name, default in spec["fields"]:
            self.inputs[name] = discord.ui.TextInput(
                label=tr(f"contest.mission.{mission_type}.field.{name}")[:MODAL_LABEL_LIMIT], default=cx.format_amount(default), max_length=20
            )
        self.inputs["points"] = discord.ui.TextInput(
            label=tr("contest.field.points")[:MODAL_LABEL_LIMIT], default=cx.format_points(spec["points"]), max_length=10
        )
        for item in self.inputs.values():
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        mission = {"type": self.mission_type}
        for name, field in self.inputs.items():
            value = cx.parse_number(field.value)
            if value is None or (name == "points" and value <= 0):
                return await interaction.response.send_message(self.panel.tr("contest.error_number", value=field.value), ephemeral=True)
            mission[name] = value
        self.panel.contest["missions"].append(mission)
        await self.panel.changed(interaction)


class _PrizesModal(discord.ui.Modal):
    def __init__(self, panel: "SetupView", key: str):
        tr = panel.tr
        category, index = key.split(":")
        super().__init__(title=cx.bracket_label(panel.contest, category, int(index), tr)[:MODAL_LABEL_LIMIT])
        self.panel, self.key = panel, key
        current = panel.contest["prizes"].get(key) or []
        self.places = []
        for place in range(1, cx.MAX_PRIZE_PLACES + 1):
            prize = current[place - 1] if place <= len(current) else None
            default = (f"{prize['gems']} | {prize['text']}" if prize.get("text") else str(prize["gems"])) if prize else None
            field = discord.ui.TextInput(
                label=tr("contest.field.place", place=place)[:MODAL_LABEL_LIMIT], required=False, max_length=150,
                default=default, placeholder=tr("contest.prize_placeholder") if place == 1 else None,
            )
            self.places.append(field)
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        prizes = []
        for field in self.places:
            if not field.value.strip():
                break
            prize = cx.parse_prize(field.value)
            if prize is None:
                return await interaction.response.send_message(self.panel.tr("contest.error_prize", value=field.value), ephemeral=True)
            prizes.append(prize)
        if prizes:
            self.panel.contest["prizes"][self.key] = prizes
        else:
            self.panel.contest["prizes"].pop(self.key, None)
        await self.panel.changed(interaction)


class _PoolModal(discord.ui.Modal):
    def __init__(self, panel: "SetupView"):
        super().__init__(title=panel.tr("contest.pool_title")[:MODAL_LABEL_LIMIT])
        self.panel = panel
        self.pool = discord.ui.TextInput(
            label=panel.tr("contest.field.prize_pool")[:MODAL_LABEL_LIMIT], style=discord.TextStyle.paragraph,
            required=False, max_length=500, default=panel.contest.get("prize_pool") or None,
        )
        self.add_item(self.pool)

    async def on_submit(self, interaction: discord.Interaction):
        self.panel.contest["prize_pool"] = self.pool.value.strip()
        await self.panel.changed(interaction)


# ------------------------------------------------------------------------------------------------ panel


class SetupView(discord.ui.View):
    """The private setup panel of one draft or scheduled contest.

    A draft is saved after every change, so nothing is lost when the panel times out (/contest edit reopens
    it). Changes to a scheduled contest are saved only by Publish, after the same checks as a first publish.
    """

    def __init__(self, contest: dict, mus: dict[str, dict], member, tr: Translator):
        super().__init__(timeout=PANEL_TIMEOUT)
        self.contest, self.mus, self.member, self.tr = contest, mus, member, tr
        # in-game names; an MU whose fetch failed shows its id
        self.mu_names = {mu_id: (mus.get(mu_id) or {}).get("name") or mu_id for mu_id in _units()}
        self.message: discord.Message | None = None
        self._last_interaction: discord.Interaction | None = None
        self.details_btn.label = tr("contest.button_details")
        self.levels_btn.label = tr("contest.button_levels")
        self.pool_btn.label = tr("contest.button_pool")
        self.publish_btn.label = tr("contest.button_publish") if contest["status"] == "draft" else tr("contest.button_save")
        self.discard_btn.label = tr("contest.button_discard") if contest["status"] == "draft" else tr("contest.button_close")
        self._build_selects()

    def text(self) -> str:
        """The panel message: the contest summary."""
        return _summary(self.contest, self.mu_names, self.tr)

    def _build_selects(self) -> None:
        for item in [i for i in self.children if isinstance(i, discord.ui.Select)]:
            self.remove_item(item)
        tr = self.tr
        units = discord.ui.Select(
            placeholder=tr("contest.select_units"), min_values=0, max_values=min(25, len(self.mu_names)) or 1, row=0,
            options=[
                discord.SelectOption(label=str(name)[:LABEL_LIMIT], value=mu_id, default=mu_id in self.contest["mu_ids"])
                for mu_id, name in list(self.mu_names.items())[:25]
            ] or [discord.SelectOption(label=tr("common.none"), value="none")],
        )
        units.callback = self._units_selected
        self.add_item(units)

        add = discord.ui.Select(
            placeholder=tr("contest.select_add_mission"), row=1, disabled=len(self.contest["missions"]) >= cx.MAX_MISSIONS,
            options=[
                discord.SelectOption(
                    label=tr(f"contest.mission.{kind}.label")[:LABEL_LIMIT], value=kind,
                    description=tr(f"contest.category.{spec['category']}")[:LABEL_LIMIT],
                )
                for kind, spec in cx.MISSIONS.items()
            ],
        )
        add.callback = self._add_mission
        self.add_item(add)

        missions = self.contest["missions"]
        remove = discord.ui.Select(
            placeholder=tr("contest.select_remove_mission"), row=2, disabled=not missions,
            options=[
                discord.SelectOption(label=f"{i}. {cx.mission_text(m, tr)}"[:LABEL_LIMIT], value=str(i - 1))
                for i, m in enumerate(missions[:25], start=1)
            ] or [discord.SelectOption(label=tr("contest.panel_no_missions")[:LABEL_LIMIT], value="none")],
        )
        remove.callback = self._remove_mission
        self.add_item(remove)

        brackets = [
            (f"{category}:{index}", cx.bracket_label(self.contest, category, index, tr))
            for category in cx.CATEGORIES
            for index in range(len(cx.bracket_bounds(self.contest, category)))
        ]
        prizes = discord.ui.Select(
            placeholder=tr("contest.select_prizes"), row=3,
            options=[discord.SelectOption(label=label[:LABEL_LIMIT], value=key) for key, label in brackets[:25]],
        )
        prizes.callback = self._prizes
        self.add_item(prizes)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only the member who opened the panel can use it."""
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(self.tr("common.not_authorized"), ephemeral=True)
            return False
        return True

    async def changed(self, interaction: discord.Interaction) -> None:
        """Save a draft, rebuild the selects and show the new summary in the panel."""
        # acknowledge first: the tracker can hold the lock for longer than Discord's 3-second limit
        await interaction.response.defer()
        self._last_interaction = interaction
        if self.contest["status"] == "draft":
            async with cx.CONTEST_LOCK:
                stored = await asyncio.to_thread(db.get_contest, self.contest["id"])
                if not stored or stored.get("status") != "draft":
                    self.stop()
                    return await interaction.edit_original_response(content=self.tr("contest.error_gone"), view=None)
                await asyncio.to_thread(db.save_contest, self.contest)
        self._build_selects()
        await interaction.edit_original_response(content=self.text(), view=self)

    async def _units_selected(self, interaction: discord.Interaction):
        values = [v for v in interaction.data.get("values", []) if v in self.mu_names]
        self.contest["mu_ids"] = [mu_id for mu_id in self.mu_names if mu_id in values]
        await self.changed(interaction)

    async def _add_mission(self, interaction: discord.Interaction):
        await interaction.response.send_modal(_MissionModal(self, interaction.data["values"][0]))

    async def _remove_mission(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]
        if value.isdigit() and int(value) < len(self.contest["missions"]):
            del self.contest["missions"][int(value)]
        await self.changed(interaction)

    async def _prizes(self, interaction: discord.Interaction):
        await interaction.response.send_modal(_PrizesModal(self, interaction.data["values"][0]))

    @discord.ui.button(label="Details", style=discord.ButtonStyle.secondary, row=4)
    async def details_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit the name, first day and duration."""
        await interaction.response.send_modal(_DetailsModal(self))

    @discord.ui.button(label="Levels", style=discord.ButtonStyle.secondary, row=4)
    async def levels_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit the fighter level limit and the bracket starts."""
        await interaction.response.send_modal(_LevelsModal(self))

    @discord.ui.button(label="Prize pool", style=discord.ButtonStyle.secondary, row=4)
    async def pool_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit the free-text prize pool."""
        await interaction.response.send_modal(_PoolModal(self))

    @discord.ui.button(label="Publish", style=discord.ButtonStyle.success, row=4)
    async def publish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Check the contest (dates, units, missions, commander, unit conflicts) and save it as scheduled."""
        await interaction.response.defer()
        tr, contest = self.tr, self.contest
        now = datetime.now(timezone.utc)
        error, _ = _validate_dates(contest["start_day"], int(contest["days"]), now, tr)
        if not error and not contest["mu_ids"]:
            error = tr("contest.error_no_units")
        if not error and not contest["missions"]:
            error = tr("contest.error_no_missions")
        if not error and not is_developer(self.member):
            mus = await _load_units()
            if not _commanded({m: mus[m] for m in contest["mu_ids"] if m in mus}, await _caller_api_id(self.member)):
                error = tr("contest.error_not_commander_selected")
        if error:
            return await interaction.followup.send(error, ephemeral=True)
        async with cx.CONTEST_LOCK:
            stored = await asyncio.to_thread(db.get_contest, contest["id"])
            if not stored or stored.get("status") not in ("draft", "scheduled"):
                self.stop()
                return await interaction.edit_original_response(content=tr("contest.error_gone"), view=None)
            other = await _conflict(contest)
            if other:
                return await interaction.followup.send(
                    tr("contest.error_conflict", name=discord.utils.escape_markdown(other.get("name") or "?")), ephemeral=True
                )
            contest["status"] = "scheduled"
            await asyncio.to_thread(db.save_contest, contest)
        self.stop()
        start = to_local(cx.start_at(contest))
        await interaction.edit_original_response(
            content=f"{self.text()}\n\n{tr('contest.published', start=tr.strftime(start, tr('contest.datetime_format')))}", view=None
        )

    @discord.ui.button(label="Discard", style=discord.ButtonStyle.danger, row=4)
    async def discard_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete a draft, or close a scheduled contest's panel without saving."""
        self.stop()
        await interaction.response.defer()
        if self.contest["status"] == "draft":
            async with cx.CONTEST_LOCK:
                await asyncio.to_thread(db.delete_contest, self.contest["id"])
            return await interaction.edit_original_response(content=self.tr("contest.discarded"), view=None)
        await interaction.edit_original_response(content=self.tr("contest.closed"), view=None)

    async def on_timeout(self):
        """Show the summary without controls and say how to reopen the panel."""
        # the latest interaction's token is still valid (15 minutes) when the panel times out after PANEL_TIMEOUT
        try:
            if self._last_interaction is not None:
                await self._last_interaction.edit_original_response(content=f"{self.text()}\n\n{self.tr('contest.panel_expired')}", view=None)
            elif self.message is not None:
                await self.message.edit(content=f"{self.text()}\n\n{self.tr('contest.panel_expired')}", view=None)
        except discord.HTTPException:
            pass


# ------------------------------------------------------------------------------------------------ cog


class Contests(commands.Cog):
    """/start_contest and the /contest group."""

    contest = app_commands.Group(name="contest", description="Manage points contests between military units.", guild_only=True)

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _open_panel(self, interaction: discord.Interaction, contest: dict, tr: Translator) -> None:
        mus = await _load_units()
        view = SetupView(contest, mus, interaction.user, tr)
        view.message = await interaction.followup.send(view.text(), view=view, ephemeral=True, wait=True)

    @app_commands.command(name="start_contest", description="Create a points contest for some military units (commanders only).")
    @app_commands.describe(
        name="Contest name",
        start_date="First day (YYYY-MM-DD); it starts at the game reset before that day",
        duration="Number of days; it ends at the game reset after the last day",
    )
    @app_commands.guild_only()
    async def start_contest(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100], start_date: str, duration: app_commands.Range[int, 1, cx.MAX_DAYS]):
        """Check the dates and that the caller commands a configured MU, save a draft and open its panel."""
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)
        now = datetime.now(timezone.utc)
        error, start_day = _validate_dates(start_date, duration, now, tr)
        if error:
            return await interaction.followup.send(error, ephemeral=True)
        if not is_developer(interaction.user):
            mus = await _load_units()
            if not _commanded(mus, await _caller_api_id(interaction.user)):
                return await interaction.followup.send(tr("contest.error_not_commander"), ephemeral=True)
        contest = cx.new_contest(interaction.guild_id, interaction.user.id, name.strip(), start_day, duration, now)
        async with cx.CONTEST_LOCK:
            await asyncio.to_thread(db.save_contest, contest)
        await self._open_panel(interaction, contest, tr)

    async def _contest_choices(self, interaction: discord.Interaction, current: str, statuses: tuple[str, ...], own: bool):
        try:
            contests = await asyncio.to_thread(db.get_contests)
        except Exception:
            return []
        current = (current or "").casefold()
        choices = []
        for contest in sorted(contests, key=lambda c: c.get("start_day") or "", reverse=True):
            if contest.get("status") not in statuses or (own and not _can_manage(interaction.user, contest)):
                continue
            label = f"{contest.get('name')} ({contest.get('start_day')}, {contest.get('status')})"
            if current in label.casefold():
                choices.append(app_commands.Choice(name=label[:LABEL_LIMIT], value=contest["id"]))
        return choices[:25]

    async def _load(self, interaction: discord.Interaction, contest_id: str, tr: Translator, statuses: tuple[str, ...], manage: bool):
        """The contest meta record when it exists, has one of `statuses` and (if `manage`) the caller may manage it."""
        contest = await asyncio.to_thread(db.get_contest, contest_id)
        if not contest:
            await interaction.followup.send(tr("contest.error_not_found"), ephemeral=True)
            return None
        if manage and not _can_manage(interaction.user, contest):
            await interaction.followup.send(tr("contest.error_not_creator"), ephemeral=True)
            return None
        if contest.get("status") not in statuses:
            await interaction.followup.send(tr("contest.error_status", status=tr(f"contest.status.{contest.get('status')}")), ephemeral=True)
            return None
        return contest

    @contest.command(name="edit", description="Reopen the setup panel of your contest before it starts.")
    @app_commands.describe(contest="The contest")
    async def contest_edit(self, interaction: discord.Interaction, contest: str):
        """Reopen the panel of a draft or scheduled contest that has not started."""
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)
        record = await self._load(interaction, contest, tr, ("draft", "scheduled"), manage=True)
        if record is None:
            return
        if datetime.now(timezone.utc) >= cx.start_at(record):
            return await interaction.followup.send(tr("contest.error_status", status=tr("contest.status.running")), ephemeral=True)
        await self._open_panel(interaction, record, tr)

    @contest.command(name="cancel", description="Cancel your contest; nothing more is posted.")
    @app_commands.describe(contest="The contest")
    async def contest_cancel(self, interaction: discord.Interaction, contest: str):
        """Delete a draft, or mark a scheduled or running contest cancelled."""
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)
        async with cx.CONTEST_LOCK:
            record = await self._load(interaction, contest, tr, ("draft", "scheduled", "running"), manage=True)
            if record is None:
                return
            if record["status"] == "draft":
                await asyncio.to_thread(db.delete_contest, record["id"])
            else:
                record["status"] = "cancelled"
                await asyncio.to_thread(db.save_contest, record)
        await interaction.followup.send(tr("contest.cancelled", name=discord.utils.escape_markdown(record["name"])), ephemeral=True)

    @contest.command(name="end", description="End your running contest now and post the final results.")
    @app_commands.describe(contest="The contest")
    async def contest_end(self, interaction: discord.Interaction, contest: str):
        """End a running contest now through the tracker, which posts the final results."""
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)
        tracker = self.bot.get_cog("ContestTrackerJob")
        if tracker is None:
            return await interaction.followup.send(tr("contest.error_tracker"), ephemeral=True)
        async with cx.CONTEST_LOCK:
            record = await self._load(interaction, contest, tr, ("running",), manage=True)
            if record is None:
                return
            try:
                await tracker.finish_now(record)
            except Exception:
                logger.exception("Ending contest %s failed", record["id"])
                return await interaction.followup.send(tr("contest.error_failed"), ephemeral=True)
        await interaction.followup.send(tr("contest.ended", name=discord.utils.escape_markdown(record["name"])), ephemeral=True)

    @contest.command(name="ranking", description="Show the current points of a running or ended contest.")
    @app_commands.describe(contest="The contest")
    async def contest_ranking(self, interaction: discord.Interaction, contest: str):
        """Show the stored points of a contest, privately."""
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)
        record = await self._load(interaction, contest, tr, ("running", "ended", "cancelled"), manage=False)
        if record is None:
            return
        players = list((await asyncio.to_thread(db.get_contest_players, record["id"])).values())
        updated = cx.parse_iso((record.get("state") or {}).get("last_refresh_at"))
        header = tr("contest.ranking_now", name=discord.utils.escape_markdown(record["name"]))
        if updated:
            header += " " + tr("contest.updated_at", time=f"{to_local(updated):%H:%M %Z}")
        for message in cx.split_lines([header, ""] + cx.ranking_lines(record, players, tr)):
            await interaction.followup.send(message, ephemeral=True)

    @contest.command(name="list", description="List scheduled and running contests.")
    async def contest_list(self, interaction: discord.Interaction):
        """List scheduled and running contests, the caller's drafts and contests ended in the last 7 days."""
        await interaction.response.defer(ephemeral=True)
        tr = await get_translator(interaction.guild_id)
        contests = await asyncio.to_thread(db.get_contests)
        lines = []
        now = datetime.now(timezone.utc)
        for record in sorted(contests, key=lambda c: c.get("start_day") or ""):
            status = record.get("status")
            visible = status in cx.ACTIVE_STATUSES or (status == "draft" and _can_manage(interaction.user, record))
            recent = status == "ended" and now - cx.end_at(record) < timedelta(days=7)
            if not (visible or recent):
                continue
            names = record.get("mu_names") or {}
            units = ", ".join(str(names.get(m) or m) for m in record.get("mu_ids") or [])
            lines.append(tr(
                "contest.list_line", name=discord.utils.escape_markdown(record.get("name") or "?"),
                status=tr(f"contest.status.{status}"), start=record.get("start_day"), days=record.get("days"),
                units=discord.utils.escape_markdown(units) or tr("common.none"),
            ))
        for message in cx.split_lines(lines or [tr("contest.list_empty")]):
            await interaction.followup.send(message, ephemeral=True)

    @contest_edit.autocomplete("contest")
    @contest_cancel.autocomplete("contest")
    async def _manageable_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._contest_choices(interaction, current, ("draft", "scheduled", "running"), own=True)

    @contest_end.autocomplete("contest")
    async def _running_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._contest_choices(interaction, current, ("running",), own=True)

    @contest_ranking.autocomplete("contest")
    async def _ranking_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._contest_choices(interaction, current, ("running", "ended"), own=False)


async def setup(bot: commands.Bot):
    """Load the contest commands."""
    await bot.add_cog(Contests(bot))
