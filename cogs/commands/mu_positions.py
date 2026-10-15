"""/mu_positions: where the members of a configured military unit stand, overall or for one battle.

Players hit only from where they stand: attackers from the region the attack was launched from
(`attacker.region`), defenders from the attacked region (`defender.region`), both sides of a resistance
battle from the disputed region (the defender's region; the attacker has none), tournament battles from
anywhere. Read-only and on demand: the reply is posted in the channel and nobody is pinged.

- Without a battle: members grouped by current region, with the active battles that can be fought there and
  how many members stand in position for each battle the MU or Romania ordered.
- With a battle: who is in position for the side the MU (or else Romania) ordered, who stands in the other
  side's region, and how far everyone else is, with the Stamina and oil the trip costs.
"""
import asyncio
import logging
import re
import time
from collections import deque
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs.commands.fight_wealth import _messages, _pack
from cogs.commands.mu_order_alignment import BATTLE_LINK, COUNTRY_NAME, SIDES, TOURNAMENT_BATTLE_TYPE, _opposite, _side_ids
from cogs.commands.pills import _unit_ids
from utils.api import (
    get_active_battles,
    get_all_countries,
    get_battle,
    get_game_config,
    get_military_unit,
    get_military_units_by_ids,
    get_regions_object,
    get_shared_session,
    get_users_full,
)
from utils.common import country_flag, country_with_flag
from utils.computational import is_economy_build
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

BATTLE_ID_RE = re.compile(r"(?:battle/)?([a-f\d]{24})\b")
MU_NAMES_TTL = 3600
COUNTRIES_TTL = 3600
# region names, owners and neighbours change rarely (owners only when a region is conquered)
REGIONS_TTL = 6 * 3600
GAME_CONFIG_TTL = 3600
# the battle autocomplete reads this cache; a command without a battle always refetches the list
BATTLES_TTL = 120
# travel costs from the game guide v0.26.1 (warera-game-expert map-and-travel.md); gameConfig has no key
# for them [checked 2026-10-14]: each region crossed costs 10 Stamina, or 2 oil when Stamina runs short
STAMINA_PER_REGION = 10
OIL_PER_REGION = 2
# fallback for gameConfig region.freeTravelHomeCooldownHours
DEFAULT_FREE_TRAVEL_HOME_HOURS = 12
EMBED_TOTAL_LIMIT = 4000
NAMES_PER_REGION = 12
MU_MARKER = "🎖️"


def required_region(battle: dict, side: str) -> str | None:
    """The region a player must stand in to hit for `side`; None when any region will do (tournaments).

    An attack is fought from its launch region and a defense from the attacked region. A resistance battle
    has no attacker region: both sides fight from the disputed region, which is the defender's.
    """
    if battle.get("type") == TOURNAMENT_BATTLE_TYPE:
        return None
    region = (battle.get(side) or {}).get("region") or (battle.get("defender") or {}).get("region")
    return str(region) if region else None


def region_distances(regions: dict[str, dict], source: str) -> dict[str, int]:
    """Regions crossed to reach `source` from every region, by breadth-first search over `neighbors`."""
    distances = {source: 0}
    queue = deque([source])
    while queue:
        region_id = queue.popleft()
        for neighbor in (regions.get(region_id) or {}).get("neighbors") or []:
            if neighbor not in distances:
                distances[neighbor] = distances[region_id] + 1
                queue.append(neighbor)
    return distances


