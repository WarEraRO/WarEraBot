"""/damage: fight builds for a Pill day, ranked by net money spent per 1,000 damage.

The model (game rules from gameConfig and the warera-game-expert references):
- One Pill per day: the player fights only during the 8 h buff, starting with full bars, so a day gives
  1 + 8 hourly regens of 10% = 1.8 Health bars and 1.8 Hunger bars (one food item per Hunger point).
- Damage per attempt: miss = Attack / 2 (no crit, no loot), crit = Attack x (1 + Crit Damage).
  Attack = (skill + weapon + 4 per Precision point over 100%) x (1 + ammo) x (1 + Pill) x (1 + military rank),
  which reproduces the API's `skills.attack.total`; the battle bonus is applied on top. Crit Chance over
  100% adds 4 Crit Damage per point.
- Health per hit = max(1, 10 x (1 - armor%)) x (1 - dodge%), armor/dodge% = points / (points + 40) rounded
  to 2 significant figures.
- Gear has 100 durability and loses 1 per hit: the weapon on every hit, other gear only on hits that are not
  dodged. A broken item auto-dismantles for 1/3 of a new item's scrap.
- Returns: cases (Loot Chance per valid hit, elite cases 1/100 of that) at market price, scrap, items of the
  round/battle loot pools (1 per 200k and 1 per 500k damage) and the companies' Automated Engine output.
Economy skills are never used; Companies only takes the points needed for the companies the user asks for.
"""
import asyncio
import logging
import math
import time

import discord
from discord import app_commands
from discord.ext import commands

from utils.api import _get_batch, get_game_config, get_market_prices, get_shared_session, get_user
from utils.i18n import get_translator, t

logger = logging.getLogger(__name__)

GAME_CONFIG_TTL = 3600

# Net money per 1,000 damage each recommendation may cost.
COST_BRACKETS = (0.00, 0.05, 0.10, 0.15)
# Patriotic bonus only: a conservative default, the real total comes from the battle tooltip.
DEFAULT_BATTLE_BONUS = 20

# Combat skills only, in display order.
SKILLS = ("attack", "precision", "criticalChance", "criticalDamages",
          "armor", "dodge", "health", "hunger", "lootChance")
ATK, PRC, CRIT, CRITD, ARM, DDG, HP, HUN, LOOT = range(len(SKILLS))
MAX_SKILL_LEVEL = 10

GEAR_SLOTS = ("weapon", "helmet", "gloves", "chest", "pants", "boots")
WEAPON_CODES = ("knife", "gun", "rifle", "sniper", "tank", "jet")
RARITIES = ("common", "uncommon", "rare", "epic", "legendary", "mythic")
# Scrap from dismantling a new item, by rarity (guide 21.2; not in gameConfig).
NEW_ITEM_SCRAP = (6, 18, 54, 162, 486, 1458)
ITEM_DURABILITY = 100
BROKEN_SCRAP_SHARE = 1 / 3
AMMO_CODES = ("lightAmmo", "ammo", "heavyAmmo")
FOOD_CODES = ("bread", "steak", "cookedFish")
PILL_CODE = "cocain"
ELITE_CASE_SHARE = 1 / 100
# Rarity split of regular cases [wiki]; used as the estimate for loot-pool items too.
POOL_RARITY_ODDS = (0.62, 0.30, 0.071, 0.0085, 0.0004, 0.0001)
OVERFLOW_PER_POINT = 4

# Items an Automated Engine can produce, offered as /damage company_product choices.
COMPANY_PRODUCTS = (
    "grain", "limestone", "iron", "lead", "coca", "petroleum", "wood", "livestock", "fish",
    "bread", "steak", "cookedFish", "concrete", "steel", "oil", "paper",
    "lightAmmo", "ammo", "heavyAmmo", "cocain",
)

# Each weight is the damage one coin is worth to the optimizer (maximize damage - weight x net cost).
# A build at the edge of an X/1k budget is optimal for weight 1000 / X; the last weight minimizes cost.
OPTIMIZER_WEIGHTS = (0, 2_000, 4_000, 5_000, 6_667, 8_000, 10_000, 13_000, 20_000, 35_000, 60_000, 1e9)

SLOT_EMOJI = {"weapon": "🔫", "helmet": "⛑️", "gloves": "🧤", "chest": "🦺", "pants": "👖", "boots": "🥾"}
RARITY_EMOJI = ("⬜", "🟩", "🟦", "🟪", "🟨", "🟥")
RARITY_COLOR = (0xAAAAAA, 0x2ECC71, 0x3498DB, 0x9B59B6, 0xF1C40F, 0xE74C3C)


# ---------------------------------------------------------------------------
# Game data
# ---------------------------------------------------------------------------

def _mid(stat_range) -> int:
    """Average roll of a dynamic stat range, matching the average market price of the item."""
    low, high = stat_range
    return int(math.floor((low + high) / 2 + 0.5))


