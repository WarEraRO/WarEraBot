"""/loot_targets: which pool item each military unit member would get from a battle, and what a better one costs.

At the end of a round (or battle) its pool items go to the players by their rank in the combined (both sides)
damage ranking, the most valuable item to rank 1. `battleRanking.getRanking` with side "merged" shows, on each
entry, the `lootItem` that rank would get now, so it is a live pool preview: rarity never rises going down the
ranking [observed 2026-10-14 on 3 battles], and ranks past the pool's size have no item.

Each round's pool is handed out at the end of that round and the battle's pool at the end of the battle, so a
player competes for both at once and the command shows both. For each member of the configured MUs (or one MU),
in each pool, it shows their rank, damage and current item, the damage to pass the next rank, and the damage to reach the closest rank holding a better rarity (🤝 when a
teammate of a configured MU holds it, so climbing there only swaps items inside the team), and how many players
below would have to pass them, with the damage each needs, before they drop to a lower rarity. The pool grows as
damage is dealt and ranks move, so the gaps are a snapshot. Read-only: the reply is posted in the channel and
nobody is pinged.
"""
import asyncio
import logging
import re
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs.commands.fight_wealth import _messages, _pack
from cogs.commands.mu_order_alignment import BATTLE_LINK, COUNTRY_NAME, SIDES, TOURNAMENT_BATTLE_TYPE, _side_ids
from cogs.commands.mu_positions import _unicode_flag
from cogs.commands.mu_readiness import RARITY_ORDER
from cogs.commands.pills import _unit_ids
from cogs.tasks.military_unit_daily_report import _fmt_short
from utils.api import (
    get_active_battles,
    get_all_countries,
    get_battle,
    get_battle_loot_summaries,
    get_game_config,
    get_military_units_by_ids,
    get_ranking_pages,
    get_regions_by_ids,
    get_shared_session,
    get_users_info,
)
from utils.common import country_with_flag
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

BATTLE_ID_RE = re.compile(r"(?:battle/)?([a-f\d]{24})\b")
MU_NAMES_TTL = 3600
COUNTRIES_TTL = 3600
GAME_CONFIG_TTL = 3600
BATTLES_TTL = 120
# a big battle's ranking has a few thousand players (3,746 seen); reading stops once every member who hit
# the battle is found, and never goes past this many pages of 100
MAX_RANKING_PAGES = 30
EMBED_TOTAL_LIMIT = 4000
RARITY_EMOJI = {"common": "⚪", "uncommon": "🟢", "rare": "🔵", "epic": "🟣", "legendary": "🟠", "mythic": "🔴"}
TEAMMATE_MARKER = "🤝"


def _rarity_index(entry: dict, game_items: dict) -> int:
    """Position of the entry's pool item rarity in RARITY_ORDER; -1 when the rank gets no item (or it is unknown)."""
    item = entry.get("lootItem")
    code = item.get("code") if isinstance(item, dict) else item
    rarity = (game_items.get(str(code or "")) or {}).get("rarity")
    return RARITY_ORDER.index(rarity) if rarity in RARITY_ORDER else -1


def loot_targets(ranking: list[dict], index: int, game_items: dict) -> dict:
    """The climbs open to the player at `ranking[index]` (entries in rank order, best first).

    Returns {"next": entry above or None, "next_damage", "better": closest entry above with a better rarity
    or None, "better_damage"}. The damage is what it takes to pass that entry's value, assuming it stays
    put; a tie needs 1 more.
    """
    entry = ranking[index]
    own_value = entry.get("value") or 0
    own_rarity = _rarity_index(entry, game_items)
    result = {"next": None, "next_damage": None, "better": None, "better_damage": None}
    for above in reversed(ranking[:index]):
        value = above.get("value") or 0
        if result["next"] is None and value > own_value:
            result["next"], result["next_damage"] = above, value - own_value + 1
        if result["better"] is None and _rarity_index(above, game_items) > own_rarity:
            result["better"], result["better_damage"] = above, max(1, value - own_value + 1)
        if result["next"] is not None and result["better"] is not None:
            break
    return result


