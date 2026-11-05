#!/usr/bin/env python3
"""WarEra combat helpers that do NOT require the (unpublished) damage formula.

Subcommands
  mitigation  Armor/Dodge effective % from points (F-MITIGATION) and next breakpoint
  hp          Expected health spent per hit and hits per health bar (F-HP-PER-HIT, inference)
  overflow    Precision/Critical-chance overflow conversion (F-OVERFLOW)
  pill        Pill phase (buff/debuff/none) at a given time (F-PILL-PHASE)
  cost1k      Cost per 1,000 damage (F-COST-1K) and sustainability for a budget
  damage      Expected damage per attempted hit and per Health bar (F-DAMAGE; partly inferred - calibrate)
  rank        Military rank and its damage bonus for a total-damage figure (data/military-ranks.yaml)

Hit outcomes (normal / crit / miss) are documented by the wiki; how Pill, ammo, rank and battle bonuses stack is
partly inferred (guide: Pill, ammo and rank multiply; battle bonuses add up). Treat damage output as an estimate.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wlib  # noqa: E402


def round_sig(x, sig=2):
    if x == 0:
        return 0.0
    return round(x, sig - int(math.floor(math.log10(abs(x)))) - 1)


def mitigation_pct(points):
    """Effective Armor/Dodge %: total/(total+40) rounded to 2 significant figures (guide 27/28.6)."""
    return round(round_sig(points / (points + 40.0), 2) * 100, 6) if points > 0 else 0.0


def cmd_mitigation(a):
    """Print the Armor/Dodge %, its breakpoint bracket and, for armor, the Health lost per hit."""
    per_level = 6 if a.stat == "armor" else 4
    total = a.total if a.total is not None else a.skill_level * per_level + sum(a.item or [])
    total = int(total) if float(total).is_integer() else total
    pct = mitigation_pct(total)
    nxt = total + 1
    while mitigation_pct(nxt) == pct and nxt < total + 500:
        nxt += 1
    lo = total
    while lo > 0 and mitigation_pct(lo - 1) == pct:
        lo -= 1
    out = {"stat": a.stat, "total_points": total, "effective_pct": pct, "bracket": f"{lo}-{nxt - 1}",
           "points_to_next_pct": nxt - total, "next_pct": mitigation_pct(nxt),
           "advice": "extra points inside the same bracket give NOTHING - buy the cheapest pieces that reach the bracket floor"}
    if a.stat == "armor":
        cost = float(wlib.value("combat.health_cost_per_hit")["base"])
        out["health_per_hit"] = round(max(1.0, cost * (1 - pct / 100)), 3)
        out["health_per_hit_note"] = ("10 x (1 - armor%) (config battle.healthCost); the wiki's minimum of 1 per hit only binds "
                                      "above 360 armor; no armor hard cap since v0.24.0")
    print(wlib.dump(out))


def cmd_hp(a):
    """Print the expected Health lost per hit and hits per Health bar for the given armor and dodge %."""
    cost = float(wlib.value("combat.health_cost_per_hit")["base"])
    per_hit = max(1.0, cost * (1 - a.armor_pct / 100)) * (1 - a.dodge_pct / 100)
    print(wlib.dump({"expected_health_per_hit": round(per_hit, 4), "hits_per_health_bar": round(a.health / per_hit, 2) if per_hit else None,
                     "rules": ["10 HP per hit reduced by armor, minimum 1 (wiki)", "dodge avoids health loss and non-weapon wear; ammo and weapon are still consumed",
                               "since v0.22.0 you can hit below 10 Health, depending on armor (exact rule not published)"]}))


def cmd_overflow(a):
    rates = wlib.value("combat.overflow_conversion")
    out = {}
    if a.precision is not None:
        out["precision_overflow"] = max(0.0, a.precision - 100)
        out["extra_attack"] = out["precision_overflow"] * rates["precision_over_100_to_attack"]
    if a.crit_chance is not None:
        out["crit_overflow"] = max(0.0, a.crit_chance - 100)
        out["extra_crit_damage"] = out["crit_overflow"] * rates["crit_chance_over_100_to_crit_damage"]
    print(wlib.dump(out))


def cmd_pill(a):
    p = wlib.value("consumables.pill", a.now)
    t0 = wlib.parse_dt(a.consumed_at)
    now = wlib.parse_dt(a.now) if a.now else wlib.utcnow()
    h = (now - t0).total_seconds() / 3600
    buff, debuff = float(p["buff_hours"]), float(p["debuff_hours"])
    if h < 0:
        phase, left = "not yet consumed", None
    elif h < buff:
        phase, left = f"BUFF (+{p.get('buff_attack_percent', '?')}% attack)", buff - h
    elif h < buff + debuff:
        phase, left = f"DEBUFF ({p.get('debuff_attack_percent', '?')}% attack) - avoid expensive gear", buff + debuff - h
    else:
        phase, left = "none (cycle finished)", None
    print(wlib.dump({"hours_since_pill": round(h, 2), "phase": phase, "hours_left_in_phase": round(left, 2) if left is not None else None,
                     "cycle_hours": buff + debuff}))


def cmd_cost1k(a):
    net = a.total_cost - a.recovered_value
    c = net / a.damage * 1000
    out = {"gross_cost": a.total_cost, "recovered_value": a.recovered_value, "net_cost": round(net, 4), "cost_per_1k_damage": round(c, 4),
           "community_target": "0.15-0.20 (0.20-0.25 acceptable) incl. cases and loot, excl. bounty income [STRATEGY-RO]"}
    if a.budget is not None and a.daily_cost:
        out["days_sustainable"] = round(a.budget / a.daily_cost, 2)
    print(wlib.dump(out))


def cmd_damage(a):
    rates = wlib.value("combat.overflow_conversion")
    prec, crit, cd = a.precision / 100, a.crit_chance / 100, a.crit_damage / 100
    attack = a.attack
    if prec > 1:
        attack += (a.precision - 100) * rates["precision_over_100_to_attack"]
        prec = 1.0
    if crit > 1:
        cd += (a.crit_chance - 100) * rates["crit_chance_over_100_to_crit_damage"] / 100
        crit = 1.0
    ammo = {"none": 0, "light": 10, "standard": 20, "heavy": 40}[a.ammo]
    pill = {"none": 0, "buff": 60, "debuff": -60}[a.pill]
    eff_attack = attack * (1 + ammo / 100) * (1 + pill / 100)
    per_attack_unit = (1 - prec) * 0.5 + prec * (1 + crit * cd)
    raw = eff_attack * per_attack_unit
    mult = (1 + a.rank_bonus / 100) * max(0.0, 1 + a.battle_bonus / 100)
    exp_hit = raw * mult
    out = {"effective_attack": round(eff_attack, 2), "expected_damage_per_attempt": round(exp_hit, 2),
           "outcome_shares": {"miss_half_damage": round(1 - prec, 4), "crit": round(prec * crit, 4), "normal": round(prec * (1 - crit), 4)},
           "multipliers": {"ammo_pct": ammo, "pill_pct": pill, "rank_pct": a.rank_bonus, "battle_bonus_total_pct": a.battle_bonus}}
    if a.health:
        cost = float(wlib.value("combat.health_cost_per_hit")["base"])
        per_hit_hp = max(1.0, cost * (1 - a.armor_pct / 100)) * (1 - a.dodge_pct / 100)
        hits = a.health / per_hit_hp
        out["hits_per_health_bar"] = round(hits, 2)
        out["expected_damage_per_health_bar"] = round(hits * exp_hit, 1)
    out["caveats"] = ["hit outcomes per wiki (miss = half Attack, cannot crit; crit = Attack x (1 + crit damage))",
                      "ammo/Pill applied as % of Attack and rank/battle bonuses as multipliers - stacking order partly inferred",
                      "Attack = skill attack + weapon attack (flat); RNG spread ignored - calibrate against real hits"]
    print(wlib.dump(out))


def cmd_rank(a):
    ranks = wlib.load_data("military-ranks.yaml")["ranks"]
    cur = max((r for r in ranks if r["total_damage"] <= a.damage), key=lambda r: r["total_damage"])
    nxt = next((r for r in ranks if r["total_damage"] > a.damage), None)
    out = {"total_damage": a.damage, "rank": cur["name"], "rank_level": cur["level"], "bonus_pct": cur["bonus_pct"], "tier": cur["tier"]}
    if nxt:
        out["next"] = {"rank": nxt["name"], "bonus_pct": nxt["bonus_pct"], "damage_needed": nxt["total_damage"] - a.damage}
    print(wlib.dump(out))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("mitigation")
    p.add_argument("--stat", choices=["armor", "dodge"], default="armor")
    p.add_argument("--total", type=float, help="total points (skill + items)")
    p.add_argument("--skill-level", type=int, default=0, help="Armor gives 6 points/level, Dodge 4")
    p.add_argument("--item", type=float, action="append", help="item stat (chest/pants for armor, boots for dodge); repeatable")
    p.set_defaults(fn=cmd_mitigation)

    p = sub.add_parser("hp")
    p.add_argument("--health", type=float, default=100)
    p.add_argument("--armor-pct", type=float, default=0)
    p.add_argument("--dodge-pct", type=float, default=0)
    p.set_defaults(fn=cmd_hp)

    p = sub.add_parser("overflow")
    p.add_argument("--precision", type=float)
    p.add_argument("--crit-chance", type=float)
    p.set_defaults(fn=cmd_overflow)

    p = sub.add_parser("pill")
    p.add_argument("--consumed-at", required=True)
    p.add_argument("--now")
    p.set_defaults(fn=cmd_pill)

    p = sub.add_parser("cost1k")
    p.add_argument("--total-cost", type=float, required=True, help="ammo + food + pills + gear durability + travel oil, in money")
    p.add_argument("--recovered-value", type=float, default=0.0, help="value of cases, scrap and loot obtained")
    p.add_argument("--damage", type=float, required=True)
    p.add_argument("--budget", type=float)
    p.add_argument("--daily-cost", type=float)
    p.set_defaults(fn=cmd_cost1k)

    p = sub.add_parser("damage")
    p.add_argument("--attack", type=float, required=True, help="Attack stat = skill attack + weapon attack")
    p.add_argument("--precision", type=float, required=True, help="percent, may exceed 100 (overflow -> +4 attack per point)")
    p.add_argument("--crit-chance", type=float, required=True, help="percent")
    p.add_argument("--crit-damage", type=float, required=True, help="percent (skill + helmet)")
    p.add_argument("--ammo", choices=["none", "light", "standard", "heavy"], default="none")
    p.add_argument("--pill", choices=["none", "buff", "debuff"], default="none")
    p.add_argument("--rank-bonus", type=float, default=0.0, help="military rank bonus percent (see 'rank')")
    p.add_argument("--battle-bonus", type=float, default=0.0, help="summed battle bonus percent (combat_bonus_calculator.py)")
    p.add_argument("--health", type=float, help="Health available, to estimate damage per bar")
    p.add_argument("--armor-pct", type=float, default=0)
    p.add_argument("--dodge-pct", type=float, default=0)
    p.set_defaults(fn=cmd_damage)

    p = sub.add_parser("rank")
    p.add_argument("--damage", type=float, required=True, help="total lifetime damage")
    p.set_defaults(fn=cmd_rank)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