def _level_value(levels: dict, level: int) -> float:
    return float(levels[str(level)]["value"])


def _mitigation(points: float, soft_cap: float) -> float:
    """Armor/Dodge share: points / (points + soft cap) rounded to 2 significant figures."""
    if points <= 0:
        return 0.0
    share = points / (points + soft_cap)
    return round(share, 1 - math.floor(math.log10(share)))


def _price_per_pp(code: str, items: dict, prices: dict) -> float | None:
    """Money one production point earns making `code`, after buying its inputs at market price."""
    item = items.get(code) or {}
    points = item.get("productionPoints")
    if code not in prices or not points:
        return None
    inputs = 0.0
    for need, qty in (item.get("productionNeeds") or {}).items():
        if need not in prices:
            return None
        inputs += qty * prices[need]
    return (prices[code] - inputs) / points


def _companies_sp(game_config: dict, count: int) -> int | None:
    """Skill points the Companies skill needs to own `count` companies (None if out of reach)."""
    levels = game_config["skills"]["companies"]["levels"]
    for lvl in range(len(levels)):
        entry = levels.get(str(lvl))
        if entry and entry["value"] >= count:
            return int(entry.get("totalCost", 0))
    return None


def _engine_levels(game_config: dict) -> dict:
    levels = game_config["upgradesConfig"]["automatedEngine"]["levels"]
    return {int(k): float(v["stats"]["dailyProd"]) for k, v in levels.items()}


async def _fetch_gear_prices(session) -> dict:
    """Average market price per equipment code (undocumented gameStat.getEquipmentAvgByCode)."""
    codes = list(WEAPON_CODES) + [
        f"{slot}{tier}" for slot in GEAR_SLOTS[1:] for tier in range(1, len(RARITIES) + 1)
    ]
    results = await _get_batch(session, "gameStat.getEquipmentAvgByCode", [{"itemCode": c} for c in codes])
    prices = {}
    for code, value in zip(codes, results):
        try:
            if value is not None and float(value) > 0:
                prices[code] = float(value)
        except (TypeError, ValueError):
            continue
    return prices