def travel_cost(distance: int, stamina: float) -> tuple[int, int]:
    """(Stamina spent, oil needed) to cross `distance` regions: Stamina pays first, oil covers the rest."""
    stamina_regions = min(distance, int(stamina // STAMINA_PER_REGION))
    return stamina_regions * STAMINA_PER_REGION, (distance - stamina_regions) * OIL_PER_REGION


def _unicode_flag(code: str | None) -> str | None:
    """The Unicode flag of an ISO 3166 alpha-2 country code; None for an invalid code.

    Used where ":flag_xx:" shortcodes do not render (autocomplete labels). The game's "uk" is the "gb" flag.
    """
    code = (code or "").strip().lower()
    code = "gb" if code == "uk" else code
    if len(code) != 2 or not code.isascii() or not code.isalpha():
        return None
    return "".join(chr(0x1F1E6 + ord(letter) - ord("a")) for letter in code)


def _parse_iso(value) -> datetime | None:
    """An ISO timestamp from the API as an aware datetime; None when missing or malformed."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class MuPositions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # MU id -> in-game name (mu.getById), for the configured military units
        self._mu_names: dict[str, str] = {}
        self._mu_names_at = 0.0
        self._mu_names_task: asyncio.Task | None = None
        # country id -> name, and the id and Unicode flag of COUNTRY_NAME
        self._country_names: dict[str, str] = {}
        self._country_id: str | None = None
        self._country_unicode_flag: str | None = None
        self._countries_at = 0.0
        # region id -> {"name", "country", "neighbors"}: the map graph, from region.getRegionsObject
        self._regions: dict[str, dict] = {}
        self._regions_at = 0.0
        self._free_travel_home_hours: float = DEFAULT_FREE_TRAVEL_HOME_HOURS
        self._game_config_at = 0.0
        # active battles, for the battle autocomplete
        self._battles: list[dict] = []
        self._battles_at = 0.0
        self._warm_task: asyncio.Task | None = None

    async def cog_load(self):
        """Warm the MU names and the autocomplete data in the background so autocomplete has them right away."""
        self._refresh_mu_names()
        self._warm()

    def cog_unload(self):
        """Cancel running background refreshes."""
        for task in (self._mu_names_task, self._warm_task):
            if task and not task.done():
                task.cancel()

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

    def _warm(self) -> None:
        """Start refreshing the battles, regions and countries the battle autocomplete labels need."""
        if self._warm_task and not self._warm_task.done():
            return

        async def _refresh():
            session = await get_shared_session()
            await asyncio.gather(self._load_battles(session, BATTLES_TTL), self._load_regions(session), self._load_countries(session))

        self._warm_task = asyncio.create_task(_refresh())

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
                self._country_unicode_flag = _unicode_flag(country.get("code"))
        self._countries_at = time.monotonic()
        return self._country_id is not None

    async def _load_regions(self, session) -> bool:
        """Refresh the map graph when stale (one ~0.9 MB request); False when no map is known."""
        if self._regions and time.monotonic() - self._regions_at < REGIONS_TTL:
            return True
        regions = await get_regions_object(session)
        if not regions:
            # a failed refresh keeps the previous map
            return bool(self._regions)
        self._regions = {
            str(region_id): {
                "name": str(region.get("name") or region_id),
                "country": str(region.get("country") or ""),
                "neighbors": [str(neighbor) for neighbor in region.get("neighbors") or []],
            }
            for region_id, region in regions.items()
            if isinstance(region, dict)
        }
        self._regions_at = time.monotonic()
        return True

    async def _load_battles(self, session, max_age: float) -> list[dict] | None:
        """The active battles, refetched when the cache is older than `max_age` seconds; None on failure."""
        if self._battles_at and time.monotonic() - self._battles_at < max_age:
            return self._battles
        battles = await get_active_battles(session)
        if battles is None:
            return None
        self._battles, self._battles_at = battles, time.monotonic()
        return battles

    async def _load_free_travel_home_hours(self, session) -> None:
        """Refresh gameConfig region.freeTravelHomeCooldownHours when stale; failures keep the last value."""
        if self._game_config_at and time.monotonic() - self._game_config_at < GAME_CONFIG_TTL:
            return
        game_config = await get_game_config(session)
        hours = ((game_config or {}).get("region") or {}).get("freeTravelHomeCooldownHours")
        if isinstance(hours, (int, float)) and hours > 0:
            self._free_travel_home_hours = float(hours)
            self._game_config_at = time.monotonic()

    @app_commands.command(
        name="mu_positions",
        description="Show where a military unit's members stand, overall or for one battle.",
    )
    @app_commands.describe(
        military_unit="Military unit (one of the units configured for this server)",
        battle="Active battle (autocomplete, or a battle link); leave empty to see where the members are",
    )
    async def mu_positions_command(self, interaction: discord.Interaction, military_unit: str, battle: str | None = None):
        tr = await get_translator(interaction.guild_id)
        mu_id = self._find_unit(military_unit)
        if mu_id is None:
            await interaction.response.send_message(tr("mu_positions.unknown_unit"), ephemeral=True)
            return
        battle_id = None
        if battle:
            match = BATTLE_ID_RE.search(battle.strip())
            if not match:
                await interaction.response.send_message(tr("mu_positions.invalid_battle"), ephemeral=True)
                return
            battle_id = match.group(1)
        await interaction.response.defer()

        session = await get_shared_session()
        military_unit_data, battle_data, regions_loaded, countries_loaded, _ = await asyncio.gather(
            get_military_unit(mu_id, session),
            get_battle(battle_id, session) if battle_id else self._load_battles(session, 0),
            self._load_regions(session),
            self._load_countries(session),
            self._load_free_travel_home_hours(session),
        )
        if not isinstance(military_unit_data, dict) or battle_data is None or not regions_loaded or not countries_loaded:
            await interaction.followup.send(tr("mu_positions.fetch_failed"), ephemeral=True)
            return
        if military_unit_data.get("name"):
            self._mu_names[mu_id] = str(military_unit_data["name"])
        if battle_id and not battle_data.get("isActive"):
            await interaction.followup.send(tr("mu_positions.battle_not_active"), ephemeral=True)
            return

        member_ids = [str(user_id) for user_id in military_unit_data.get("members") or []]
        users = await get_users_full(member_ids, session)
        members = [self._member_row(users[user_id], tr) for user_id in member_ids if user_id in users]
        mu_name = discord.utils.escape_markdown(self._mu_names.get(mu_id, mu_id))
        now = datetime.now(timezone.utc)
        if battle_id:
            embeds = self._battle_embeds(mu_name, mu_id, battle_data, members, len(member_ids), now, tr)
        else:
            embeds = self._map_embeds(mu_name, mu_id, battle_data, members, len(member_ids), now, tr)
        for message_embeds in _messages(embeds):
            await interaction.followup.send(embeds=message_embeds)

    def _member_row(self, user: dict, tr: Translator) -> dict:
        """What the report needs of one member: name, current and home region, Stamina, free trip home."""
        last_free_trip = _parse_iso((user.get("dates") or {}).get("lastFreeTravelHomeAt"))
        return {
            "name": discord.utils.escape_markdown(str(user.get("username") or tr("common.unknown"))),
            "location": str(user.get("location") or ""),
            "home": str(user.get("region") or ""),
            "stamina": float(((user.get("skills") or {}).get("stamina") or {}).get("currentBarValue") or 0),
            # never used, or used longer ago than the cooldown
            "free_trip_at": (last_free_trip + timedelta(hours=self._free_travel_home_hours)) if last_free_trip else None,
            # fighters are members with a fight build, as in the daily report
            "economy": is_economy_build(user) is not False,
        }

    def _member_name(self, row: dict, bold: bool = True) -> str:
        """The member's name (bold on its own line, plain in a comma list), with 🏭 for an economy build."""
        name = f"**{row['name']}**" if bold else row["name"]
        return name + (" 🏭" if row["economy"] else "")

    def _region_label(self, region_id: str, tr: Translator, flag: bool = True) -> str:
        """The region's name followed by its owner's flag; `flag=False` for field names, where only the name goes."""
        region = self._regions.get(region_id)
        if not region:
            return tr("mu_positions.unknown_region")
        name = discord.utils.escape_markdown(region["name"])
        owner_flag = country_flag(self._country_names.get(region["country"])) if flag else None
        return f"{name} {owner_flag}" if owner_flag else name

    def _side_label(self, battle: dict, side: str, tr: Translator) -> str:
        """The country fighting on `side` with its flag; the side's name in tournament battles."""
        country_id = str((battle.get(side) or {}).get("country") or "")
        if not country_id:
            return tr(f"common.side_title.{side}")
        return country_with_flag(self._country_names.get(country_id), left=True, unknown=tr("common.unknown"))

    def _battle_title(self, battle: dict, tr: Translator) -> str:
        """Linked "A vs B" (or "Tournament battle")."""
        attacker = str((battle.get("attacker") or {}).get("country") or "")
        defender = str((battle.get("defender") or {}).get("country") or "")
        unknown = tr("common.unknown")
        if battle.get("type") != TOURNAMENT_BATTLE_TYPE:
            title = (
                f"{country_with_flag(self._country_names.get(attacker), left=True, unknown=unknown)} vs "
                f"{country_with_flag(self._country_names.get(defender), left=False, unknown=unknown)}"
            )
        else:
            title = tr("common.tournament_battle")
        return f"[{title}]({BATTLE_LINK.format(battle.get('_id'))})"

    def _order_markers(self, battle: dict, side: str, mu_id: str) -> str:
        """🎖️ when the MU ordered `side`, the country's flag when it did, joined by a space."""
        markers = []
        if mu_id in _side_ids(battle, side, "muOrders"):
            markers.append(MU_MARKER)
        if self._country_id and self._country_id in _side_ids(battle, side, "countryOrders"):
            markers.append(country_flag(COUNTRY_NAME) or COUNTRY_NAME)
        return " ".join(markers)

    def _map_embeds(
        self, mu_name: str, mu_id: str, battles: list[dict], members: list[dict], member_count: int, now: datetime, tr: Translator
    ) -> list[discord.Embed]:
        """Members grouped by current region, the battles fightable there, and who is in position per ordered battle."""
        # region -> [(battle, side or None when both sides fight from there)]
        battles_by_region: dict[str, list[tuple[dict, str | None]]] = {}
        ordered: list[tuple[dict, str]] = []
        for battle in battles:
            sides_by_region: dict[str, list[str]] = {}
            for side in SIDES:
                region_id = required_region(battle, side)
                if region_id:
                    sides_by_region.setdefault(region_id, []).append(side)
                if self._order_markers(battle, side, mu_id):
                    ordered.append((battle, side))
            for region_id, sides in sides_by_region.items():
                battles_by_region.setdefault(region_id, []).append((battle, sides[0] if len(sides) == 1 else None))

        by_region: dict[str, list[dict]] = {}
        for row in members:
            by_region.setdefault(row["location"], []).append(row)
        unknown = by_region.pop("", [])

        fields: list[tuple[str, str]] = []
        if ordered:
            # the MU's own orders first
            ordered.sort(key=lambda pair: MU_MARKER not in self._order_markers(pair[0], pair[1], mu_id))
            lines = []
            for battle, side in ordered:
                region_id = required_region(battle, side)
                in_position = len(members) if region_id is None else len(by_region.get(region_id, []))
                region = tr("mu_positions.anywhere") if region_id is None else self._region_label(region_id, tr)
                lines.append(tr(
                    "mu_positions.ordered_line",
                    battle=self._battle_title(battle, tr),
                    side=self._side_label(battle, side, tr),
                    markers=self._order_markers(battle, side, mu_id),
                    region=region,
                    count=in_position,
                    members=len(members),
                ))
            fields += _pack(tr("mu_positions.ordered_title", count=len(ordered)), lines)

        blocks = []
        for region_id, rows in sorted(by_region.items(), key=lambda item: (-len(item[1]), self._region_label(item[0], tr))):
            block = tr("mu_positions.region_line", region=self._region_label(region_id, tr), count=len(rows))
            for battle, side in battles_by_region.get(region_id, []):
                side_text = tr("mu_positions.both_sides") if side is None else self._side_label(battle, side, tr)
                markers = " ".join(filter(None, (self._order_markers(battle, s, mu_id) for s in ([side] if side else SIDES))))
                block += "\n" + tr("mu_positions.battle_here", battle=self._battle_title(battle, tr), side=side_text)
                if markers:
                    block += f" {markers}"
            names = [self._member_name(row, bold=False) for row in sorted(rows, key=lambda row: row["name"].lower())]
            shown = ", ".join(names[:NAMES_PER_REGION])
            if len(names) > NAMES_PER_REGION:
                shown += ", " + tr("mu_daily.and_more", count=len(names) - NAMES_PER_REGION)
            blocks.append(f"{block}\n{shown}")
        if blocks:
            fields += _pack(tr("mu_positions.regions_title", count=len(by_region)), blocks)
        if unknown:
            fields += _pack(tr("mu_positions.unknown_location_title", count=len(unknown)), [", ".join(self._member_name(row, bold=False) for row in unknown)])

        description = tr("mu_positions.map_summary", members=member_count, regions=len(by_region))
        if len(members) < member_count:
            description += "\n" + tr("mu_positions.members_missing", count=member_count - len(members))
        return self._split(tr("mu_positions.title_map", mu=mu_name), description, fields, tr("mu_positions.footer_map", mu=MU_MARKER, country=country_flag(COUNTRY_NAME) or COUNTRY_NAME), now)

    def _battle_embeds(
        self, mu_name: str, mu_id: str, battle: dict, members: list[dict], member_count: int, now: datetime, tr: Translator
    ) -> list[discord.Embed]:
        """Who is in position for one battle, who stands on the other side, and the trip for everyone else."""
        mu_sides = [side for side in SIDES if mu_id in _side_ids(battle, side, "muOrders")]
        country_sides = [side for side in SIDES if self._country_id and self._country_id in _side_ids(battle, side, "countryOrders")]
        notes = []
        if mu_sides:
            side = mu_sides[0]
            notes.append(tr("mu_positions.side_from_mu"))
            if country_sides and side not in country_sides:
                notes.append(tr("mu_positions.side_conflict", country=COUNTRY_NAME))
        elif country_sides:
            side = country_sides[0]
            notes.append(tr("mu_positions.side_from_country", country=COUNTRY_NAME))
        else:
            side = None
        target = required_region(battle, side) if side else None

        fields: list[tuple[str, str]] = []
        if battle.get("type") == TOURNAMENT_BATTLE_TYPE:
            description = self._battle_title(battle, tr) + "\n" + tr("mu_positions.tournament_anywhere")
        elif target is None:
            # no order to follow (or, rarely, no region for the ordered side): who stands where each side fights from
            description = self._battle_title(battle, tr) + "\n" + (
                tr("mu_positions.no_order", country=COUNTRY_NAME) if side is None else tr("mu_positions.no_side_region")
            )
            placed: set[int] = set()
            for each_side in SIDES:
                region_id = required_region(battle, each_side)
                rows = sorted(
                    (row for row in members if region_id and row["location"] == region_id), key=lambda row: row["name"].lower()
                )
                placed.update(id(row) for row in rows)
                if rows:
                    title = tr(f"mu_positions.{each_side}_region_title", region=self._region_label(region_id, tr, flag=False), count=len(rows))
                    fields += _pack(title, [", ".join(self._member_name(row, bold=False) for row in rows)])
            rest = [row for row in members if id(row) not in placed]
            if rest:
                lines = [
                    tr("mu_positions.elsewhere_plain", name=self._member_name(row), region=self._region_label(row["location"], tr))
                    for row in sorted(rest, key=lambda row: row["name"].lower())
                ]
                fields += _pack(tr("mu_positions.elsewhere_title", count=len(rest)), lines)
        else:
            other = required_region(battle, _opposite(side))
            distances = region_distances(self._regions, target)
            in_position = [row for row in members if row["location"] == target]
            other_side = [row for row in members if other != target and row["location"] == other]
            elsewhere = [row for row in members if row["location"] not in (target, other)]
            description = "\n".join([
                tr("mu_positions.battle_header", battle=self._battle_title(battle, tr), side=self._side_label(battle, side, tr)),
                tr("mu_positions.stand_in", region=self._region_label(target, tr)),
                *notes,
                tr("mu_positions.battle_counts", in_position=len(in_position), other_side=len(other_side), elsewhere=len(elsewhere)),
            ])
            if in_position:
                fields += _pack(
                    tr("mu_positions.in_position_title", count=len(in_position)),
                    [", ".join(self._member_name(row, bold=False) for row in sorted(in_position, key=lambda row: row["name"].lower()))],
                )
            if other_side:
                # standing there they can only hit for the other side, so they need the trip too
                fields += _pack(
                    tr("mu_positions.other_side_title", region=self._region_label(other, tr, flag=False), count=len(other_side)),
                    [self._trip_line(row, target, distances, now, tr) for row in sorted(other_side, key=lambda row: row["name"].lower())],
                )
            if elsewhere:
                rows = sorted(elsewhere, key=lambda row: (distances.get(row["location"], 99), row["name"].lower()))
                fields += _pack(
                    tr("mu_positions.elsewhere_title", count=len(elsewhere)),
                    [self._trip_line(row, target, distances, now, tr) for row in rows],
                )

        if len(members) < member_count:
            description += "\n" + tr("mu_positions.members_missing", count=member_count - len(members))
        return self._split(tr("mu_positions.title_battle", mu=mu_name), description, fields, tr("mu_positions.footer_battle", stamina=STAMINA_PER_REGION, oil=OIL_PER_REGION), now)

    def _trip_line(self, row: dict, target: str, distances: dict[str, int], now: datetime, tr: Translator) -> str:
        """One member's trip to `target`: where they are, how many regions away, and what it costs."""
        region = self._region_label(row["location"], tr) if row["location"] else tr("mu_positions.unknown_region")
        distance = distances.get(row["location"])
        if distance is None:
            return tr("mu_positions.elsewhere_plain", name=self._member_name(row), region=region)
        # the free trip home costs nothing when the battle is fought from the member's home region
        if row["home"] == target and (row["free_trip_at"] is None or row["free_trip_at"] <= now):
            cost = tr("mu_positions.free_home")
        else:
            stamina, oil = travel_cost(distance, row["stamina"])
            cost = tr("mu_positions.cost_stamina", stamina=stamina) if not oil else tr("mu_positions.cost_oil", stamina=stamina, oil=oil)
        return tr("mu_positions.elsewhere_line", name=self._member_name(row), region=region, distance=distance, cost=cost)

    def _split(self, title: str, description: str, fields: list[tuple[str, str]], footer: str, now: datetime) -> list[discord.Embed]:
        """The fields in as many embeds as EMBED_TOTAL_LIMIT needs, titles numbered "(i/N)" when there are several."""

        def new_embed(first: bool) -> discord.Embed:
            embed = discord.Embed(title=title, description=description if first else None, color=discord.Color.teal(), timestamp=now)
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

    @mu_positions_command.autocomplete("military_unit")
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

    @mu_positions_command.autocomplete("battle")
    async def battle_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Active battles from the cache, those the chosen MU ordered first, then the country's, then the rest.

        Labels carry API names only (no translated words, so no database read here): "A vs B · region",
        then 🎖️ for an MU order and the country's flag for a country order.
        """
        if time.monotonic() - self._battles_at > BATTLES_TTL:
            self._warm()
        mu_id = self._find_unit(str(getattr(interaction.namespace, "military_unit", "") or "")) or ""
        current = (current or "").lower()
        choices = []
        for battle in self._battles:
            battle_id = str(battle.get("_id") or "")
            if not battle_id:
                continue
            names = [self._country_names.get(str((battle.get(side) or {}).get("country") or ""), "?") for side in SIDES]
            region = self._regions.get(required_region(battle, "defender") or "", {}).get("name", "")
            label = " vs ".join(names) + (f" · {region}" if region else "")
            mu_ordered = any(mu_id and mu_id in _side_ids(battle, side, "muOrders") for side in SIDES)
            country_ordered = any(self._country_id and self._country_id in _side_ids(battle, side, "countryOrders") for side in SIDES)
            if mu_ordered:
                label += f" · {MU_MARKER}"
            if country_ordered:
                label += f" · {self._country_unicode_flag or COUNTRY_NAME}"
            if current and current not in label.lower() and current not in battle_id:
                continue
            choices.append(((not mu_ordered, not country_ordered, label.lower()), label, battle_id))
        choices.sort()
        return [app_commands.Choice(name=label[:100], value=battle_id) for _, label, battle_id in choices[:25]]


async def setup(bot: commands.Bot):
    """Extension entry point for bot.load_extension."""
    await bot.add_cog(MuPositions(bot))
