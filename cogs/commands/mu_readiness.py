"""/mu_readiness: one commander checklist for a configured military unit, before or during a fight.

Read-only and on demand: the reply is posted in the channel and nobody is pinged. It gathers, for the MU now:
headquarters status, whether its battle orders follow Romania's (as /mu_order_alignment), how many fighters stand
where each ordered battle is fought from (as /mu_positions), its latest won contract on an active battle, pill
phases, health and hunger, MU help, equipped gear, the MU tournament (while one is open) and how many leaders
were online lately.

Only objective problems count as "to fix": MU orders that do not follow Romania's, a headquarters that is not
active while the MU has orders, fighters without a weapon or with gear under LOW_DURABILITY_PERCENT, and, during
an open MU tournament, a missing registration or gear above the rarity cap. Counts (pills, help, positions)
are shown without judging them. The MU's oil and paper stock and a contract's progress are not readable with
the bot's API key (session-only procedures), so they are left out.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs.commands.fight_wealth import _messages, _pack
from cogs.commands.mu_order_alignment import BATTLE_LINK, COUNTRY_NAME, TOURNAMENT_BATTLE_TYPE, classify_orders
from cogs.commands.mu_positions import required_region
from cogs.commands.pills import _unit_ids
from cogs.tasks.military_unit_contract_monitor import can_fight, format_amount, format_duration
from cogs.tasks.military_unit_daily_report import _fmt_short, _parse_iso, _pill_settings, pill_state
from utils.api import (
    get_active_battles,
    get_all_countries,
    get_game_config,
    get_last_tournament,
    get_military_unit,
    get_military_units_by_ids,
    get_mu_upgrades,
    get_regions_by_ids,
    get_shared_session,
    get_users_equipment,
    get_users_full,
    get_won_auctions_by_battles,
)
from utils.common import country_with_flag, to_local
from utils.computational import is_economy_build
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

MU_NAMES_TTL = 3600
COUNTRIES_TTL = 3600
GAME_CONFIG_TTL = 3600
EMBED_TOTAL_LIMIT = 4000
# equipped items at or below this share of their durability (state / maxState) are flagged
LOW_DURABILITY_PERCENT = 20
EQUIPMENT_SLOTS = ("weapon", "helmet", "chest", "pants", "boots", "gloves")
# gameConfig items[*].rarity values, lowest first (gameConfig has no ordered list of them)
RARITY_ORDER = ("common", "uncommon", "rare", "epic", "legendary", "mythic")
# tournament.status values after which the tournament no longer needs registering or gear checks
CLOSED_TOURNAMENT_STATUSES = {"ended", "cancelled"}
MU_TOURNAMENT_TYPE = "mu"
# fallback for gameConfig mu.helpCooldownHours
DEFAULT_HELP_COOLDOWN_HOURS = 12
LEADER_ONLINE_WINDOW = timedelta(hours=24)
NAMES_SHOWN = 10
ORDERS_SHOWN = 5


def _current_round_id(battle: dict) -> str:
    """The id of the battle's current round; battle.getBattles populates it, battle.getById gives the id."""
    current = battle.get("currentRound")
    if isinstance(current, dict):
        current = current.get("_id")
    return str(current or "")


def latest_contract(auctions_by_battle: dict[str, list[dict]], battles_by_id: dict[str, dict], mu_id: str) -> dict | None:
    """The MU's most recently won contract that is still on; None when there is none.

    Still on means its battle is active and, for a round contract, its round is the battle's current round.
    Whether the MU already dealt the minimum damage is not visible.
    """
    candidates = []
    for battle_id, auctions in auctions_by_battle.items():
        battle = battles_by_id.get(battle_id)
        if not battle:
            continue
        for auction in auctions:
            if str(auction.get("currentWinner") or "") != mu_id:
                continue
            if auction.get("round") and str(auction["round"]) != _current_round_id(battle):
                continue
            candidates.append(auction)
    return max(candidates, key=lambda auction: str(auction.get("createdAt") or ""), default=None)