def loot_risk(ranking: list[dict], index: int, game_items: dict, complete: bool) -> dict | None:
    """How the player at `ranking[index]` could drop to a lower rarity.

    They keep their rarity while they stay above the last rank holding it. With k more ranks of that rarity
    below them, k + 1 players from below must pass them; the cheapest are the k + 1 closest below, each needing
    to pass the player's value (a tie needs 1). They would then sit where the first lower rarity is now.

    Returns {"fall_to": that entry (its item, or none, is what they would get), "damages": damage each of those
    players needs, closest first}; {"safe": True} when nobody ranked below holds a lower rarity (whole ranking
    read); None for a rank with no item, or when the pages read end before the player's rarity does.
    """
    own_rarity = _rarity_index(ranking[index], game_items)
    if own_rarity < 0:
        return None
    own_value = ranking[index].get("value") or 0
    # rarity never rises going down, so the first lower rarity below ends the player's block
    fall_index = next((i for i in range(index + 1, len(ranking)) if _rarity_index(ranking[i], game_items) < own_rarity), None)
    if fall_index is None:
        return {"safe": True} if complete else None
    damages = [max(1, own_value - (entry.get("value") or 0) + 1) for entry in ranking[index + 1:fall_index + 1]]
    return {"fall_to": ranking[fall_index], "damages": damages}


def rarity_thresholds(ranking: list[dict], complete: bool, game_items: dict) -> list[tuple[str, int]]:
    """(rarity, damage to beat) for each rarity in the pool: the value of the last rank holding it or better.

    A rarity is listed only when that last rank is known: the whole ranking was read, or a lower rarity
    (or no item) was already seen further down the pages read.
    """
    lowest_seen = _rarity_index(ranking[-1], game_items) if ranking else -1
    thresholds = []
    present = {_rarity_index(entry, game_items) for entry in ranking}
    for rarity_index in range(len(RARITY_ORDER) - 1, -1, -1):
        holders = [entry for entry in ranking if _rarity_index(entry, game_items) >= rarity_index]
        # a rarity missing from the pool would repeat the next better one's threshold
        if rarity_index not in present or (not complete and lowest_seen >= rarity_index):
            continue
        thresholds.append((RARITY_ORDER[rarity_index], holders[-1].get("value") or 0))
    return thresholds


