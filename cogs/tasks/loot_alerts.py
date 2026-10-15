"""loot_alerts: DM each subscriber the loot pools of the battles they hit, shortly before a round can end.

Members subscribe with `/subscribe loot` (cogs/commands/subscriptions.py). Every tick (2 minutes) the job:

1. Reads the subscribers and stops there when there are none, so it makes no API request without them.
2. Lists the active battles and keeps the rounds that can end within ALERT_WINDOW. A round ends when a side
   reaches the points to win, and the API has no end time, so this is `round_eta`: the leading side wins
   every remaining tick. A contested round can last longer than the DM says.
3. Skips subscribers on an economy build (no skill points counts as economy), without stats (health < 10
   and hunger < 1) or in debuff, as the contract pings do. Skipped subscribers are checked again on the
   next run while the round is still ending.
4. For each subscriber who hit the battle, reads the round and battle pools the way /loot_targets does, and
   estimates the damage they can still deal from their current gear, battle bonus, health and hunger
   (`estimate_fight_damage`). A battle is shown when they hold a pool item or could reach one with that
   damage. Each subscriber gets one DM with one embed per battle.

Each subscriber is evaluated once per round. Rounds already ending at the first run after a restart are
skipped, so a restart never repeats a DM (the trade-off: those rounds get no DM).

The bot's API key cannot read the battle's damage bonuses (`battle.getDamageBonuses` is session-only), so
the bonus counts only what the bot can derive: patriotic, the country and MU orders on the player's side
(+5/+10/+15% by priority) and an active MU headquarters. The side is the player's country's side, else the
side their MU or country ordered.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from cogs.commands.damage import estimate_fight_damage
from cogs.commands.fight_wealth import _messages
from cogs.commands.loot_targets import (
    MAX_RANKING_PAGES,
    _rarity_index,
    battle_title,
    best_reachable,
    item_label,
    pool_lines,
    pool_scopes,
    pool_summary_lines,
)
from cogs.commands.mu_order_alignment import SIDES, _side_ids
from cogs.commands.mu_readiness import RARITY_ORDER
from cogs.tasks.military_unit_contract_monitor import (
    DEFAULT_POINTS_TO_WIN_ROUND,
    DEFAULT_TICK_POINTS,
    DEFAULT_ROUNDS_TO_WIN,
    can_fight,
    format_duration,
    parse_iso,
    round_eta,
)
from cogs.tasks.military_unit_daily_report import _fmt_short
from config import config
from utils.api import (
    get_active_battles,
    get_all_countries,
    get_battle_loot_summaries,
    get_battle_orders,
    get_game_config,
    get_military_units_by_ids,
    get_mu_upgrades,
    get_ranking_pages,
    get_shared_session,
    get_users_info,
)
from utils.common import country_with_flag
from utils.computational import is_economy_build
from utils.db import get_job_subscribers, remove_job_subscription
from utils.i18n import Translator, get_translator

logger = logging.getLogger(__name__)

# one tick, so a round is looked at about 5 times while it is in the window
LOOT_ALERT_INTERVAL_MINUTES = 2
ALERT_WINDOW = timedelta(minutes=10)
GAME_CONFIG_TTL = 3600
COUNTRIES_TTL = 3600

# job name and target in the job_subscriptions table. Nothing per battle is stored: a subscriber is
# alerted for every battle they hit.
SUBSCRIPTION_JOB = "loot_alerts"
SUBSCRIPTION_TARGET = "hit_battles"

# share of gameConfig.battle.<country|mu>OrderBonusPercent (10) by order priority: the guide gives
# +5/+10/+15% for low/medium/high, and the config's single value is the medium one
ORDER_PRIORITY_SHARE = {"low": 0.5, "medium": 1.0, "high": 1.5}


def confirmed_mu(user: dict, mu_members: dict[str, set[str]]) -> str:
    """The player's MU id when that MU's member list (mu.getById) has them, else "".

    An MU whose fetch failed is not confirmed, so a player outside an MU, or one whose MU cannot be
    checked, gets no MU order or headquarters bonus.
    """
    mu_id = str(user.get("mu") or "")
    return mu_id if mu_id and str(user.get("_id") or "") in mu_members.get(mu_id, set()) else ""


def fighting_side(battle: dict, user: dict, mu_country: str | None = None) -> str | None:
    """The side the player most likely fights for in `battle`.

    Their country's side; else the side their MU ordered; else the side their country ordered; else
    the side of their MU's country (`mu_country`); None when there is no hint. A mercenary fighting a
    contract for a foreign country is guessed wrong.
    """
    country, mu = str(user.get("country") or ""), str(user.get("mu") or "")
    for side in SIDES:
        if country and str((battle.get(side) or {}).get("country") or "") == country:
            return side
    for side in SIDES:
        if mu and mu in _side_ids(battle, side, "muOrders"):
            return side
    for side in SIDES:
        if country and country in _side_ids(battle, side, "countryOrders"):
            return side
    for side in SIDES:
        if mu_country and str((battle.get(side) or {}).get("country") or "") == mu_country:
            return side
    return None


def bonus_parts(
    battle: dict, side: str | None, user: dict, side_orders: list[dict] | None, hq_bonus: float, battle_config: dict
) -> list[tuple[str, float]]:
    """The battle bonus parts (key, percent) the bot can see for the player fighting for `side`.

    Patriotic when their country is that side; the country and MU orders on that side that apply to them,
    scaled by priority (from `side_orders`, the side's battleOrder.getByBattle; when it failed, the side's
    `countryOrders`/`muOrders` at the medium value); and their MU's active headquarters, which counts in any
    battle. Keys are `loot_alerts.bonus.<key>`.
    """
    parts: list[tuple[str, float]] = []
    country, mu = str(user.get("country") or ""), str(user.get("mu") or "")
    if side:
        if country and str((battle.get(side) or {}).get("country") or "") == country:
            parts.append(("patriotic", float(battle_config.get("patrioticBonusPercent") or 0)))
        for key, field, owner, orders_key, config_key in (
            ("country_order", "country", country, "countryOrders", "countryOrderBonusPercent"),
            ("mu_order", "mu", mu, "muOrders", "muOrderBonusPercent"),
        ):
            if not owner:
                continue
            if side_orders is None:
                share = 1.0 if owner in _side_ids(battle, side, orders_key) else None
            else:
                order = next((order for order in side_orders if str(order.get(field) or "") == owner), None)
                share = ORDER_PRIORITY_SHARE.get(str(order.get("priority") or ""), 1.0) if order else None
            if share is not None:
                parts.append((key, float(battle_config.get(config_key) or 0) * share))
    if hq_bonus:
        parts.append(("headquarters", hq_bonus))
    return parts


def hq_bonus_percent(mu: dict | None, upgrade: dict | None, game_config: dict, now: datetime) -> float:
    """The attack bonus of the MU's headquarters when it is active (as /mu_readiness reads it), else 0."""
    upgrade = upgrade or {}
    level = int(upgrade.get("level") or ((mu or {}).get("activeUpgradeLevels") or {}).get("headquarters") or 0)
    if not level:
        return 0.0
    active_at = parse_iso(upgrade.get("willBeActiveAt"))
    if (active_at and active_at > now) or not (upgrade.get("status") == "active" or (not upgrade and level)):
        return 0.0
    levels = ((game_config.get("upgradesConfig") or {}).get("headquarters") or {}).get("levels") or {}
    return float((((levels.get(str(level)) or {}).get("stats") or {}).get("attackBonus")) or 0)


