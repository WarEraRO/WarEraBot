#!/usr/bin/env python3
"""Break-even for a company move / product change (references/formulas.md F-BREAKEVEN).

  days = switch_cost_money / (new_daily_profit - old_daily_profit)

Mode A - direct profits:
  python break_even.py --cost-concrete 5 --concrete-price 1.6 --old-daily 12.0 --new-daily 14.5 [--advantage-days 6]

Mode B - same item, different production bonus (typical deposit move):
  python break_even.py --cost-concrete 5 --concrete-price 1.6 --item steel --daily-base-pp 300 \
      --old-bonus 20 --new-bonus 37 --price steel=1.8 --price iron=0.12 [--advantage-days 6]

Mode C - product change (+ optional move):
  python break_even.py --cost-concrete 10 --concrete-price 1.6 --item iron --new-item steel --daily-base-pp 300 \
      --old-bonus 30 --new-bonus 34 --price steel=1.8 --price iron=0.12

--advantage-days: how long the new advantage lasts (deposit time left shown in the move window, or the
policy horizon). If break-even > advantage-days the move does not pay.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import economy_calculator as ec  # noqa: E402
import wlib  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cost-concrete", type=float, help="concrete spent (move 5, product change 5, both 10)")
    ap.add_argument("--concrete-price", type=float, help="market price of concrete")
    ap.add_argument("--cost-money", type=float, default=0.0, help="extra money cost (lost production during the switch, etc.)")
    ap.add_argument("--old-daily", type=float)
    ap.add_argument("--new-daily", type=float)
    ap.add_argument("--item")
    ap.add_argument("--new-item")
    ap.add_argument("--daily-base-pp", type=float, help="base PP/day of the company (engine + self-work + employees, before bonus)")
    ap.add_argument("--old-bonus", type=float, default=0.0)
    ap.add_argument("--new-bonus", type=float, default=0.0)
    ap.add_argument("--wage-per-pp", type=float, default=0.0)
    ap.add_argument("--price", action="append")
    ap.add_argument("--bonus-inputs", choices=["scaled", "base"], default="scaled")
    ap.add_argument("--advantage-days", type=float)
    a = ap.parse_args()

    cost = a.cost_money
    if a.cost_concrete:
        if a.concrete_price is None:
            raise SystemExit("--concrete-price is required with --cost-concrete (concrete is never free: use its market price)")
        cost += a.cost_concrete * a.concrete_price

    if a.old_daily is not None and a.new_daily is not None:
        old, new = a.old_daily, a.new_daily
        detail = {}
    else:
        if not (a.item and a.daily_base_pp):
            raise SystemExit("give --old-daily/--new-daily, or --item + --daily-base-pp (+ bonuses and prices)")
        prices = ec.parse_prices(a.price)
        old_r = ec.product_economics(ec.item_code(a.item), a.daily_base_pp, a.old_bonus, prices, a.wage_per_pp, False, a.bonus_inputs)
        new_item = ec.item_code(a.new_item or a.item)
        new_r = ec.product_economics(new_item, a.daily_base_pp, a.new_bonus, prices, a.wage_per_pp, False, a.bonus_inputs)
        old, new = old_r["economic_profit"], new_r["economic_profit"]
        detail = {"old": old_r, "new": new_r}

    gain = new - old
    out = {"switch_cost_money": round(cost, 4), "old_daily_profit": round(old, 4), "new_daily_profit": round(new, 4), "daily_gain": round(gain, 4)}
    if gain <= 0:
        out["verdict"] = "never breaks even (no daily gain)"
    else:
        days = cost / gain
        out["break_even_days"] = round(days, 2)
        if a.advantage_days is not None:
            out["advantage_days"] = a.advantage_days
            out["net_gain_over_advantage"] = round(gain * a.advantage_days - cost, 4)
            out["verdict"] = "worth it" if days < a.advantage_days else "NOT worth it (advantage ends before break-even)"
        else:
            out["verdict"] = "pays back if the advantage lasts longer than break_even_days (deposit time left unknown)"
    if detail:
        out["detail"] = detail
    print(wlib.dump(out))


if __name__ == "__main__":
    main()