def gear_issues(equipment: dict | None, game_items: dict, max_rarity: str | None) -> dict:
    """What is wrong with one fighter's equipped gear.

    Returns {"no_weapon": bool, "low": [(slot, percent)], "over_cap": [code]}; `over_cap` is filled only when
    `max_rarity` is a known rarity (an open MU tournament's cap) and covers the ammo too.
    """
    equipment = equipment or {}
    low = []
    for slot in EQUIPMENT_SLOTS:
        item = equipment.get(slot)
        if not isinstance(item, dict) or not item.get("maxState"):
            continue
        percent = 100 * float(item.get("state") or 0) / float(item["maxState"])
        if percent <= LOW_DURABILITY_PERCENT:
            low.append((slot, round(percent)))
    over_cap = []
    if max_rarity in RARITY_ORDER:
        cap = RARITY_ORDER.index(max_rarity)
        codes = [item.get("code") for slot in EQUIPMENT_SLOTS if isinstance(item := equipment.get(slot), dict)]
        codes.append(equipment.get("ammo"))
        for code in filter(None, codes):
            rarity = (game_items.get(str(code)) or {}).get("rarity")
            if rarity in RARITY_ORDER and RARITY_ORDER.index(rarity) > cap:
                over_cap.append(str(code))
    return {"no_weapon": not isinstance(equipment.get("weapon"), dict), "low": low, "over_cap": over_cap}