def round_can_end_battle(battle: dict, round_obj: dict, rounds_to_win: int) -> bool:
    """True when a side leading the round (on points) would also win the battle by winning it."""
    points = {side: (round_obj.get(side) or {}).get("points") or 0 for side in SIDES}
    top = max(points.values())
    return any(
        points[side] == top and ((battle.get(side) or {}).get("wonRoundsCount") or 0) + 1 >= rounds_to_win
        for side in SIDES
    )


class LootAlertJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._seeded = False
        # rounds already ending at the first run: never alerted (see the module docstring)
        self._skipped_rounds: set[str] = set()
        # round id -> Discord ids of the subscribers already evaluated for it
        self._handled: dict[str, set[str]] = {}
        self._game_config: dict = {}
        self._game_config_at = 0.0
        self._country_names: dict[str, str] = {}
        self._countries_at = 0.0
        self.loot_alert_monitor.start()

    def cog_unload(self):
        """Stop the loop."""
        self.loot_alert_monitor.cancel()

    @tasks.loop(minutes=LOOT_ALERT_INTERVAL_MINUTES)
    async def loot_alert_monitor(self):
        """DM the eligible subscribers the loot pools of the battles they hit whose round can end soon."""
        guild = self.bot.get_guild(config["guild"])
        if guild is None:
            return
        try:
            subscriptions = await asyncio.to_thread(get_job_subscribers, SUBSCRIPTION_JOB, SUBSCRIPTION_TARGET)
        except Exception:
            logger.exception("Could not read the loot alert subscribers")
            return
        # without subscribers the job makes no API request
        if not subscriptions:
            return
        subscriptions = await self._drop_departed(subscriptions, guild)
        api_ids = {str(s["discord_id"]): str(s["api_id"]) for s in subscriptions if s.get("api_id")}
        if not api_ids:
            return

        session = await get_shared_session()
        battles, game_config = await asyncio.gather(get_active_battles(session), self._load_game_config(session))
        if battles is None or not game_config:
            return
        now = datetime.now(timezone.utc)
        ending = self._ending_rounds(battles, game_config, now)
        # forget the rounds that are over
        active_rounds = {round_id for battle in battles if (round_id := _current_round_id(battle))}
        self._skipped_rounds &= active_rounds
        self._handled = {round_id: done for round_id, done in self._handled.items() if round_id in active_rounds}

        if not self._seeded:
            # after a restart, the rounds already ending may have been alerted before it
            self._skipped_rounds |= {round_id for _, round_id, _ in ending}
            self._seeded = True
            logger.info("Loot alerts seeded with %d rounds already ending", len(ending))
            return

        pending = [
            (battle, round_id, eta) for battle, round_id, eta in ending
            if round_id not in self._skipped_rounds and set(api_ids) - self._handled.get(round_id, set())
        ]
        if not pending:
            return
        waiting = {discord_id for _, round_id, _ in pending for discord_id in api_ids if discord_id not in self._handled.get(round_id, set())}
        # one batched request; a subscriber whose stats could not be fetched is retried on the next run
        users = await get_users_info([api_ids[discord_id] for discord_id in waiting], session)
        eligible = {
            discord_id: user for discord_id in waiting
            if (user := users.get(api_ids[discord_id])) and is_economy_build(user) is False and can_fight(user, now)
        }
        if not eligible:
            return

        # who hit each battle, one batched request per battle; players who have not hit it are looked
        # at again on the next run, in case they do
        players_of = [
            {d: user for d, user in eligible.items() if d not in self._handled.get(round_id, set())}
            for _, round_id, _ in pending
        ]
        hitters_of = await asyncio.gather(*(
            self._hitters(str(battle["_id"]), players, session) for (battle, _, _), players in zip(pending, players_of)
        ))
        if not any(hitters_of):
            return

        hitting = {d: eligible[d] for hitters in hitters_of for d in hitters}
        await self._load_countries(session)
        context = await self._player_context(hitting, [item for item, hitters in zip(pending, hitters_of) if hitters], game_config, session, now)
        tr = await get_translator()
        alerts: dict[str, list[discord.Embed]] = {}
        for (battle, round_id, eta), hitters in zip(pending, hitters_of):
            if not hitters:
                continue
            results = await self._battle_alerts(battle, eta, hitters, context, game_config, session, now, tr)
            for discord_id, embed in results.items():
                self._handled.setdefault(round_id, set()).add(discord_id)
                if embed is not None:
                    alerts.setdefault(discord_id, []).append(embed)
        for discord_id, embeds in alerts.items():
            await self._send(guild, discord_id, embeds)

    @loot_alert_monitor.before_loop
    async def before_loot_alert_monitor(self):
        """Wait for the bot to be ready before the first run."""
        await self.bot.wait_until_ready()

    async def _drop_departed(self, subscriptions: list[dict], guild: discord.Guild) -> list[dict]:
        """The subscriptions of members still in the guild; the others are removed from the database.

        Membership is only judged once the guild's member list is fully cached (`guild.chunked`),
        so a member missing from a partial cache is neither skipped nor unsubscribed.
        """
        if not guild.chunked:
            return subscriptions
        staying = []
        for subscription in subscriptions:
            discord_id = str(subscription["discord_id"])
            if discord_id.isdigit() and guild.get_member(int(discord_id)) is None:
                try:
                    await asyncio.to_thread(remove_job_subscription, SUBSCRIPTION_JOB, SUBSCRIPTION_TARGET, discord_id)
                    logger.info("Dropped the loot alert subscription of %s, who left the server", discord_id)
                except Exception:
                    logger.exception("Could not drop the loot alert subscription of %s", discord_id)
                continue
            staying.append(subscription)
        return staying

    def _ending_rounds(self, battles: list[dict], game_config: dict, now: datetime) -> list[tuple[dict, str, timedelta]]:
        """(battle, round id, ETA) of the active battles whose current round can end within ALERT_WINDOW."""
        battle_config = game_config.get("battle") or {}
        try:
            tick_points = {int(k): int(v) for k, v in (battle_config.get("tickPoints") or {}).items()}
        except (TypeError, ValueError):
            tick_points = {}
        points_to_win = int(battle_config.get("pointsToWinRound") or DEFAULT_POINTS_TO_WIN_ROUND)
        ending = []
        for battle in battles:
            round_obj = battle.get("currentRound")
            round_id = _current_round_id(battle)
            # battle.getBattles populates the current round; an id alone has no points to estimate from
            if not isinstance(round_obj, dict) or not round_id or not battle.get("_id"):
                continue
            eta = round_eta(round_obj, tick_points or DEFAULT_TICK_POINTS, points_to_win, now)
            if eta <= ALERT_WINDOW:
                ending.append((battle, round_id, eta))
        return ending

    async def _hitters(self, battle_id: str, players: dict[str, dict], session) -> dict[str, dict]:
        """{Discord id: user} of the `players` who hit the battle; a failed summary counts as no hit."""
        if not players:
            return {}
        discord_ids = {str(user.get("_id")): discord_id for discord_id, user in players.items() if user.get("_id")}
        summaries = await get_battle_loot_summaries(battle_id, list(discord_ids), session)
        return {
            discord_ids[api_id]: players[discord_ids[api_id]]
            for api_id, summary in summaries.items()
            if api_id in discord_ids and (summary.get("hits") or summary.get("totalDmg"))
        }

    async def _player_context(self, players: dict[str, dict], pending: list, game_config: dict, session, now: datetime) -> dict:
        """What the alerts need about the players: their MUs' members, country and headquarters bonus, and the orders.

        Returns {"mu_members": {mu id: set of user ids}, "mu_country": {mu id: country id},
        "hq": {mu id: percent}, "orders": {(battle id, side): [order]}}; a failed fetch leaves its keys out.
        """
        mu_ids = sorted({str(user.get("mu")) for user in players.values() if user.get("mu")})
        sides = [(str(battle["_id"]), side) for battle, _, _ in pending for side in SIDES]
        military_units, orders, *upgrades = await asyncio.gather(
            get_military_units_by_ids(mu_ids, session) if mu_ids else asyncio.sleep(0, result={}),
            get_battle_orders(sides, session),
            *(get_mu_upgrades(mu_id, ["headquarters"], session) for mu_id in mu_ids),
        )
        return {
            "mu_members": {mu_id: {str(member) for member in mu.get("members") or []} for mu_id, mu in military_units.items()},
            "mu_country": {mu_id: str(mu["country"]) for mu_id, mu in military_units.items() if mu.get("country")},
            "hq": {
                mu_id: hq_bonus_percent(military_units.get(mu_id), mu_upgrades.get("headquarters"), game_config, now)
                for mu_id, mu_upgrades in zip(mu_ids, upgrades)
                if military_units.get(mu_id) or mu_upgrades
            },
            "orders": orders,
        }

    async def _battle_alerts(
        self, battle: dict, eta: timedelta, players: dict[str, dict], context: dict, game_config: dict, session,
        now: datetime, tr: Translator,
    ) -> dict[str, discord.Embed | None]:
        """{Discord id: embed, or None when nothing is worth a DM} for `players`, who all hit `battle`.

        A failed ranking read returns {} so that the players are retried on the next run.
        """
        battle_id = str(battle["_id"])
        by_api_id = {str(user["_id"]): discord_id for discord_id, user in players.items()}
        hitters = set(by_api_id)
        game_items = game_config.get("items") or {}

        def found_all(items: list[dict]) -> bool:
            # past the end of the pool, whoever is still missing gets no item, and every found player's
            # rarity block has ended
            if items and _rarity_index(items[-1], game_items) < 0:
                return True
            if not hitters <= {str(item.get("user")) for item in items}:
                return False
            rarities = [_rarity_index(item, game_items) for item in items if str(item.get("user")) in hitters]
            rarities = [rarity for rarity in rarities if rarity >= 0]
            return not rarities or _rarity_index(items[-1], game_items) < min(rarities)

        scopes = pool_scopes(battle, tr)
        rankings = await asyncio.gather(*(
            get_ranking_pages(scope, "damage", "user", "merged", session, stop=found_all, max_pages=MAX_RANKING_PAGES)
            for _, _, scope in scopes
        ))
        if any(ranking is None for ranking in rankings):
            return {}
        pools = [
            {
                "label": label,
                "items": items,
                "complete": complete,
                "index_of": {str(entry.get("user")): index for index, entry in enumerate(items)},
            }
            for (_, label, _), (items, complete) in zip(scopes, rankings)
        ]
        battle_config = game_config.get("battle") or {}
        rounds_to_win = int(battle.get("roundsToWin") or battle_config.get("roundsToWin") or DEFAULT_ROUNDS_TO_WIN)
        header = [battle_title(battle, self._country_names, tr), tr("loot_alerts.round_ending", pool=pools[0]["label"], eta=format_duration(eta))]
        if isinstance(battle.get("currentRound"), dict) and round_can_end_battle(battle, battle["currentRound"], rounds_to_win):
            header.append(tr("loot_alerts.battle_ending"))
        summary = [line for pool in pools for line in pool_summary_lines(pool, game_items, tr)]

        results: dict[str, discord.Embed | None] = {}
        for api_id in hitters:
            discord_id, user = by_api_id[api_id], players[by_api_id[api_id]]
            # the MU order and headquarters bonuses count only for a confirmed MU member
            mu_id = confirmed_mu(user, context["mu_members"])
            user = {**user, "mu": mu_id or None}
            side = fighting_side(battle, user, context["mu_country"].get(mu_id))
            parts = bonus_parts(
                battle, side, user, context["orders"].get((battle_id, side)) if side else None,
                context["hq"].get(mu_id, 0.0), battle_config,
            )
            estimate = estimate_fight_damage(user, sum(value for _, value in parts), game_config)
            lines, relevant = self._player_lines(pools, api_id, context["mu_members"].get(mu_id, set()), estimate["damage_food"], game_items, tr)
            if not relevant:
                results[discord_id] = None
                continue
            description = "\n".join(
                header + [self._side_line(battle, side, parts, tr), self._damage_line(estimate, tr), ""] + summary + [""] + lines
            )
            embed = discord.Embed(title=tr("loot_alerts.title"), description=description, color=discord.Color.purple(), timestamp=now)
            embed.set_footer(text=tr("loot_alerts.footer"))
            results[discord_id] = embed
        return results

    def _player_lines(
        self, pools: list[dict], api_id: str, teammates: set[str], budget: float, game_items: dict, tr: Translator
    ) -> tuple[list[str], bool]:
        """The player's lines in each pool, and whether any pool is worth a DM.

        A pool is worth one when the player holds an item in it, when their estimated damage (`budget`)
        reaches a better rarity, or when the pages read stop before the pool ends without finding them
        (they may hold an item further down). A player outside the pool climbs from 0 damage, the most
        it can need.
        """
        lines: list[str] = []
        relevant = False
        for pool in pools:
            items = pool["items"]
            index = pool["index_of"].get(api_id)
            upper_bound = False
            if index is not None:
                lines += pool_lines(pool, index, teammates, game_items, tr)
                ranking = items
                relevant |= _rarity_index(items[index], game_items) >= 0
            elif pool["complete"] or (items and _rarity_index(items[-1], game_items) < 0):
                lines.append(tr("loot_targets.pool_missing" if pool["complete"] else "loot_targets.pool_beyond", pool=pool["label"]))
                ranking, index = items + [{"user": api_id, "value": 0}], len(items)
                # below the pages read, their damage is unknown, so the climb counted from 0 is at most that
                upper_bound = not pool["complete"]
            else:
                lines.append(tr("loot_targets.pool_beyond", pool=pool["label"]))
                relevant = True
                continue
            if _rarity_index(ranking[index], game_items) == len(RARITY_ORDER) - 1:
                continue
            reach = best_reachable(ranking, index, game_items, budget)
            if reach:
                relevant = True
                entry, damage = reach
                lines.append(tr(
                    "loot_alerts.reach_upper_bound" if upper_bound else "loot_alerts.reach",
                    item=item_label(entry, game_items, tr), rank=entry.get("rank"), damage=_fmt_short(damage),
                ))
            else:
                lines.append(tr("loot_alerts.no_reach"))
        return lines, relevant

    def _side_line(self, battle: dict, side: str | None, parts: list[tuple[str, float]], tr: Translator) -> str:
        """The side the estimate assumes and the bonus parts counted."""
        if side is None:
            side_text = tr("loot_alerts.side_unknown")
        else:
            country = self._country_names.get(str((battle.get(side) or {}).get("country") or ""))
            side_text = f"{country_with_flag(country, left=True)} ({tr(f'common.side.{side}')})" if country else tr(f"common.side.{side}")
        total = sum(value for _, value in parts)
        details = ", ".join(f"{tr(f'loot_alerts.bonus.{key}')} +{value:g}%" for key, value in parts) or tr("loot_alerts.bonus_none")
        return tr("loot_alerts.side_line", side=side_text, bonus=f"{total:+g}", details=details)

    def _damage_line(self, estimate: dict, tr: Translator) -> str:
        """Damage per hit, then what the Health bar and the Hunger bar (as food) can still deal."""
        return tr(
            "loot_alerts.damage_line",
            per_hit=_fmt_short(round(estimate["per_hit"])),
            now=_fmt_short(round(estimate["damage_now"])), hits_now=int(estimate["hits_now"]),
            food=_fmt_short(round(estimate["damage_food"])), hits_food=int(estimate["hits_food"]),
        )

    async def _send(self, guild: discord.Guild, discord_id: str, embeds: list[discord.Embed]) -> None:
        """DM the embeds to a member of the guild; a member who left or closed their DMs is skipped."""
        if not discord_id.isdigit():
            return
        member = guild.get_member(int(discord_id))
        try:
            if member is None:
                member = await guild.fetch_member(int(discord_id))
            for message_embeds in _messages(embeds):
                await member.send(embeds=message_embeds)
        except discord.NotFound:
            logger.info("Loot alert subscriber %s is not in the server", discord_id)
        except discord.Forbidden:
            logger.info("Loot alert subscriber %s does not accept DMs", discord_id)
        except discord.HTTPException:
            logger.exception("Could not DM the loot alert to %s", discord_id)

    async def _load_game_config(self, session) -> dict:
        """gameConfig, refreshed when stale; a failed refresh keeps the last one ({} before the first)."""
        if self._game_config and time.monotonic() - self._game_config_at < GAME_CONFIG_TTL:
            return self._game_config
        game_config = await get_game_config(session)
        if game_config:
            self._game_config, self._game_config_at = game_config, time.monotonic()
        return self._game_config

    async def _load_countries(self, session) -> None:
        """Refresh the country names when stale; a failed refresh keeps the previous ones."""
        if self._country_names and time.monotonic() - self._countries_at < COUNTRIES_TTL:
            return
        countries = await get_all_countries(session)
        if not countries:
            return
        for country in countries:
            country_id = str(country.get("_id") or country.get("id") or "")
            if country_id and country.get("name"):
                self._country_names[country_id] = str(country["name"])
        self._countries_at = time.monotonic()


def _current_round_id(battle: dict) -> str | None:
    """The id of the battle's current round, whether `currentRound` is populated or an id."""
    round_obj = battle.get("currentRound")
    round_id = round_obj.get("_id") if isinstance(round_obj, dict) else round_obj
    return str(round_id) if round_id else None


async def setup(bot: commands.Bot):
    """Extension entry point for bot.load_extension."""
    await bot.add_cog(LootAlertJob(bot))
