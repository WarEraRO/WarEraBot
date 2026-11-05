#!/usr/bin/env python3
"""WarEra economy calculator. Formulas: references/formulas.md (F-ENGINE, F-SELFWORK, F-PROFIT, F-MAXWAGE, F-CASE-EV).

Percent inputs are percentage POINTS (34 = +34%). Prices are per unit in money.

Subcommands
  product   value/profit of producing an item from a PP budget (accounting vs opportunity cost)
  compare   rank several products by economic profit per base PP
  wage      maximum profitable wage per PP for an employer, and a verdict on an offered wage
  selfwork  PP/day from Entrepreneurship self-work
  employee  PP/day an employee produces for an employer from Energy (before production bonus; pre-v0.27 player workers)
  npc       v0.27 hired employee: output, wage, daily profit, value of training cards, toolboxes,
            quit chance and training-card odds (formulas.md F-EMPLOYEE-*, F-TRAINING-RARITY)
  engine    Automated Engine PP/day
  storage   hours until storage is full
  case-ev   expected value of a case from a drop table

Ambiguity handled explicitly (unresolved-mechanics.md U-ECO-1): the guide gives two formulas that
disagree on whether bonus output also consumes raw inputs. --bonus-inputs selects:
  scaled  (default, conservative)  inputs consumed for every output unit incl. bonus units
  base    inputs consumed only for base units (guide's Cost/Revenue formula)
  both    print both
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wlib  # noqa: E402


def recipes():
    data = wlib.load_data("recipes.yaml")
    table = {}
    for row in data["raw"]:
        table[row["code"]] = {"pp": float(row["pp"]), "inputs": {}}
    for row in data["products"]:
        table[row["code"]] = {"pp": float(row["pp"]), "inputs": {k: float(v) for k, v in (row.get("inputs") or {}).items()}}
    return table


ALIASES = {"pill": "cocain", "cooked_fish": "cookedFish", "light_ammo": "lightAmmo", "heavy_ammo": "heavyAmmo", "mysterious_plant": "coca"}


def item_code(name):
    name = ALIASES.get(name, name)
    if name not in recipes():
        raise SystemExit(f"unknown item {name!r}; known: {', '.join(sorted(recipes()))}")
    return name


def parse_prices(pairs):
    prices = {}
    for p in pairs or []:
        k, _, v = p.partition("=")
        prices[ALIASES.get(k, k)] = float(v)
    return prices


def product_economics(item, base_pp, bonus_pct, prices, wage_per_pp=0.0, owned_inputs=False, bonus_inputs="scaled"):
    """Return a dict of production economics for `base_pp` production points spent on `item`."""
    rec = recipes()[item]
    if item not in prices:
        raise SystemExit(f"missing --price {item}=<price>")
    b = bonus_pct / 100.0
    base_units = base_pp / rec["pp"]
    out_units = base_units * (1 + b)
    consumed_units = out_units if bonus_inputs == "scaled" else base_units
    inputs = {}
    input_value = 0.0
    for code, qty in rec["inputs"].items():
        if code not in prices:
            raise SystemExit(f"missing --price {code}=<price> (input of {item})")
        n = consumed_units * qty
        inputs[code] = round(n, 4)
        input_value += n * prices[code]
    revenue = out_units * prices[item]
    wages = base_pp * wage_per_pp
    cash_cost = wages + (0.0 if owned_inputs else input_value)
    economic_cost = wages + input_value  # opportunity cost: owned inputs could have been sold
    return {
        "item": item,
        "base_pp": base_pp,
        "bonus_pct": bonus_pct,
        "bonus_inputs_model": bonus_inputs,
        "base_units": round(base_units, 4),
        "output_units": round(out_units, 4),
        "inputs_consumed": inputs,
        "gross_revenue": round(revenue, 4),
        "input_market_value": round(input_value, 4),
        "wages": round(wages, 4),
        "accounting_cost": round(cash_cost, 4),
        "accounting_profit": round(revenue - cash_cost, 4),
        "economic_profit": round(revenue - economic_cost, 4),
        "economic_profit_per_base_pp": round((revenue - economic_cost) / base_pp, 6) if base_pp else None,
        "note": "economic profit counts owned inputs at market value (opportunity cost); accounting profit treats them as free"
        if owned_inputs
        else "inputs assumed bought at market price (accounting = economic)",
    }


def max_wage_per_pp(item, bonus_pct, loyalty_pct, prices, bonus_inputs="scaled"):
    rec = recipes()[item]
    input_cost_unit = sum(q * prices[c] for c, q in rec["inputs"].items())
    mult = 1 + (bonus_pct + loyalty_pct) / 100.0
    if bonus_inputs == "scaled":
        # guide F-MAXWAGE: (1 + bonus + loyalty) * (price - input cost per unit) / recipe PP
        return mult * (prices[item] - input_cost_unit) / rec["pp"]
    # inputs only for base units
    return (mult * prices[item] - input_cost_unit) / rec["pp"]


def models(arg):
    return ["scaled", "base"] if arg == "both" else [arg]


def cmd_product(a):
    item = item_code(a.item)
    prices = parse_prices(a.price)
    for m in models(a.bonus_inputs):
        print(wlib.dump(product_economics(item, a.base_pp, a.bonus, prices, a.wage_per_pp, a.owned_inputs, m)))


def cmd_compare(a):
    prices = parse_prices(a.price)
    rows = []
    for spec in a.product:
        name, _, bonus = spec.partition(":")
        item = item_code(name)
        for m in models(a.bonus_inputs):
            r = product_economics(item, a.base_pp, float(bonus or 0), prices, a.wage_per_pp, False, m)
            rows.append((r["economic_profit_per_base_pp"], item, float(bonus or 0), m, r["economic_profit"]))
    rows.sort(reverse=True)
    print(f"{'rank':<5}{'item':<12}{'bonus%':>8}{'model':>8}{'profit/PP':>14}{'profit':>12}")
    for i, (ppp, item, bonus, m, prof) in enumerate(rows, 1):
        print(f"{i:<5}{item:<12}{bonus:>8.1f}{m:>8}{ppp:>14.6f}{prof:>12.4f}")
    print("\nprofit/PP = economic profit per BASE production point (inputs at market value, wages included).")


def cmd_wage(a):
    item = item_code(a.item)
    prices = parse_prices(a.price)
    for m in models(a.bonus_inputs):
        mx = max_wage_per_pp(item, a.bonus, a.loyalty, prices, m)
        out = {"item": item, "model": m, "bonus_pct": a.bonus, "loyalty_pct": a.loyalty, "max_profitable_wage_per_pp": round(mx, 6)}
        if a.offered is not None:
            margin = mx - a.offered
            out.update({"offered_wage_per_pp": a.offered, "margin_per_pp": round(margin, 6), "verdict": "profitable" if margin > 0 else "NOT profitable"})
        print(wlib.dump(out))
    print("Wage is gross (employer side). Loyalty accrues ~1%/day up to 10% and is lost if the worker leaves.")


def cmd_selfwork(a):
    regen = wlib.value("economy.regen_fraction_per_hour")
    per_action = wlib.value("economy.bar_cost_per_action")
    bars_per_day = 24 * float(regen)
    actions = a.entrepreneurship * bars_per_day / float(per_action)
    pp = actions * a.production * (1 + a.bonus / 100.0)
    print(wlib.dump({"formula": "Entrepreneurship/10 * Production * 2.4 * (1 + bonus)", "actions_per_day": round(actions, 3), "pp_per_day": round(pp, 3),
                     "assumption": "player logs in often enough that the bar never caps (2.4 = 24 hourly regens of 10%)"}))


def cmd_employee(a):
    regen = wlib.value("economy.regen_fraction_per_hour")
    per_action = wlib.value("economy.bar_cost_per_action")
    actions = a.energy * 24 * float(regen) / float(per_action)
    print(wlib.dump({"actions_per_day": round(actions, 3), "base_pp_per_day": round(actions * a.production, 3),
                     "note": "employer's production bonus and loyalty apply on top; wage is paid on base PP"}))


RARITY_BASE = {"common": 55, "uncommon": 25, "rare": 13, "epic": 5, "legendary": 2}
RARITY_PER_MANAGEMENT = {"uncommon": 1, "rare": 0.6, "epic": 0.3, "legendary": 0.1}
RARITY_PER_LUCK = {"uncommon": 0.5, "rare": 0.3, "epic": 0.15, "legendary": 0.05}


def training_odds(management, luck):
    """Return the training-card rarity shares in percent for a Management level and an employee's Luck.

    Management (Leadership until v0.27.3) and Luck move weight off Common (live client constants); shares
    are weight / total, which is 100 until Common reaches 0.
    """
    management, luck = max(0.0, management), max(0.0, luck)
    w = {r: RARITY_BASE[r] + RARITY_PER_MANAGEMENT[r] * management + RARITY_PER_LUCK[r] * luck for r in RARITY_PER_MANAGEMENT}
    w["common"] = max(0.0, RARITY_BASE["common"] - 2 * management - luck)
    total = sum(w.values())
    return {r: round(100 * w[r] / total, 2) for r in RARITY_BASE}


def quit_chance_per_hour(happiness, flight_risk=False):
    """Return the derived hourly quit chance (fraction): 5% x (T - happiness) / T below T = 30, or 50 for Flight risk."""
    threshold = 50.0 if flight_risk else 30.0
    if happiness >= threshold:
        return 0.0
    return 0.05 * (threshold - max(0.0, happiness)) / threshold


def cmd_npc(a):
    """Print a v0.27 employee's daily output, wage and profit, plus marginal values of training choices.

    Values are in money at --pp-value (raw goods; for processed goods pass --output-value per PP). The
    bonus parts add (in-game "added together"); the employee tax is not deducted (who bears it is a GAP).
    """
    paid = a.production if a.paid_production is None else a.paid_production
    b = a.bonus / 100.0
    e = 1 + a.expectation / 100.0
    v_out = a.pp_value if a.output_value is None else a.output_value
    pp_day = 6 * a.production * (1 + b)
    wage_day = 6 * paid * a.pp_value * e
    out = {
        "formula": "PP/day = 6 x Production x (1 + bonus); wage/day = 6 x paid Production x PP value x expectation",
        "pp_per_hour": round(pp_day / 24, 4),
        "pp_per_day": round(pp_day, 3),
        "output_value_per_day": round(pp_day * v_out, 4),
        "wage_per_hour": round(wage_day / 24, 5),
        "wage_per_day": round(wage_day, 4),
        "profit_per_day": round(pp_day * v_out - wage_day, 4),
        "marginal_per_day": {
            "drill_plus1_production": round(6 * (v_out * (1 + b) - a.pp_value * e), 4),
            "trait_plus1_production_unpaid": round(6 * v_out * (1 + b), 4),
            "negotiation_minus5": round(6 * paid * a.pp_value * 0.05, 4),
            "negotiation_minus10": round(6 * paid * a.pp_value * 0.10, 4),
            "negotiation_minus20": round(6 * paid * a.pp_value * 0.20, 4),
            "plus1_percent_bonus": round(6 * a.production * 0.01 * v_out, 4),
            "owner_management_level_for_this_employee": round(6 * a.production * 0.02 * v_out, 4),
            "drill_plus1_responsibility_v0273": round(6 * a.production * 0.03 * v_out, 4),
        },
        "notes": "hourly output rolls +/-10%; every hour must be paid in full or nobody works; "
                 "Responsibility = +3 happiness (+3% output) per point since v0.27.3, worthless once happiness is 100",
    }
    if a.luck is not None:
        p = 0.001 * a.luck  # uncapped since 2026-10-29 (was 2%/h)
        out["toolbox_chance_per_hour"] = p
        out["toolboxes_per_24_worked_hours"] = round(1 - (1 - p) ** 24, 4)
    if a.happiness is not None:
        q = quit_chance_per_hour(a.happiness, a.flight_risk)
        out["quit_chance_per_hour_derived"] = round(q, 5)
        out["quit_within_24h_derived"] = round(1 - (1 - q) ** 24, 4)
    if a.management is not None:
        out["training_rarity_percent"] = training_odds(a.management, a.luck or 0.0)
    print(wlib.dump(out))


def cmd_engine(a):
    levels = wlib.value("company.engine_levels")
    lvl = levels.get(f"L{a.level}")
    if not lvl:
        raise SystemExit("engine level must be 1..7")
    pp = lvl["pp_per_day"] * (1 + a.bonus / 100.0)
    print(wlib.dump({"level": a.level, "base_pp_per_day": lvl["pp_per_day"], "pp_per_day_with_bonus": round(pp, 3), "next_level_steel": (levels.get(f"L{a.level + 1}") or {}).get("steel")}))


def cmd_storage(a):
    cap = wlib.value("company.storage_levels")[f"L{a.level}"]["capacity"]
    free = cap - a.stored
    hours = free / (a.daily_pp / 24.0) if a.daily_pp > 0 else None
    print(wlib.dump({"capacity_pp": cap, "free_pp": free, "hours_until_full": round(hours, 2) if hours is not None else None,
                     "warning": "when full, engine, self-work AND employees all stop adding PP"}))


def cmd_case_ev(a):
    ev, total_p = 0.0, 0.0
    for d in a.drop:
        name, p, v = d.split(":")
        p, v = float(p), float(v)
        total_p += p
        ev += p * v
    if abs(total_p - 1) > 1e-6 and abs(total_p - 100) > 1e-6:
        print(f"WARNING: probabilities sum to {total_p}, expected 1 or 100")
    if total_p > 1.5:
        ev /= 100.0
    out = {"expected_value": round(ev, 4)}
    if a.case_price is not None:
        out["case_price"] = a.case_price
        out["decision"] = "open (EV > price, but high variance)" if ev > a.case_price else "sell (price >= EV)"
    print(wlib.dump(out))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--price", action="append", help="item=price (repeatable), e.g. --price steel=1.8 --price iron=0.12")
        p.add_argument("--bonus-inputs", choices=["scaled", "base", "both"], default="scaled")

    p = sub.add_parser("product")
    p.add_argument("--item", required=True)
    p.add_argument("--base-pp", type=float, required=True, help="production points before bonus")
    p.add_argument("--bonus", type=float, default=0.0, help="total production bonus, percent points")
    p.add_argument("--wage-per-pp", type=float, default=0.0)
    p.add_argument("--owned-inputs", action="store_true", help="inputs come from own stock (accounting cost 0, opportunity cost kept)")
    common(p)
    p.set_defaults(fn=cmd_product)

    p = sub.add_parser("compare")
    p.add_argument("--base-pp", type=float, default=1000.0)
    p.add_argument("--product", action="append", required=True, help="item:bonus_pct (repeatable)")
    p.add_argument("--wage-per-pp", type=float, default=0.0)
    common(p)
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser("wage")
    p.add_argument("--item", required=True)
    p.add_argument("--bonus", type=float, default=0.0)
    p.add_argument("--loyalty", type=float, default=0.0)
    p.add_argument("--offered", type=float, help="offered gross wage per PP")
    common(p)
    p.set_defaults(fn=cmd_wage)

    p = sub.add_parser("selfwork")
    p.add_argument("--entrepreneurship", type=float, required=True, help="max Entrepreneurship bar")
    p.add_argument("--production", type=float, required=True, help="Production skill value (PP per action)")
    p.add_argument("--bonus", type=float, default=0.0)
    p.set_defaults(fn=cmd_selfwork)

    p = sub.add_parser("employee")
    p.add_argument("--energy", type=float, required=True, help="max Energy bar")
    p.add_argument("--production", type=float, required=True)
    p.set_defaults(fn=cmd_employee)

    p = sub.add_parser("npc", help="v0.27 hired employee economics")
    p.add_argument("--production", type=float, required=True, help="total Production stat (base + trained + traits/coworkers)")
    p.add_argument("--paid-production", type=float, help="base + trained Production (the wage basis); default = --production")
    p.add_argument("--expectation", type=float, default=0.0, help="shown wage expectation in percent points, e.g. -22.7")
    p.add_argument("--bonus", type=float, default=0.0, help="total production bonus in percent points (happiness, tool, Management ...)")
    p.add_argument("--pp-value", type=float, required=True, help="market value of 1 PP (the game's wage basis)")
    p.add_argument("--output-value", type=float, help="net value per PP of the good produced; default = --pp-value")
    p.add_argument("--luck", type=float, help="employee Luck (toolbox chance; also used for card odds)")
    p.add_argument("--happiness", type=float, help="current happiness, for the derived quit chance")
    p.add_argument("--flight-risk", action="store_true", help="employee has the Flight risk trait (quit threshold 50)")
    p.add_argument("--management", "--leadership", dest="management", type=float,
                   help="your Management level, to print training-card odds (--leadership: alias from before v0.27.3)")
    p.set_defaults(fn=cmd_npc)

    p = sub.add_parser("engine")
    p.add_argument("--level", type=int, required=True)
    p.add_argument("--bonus", type=float, default=0.0)
    p.set_defaults(fn=cmd_engine)

    p = sub.add_parser("storage")
    p.add_argument("--level", type=int, required=True)
    p.add_argument("--stored", type=float, default=0.0)
    p.add_argument("--daily-pp", type=float, required=True)
    p.set_defaults(fn=cmd_storage)

    p = sub.add_parser("case-ev")
    p.add_argument("--drop", action="append", required=True, help="name:probability:value (probability as fraction or percent)")
    p.add_argument("--case-price", type=float)
    p.set_defaults(fn=cmd_case_ev)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
