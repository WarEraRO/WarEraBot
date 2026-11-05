#!/usr/bin/env python3
"""WarEra country / politics helpers (references/formulas.md F-ORDER-PAPER, F-TREATY-UPKEEP, F-INIT-DEV, F-RESISTANCE-BAR, F-SEATS).

Subcommands
  order-cost      paper cost of a battle order (country: active citizens; MU: members)
  upkeep          daily paper upkeep of Sworn Enemy / Defensive Pacts / alliance from average development
  initial-dev     a new country's initial development
  resistance-bar  resistance bar size and contributions needed to fill it
  seats           Congress seats

Most formulas here come from warera.wiki, which is OUTDATED: treat outputs as estimates unless the rule is also confirmed by
the live config or the guide (resistance bar and seats are; order cost and treaty upkeep are wiki-only). See unresolved-mechanics.md.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wlib  # noqa: E402

BASE = {"low": 5, "medium": 10, "high": 20}


def cmd_order_cost(a):
    n = a.members if a.issuer == "mu" else a.active_citizens
    if n is None:
        raise SystemExit("--active-citizens (country) or --members (mu) is required")
    scale = max(1, math.floor(n / 5))
    cost = BASE[a.priority] * scale
    notes = []
    if a.issuer == "country":
        if a.unethical:
            cost *= 2
            notes.append("Unethical: double paper (and double priority bonus)")
        if a.fanatic_pacifist_core_or_revolt:
            cost = 0
            notes.append("Fanatic Pacifist: core-defense and revolt orders are free")
        if a.discount_50:
            cost *= 0.5
            notes.append("50% discount applied (Fanatic Diplomatic supporting a pact partner / Fanatic Isolationist vs Sworn Enemy)")
    print(wlib.dump({"issuer": a.issuer, "priority": a.priority, "base_paper": BASE[a.priority], "scale": scale, "paper": cost,
                     "rule": "WIKI-ONLY estimate: base (5/10/20) x max(1, floor(n / 5)), n = active citizens (country) or members (MU)", "notes": notes,
                     "warning": "the wiki is outdated; the guide says country order cost scales with AVERAGE DEVELOPMENT (exact formula unknown) - "
                                "trust the cost shown in the order dialog (U-ORD-1). MU scaling by members agrees with the guide."}))


def cmd_upkeep(a):
    d = a.avg_dev
    tens = math.floor(d / 10)
    iso = 1.5 if a.fanatic_isolationist else 1.0
    dip_pact = 0.5 if a.fanatic_diplomatic else 1.0
    dip_enemy = 2.0 if a.fanatic_diplomatic else 1.0
    out = {"average_development": d,
           "sworn_enemy_per_day": tens * 10 * iso * dip_enemy,
           "defensive_pact_per_day_each": tens * 5 * iso * dip_pact,
           "defensive_pact_per_day_each_alt": tens * iso * dip_pact,
           "notes": ["WIKI country page: pact = floor(dev/10) x 5; WIKI pact page: floor(dev/10) - conflicting (alt value)",
                     "Fanatic Isolationist +50% on all treaties; Fanatic Diplomatic -50% pacts, +100% Sworn Enemy",
                     "low confidence - check the treaty cost shown in the law form"]}
    if a.alliance_avg_dev is not None:
        out["alliance_per_day"] = math.floor((d + 0.5 * a.alliance_avg_dev) * iso)
    print(wlib.dump(out))


def cmd_initial_dev(a):
    dev = ((a.active_citizens * a.avg_level) / 20) ** 0.95
    print(wlib.dump({"initial_development": round(dev, 2), "rule": "((active citizens x average level) / 20) ^ 0.95 (WIKI)"}))


def cmd_resistance_bar(a):
    bar = a.region_dev * 100
    need = max(0.0, bar - a.current)
    print(wlib.dump({"bar_max": bar, "missing": need,
                     "contributions_if_citizens": math.ceil(need / 2), "contributions_if_non_citizens": math.ceil(need),
                     "cost_each": "10 Health or 10 Energy", "bonus_at_current_fill_pct": round(30 * min(1, a.current / bar), 2) if bar else None,
                     "rule": "bar = region development x 100; citizens +2, non-citizens +1 per contribution; bonus up to +30% (allies half)"}))


def cmd_seats(a):
    print(wlib.dump({"active_population": a.active, "congress_seats": min(50, max(5, math.ceil(a.active / 20) + 2))}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("order-cost")
    p.add_argument("--issuer", choices=["country", "mu"], default="country")
    p.add_argument("--priority", choices=list(BASE), required=True)
    p.add_argument("--active-citizens", type=int)
    p.add_argument("--members", type=int)
    p.add_argument("--unethical", action="store_true")
    p.add_argument("--fanatic-pacifist-core-or-revolt", action="store_true")
    p.add_argument("--discount-50", action="store_true")
    p.set_defaults(fn=cmd_order_cost)
    p = sub.add_parser("upkeep")
    p.add_argument("--avg-dev", type=float, required=True, help="country average development")
    p.add_argument("--alliance-avg-dev", type=float, help="average development of alliance members")
    p.add_argument("--fanatic-isolationist", action="store_true")
    p.add_argument("--fanatic-diplomatic", action="store_true")
    p.set_defaults(fn=cmd_upkeep)
    p = sub.add_parser("initial-dev")
    p.add_argument("--active-citizens", type=float, required=True)
    p.add_argument("--avg-level", type=float, required=True)
    p.set_defaults(fn=cmd_initial_dev)
    p = sub.add_parser("resistance-bar")
    p.add_argument("--region-dev", type=float, required=True)
    p.add_argument("--current", type=float, default=0.0)
    p.set_defaults(fn=cmd_resistance_bar)
    p = sub.add_parser("seats")
    p.add_argument("--active", type=int, required=True)
    p.set_defaults(fn=cmd_seats)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