class Model:
    """Everything a build evaluation needs: skill tables, gear options, prices and the player's bonuses."""

    def __init__(self, game_config: dict, prices: dict, gear_prices: dict, player_level: int,
                 rank_pct: float, battle_pct: float, company_income: float):
        items = game_config["items"]
        skills = game_config["skills"]
        battle = game_config["battle"]

        self.health_cost = float(battle.get("healthCost", 10))
        self.soft_cap = 40.0
        regen = 1 / float(game_config["user"].get("regenDividedBy", 10))
        pill = items[PILL_CODE]["flatStats"]
        self.pill_pct = float(pill["percentAttack"]) / 100
        self.buff_hours = float(pill["buffDurationHours"])
        # full bars at the start of the buff plus one regen per hour of it
        self.bars = 1 + regen * self.buff_hours

        self.skill_values = []
        self.skill_max = []
        for code in SKILLS:
            levels = skills[code]["levels"]
            unlocked = player_level >= int(levels["0"].get("unlockAtLevel", 1))
            top = min(MAX_SKILL_LEVEL, max(int(k) for k in levels)) if unlocked else 0
            self.skill_values.append([_level_value(levels, lvl) for lvl in range(top + 1)])
            self.skill_max.append(top)
        self.level_cost = [lvl * (lvl + 1) // 2 for lvl in range(MAX_SKILL_LEVEL + 1)]

        self.scrap_price = prices.get("scraps", 0.0)
        self.case_price = prices.get("case1", 0.0)
        self.elite_case_price = prices.get("case2", 0.0)
        self.pill_price = prices[PILL_CODE]

        # gear[slot] = list of options (tier, stats, price, broken scrap); tier 0 is "nothing equipped"
        self.gear = []
        for slot in GEAR_SLOTS:
            options = [(0, {}, 0.0, 0.0)]
            for tier in range(1, len(RARITIES) + 1):
                code = WEAPON_CODES[tier - 1] if slot == "weapon" else f"{slot}{tier}"
                if code not in gear_prices or code not in items:
                    continue
                stats = {stat: _mid(rng) for stat, rng in items[code]["dynamicStats"].items()}
                scrap = NEW_ITEM_SCRAP[tier - 1] * BROKEN_SCRAP_SHARE
                options.append((tier, stats, gear_prices[code], scrap))
            self.gear.append(options)

        self.ammo = [(None, 0.0, 0.0)] + [
            (code, items[code]["flatStats"]["percentAttack"] / 100, prices[code])
            for code in AMMO_CODES if code in prices
        ]
        if len(self.ammo) == 1:
            # without ammo prices only the knife can be priced
            self.gear[0] = [option for option in self.gear[0] if option[0] < 2]
        self.food = [(None, 0.0, 0.0)] + [
            (code, items[code]["flatStats"]["healthRegenPercent"] / 100, prices[code])
            for code in FOOD_CODES if code in prices
        ]

        self.rank_pct = rank_pct
        self.battle_pct = battle_pct
        self.company_income = company_income

        # one item per 200k round damage and one per 500k battle damage
        self.pool_items_per_damage = (1 / float(game_config["loot"].get("damagePerLootItem", 200_000))
                                      + 1 / float(game_config["loot"].get("battleLootDamagePerLootItem", 500_000)))
        weapon_share = float(game_config["loot"].get("weaponChancePercent", 30)) / 100
        self.pool_item_value = 0.0
        for idx, odds in enumerate(POOL_RARITY_ODDS):
            tier = idx + 1
            fallback = NEW_ITEM_SCRAP[idx] * self.scrap_price
            weapon = gear_prices.get(WEAPON_CODES[idx], fallback)
            others = [gear_prices.get(f"{slot}{tier}", fallback) for slot in GEAR_SLOTS[1:]]
            self.pool_item_value += odds * (weapon_share * weapon + (1 - weapon_share) * sum(others) / len(others))

        self._mitigation = [_mitigation(p, self.soft_cap) for p in range(1001)]

    def mitigation(self, points: float) -> float:
        idx = int(points)
        if idx == points and 0 <= idx < len(self._mitigation):
            return self._mitigation[idx]
        return _mitigation(points, self.soft_cap)

    def sp_cost(self, levels) -> int:
        return sum(self.level_cost[lvl] for lvl in levels)

    def loadout(self, gear: tuple, ammo: int, food: int) -> tuple:
        """Constants of a gear/ammo/food choice, computed once and reused for every skill trial."""
        stats = {}
        weapon_price = weapon_scrap = other_price = other_scrap = 0.0
        for slot_idx, tier_idx in enumerate(gear):
            _, item_stats, price, scrap = self.gear[slot_idx][tier_idx]
            for stat, value in item_stats.items():
                stats[stat] = stats.get(stat, 0) + value
            if slot_idx == 0:
                weapon_price, weapon_scrap = price, scrap
            else:
                other_price += price
                other_scrap += scrap
        _, ammo_pct, ammo_price = self.ammo[ammo]
        _, food_pct, food_price = self.food[food]
        mult = (1 + ammo_pct) * (1 + self.pill_pct) * (1 + self.rank_pct / 100) * max(0.0, 1 + self.battle_pct / 100)
        return (
            stats.get("attack", 0), stats.get("precision", 0), stats.get("criticalChance", 0),
            stats.get("criticalDamages", 0), stats.get("armor", 0), stats.get("dodge", 0),
            mult, food_pct, food_price, ammo_price,
            weapon_price, weapon_scrap, other_price, other_scrap,
        )

    def evaluate(self, terms: tuple, levels, detail: bool = False):
        """(damage, net cost) of one Pill day, or a dict with every intermediate value when `detail`."""
        (g_atk, g_prc, g_crit, g_critd, g_arm, g_ddg, mult, food_pct, food_price, ammo_price,
         weapon_price, weapon_scrap, other_price, other_scrap) = terms
        sv = self.skill_values

        precision = sv[PRC][levels[PRC]] + g_prc
        crit = sv[CRIT][levels[CRIT]] + g_crit
        attack = sv[ATK][levels[ATK]] + g_atk + OVERFLOW_PER_POINT * max(0.0, precision - 100)
        crit_damage = sv[CRITD][levels[CRITD]] + g_critd + OVERFLOW_PER_POINT * max(0.0, crit - 100)
        p = min(precision, 100.0) / 100
        c = min(crit, 100.0) / 100
        attack *= mult
        per_hit = attack * ((1 - p) * 0.5 + p * (1 + c * crit_damage / 100))

        armor = sv[ARM][levels[ARM]] + g_arm
        dodge = sv[DDG][levels[DDG]] + g_ddg
        armor_share = self.mitigation(armor)
        dodge_share = self.mitigation(dodge)
        health_per_hit = max(1.0, self.health_cost * (1 - armor_share)) * (1 - dodge_share)

        health = sv[HP][levels[HP]]
        foods = sv[HUN][levels[HUN]] * self.bars if food_pct else 0.0
        hits = (health * self.bars + foods * food_pct * health) / health_per_hit
        damage = hits * per_hit

        weapon_wear = hits / ITEM_DURABILITY
        other_wear = hits * (1 - dodge_share) / ITEM_DURABILITY
        gear_cost = weapon_wear * weapon_price + other_wear * other_price
        scrap = weapon_wear * weapon_scrap + other_wear * other_scrap
        food_cost = foods * food_price
        ammo_cost = hits * ammo_price
        cost = self.pill_price + food_cost + ammo_cost + gear_cost

        cases = hits * p * sv[LOOT][levels[LOOT]] / 100
        elite_cases = cases * ELITE_CASE_SHARE
        pool_items = damage * self.pool_items_per_damage
        scrap_value = scrap * self.scrap_price
        case_value = cases * self.case_price
        elite_value = elite_cases * self.elite_case_price
        pool_value = pool_items * self.pool_item_value
        returns = scrap_value + case_value + elite_value + pool_value + self.company_income
        net = cost - returns

        if not detail:
            return damage, net
        return {
            "damage": damage, "net": net, "cost": cost, "returns": returns,
            "per_hit": per_hit, "hits": hits, "attack": attack,
            "precision": precision, "crit": crit, "crit_damage": crit_damage,
            "armor": armor, "armor_share": armor_share, "dodge": dodge, "dodge_share": dodge_share,
            "health": health, "hunger": sv[HUN][levels[HUN]], "loot": sv[LOOT][levels[LOOT]],
            "health_per_hit": health_per_hit, "foods": foods,
            "pill_cost": self.pill_price, "food_cost": food_cost, "ammo_cost": ammo_cost, "gear_cost": gear_cost,
            "cases": cases, "case_value": case_value, "elite_cases": elite_cases, "elite_value": elite_value,
            "scrap": scrap, "scrap_value": scrap_value, "pool_items": pool_items, "pool_value": pool_value,
            "company_income": self.company_income,
        }


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

def _optimize_skills(model: Model, terms: tuple, weight: float, sp: int, start=None) -> tuple:
    """Local search over the 9 combat skills for max damage - weight x net cost within `sp` points.

    Adds the levels with the best gain per point first (up to 3 at a time, to cross flat stretches such as
    armor rounding or precision below the cap), then moves points between skills until nothing improves."""
    cache = {}

    def score(lv):
        key = tuple(lv)
        if key not in cache:
            damage, net = model.evaluate(terms, lv)
            cache[key] = damage - weight * net
        return cache[key]

    levels = list(start) if start else [0] * len(SKILLS)
    while model.sp_cost(levels) > sp:
        top = max(range(len(SKILLS)), key=lambda i: levels[i])
        levels[top] -= 1
    current = score(levels)
    cost = model.level_cost

    while True:
        used = model.sp_cost(levels)
        best_ratio, best = 0.0, None
        for i in range(len(SKILLS)):
            for step in (1, 2, 3):
                target = levels[i] + step
                if target > model.skill_max[i]:
                    break
                extra = cost[target] - cost[levels[i]]
                if used + extra > sp:
                    break
                trial = levels.copy()
                trial[i] = target
                gain = score(trial) - current
                if gain > 1e-9 and gain / extra > best_ratio:
                    best_ratio, best = gain / extra, trial
        if best:
            levels, current = best, score(best)
            continue

        best_value, best = current + 1e-9, None
        for i in range(len(SKILLS)):
            for down in (1, 2):
                if levels[i] - down < 0:
                    break
                freed = cost[levels[i]] - cost[levels[i] - down]
                base = levels.copy()
                base[i] -= down
                value = score(base)
                if value > best_value:
                    best_value, best = value, base
                for j in range(len(SKILLS)):
                    if j == i:
                        continue
                    for step in (1, 2, 3):
                        target = levels[j] + step
                        if target > model.skill_max[j]:
                            break
                        if used - freed + cost[target] - cost[levels[j]] > sp:
                            break
                        trial = base.copy()
                        trial[j] = target
                        value = score(trial)
                        if value > best_value:
                            best_value, best = value, trial
        if not best:
            return tuple(levels)
        levels, current = best, best_value


def _ammo_options(model: Model, gear: tuple) -> range:
    # a knife (or no weapon) cannot use ammo; every other weapon needs it to fight
    weapon_tier = model.gear[0][gear[0]][0]
    return range(1, len(model.ammo)) if weapon_tier >= 2 else range(1)


def _fit_ammo(model: Model, gear: tuple, ammo: int) -> int:
    """`ammo` if the weapon takes it, else the weapon's first valid choice (the cheapest ammo for a gun)."""
    options = _ammo_options(model, gear)
    return ammo if ammo in options else options[0]


def _search(model: Model, sp: int, weights=OPTIMIZER_WEIGHTS) -> list:
    """Candidate builds from coordinate descent (skills, then each gear slot, ammo and food) per weight."""
    builds = {}

    def record(levels, gear, ammo, food):
        key = (levels, gear, ammo, food)
        if key not in builds:
            damage, net = model.evaluate(model.loadout(gear, ammo, food), levels)
            builds[key] = (damage, net)

    for weight in weights:
        seen_starts = set()
        for tier in range(0, len(RARITIES) + 1):
            gear = tuple(
                max(i for i, opt in enumerate(options) if opt[0] <= tier) for options in model.gear
            )
            if gear in seen_starts:
                continue
            seen_starts.add(gear)
            ammo = _fit_ammo(model, gear, 2)
            food = len(model.food) - 1
            levels = None

            def objective(lv, g, a, f):
                damage, net = model.evaluate(model.loadout(g, a, f), lv)
                return damage - weight * net

            for _ in range(8):
                levels = _optimize_skills(model, model.loadout(gear, ammo, food), weight, sp, levels)
                record(levels, gear, ammo, food)
                best = (objective(levels, gear, ammo, food), gear, ammo, food)
                for slot in range(len(GEAR_SLOTS)):
                    for option in range(len(model.gear[slot])):
                        trial = gear[:slot] + (option,) + gear[slot + 1:]
                        trial_ammo = _fit_ammo(model, trial, ammo)
                        value = objective(levels, trial, trial_ammo, food)
                        if value > best[0] + 1e-9:
                            best = (value, trial, trial_ammo, food)
                for option in _ammo_options(model, gear):
                    value = objective(levels, gear, option, food)
                    if value > best[0] + 1e-9:
                        best = (value, gear, option, food)
                for option in range(len(model.food)):
                    value = objective(levels, gear, ammo, option)
                    if value > best[0] + 1e-9:
                        best = (value, gear, ammo, option)
                if best[1:] == (gear, ammo, food):
                    break
                _, gear, ammo, food = best
            record(levels, gear, ammo, food)

    return [
        {"levels": levels, "gear": gear, "ammo": ammo, "food": food, "damage": damage, "net": net}
        for (levels, gear, ammo, food), (damage, net) in builds.items()
        if damage > 0
    ]


def _skill_neighbors(model: Model, levels: tuple, sp: int):
    """Skill builds one move away: add up to 3 levels, drop 1-2 levels, or move points between two skills."""
    cost = model.level_cost
    used = model.sp_cost(levels)
    n = len(SKILLS)
    for i in range(n):
        for step in (1, 2, 3):
            target = levels[i] + step
            if target > model.skill_max[i] or used + cost[target] - cost[levels[i]] > sp:
                break
            yield levels[:i] + (target,) + levels[i + 1:]
    for i in range(n):
        for down in (1, 2):
            if levels[i] - down < 0:
                break
            base = levels[:i] + (levels[i] - down,) + levels[i + 1:]
            yield base
            room = sp - used + cost[levels[i]] - cost[levels[i] - down]
            for j in range(n):
                if j == i:
                    continue
                for step in (1, 2, 3):
                    target = levels[j] + step
                    if target > model.skill_max[j] or cost[target] - cost[levels[j]] > room:
                        break
                    yield base[:j] + (target,) + base[j + 1:]


def _loadout_neighbors(model: Model, gear: tuple, ammo: int, food: int):
    for slot in range(len(GEAR_SLOTS)):
        for option in range(len(model.gear[slot])):
            if option != gear[slot]:
                trial = gear[:slot] + (option,) + gear[slot + 1:]
                yield trial, _fit_ammo(model, trial, ammo), food
    for option in _ammo_options(model, gear):
        if option != ammo:
            yield gear, option, food
    for option in range(len(model.food)):
        if option != food:
            yield gear, ammo, option


def _refine(model: Model, sp: int, build: dict, bracket: float) -> dict:
    """Hill-climb on damage from a build within `bracket`, keeping every step within that budget.

    The weighted search only finds builds on the convex hull of damage vs cost; this fills the gaps between
    them. Gear/ammo/food changes are also tried together with one skill move, so a pricier item can be paid
    for by moving points (e.g. into Loot Chance)."""
    def fits(damage, net):
        return damage > 0 and net * 1000 <= bracket * damage + 1e-9

    levels, gear, ammo, food = build["levels"], build["gear"], build["ammo"], build["food"]
    best_damage, best_net = build["damage"], build["net"]
    while True:
        found = None
        terms = model.loadout(gear, ammo, food)
        for trial in _skill_neighbors(model, levels, sp):
            damage, net = model.evaluate(terms, trial)
            if damage > best_damage + 1e-6 and fits(damage, net):
                best_damage, best_net, found = damage, net, (trial, gear, ammo, food)
        neighbors = list(_skill_neighbors(model, levels, sp))
        for loadout in _loadout_neighbors(model, gear, ammo, food):
            terms = model.loadout(*loadout)
            for trial in [levels] + neighbors:
                damage, net = model.evaluate(terms, trial)
                if damage > best_damage + 1e-6 and fits(damage, net):
                    best_damage, best_net, found = damage, net, (trial, *loadout)
        if not found:
            break
        levels, gear, ammo, food = found
    return {"levels": levels, "gear": gear, "ammo": ammo, "food": food, "damage": best_damage, "net": best_net}


def _select_by_bracket(model: Model, sp: int, builds: list, brackets, starts: int = 8) -> list:
    """Per budget: the most damage whose net cost per 1k fits it (refined from the best candidates with
    different gear), or, when nothing fits, the cheapest build per 1k flagged as not fitting."""
    selected, cheapest = [], None
    for bracket in brackets:
        fits = [b for b in builds if b["net"] * 1000 <= bracket * b["damage"] + 1e-9]
        if fits:
            fits.sort(key=lambda b: (b["damage"], -b["net"]), reverse=True)
            seeds, seen_gear = [], set()
            for build in fits:
                if build["gear"] not in seen_gear:
                    seen_gear.add(build["gear"])
                    seeds.append(build)
                    if len(seeds) == starts:
                        break
            # a smaller budget's pick also fits this one
            seeds += [build for _, build, ok in selected if ok]
            refined = [_refine(model, sp, b, bracket) for b in seeds]
            selected.append((bracket, max(refined, key=lambda b: (b["damage"], -b["net"])), True))
        else:
            cheapest = cheapest or _cheapest(model, sp, builds)
            selected.append((bracket, cheapest, False))
    return selected


def _per_damage(build: dict) -> float:
    return build["net"] / build["damage"]


def _cheapest(model: Model, sp: int, builds: list) -> dict:
    """Build with the lowest net cost per damage (Dinkelbach: a build costing r per damage is beaten by any
    build with damage - net / r > 0, so search again with weight 1 / r until nothing cheaper turns up)."""
    best = min(builds, key=lambda b: (_per_damage(b), -b["damage"]))
    for _ in range(4):
        ratio = _per_damage(best)
        if ratio <= 0:
            break
        found = _search(model, sp, (1 / ratio,))
        candidate = min(found, key=lambda b: (_per_damage(b), -b["damage"]), default=None)
        if candidate is None or _per_damage(candidate) >= ratio - 1e-12:
            break
        best = candidate
    return best


def _recommend(model: Model, sp: int, brackets=COST_BRACKETS) -> list:
    """[(bracket, build, fits)] for every budget; CPU-bound, run it in a thread."""
    builds = _search(model, sp)
    return _select_by_bracket(model, sp, builds, brackets) if builds else []


# ---------------------------------------------------------------------------
# Embeds
# ---------------------------------------------------------------------------

def _fmt(n: float, decimals: int = 2) -> str:
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if abs(n) >= 10_000:
        return f"{n / 1_000:.1f}k"
    return f"{n:,.{decimals}f}"


def _item_name(tr, slot: str, tier: int) -> str:
    if tier == 0:
        return tr("damage.gear_none")
    if slot == "weapon":
        return tr(f"damage.weapons.{WEAPON_CODES[tier - 1]}")
    return tr(f"damage.rarities.{RARITIES[tier - 1]}")


def _build_embed(tr, model: Model, sp: int, brackets: list, build: dict, fits: bool,
                 same_as: float | None) -> discord.Embed:
    """One budget's build; `brackets` lists every budget it stands for (all unreachable ones share the
    cheapest build)."""
    gear, levels = build["gear"], build["levels"]
    weapon_tier = model.gear[0][gear[0]][0]
    color = RARITY_COLOR[weapon_tier - 1] if weapon_tier else 0x808080
    d = model.evaluate(model.loadout(gear, build["ammo"], build["food"]), levels, detail=True)
    per_1k = d["net"] * 1000 / d["damage"]
    budget = f"{brackets[0]:.2f}"

    if not fits:
        embed = discord.Embed(
            title=tr("damage.bracket_unreachable_title", damage=_fmt(d["damage"]), cost=f"{per_1k:.3f}"),
            description=tr("damage.bracket_unreachable", brackets=", ".join(f"{b:.2f}" for b in brackets)),
            color=0x808080,
        )
    elif same_as is not None:
        return discord.Embed(
            title=tr("damage.bracket_title", bracket=budget, damage=_fmt(d["damage"]), cost=f"{per_1k:.3f}"),
            description=tr("damage.bracket_same", bracket=f"{same_as:.2f}"),
            color=color,
        )
    else:
        embed = discord.Embed(
            title=tr("damage.bracket_title", bracket=budget, damage=_fmt(d["damage"]), cost=f"{per_1k:.3f}"),
            color=color,
        )

    names = [tr(f"damage.skills.{code}") for code in SKILLS]
    skill_lines = [
        " · ".join(f"{names[i]} **{levels[i]}**" for i in row)
        for row in ((ATK, PRC, CRIT), (CRITD, ARM, DDG), (HP, HUN, LOOT))
    ]
    embed.add_field(name=tr("damage.field_skills"), value="\n".join(skill_lines), inline=False)

    gear_lines = []
    for slot_idx, slot in enumerate(GEAR_SLOTS):
        tier, stats, price, _ = model.gear[slot_idx][gear[slot_idx]]
        emoji = RARITY_EMOJI[tier - 1] if tier else "▫️"
        stat_text = ", ".join(tr(f"damage.stat_short.{stat}", value=value) for stat, value in stats.items())
        line = f"{SLOT_EMOJI[slot]} {tr(f'damage.slots.{slot}')}: {emoji} {_item_name(tr, slot, tier)}"
        if tier:
            line += f" ({stat_text}) · {_fmt(price)}"
        gear_lines.append(line)
    embed.add_field(name=tr("damage.field_gear"), value="\n".join(gear_lines), inline=False)

    ammo_code = model.ammo[build["ammo"]][0]
    food_code = model.food[build["food"]][0]
    consumables = [tr("damage.pill_line", cost=_fmt(d["pill_cost"]))]
    consumables.append(
        tr("damage.ammo_line", name=tr(f"damage.ammo.{ammo_code}"), count=_fmt(d["hits"], 0), cost=_fmt(d["ammo_cost"]))
        if ammo_code else tr("damage.no_ammo")
    )
    consumables.append(
        tr("damage.food_line", name=tr(f"damage.food.{food_code}"), count=_fmt(d["foods"], 1), cost=_fmt(d["food_cost"]))
        if food_code else tr("damage.no_food")
    )
    embed.add_field(name=tr("damage.field_consumables"), value="\n".join(consumables), inline=False)

    combat = tr(
        "damage.combat",
        per_hit=_fmt(d["per_hit"], 0), hits=_fmt(d["hits"], 0), attack=_fmt(d["attack"], 0),
        precision=f"{d['precision']:.0f}", crit=f"{d['crit']:.0f}", crit_damage=f"{d['crit_damage']:.0f}",
        armor=f"{d['armor']:.0f}", armor_pct=f"{d['armor_share'] * 100:.0f}",
        dodge=f"{d['dodge']:.0f}", dodge_pct=f"{d['dodge_share'] * 100:.0f}",
        health=f"{d['health']:.0f}", hunger=f"{d['hunger']:.0f}", loot=f"{d['loot']:.0f}",
        health_per_hit=f"{d['health_per_hit']:.2f}",
    )
    embed.add_field(name=tr("damage.field_combat"), value=combat, inline=False)

    costs = tr(
        "damage.costs",
        pill=_fmt(d["pill_cost"]), ammo=_fmt(d["ammo_cost"]), food=_fmt(d["food_cost"]),
        gear=_fmt(d["gear_cost"]), total=_fmt(d["cost"]),
    )
    embed.add_field(name=tr("damage.field_costs"), value=costs, inline=True)
    returns = tr(
        "damage.returns",
        cases=_fmt(d["cases"], 1), case_value=_fmt(d["case_value"]),
        elite=_fmt(d["elite_cases"], 2), elite_value=_fmt(d["elite_value"]),
        scrap=_fmt(d["scrap"], 0), scrap_value=_fmt(d["scrap_value"]),
        pool=_fmt(d["pool_items"], 1), pool_value=_fmt(d["pool_value"]),
        companies=_fmt(d["company_income"]), total=_fmt(d["returns"]),
    )
    embed.add_field(name=tr("damage.field_returns"), value=returns, inline=True)
    embed.add_field(
        name=tr("damage.field_net"),
        value=tr("damage.net", net=_fmt(d["net"]), cost=f"{per_1k:.3f}"),
        inline=False,
    )
    embed.set_footer(text=tr("damage.footer", used=model.sp_cost(levels), sp=sp))
    return embed


def _chunk_embeds(embeds: list, max_chars: int = 5_900, max_embeds: int = 10) -> list:
    """Pack embeds within Discord's per-message aggregate limits."""
    chunks, current, current_chars = [], [], 0
    for embed in embeds:
        size = len(embed)
        if current and (len(current) >= max_embeds or current_chars + size > max_chars):
            chunks.append(current)
            current, current_chars = [], 0
        current.append(embed)
        current_chars += size
    if current:
        chunks.append(current)
    return chunks


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class DamageBuildHelper(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._game_config = None
        self._game_config_at = 0.0

    async def _get_game_config(self, session):
        if self._game_config is None or time.monotonic() - self._game_config_at > GAME_CONFIG_TTL:
            game_config = await get_game_config(session)
            if game_config:
                self._game_config = game_config
                self._game_config_at = time.monotonic()
        return self._game_config

    @app_commands.command(
        name="damage",
        description="Fight builds for a Pill day, ranked by net money spent per 1,000 damage.",
    )
    @app_commands.describe(
        player_name="In-game player name.",
        number_of_companies="Companies kept active (0-12); their Companies skill points are reserved.",
        companies_level="Automated Engine level of those companies (0-7).",
        company_product="What the companies produce (default: the most profitable per production point).",
        production_bonus="Production bonus of the companies in percent (deposit, country, ...).",
        battle_bonus="Total battle bonus in percent (patriotic, orders, alliance, ...). Default 20.",
    )
    @app_commands.choices(company_product=[
        # Discord shows choice names untranslated, so they use the English locale
        app_commands.Choice(name=t("en", f"damage.products.{code}"), value=code) for code in COMPANY_PRODUCTS
    ])
    async def calculate_build(
        self,
        interaction: discord.Interaction,
        player_name: str,
        number_of_companies: app_commands.Range[int, 0, 12] = 0,
        companies_level: app_commands.Range[int, 0, 7] = 0,
        company_product: str | None = None,
        production_bonus: app_commands.Range[int, 0, 200] = 0,
        battle_bonus: app_commands.Range[int, -100, 300] = DEFAULT_BATTLE_BONUS,
    ) -> None:
        await interaction.response.defer(thinking=True)
        tr = await get_translator(interaction.guild_id)

        session = await get_shared_session()
        user_data, game_config, prices_raw, gear_prices = await asyncio.gather(
            get_user(player_name, session),
            self._get_game_config(session),
            get_market_prices(session),
            _fetch_gear_prices(session),
        )
        if not user_data:
            await interaction.followup.send(tr("damage.player_not_found", name=player_name), ephemeral=True)
            return
        prices = ((prices_raw or {}).get("result") or {}).get("data") or {}
        if not game_config or PILL_CODE not in prices or not gear_prices:
            await interaction.followup.send(tr("damage.data_unavailable"), ephemeral=True)
            return

        level = user_data.get("leveling", {}).get("level", 1)
        total_sp = user_data.get("leveling", {}).get("totalSkillPoints", level * 4)
        rank_pct = float((user_data.get("skills", {}).get("attack") or {}).get("militaryRankPercent") or 0)

        reserved_sp = _companies_sp(game_config, number_of_companies) if number_of_companies else 0
        companies_unlock = int(game_config["skills"]["companies"]["levels"]["0"].get("unlockAtLevel", 1))
        if reserved_sp is None or (reserved_sp and level < companies_unlock) or reserved_sp > total_sp:
            await interaction.followup.send(
                tr("damage.not_enough_sp", name=player_name, total=total_sp, count=number_of_companies),
                ephemeral=True,
            )
            return
        sp = total_sp - reserved_sp

        items = game_config["items"]
        per_pp = {code: _price_per_pp(code, items, prices) for code in COMPANY_PRODUCTS}
        per_pp = {code: value for code, value in per_pp.items() if value is not None}
        product = company_product if company_product in per_pp else max(per_pp, key=per_pp.get, default=None)
        engine_pp = _engine_levels(game_config).get(companies_level, 0.0)
        daily_pp = number_of_companies * engine_pp * (1 + production_bonus / 100)
        company_income = daily_pp * per_pp[product] if product else 0.0

        model = Model(game_config, prices, gear_prices, level, rank_pct, battle_bonus, company_income)
        selected = await asyncio.to_thread(_recommend, model, sp)
        if not selected:
            await interaction.followup.send(tr("damage.no_builds"))
            return

        header = discord.Embed(title=tr("damage.title", name=user_data.get("username", player_name)), color=0x3498DB)
        lines = [
            tr("damage.header_player", level=level, sp=sp, reserved=reserved_sp),
            tr("damage.header_bonus", rank=f"{rank_pct:g}", battle=battle_bonus),
        ]
        if number_of_companies and engine_pp and product:
            lines.append(tr(
                "damage.header_companies",
                count=number_of_companies, level=companies_level, bonus=production_bonus,
                pp=_fmt(daily_pp, 0), product=tr(f"damage.products.{product}"),
                per_pp=f"{per_pp[product]:.3f}", income=_fmt(company_income),
            ))
        else:
            lines.append(tr("damage.header_no_companies"))
        lines.append(tr(
            "damage.header_prices",
            pill=_fmt(model.pill_price), case=_fmt(model.case_price),
            elite=_fmt(model.elite_case_price), scrap=f"{model.scrap_price:.3f}",
            pool=_fmt(model.pool_item_value),
        ))
        header.description = "\n".join(lines)
        header.add_field(name=tr("damage.model_title"), value=tr("damage.model_text"), inline=False)

        embeds = [header]
        unreachable = [(bracket, build) for bracket, build, fits in selected if not fits]
        if unreachable:
            embeds.append(_build_embed(tr, model, sp, [b for b, _ in unreachable], unreachable[0][1], False, None))
        previous = None
        for bracket, build, fits in selected:
            if not fits:
                continue
            key = (build["levels"], build["gear"], build["ammo"], build["food"])
            same_as = previous[0] if previous and previous[1] == key else None
            embeds.append(_build_embed(tr, model, sp, [bracket], build, True, same_as))
            if same_as is None:
                previous = (bracket, key)

        for chunk in _chunk_embeds(embeds):
            await interaction.followup.send(embeds=chunk)


async def setup(bot: commands.Bot):
    await bot.add_cog(DamageBuildHelper(bot))