class MuReadiness(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # MU id -> in-game name (mu.getById), for the configured military units
        self._mu_names: dict[str, str] = {}
        self._mu_names_at = 0.0
        self._mu_names_task: asyncio.Task | None = None
        # country id -> name, and the id of COUNTRY_NAME
        self._country_names: dict[str, str] = {}
        self._country_id: str | None = None
        self._countries_at = 0.0
        self._game_config: dict = {}
        self._game_config_at = 0.0
        # region id -> name; region names do not change
        self._region_names: dict[str, str] = {}

    async def cog_load(self):
        """Start fetching the configured MUs' names; warmed in the background so autocomplete has them right away."""
        self._refresh_mu_names()

    def cog_unload(self):
        """Cancel a running MU name refresh."""
        if self._mu_names_task and not self._mu_names_task.done():
            self._mu_names_task.cancel()

    def _refresh_mu_names(self) -> None:
        """Start refreshing the MU names unless a refresh is already running."""
        if self._mu_names_task and not self._mu_names_task.done():
            return

        async def _refresh():
            session = await get_shared_session()
            unit_ids = _unit_ids()
            military_units = await get_military_units_by_ids(unit_ids, session)
            for mu_id in unit_ids:
                military_unit = military_units.get(mu_id)
                # a failed fetch keeps the name already known
                if isinstance(military_unit, dict) and military_unit.get("name"):
                    self._mu_names[mu_id] = str(military_unit["name"])
            self._mu_names_at = time.monotonic()

        self._mu_names_task = asyncio.create_task(_refresh())

    def _find_unit(self, value: str) -> str | None:
        """The configured MU id matching an MU id (autocomplete value) or in-game MU name (typed by hand)."""
        value = (value or "").strip()
        for mu_id in _unit_ids():
            if value == mu_id or value.lower() == self._mu_names.get(mu_id, "").lower():
                return mu_id
        return None

    async def _load_countries(self, session) -> bool:
        """Refresh the country names and COUNTRY_NAME's id when stale; False when the id is unknown."""
        if self._country_id and time.monotonic() - self._countries_at < COUNTRIES_TTL:
            return True
        countries = await get_all_countries(session)
        if not countries:
            # a failed refresh keeps the previous list
            return self._country_id is not None
        for country in countries:
            country_id = str(country.get("_id") or country.get("id") or "")
            name = str(country.get("name") or "")
            if not country_id or not name:
                continue
            self._country_names[country_id] = name
            if name.lower() == COUNTRY_NAME.lower():
                self._country_id = country_id
        self._countries_at = time.monotonic()
        return self._country_id is not None

    async def _load_game_config(self, session) -> dict:
        """gameConfig, refreshed when stale; a failed refresh keeps the last one ({} before the first)."""
        if self._game_config and time.monotonic() - self._game_config_at < GAME_CONFIG_TTL:
            return self._game_config
        game_config = await get_game_config(session)
        if game_config:
            self._game_config, self._game_config_at = game_config, time.monotonic()
        return self._game_config

    async def _load_region_names(self, region_ids: set[str], session) -> None:
        """Fetch the names of the regions not cached yet; regions that fail are shown without a name."""
        missing = [region_id for region_id in region_ids if region_id not in self._region_names]
        if not missing:
            return
        for region_id, region in (await get_regions_by_ids(missing, session)).items():
            if isinstance(region, dict) and region.get("name"):
                self._region_names[region_id] = str(region["name"])

    @app_commands.command(
        name="mu_readiness",
        description="Commander checklist for a military unit: HQ, orders, positions, contract, pills, help, gear.",
    )
    @app_commands.describe(military_unit="Military unit (one of the units configured for this server)")
    async def mu_readiness_command(self, interaction: discord.Interaction, military_unit: str):
        tr = await get_translator(interaction.guild_id)
        mu_id = self._find_unit(military_unit)
        if mu_id is None:
            await interaction.response.send_message(tr("mu_readiness.unknown_unit"), ephemeral=True)
            return
        await interaction.response.defer()

        session = await get_shared_session()
        mu, battles, countries_loaded, game_config, upgrades, tournament = await asyncio.gather(
            get_military_unit(mu_id, session),
            get_active_battles(session),
            self._load_countries(session),
            self._load_game_config(session),
            get_mu_upgrades(mu_id, ["headquarters", "dormitories"], session),
            get_last_tournament(session),
        )
        if not isinstance(mu, dict) or battles is None or not countries_loaded:
            await interaction.followup.send(tr("mu_readiness.fetch_failed"), ephemeral=True)
            return
        if mu.get("name"):
            self._mu_names[mu_id] = str(mu["name"])

        member_ids = [str(user_id) for user_id in mu.get("members") or []]
        leader_ids = list(dict.fromkeys(str(user_id) for user_id in [mu.get("user"), *((mu.get("roles") or {}).get("commanders") or [])] if user_id))
        battles_by_id = {str(battle.get("_id")): battle for battle in battles if battle.get("_id")}
        users, auctions = await asyncio.gather(
            get_users_full(member_ids + leader_ids, session),
            get_won_auctions_by_battles(list(battles_by_id), session) if battles_by_id else asyncio.sleep(0, result={}),
        )
        members = [users[user_id] for user_id in member_ids if user_id in users]
        fighters = [user for user in members if is_economy_build(user) is False]

        categories = classify_orders(battles, mu_id, self._country_id)
        contract = latest_contract(auctions, battles_by_id, mu_id)
        mu_orders = [pair for category in ("aligned", "opposite", "not_ordered", "tournament") for pair in categories[category]]
        targets = [battle for battle, _ in mu_orders] + ([battles_by_id[str(contract["battle"])]] if contract else [])
        region_ids = {region_id for battle in targets for side in ("attacker", "defender") if (region_id := required_region(battle, side))}
        equipment, _ = await asyncio.gather(
            get_users_equipment([str(user["_id"]) for user in fighters if user.get("_id")], session) if fighters else asyncio.sleep(0, result={}),
            self._load_region_names(region_ids, session),
        )

        context = {
            "mu_id": mu_id,
            "mu": mu,
            "members": members,
            "member_count": len(member_ids),
            "fighters": fighters,
            "leaders": [users[user_id] for user_id in leader_ids if user_id in users],
            "leader_count": len(leader_ids),
            "categories": categories,
            "mu_orders": mu_orders,
            "battles_by_id": battles_by_id,
            "contract": contract,
            "game_config": game_config,
            "upgrades": upgrades,
            "tournament": tournament,
            "equipment": equipment,
            "now": datetime.now(timezone.utc),
        }
        mu_name = discord.utils.escape_markdown(self._mu_names.get(mu_id, mu_id))
        for message_embeds in _messages(self._build_embeds(mu_name, context, tr)):
            await interaction.followup.send(embeds=message_embeds)

    def _name(self, user: dict, tr: Translator) -> str:
        """The player's escaped username."""
        return discord.utils.escape_markdown(str(user.get("username") or tr("common.unknown")))

    def _names(self, names: list[str], tr: Translator) -> str:
        """The first NAMES_SHOWN names joined by commas, plus "and N more"."""
        shown = ", ".join(names[:NAMES_SHOWN])
        if len(names) > NAMES_SHOWN:
            shown += ", " + tr("mu_daily.and_more", count=len(names) - NAMES_SHOWN)
        return shown

    def _time(self, value: datetime, tr: Translator) -> str:
        """A time in the configured timezone, e.g. "21:00 EEST" (with the date when it is not today)."""
        local, today = to_local(value), to_local(datetime.now(timezone.utc)).date()
        if local.date() == today:
            return f"{local:%H:%M} {local.tzname()}"
        return f"{tr.strftime(local, tr('mu_daily.datetime_format'))} {local.tzname()}"

    def _battle_title(self, battle: dict, tr: Translator) -> str:
        """Linked "A vs B" (or "Tournament battle")."""
        unknown = tr("common.unknown")
        if battle.get("type") == TOURNAMENT_BATTLE_TYPE:
            title = tr("common.tournament_battle")
        else:
            attacker = self._country_names.get(str((battle.get("attacker") or {}).get("country") or ""))
            defender = self._country_names.get(str((battle.get("defender") or {}).get("country") or ""))
            title = f"{country_with_flag(attacker, left=True, unknown=unknown)} vs {country_with_flag(defender, left=False, unknown=unknown)}"
        return f"[{title}]({BATTLE_LINK.format(battle.get('_id'))})"

    def _side_label(self, battle: dict, side: str, tr: Translator) -> str:
        """The country fighting on `side` with its flag; the side's name in tournament battles."""
        country_id = str((battle.get(side) or {}).get("country") or "")
        if not country_id:
            return tr(f"common.side_title.{side}")
        return country_with_flag(self._country_names.get(country_id), left=True, unknown=tr("common.unknown"))

    def _position(self, battle: dict, side: str, fighters: list[dict], tr: Translator) -> str:
        """How many fighters stand where `side` of the battle is fought from, e.g. "📍 17/24 in Belgrade"."""
        region_id = required_region(battle, side)
        if region_id is None:
            return tr("mu_readiness.position_anywhere", count=len(fighters))
        in_position = sum(1 for user in fighters if str(user.get("location") or "") == region_id)
        region = discord.utils.escape_markdown(self._region_names.get(region_id) or tr("mu_positions.unknown_region"))
        return tr("mu_readiness.position", count=in_position, fighters=len(fighters), region=region)

    def _hq_field(self, context: dict, tr: Translator) -> tuple[str, bool]:
        """The headquarters line and whether it is a problem (not active while the MU has orders)."""
        upgrade = context["upgrades"].get("headquarters") or {}
        level = int(upgrade.get("level") or (context["mu"].get("activeUpgradeLevels") or {}).get("headquarters") or 0)
        has_orders = bool(context["mu_orders"])
        if not level:
            return tr("mu_readiness.hq_none"), has_orders
        levels = (((context["game_config"].get("upgradesConfig") or {}).get("headquarters") or {}).get("levels") or {})
        level_config = levels.get(str(level)) or {}
        bonus = (level_config.get("stats") or {}).get("attackBonus")
        oil_per_hour = level_config.get("maintenanceCost")
        details = tr("mu_readiness.hq_details", bonus=bonus, oil=oil_per_hour, oil_day=oil_per_hour * 24) if bonus is not None and oil_per_hour is not None else ""
        active_at = _parse_iso(upgrade.get("willBeActiveAt"))
        if active_at and active_at > context["now"]:
            return tr("mu_readiness.hq_activating", level=level, time=self._time(active_at, tr)) + details, False
        if upgrade.get("status") == "active" or (not upgrade and level):
            return tr("mu_readiness.hq_active", level=level) + details, False
        return tr("mu_readiness.hq_disabled", level=level), has_orders

    def _build_embeds(self, mu_name: str, context: dict, tr: Translator) -> list[discord.Embed]:
        """The checklist: verdict and roster in the description, then one field per check."""
        now, fighters, categories = context["now"], context["fighters"], context["categories"]
        country = country_with_flag(COUNTRY_NAME, left=True)
        issues = 0
        fields: list[tuple[str, str]] = []

        # headquarters
        hq_text, hq_issue = self._hq_field(context, tr)
        issues += hq_issue
        fields.append((tr("mu_readiness.hq_title"), ("⚠️ " if hq_issue else "") + hq_text))

        # orders, as /mu_order_alignment
        wrong = len(categories["opposite"]) + len(categories["not_ordered"])
        issues += wrong
        country_orders = len(categories["aligned"]) + len(categories["opposite"]) + len(categories["missing"])
        if wrong:
            orders_text = tr("mu_readiness.orders_wrong", count=wrong, total=len(context["mu_orders"]), country=country)
        elif context["mu_orders"]:
            orders_text = tr("mu_readiness.orders_ok", count=len(context["mu_orders"]), country=country)
        else:
            orders_text = tr("mu_readiness.orders_none", country=country, count=country_orders)
        if categories["missing"]:
            orders_text += "\n" + tr("mu_readiness.orders_missing", count=len(categories["missing"]), country=country)
        fields.append((tr("mu_readiness.orders_title"), orders_text))

        # positions for each MU order, as /mu_positions
        if context["mu_orders"]:
            lines = [
                f"{self._battle_title(battle, tr)} · {tr('mu_alignment.for_side', side=self._side_label(battle, side, tr))}\n"
                f"{self._position(battle, side, fighters, tr)}"
                for battle, side in context["mu_orders"][:ORDERS_SHOWN]
            ]
            if len(context["mu_orders"]) > ORDERS_SHOWN:
                lines.append(tr("mu_daily.and_more", count=len(context["mu_orders"]) - ORDERS_SHOWN))
            fields += _pack(tr("mu_readiness.positions_title"), lines)

        # latest won contract on an active battle
        contract = context["contract"]
        if contract:
            battle = context["battles_by_id"][str(contract["battle"])]
            side = str(contract.get("forCountrySide") or "attacker")
            won_at = _parse_iso(contract.get("createdAt"))
            contract_text = "\n".join([
                f"{self._battle_title(battle, tr)} · {tr('mu_alignment.for_side', side=self._side_label(battle, side, tr))}",
                tr(
                    "mu_readiness.contract_terms",
                    minimum=_fmt_short(contract.get("minimumDamage")),
                    per_k=format_amount(contract.get("currentPerK"), tr("common.unknown")),
                    payout=format_amount(contract.get("currentPayout"), tr("common.unknown")),
                ),
                (tr("mu_readiness.contract_won", ago=format_duration(now - won_at)) + " · " if won_at else "")
                + self._position(battle, side, fighters, tr),
            ])
        else:
            contract_text = tr("mu_readiness.contract_none")
        fields.append((tr("mu_readiness.contract_title"), contract_text))

        # pills, health and hunger, MU help (fighters only)
        settings = _pill_settings(context["game_config"])
        pills = [(user, pill_state(user, now, settings)) for user in fighters]
        buffed = [user for user, state in pills if state["phase"] == "buff"]
        debuffed = [state for _, state in pills if state["phase"] == "debuff"]
        pills_text = tr(
            "mu_readiness.pills",
            buffed=len(buffed),
            ready=sum(1 for _, state in pills if state["phase"] is None),
            debuff=len(debuffed),
        )
        if debuffed:
            pills_text += "\n" + tr("mu_readiness.next_pill", time=self._time(min(state["ready_at"] for state in debuffed), tr))
        fields.append((tr("mu_readiness.pills_title"), pills_text))

        full_bars = 0
        for user, state in pills:
            skills = user.get("skills") or {}
            if state["phase"] != "debuff" and any(
                (skills.get(skill) or {}).get("total") and ((skills[skill].get("currentBarValue") or 0) >= skills[skill]["total"])
                for skill in ("health", "hunger")
            ):
                full_bars += 1
        fields.append((
            tr("mu_readiness.stats_title"),
            tr("mu_readiness.stats", can_fight=sum(1 for user in fighters if can_fight(user, now)), fighters=len(fighters), full=full_bars),
        ))

        cooldown = timedelta(hours=float(((context["game_config"].get("mu") or {}).get("helpCooldownHours")) or DEFAULT_HELP_COOLDOWN_HOURS))

        def help_ready(user: dict) -> bool:
            asked_at = _parse_iso((user.get("dates") or {}).get("lastHelpAskedAt"))
            return asked_at is None or asked_at + cooldown <= now

        help_text = tr("mu_readiness.help", count=sum(1 for user in fighters if help_ready(user)), fighters=len(fighters))
        buffed_no_help = sorted((self._name(user, tr) for user in buffed if help_ready(user)), key=str.lower)
        if buffed_no_help:
            help_text += "\n" + tr("mu_readiness.help_buffed", names=self._names(buffed_no_help, tr))
        fields.append((tr("mu_readiness.help_title"), help_text))

        # gear, and the open MU tournament
        tournament = context["tournament"] or {}
        open_mu_tournament = tournament.get("type") == MU_TOURNAMENT_TYPE and str(tournament.get("status") or "") not in CLOSED_TOURNAMENT_STATUSES
        max_rarity = str(tournament.get("maxRarity") or "") if open_mu_tournament else None
        game_items = context["game_config"].get("items") or {}
        equipment = context["equipment"]
        gear_lines, over_cap = [], []
        if not fighters:
            gear_text = tr("mu_readiness.no_fighters")
        elif not equipment:
            gear_text = tr("common.unavailable")
        else:
            no_weapon, low = [], []
            for user in sorted(fighters, key=lambda user: self._name(user, tr).lower()):
                found = equipment.get(str(user.get("_id")))
                gear = gear_issues(found, game_items, max_rarity)
                if gear["no_weapon"]:
                    no_weapon.append(self._name(user, tr))
                if gear["low"]:
                    slots = ", ".join(f"{tr(f'mu_readiness.slot.{slot}')} {percent}%" for slot, percent in gear["low"])
                    low.append(f"{self._name(user, tr)} ({slots})")
                if gear["over_cap"]:
                    over_cap.append(f"{self._name(user, tr)} ({', '.join(gear['over_cap'])})")
            issues += len(no_weapon) + len(low)
            if no_weapon:
                gear_lines.append(tr("mu_readiness.gear_no_weapon", names=self._names(no_weapon, tr)))
            if low:
                gear_lines.append(tr("mu_readiness.gear_low", percent=LOW_DURABILITY_PERCENT, names=self._names(low, tr)))
            gear_text = "\n".join(gear_lines) or tr("mu_readiness.gear_ok", fighters=len(fighters))
        fields += _pack(tr("mu_readiness.gear_title"), gear_text.split("\n"))

        if open_mu_tournament:
            registered = context["mu_id"] in [str(mu) for mu in ((tournament.get("registered") or {}).get("mus") or [])]
            issues += (not registered) + len(over_cap)
            start_at = _parse_iso(tournament.get("startAt"))
            lines = [
                tr("mu_readiness.tournament_registered" if registered else "mu_readiness.tournament_not_registered")
                + (" · " + tr("mu_readiness.tournament_start", time=self._time(start_at, tr)) if start_at else ""),
                tr(
                    "mu_readiness.tournament_rules",
                    rarity=(max_rarity or tr("common.unknown")).capitalize(),
                    skill=str(tournament.get("skillKey") or tr("common.unknown")).capitalize(),
                ),
            ]
            if over_cap:
                lines.append(tr("mu_readiness.tournament_over_cap", names=self._names(over_cap, tr)))
            fields += _pack(tr("mu_readiness.tournament_title"), lines)

        # leaders (owner and commanders) seen lately
        online = sum(
            1 for user in context["leaders"]
            if (seen := _parse_iso((user.get("dates") or {}).get("lastConnectionAt"))) and now - seen < LEADER_ONLINE_WINDOW
        )
        fields.append((tr("mu_readiness.leaders_title"), tr("mu_readiness.leaders", online=online, total=context["leader_count"])))

        dormitories = context["upgrades"].get("dormitories") or {}
        dorm_level = str(dormitories.get("level") or (context["mu"].get("activeUpgradeLevels") or {}).get("dormitories") or "")
        dorm_levels = (((context["game_config"].get("upgradesConfig") or {}).get("dormitories") or {}).get("levels") or {})
        capacity = ((dorm_levels.get(dorm_level) or {}).get("stats") or {}).get("members")
        description = "\n".join([
            tr("mu_readiness.verdict_issues", count=issues) if issues else tr("mu_readiness.verdict_ok"),
            tr(
                "mu_readiness.roster",
                members=context["member_count"],
                capacity=capacity if capacity else "?",
                fighters=len(fighters),
                economy=len(context["members"]) - len(fighters),
            ),
        ])
        return self._split(tr("mu_readiness.title", mu=mu_name), description, fields, tr("mu_readiness.footer", percent=LOW_DURABILITY_PERCENT), now)

    def _split(self, title: str, description: str, fields: list[tuple[str, str]], footer: str, now: datetime) -> list[discord.Embed]:
        """The fields in as many embeds as EMBED_TOTAL_LIMIT needs, titles numbered "(i/N)" when there are several."""

        def new_embed(first: bool) -> discord.Embed:
            embed = discord.Embed(title=title, description=description if first else None, color=discord.Color.dark_teal(), timestamp=now)
            embed.set_footer(text=footer)
            return embed

        embeds = [new_embed(first=True)]
        for name, value in fields:
            # room is kept for the " (i/N)" added to the titles below
            if embeds[-1].fields and len(embeds[-1]) + len(name) + len(value) + len(" (10/10)") > EMBED_TOTAL_LIMIT:
                embeds.append(new_embed(first=False))
            embeds[-1].add_field(name=name, value=value, inline=False)
        if len(embeds) > 1:
            for index, embed in enumerate(embeds, start=1):
                embed.title = f"{title} ({index}/{len(embeds)})"
        return embeds

    @mu_readiness_command.autocomplete("military_unit")
    async def military_unit_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Configured MUs whose in-game name contains `current`, from the cache only (Discord waits about 3 s)."""
        if time.monotonic() - self._mu_names_at > MU_NAMES_TTL:
            self._refresh_mu_names()
        current = (current or "").lower()
        # an MU whose name has not been fetched yet is offered by its id
        names = sorted(((self._mu_names.get(mu_id, mu_id), mu_id) for mu_id in _unit_ids()), key=lambda item: item[0].lower())
        return [
            app_commands.Choice(name=name[:100], value=mu_id)
            for name, mu_id in names
            if current in name.lower()
        ][:25]


async def setup(bot: commands.Bot):
    """Extension entry point for bot.load_extension."""
    await bot.add_cog(MuReadiness(bot))