class LootTargets(commands.Cog):
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
        self._game_config: dict = {}
        self._game_config_at = 0.0
        # active battles and their region names, for the battle autocomplete
        self._battles: list[dict] = []
        self._battles_at = 0.0
        self._region_names: dict[str, str] = {}
        self._warm_task: asyncio.Task | None = None

    async def cog_load(self):
        """Warm the MU names and the battle autocomplete in the background."""
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
        """Start refreshing the active battles, their region names and the countries for the battle autocomplete."""
        if self._warm_task and not self._warm_task.done():
            return

        async def _refresh():
            session = await get_shared_session()
            battles, _ = await asyncio.gather(get_active_battles(session), self._load_countries(session))
            if battles is None:
                return
            self._battles, self._battles_at = battles, time.monotonic()
            region_ids = {str(region) for battle in battles if (region := (battle.get("defender") or {}).get("region"))}
            missing = [region_id for region_id in region_ids if region_id not in self._region_names]
            if missing:
                for region_id, region in (await get_regions_by_ids(missing, session)).items():
                    if region.get("name"):
                        self._region_names[region_id] = str(region["name"])

        self._warm_task = asyncio.create_task(_refresh())

    def _find_unit(self, value: str) -> str | None:
        """The configured MU id matching an MU id (autocomplete value) or in-game MU name (typed by hand)."""
        value = (value or "").strip()
        for mu_id in _unit_ids():
            if value == mu_id or value.lower() == self._mu_names.get(mu_id, "").lower():
                return mu_id
        return None

    async def _load_countries(self, session) -> bool:
        """Refresh the country names and COUNTRY_NAME's id when stale; False when no country list is known."""
        if self._country_names and time.monotonic() - self._countries_at < COUNTRIES_TTL:
            return True
        countries = await get_all_countries(session)
        if not countries:
            # a failed refresh keeps the previous list
            return bool(self._country_names)
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
        return True

    async def _load_game_config(self, session) -> dict:
        """gameConfig, refreshed when stale; a failed refresh keeps the last one ({} before the first)."""
        if self._game_config and time.monotonic() - self._game_config_at < GAME_CONFIG_TTL:
            return self._game_config
        game_config = await get_game_config(session)
        if game_config:
            self._game_config, self._game_config_at = game_config, time.monotonic()
        return self._game_config

    @app_commands.command(
        name="loot_targets",
        description="Show the round and battle pool items each MU member would get and the damage a better one needs.",
    )
    @app_commands.describe(
        battle="Battle (autocomplete, or a battle link)",
        military_unit="Military unit (default: every unit configured for this server)",
    )
    async def loot_targets_command(self, interaction: discord.Interaction, battle: str, military_unit: str | None = None):
        tr = await get_translator(interaction.guild_id)
        match = BATTLE_ID_RE.search((battle or "").strip())
        if not match:
            await interaction.response.send_message(tr("loot_targets.invalid_battle"), ephemeral=True)
            return
        battle_id = match.group(1)
        mu_filter = None
        if military_unit:
            mu_filter = self._find_unit(military_unit)
            if mu_filter is None:
                await interaction.response.send_message(tr("loot_targets.unknown_unit"), ephemeral=True)
                return
        await interaction.response.defer()

        session = await get_shared_session()
        battle_data, military_units, countries_loaded, game_config = await asyncio.gather(
            get_battle(battle_id, session),
            get_military_units_by_ids(_unit_ids(), session),
            self._load_countries(session),
            self._load_game_config(session),
        )
        if not isinstance(battle_data, dict) or not military_units or not countries_loaded:
            await interaction.followup.send(tr("loot_targets.fetch_failed"), ephemeral=True)
            return
        for mu_id, mu in military_units.items():
            if mu.get("name"):
                self._mu_names[mu_id] = str(mu["name"])

        # every configured MU's members are teammates; the report lists the chosen MU's (or all of them)
        member_mu = {str(user_id): mu_id for mu_id, mu in military_units.items() for user_id in mu.get("members") or []}
        listed = {user_id: mu_id for user_id, mu_id in member_mu.items() if mu_filter in (None, mu_id)}

        # the current round's pool (the last round's once the battle ended) and the whole battle's pool
        rounds = [str(round_id) for round_id in battle_data.get("rounds") or []]
        round_id = battle_data.get("currentRound") or (rounds[-1] if rounds else None)
        if isinstance(round_id, dict):
            round_id = round_id.get("_id")
        round_id = str(round_id) if round_id else None
        round_number = rounds.index(round_id) + 1 if round_id in rounds else max(1, len(rounds))
        scopes = ([("round", {"roundId": round_id})] if round_id else []) + [("battle", {"battleId": battle_id})]

        # members who hit the battle at all; a member with no hits is not looked for in the rankings
        summaries = await get_battle_loot_summaries(battle_id, list(listed), session)
        hitters = {user_id for user_id, summary in summaries.items() if (summary.get("hits") or summary.get("totalDmg"))}

        game_items = game_config.get("items") or {}

        def found_all(items: list[dict]) -> bool:
            # with no member hitting, the first page still gives the pool summary and rarity thresholds
            if not hitters:
                return True
            if not hitters <= {str(item.get("user")) for item in items}:
                return False
            # who can take a member's rarity needs the first lower rarity below the weakest member's block
            rarities = [_rarity_index(item, game_items) for item in items if str(item.get("user")) in hitters]
            rarities = [rarity for rarity in rarities if rarity >= 0]
            return not rarities or _rarity_index(items[-1], game_items) < min(rarities)

        # both pools are read at once, each stopping on its own; a member who hit only earlier rounds is never
        # found in the round ranking, so that read can run to its end or to MAX_RANKING_PAGES
        rankings = await asyncio.gather(*(
            get_ranking_pages(scope, "damage", "user", "merged", session, stop=found_all, max_pages=MAX_RANKING_PAGES)
            for _, scope in scopes
        ))
        if any(ranking is None for ranking in rankings):
            await interaction.followup.send(tr("loot_targets.fetch_failed"), ephemeral=True)
            return
        pools = [
            {
                "label": tr("loot_targets.pool_round", number=round_number) if kind == "round" else tr("loot_targets.pool_battle"),
                "items": items,
                "complete": complete,
                "index_of": {str(entry.get("user")): index for index, entry in enumerate(items)},
            }
            for (kind, _), (items, complete) in zip(scopes, rankings)
        ]
        found = {user_id for pool in pools for user_id in pool["index_of"] if user_id in listed}
        users = await get_users_info(list(found), session) if found else {}

        embeds = self._build_embeds(
            battle_data, pools, listed, member_mu, hitters, users, mu_filter, game_items, datetime.now(timezone.utc), tr
        )
        for message_embeds in _messages(embeds):
            await interaction.followup.send(embeds=message_embeds)

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

    def _item(self, entry: dict | None, game_items: dict, tr: Translator) -> str:
        """The pool item of a ranking entry with its rarity emoji (e.g. "🟣 helmet4"); "no item" past the pool."""
        item = (entry or {}).get("lootItem")
        code = item.get("code") if isinstance(item, dict) else item
        if not code:
            return tr("loot_targets.no_item")
        rarity = (game_items.get(str(code)) or {}).get("rarity")
        return f"{RARITY_EMOJI.get(rarity, '❔')} {code}"

    def _pool_lines(self, pool: dict, index: int, member_mu: dict, game_items: dict, tr: Translator) -> list[str]:
        """The lines of one member in one pool.

        Rank, damage and item; the next rank and the closest better rarity; and, when they hold an item,
        who below could push them to a lower rarity.
        """
        items, entry = pool["items"], pool["items"][index]
        user_id = str(entry.get("user"))
        head = tr(
            "loot_targets.pool_line",
            pool=pool["label"], rank=entry.get("rank"), damage=_fmt_short(entry.get("value")), item=self._item(entry, game_items, tr),
        )
        targets = loot_targets(items, index, game_items)
        parts = []
        better = targets["better"]
        if targets["next"] is None:
            parts.append(tr("loot_targets.top"))
        elif targets["next"] is not better:
            # when the next rank already holds a better rarity, the better-rarity part says it all
            parts.append(tr("loot_targets.next_rank", rank=targets["next"].get("rank"), damage=_fmt_short(targets["next_damage"])))
        if better is not None:
            teammate = f" {TEAMMATE_MARKER}" if str(better.get("user")) in member_mu and str(better.get("user")) != user_id else ""
            key = "loot_targets.enter_pool" if _rarity_index(entry, game_items) < 0 else "loot_targets.better"
            parts.append(tr(key, item=self._item(better, game_items, tr), rank=better.get("rank"), damage=_fmt_short(targets["better_damage"])) + teammate)
        elif _rarity_index(entry, game_items) == len(RARITY_ORDER) - 1:
            parts.append(tr("loot_targets.best_rarity"))
        lines = [head, "⬆️ " + " · ".join(parts)]
        risk = loot_risk(items, index, game_items, pool["complete"])
        if risk and risk.get("safe"):
            lines.append(tr("loot_targets.fall_safe"))
        elif risk:
            damages = ["+" + _fmt_short(damage) for damage in risk["damages"]]
            # every player's need is listed up to 3; beyond that the closest and the furthest
            shown = ", ".join(damages) if len(damages) <= 3 else f"{damages[0]} … {damages[-1]}"
            lines.append(tr.plural("loot_targets.fall", len(damages), item=self._item(risk["fall_to"], game_items, tr), damages=shown))
        return lines

    def _member_block(self, user_id: str, pools: list[dict], member_mu: dict, users: dict, game_items: dict, tr: Translator) -> str:
        """The member's name, then their lines in each pool (round first, then battle)."""
        name = discord.utils.escape_markdown(str((users.get(user_id) or {}).get("username") or tr("common.unknown")))
        lines = [f"**{name}**"]
        for pool in pools:
            index = pool["index_of"].get(user_id)
            if index is None:
                # with the whole ranking read they dealt no damage in this pool; otherwise they are further down
                lines.append(tr("loot_targets.pool_missing" if pool["complete"] else "loot_targets.pool_beyond", pool=pool["label"]))
            else:
                lines += self._pool_lines(pool, index, member_mu, game_items, tr)
        return "\n".join(lines)

    def _build_embeds(
        self,
        battle: dict,
        pools: list[dict],
        listed: dict[str, str],
        member_mu: dict[str, str],
        hitters: set[str],
        users: dict,
        mu_filter: str | None,
        game_items: dict,
        now: datetime,
        tr: Translator,
    ) -> list[discord.Embed]:
        """Both pools' size and rarity thresholds in the description, then one section per MU, members in rank order."""
        lines = [self._battle_title(battle, tr)]
        if not battle.get("isActive"):
            lines.append(tr("loot_targets.battle_ended"))
        for pool in pools:
            items = pool["items"]
            with_item = sum(1 for entry in items if _rarity_index(entry, game_items) >= 0)
            key = "loot_targets.pool_summary_complete" if pool["complete"] else "loot_targets.pool_summary_partial"
            lines.append(tr(key, pool=pool["label"], ranked=len(items), with_item=with_item))
            thresholds = rarity_thresholds(items, pool["complete"], game_items)
            if thresholds:
                lines.append(tr("loot_targets.thresholds") + " " + " · ".join(
                    f"{RARITY_EMOJI[rarity]} >{_fmt_short(value)}" for rarity, value in thresholds
                ))
        description = "\n".join(lines)

        def rank_key(user_id: str) -> tuple:
            # the round pool is decided first, so its rank orders the list; the battle rank breaks ties
            return tuple(pool["index_of"].get(user_id, float("inf")) for pool in pools)

        fields: list[tuple[str, str]] = []
        mu_ids = [mu_filter] if mu_filter else sorted({mu_id for mu_id in listed.values()}, key=lambda mu_id: self._mu_names.get(mu_id, mu_id).lower())
        for mu_id in mu_ids:
            members = [user_id for user_id, member_mu_id in listed.items() if member_mu_id == mu_id]
            shown = sorted((user_id for user_id in members if any(user_id in pool["index_of"] for pool in pools)), key=rank_key)
            # hit the battle but found in neither ranking read
            unranked = [user_id for user_id in members if user_id in hitters and user_id not in shown]
            if not shown and not unranked:
                continue
            mu_name = discord.utils.escape_markdown(self._mu_names.get(mu_id, mu_id))
            section = [self._member_block(user_id, pools, member_mu, users, game_items, tr) for user_id in shown]
            if unranked:
                section.append(tr("loot_targets.unranked", count=len(unranked)))
            fields += _pack(tr("loot_targets.mu_title", mu=mu_name, count=len(shown)), section)
        if not fields:
            description += "\n" + tr("loot_targets.no_members")
        return self._split(tr("loot_targets.title"), description, fields, tr("loot_targets.footer", teammate=TEAMMATE_MARKER), now)

    def _split(self, title: str, description: str, fields: list[tuple[str, str]], footer: str, now: datetime) -> list[discord.Embed]:
        """The fields in as many embeds as EMBED_TOTAL_LIMIT needs, titles numbered "(i/N)" when there are several."""

        def new_embed(first: bool) -> discord.Embed:
            embed = discord.Embed(title=title, description=description if first else None, color=discord.Color.purple(), timestamp=now)
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

    @loot_targets_command.autocomplete("military_unit")
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

    @loot_targets_command.autocomplete("battle")
    async def battle_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Active battles from the cache: those the configured MUs ordered first, then the country's, then the rest.

        Labels carry API names only (no translated words, so no database read here): "A vs B · region",
        then 🎖️ for an order from a configured MU (the chosen one, when picked) and the country's flag for a
        country order.
        """
        if time.monotonic() - self._battles_at > BATTLES_TTL:
            self._warm()
        chosen = self._find_unit(str(getattr(interaction.namespace, "military_unit", "") or ""))
        mu_ids = {chosen} if chosen else set(_unit_ids())
        current = (current or "").lower()
        choices = []
        for battle in self._battles:
            battle_id = str(battle.get("_id") or "")
            if not battle_id:
                continue
            names = [self._country_names.get(str((battle.get(side) or {}).get("country") or ""), "?") for side in SIDES]
            region = self._region_names.get(str((battle.get("defender") or {}).get("region") or ""), "")
            label = " vs ".join(names) + (f" · {region}" if region else "")
            mu_ordered = any(mu_ids & _side_ids(battle, side, "muOrders") for side in SIDES)
            country_ordered = any(self._country_id and self._country_id in _side_ids(battle, side, "countryOrders") for side in SIDES)
            if mu_ordered:
                label += " · 🎖️"
            if country_ordered:
                label += f" · {self._country_unicode_flag or COUNTRY_NAME}"
            if current and current not in label.lower() and current not in battle_id:
                continue
            choices.append(((not mu_ordered, not country_ordered, label.lower()), label, battle_id))
        choices.sort()
        return [app_commands.Choice(name=label[:100], value=battle_id) for _, label, battle_id in choices[:25]]


async def setup(bot: commands.Bot):
    """Extension entry point for bot.load_extension."""
    await bot.add_cog(LootTargets(bot))
