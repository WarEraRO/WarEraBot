#!/usr/bin/env python3
"""Version-aware WarEra battle damage-bonus aggregator (references/formulas.md F-BONUS-SUM, F-ALLIANCE).

Battle bonuses are summed (guide 33.1) and floored at -100%. Pill, ammo and military rank are separate
multipliers in the unpublished damage formula and are NOT included here.

Values are read from data/mechanics.yaml for --as-of (default now). Disputed mechanics are used with a warning;
pass --override key=value with the in-game tooltip value whenever you have it (tooltip beats this script).

Examples
  python combat_bonus_calculator.py --patriotic --country-order high --mu-order high --hq-level 4 \
      --enemy-days 10 --bunker-level 5
  python combat_bonus_calculator.py --alliance-share 12            # alliance part only
  python combat_bonus_calculator.py --patriotic --government nationalist_state --as-of 2026-10-27
  python combat_bonus_calculator.py --selftest                     # replay guide 33.1 scenarios

Party ethics (--unethical, --isolationist, --pacification-level) exist only before v0.27 (2026-10-26); from v0.27
--government selects the government type that changes patriotic, Sworn Enemy, pact and bunker values.
Keys for --override: patriotic, country_order, mu_order, headquarters, alliance, defensive_pact, main_enemy,
  resistance, military_base, bunker, pacification_center, not_linked_to_capital, fighting_for_occupier, other
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wlib  # noqa: E402

PRIOS = ("low", "medium", "high")
GOVERNMENTS = ("provisional", "republic", "nationalist_state", "homeland_front", "federation", "plutocracy",
               "autocracy", "mercenary_state")
# The guide 33.1 scenarios describe the pre-v0.27 rules (ethics, single patriotic value); replay them on a date
# when those rules were in force, not "now".
SCENARIO_DATE = "2026-10-25T00:00:00Z"


def alliance_bonus(params, share_pct):
    full = float(params["full_bonus"])
    thr = float(params["full_bonus_max_share_percent"])
    slope = float(params["slope_per_point_above"])
    floor = float(params["floor"])
    if share_pct <= thr:
        return full
    return max(floor, full + slope * (share_pct - thr))


def compute(a, as_of=None):
    """Sum the battle bonuses selected by the parsed CLI arguments `a`, using the values in force at `as_of`.

    From v0.27, `a.government` picks the government-type variant of the patriotic, Sworn Enemy, pact and bunker
    values; it is reset to None (with a warning) for dates before government types exist. Ethics flags fall back
    to the normal values, with a warning, on dates after ethics were removed. Overrides replace computed parts.

    Returns:
        A dict with ``parts`` (source -> percent), ``sum``, ``total`` (sum floored at ``floor``), ``floor``,
        and de-duplicated ``warnings`` and ``notes``. Before v0.25.5 there is no floor: ``floor`` is None and
        ``total`` equals ``sum``. A bunker/base level whose bonus isn't stated for the date is left out with a warning.
    """
    parts, warnings, notes = {}, [], []

    def get(mid):
        res = wlib.resolve(mid, as_of)
        warnings.extend(res["warnings"])
        return res["value"]

    def num(mid, v):
        try:
            return float(v)
        except (TypeError, ValueError):
            warnings.append(f"{mid}: value {v!r} is not numeric for this date - part excluded")
            return None

    if a.government and get("government.types") is None:
        warnings.append(f"--government {a.government}: government types don't exist on this date (v0.27+) - ignored")
        a.government = None
    if a.government == "federation" and a.ally:
        notes.append("Federation gets +5% when fighting for an ally: add it with --override other=5")
    if a.government == "mercenary_state" and a.country_order:
        notes.append("Mercenary State doubles order damage (normal while its capital is occupied): pass the "
                     "tooltip value with --override country_order=...")
    if a.patriotic:
        if a.ally:
            warnings.append("--patriotic with --ally: patriotic applies only when your OWN country is a side")
        v = get("bonus.patriotic")
        if isinstance(v, dict):  # v0.27+: the value depends on the government type
            v = v.get(a.government, v["default"])
        v = num("bonus.patriotic", v)
        if v is not None:
            parts["patriotic"] = v
    if a.country_order:
        mid = "bonus.unethical_country_order" if a.unethical else "bonus.country_order"
        table = get(mid)
        if a.unethical and not isinstance(table, dict):
            warnings.append("--unethical: party ethics don't exist on this date - normal country order used")
            mid = "bonus.country_order"
            table = get(mid)
        parts["country_order"] = float(table[a.country_order]) if isinstance(table, dict) else num(mid, table)
    if a.mu_order:
        table = get("bonus.mu_order")
        parts["mu_order"] = float(table[a.mu_order]) if isinstance(table, dict) else num("bonus.mu_order", table)
    if a.hq_level:
        parts["headquarters"] = float(get("bonus.headquarters")[f"L{a.hq_level}"]["bonus"])
        notes.append("HQ bonus applies in any battle while the HQ is ACTIVE (oil in stock, 3h + time to next hourly tick to activate)")
    if a.alliance_share is not None:
        params = get("bonus.alliance")
        if isinstance(params, dict):
            parts["alliance"] = alliance_bonus(params, a.alliance_share)
        else:
            warnings.append(f"bonus.alliance: no formula known for this date ({params!r}) - part excluded")
    if a.pact_days is not None:
        p = get("bonus.defensive_pact")
        if a.government in p.get("not_allowed", []):
            warnings.append(f"bonus.defensive_pact: a {a.government} country can't have pacts - part excluded")
        else:
            start = float(p.get("start", p["per_day"]))
            per = float(p["federation_per_day"] if a.government == "federation" and "federation_per_day" in p
                        else p["per_day"])
            if per != float(p["per_day"]):
                notes.append("Federation pact growth: start and max are not restated by v0.27 - assumed unchanged")
            parts["defensive_pact"] = min(start + a.pact_days * per, float(p["max"]))
    if a.enemy_days is not None:
        p = get("bonus.main_enemy")
        if a.government in p.get("not_allowed", []):
            warnings.append(f"bonus.main_enemy: a {a.government} country can't have a sworn enemy - part excluded")
        else:
            rate = p[a.government] if isinstance(p.get(a.government), dict) else p
            if a.isolationist and "isolationist_per_day" in p:
                rate = {"start": p["isolationist_start"], "per_day": p["isolationist_per_day"], "max": p["max"]}
            elif a.isolationist:
                warnings.append("--isolationist: party ethics don't exist on this date - normal rate used")
            start = float(rate.get("start", rate["per_day"]))
            parts["main_enemy"] = min(start + a.enemy_days * float(rate["per_day"]), float(rate["max"]))
    if a.resistance_fill is not None:
        p = get("bonus.resistance")
        full = float(p["allies"] if a.ally else p["citizens"])
        parts["resistance"] = full * max(0.0, min(a.resistance_fill, 100.0)) / 100.0
        notes.append("resistance bonus applies to revolt attackers; bar cap grows with citizen count")
    for key, flag, mid in (("military_base", a.base_level, "bonus.base"), ("bunker", a.bunker_level, "bonus.bunker")):
        if flag:
            table = get(mid)
            if f"L{flag}" not in table:  # entries before v0.25.0 (2026-06-10) don't restate the level bonuses
                warnings.append(f"{mid}: level bonuses are not stated for this date - part excluded")
                continue
            v = float(table[f"L{flag}"])
            if key == "bunker" and a.government == "homeland_front" and not a.ally and "homeland_front_extra" in table:
                v += float(table["homeland_front_extra"])
                notes.append("Homeland Front '+5% bunker' read as +5 points on the level value (unverified)")
            if a.pact_partner:
                notes.append(f"{key}: Defensive Pact partners (not allies) get NO building bonus")
                continue
            parts[key] = v / 2 if a.ally else v
            notes.append(f"{key} requires the building to be ACTIVE (~12h activation)")
    if a.pacification_level:
        if str(get("bonus.fanatic_expansionist_pacification")).startswith("none"):
            warnings.append("--pacification-level: Fanatic Expansionist doesn't exist on this date - part excluded")
        else:
            parts["pacification_center"] = 3.0 * a.pacification_level
    if a.not_linked:
        parts["not_linked_to_capital"] = float(get("malus.not_linked_to_capital"))
    if a.for_occupier:
        parts["fighting_for_occupier"] = float(get("malus.fighting_for_occupier"))

    for ov in a.override or []:
        k, _, v = ov.partition("=")
        parts[k] = float(v)
        notes.append(f"{k} overridden with supplied value {v}")

    total = sum(parts.values())
    floor = get("bonus.total_floor")
    if floor is None:  # the -100% floor only exists since v0.25.5 (2026-08-29)
        notes.append("no total-bonus floor on this date (added in v0.25.5)")
    else:
        floor = float(floor)
        total_floored = max(total, floor)
    return {"parts": parts, "sum": total, "total": total if floor is None else total_floored, "floor": floor,
            "warnings": _dedupe(warnings), "notes": _dedupe(notes)}


def _dedupe(seq):
    out = []
    for x in seq:
        if x not in out:
            out.append(x)
    return out


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as-of", help="ISO date/datetime (UTC); default now")
    ap.add_argument("--patriotic", action="store_true", help="your own country is one of the sides")
    ap.add_argument("--ally", action="store_true", help="you fight as an ally (halves base/bunker, ally resistance rate)")
    ap.add_argument("--country-order", choices=PRIOS)
    ap.add_argument("--mu-order", choices=PRIOS)
    ap.add_argument("--unethical", action="store_true", help="country uses the Unethical ethic (before v0.27)")
    ap.add_argument("--government", choices=GOVERNMENTS, help="your country's government type (v0.27+)")
    ap.add_argument("--hq-level", type=int, choices=[1, 2, 3, 4])
    ap.add_argument("--alliance-share", type=float, help="alliance share of world development, percent")
    ap.add_argument("--pact-partner", action="store_true", help="you defend a Defensive Pact partner that is not an ally (no building bonus)")
    ap.add_argument("--pact-days", type=float, help="full days since the pact became active (bonus = 1 + days, max 10)")
    ap.add_argument("--enemy-days", type=float, help="full days since the Sworn/Main Enemy was declared")
    ap.add_argument("--isolationist", action="store_true", help="Fanatic Isolationist (before v0.27): enemy bonus starts at 5, +5/day")
    ap.add_argument("--resistance-fill", type=float, help="resistance bar fill, percent")
    ap.add_argument("--base-level", type=int, choices=[1, 2, 3, 4, 5])
    ap.add_argument("--bunker-level", type=int, choices=[1, 2, 3, 4, 5])
    ap.add_argument("--pacification-level", type=int, choices=[1, 2, 3, 4, 5], help="Fanatic Expansionist only (before v0.27)")
    ap.add_argument("--not-linked", action="store_true", help="you defend a region not linked to its capital")
    ap.add_argument("--for-occupier", action="store_true", help="you fight for a country occupying your core region")
    ap.add_argument("--override", action="append", help="key=value from the in-game tooltip")
    ap.add_argument("--selftest", action="store_true")
    return ap


def selftest():
    """Replay the guide 33.1 reference scenarios at SCENARIO_DATE, print OK/FAIL per scenario, and exit 0 only if all match."""
    cb = wlib.load_data("combat-bonuses.yaml")
    ap = build_parser()
    ok = True
    for sc in cb["reference_scenarios"]:
        argv, overrides = [], []
        ally = sc["name"].startswith("allied")
        if ally:
            argv.append("--ally")
        for k, v in sc["parts"].items():
            v = float(v)
            if k == "patriotic":
                argv.append("--patriotic")
            elif k == "country_order" and v == 15:
                argv += ["--country-order", "high"]
            elif k == "mu_order" and v == 15:
                argv += ["--mu-order", "high"]
            elif k == "unethical_country_order" and v == 30:
                argv += ["--unethical", "--country-order", "high"]
            elif k == "headquarters" and v == 20:
                argv += ["--hq-level", "4"]
            elif k == "alliance" and v == 20:
                argv += ["--alliance-share", "10"]
            elif k == "defensive_pact" and v == 10:
                argv += ["--pact-days", "10"]
            elif k == "main_enemy" and v == 10:
                argv += ["--enemy-days", "10"]
            elif k == "resistance" and v == (15 if ally else 30):
                argv += ["--resistance-fill", "100"]
            elif k == "military_base" and v == (12.5 if ally else 25):
                argv += ["--base-level", "5"]
            elif k == "bunker" and v == (12.5 if ally else 25):
                argv += ["--bunker-level", "5"]
            else:
                key = "country_order" if k == "unethical_country_order" else k
                overrides += ["--override", f"{key}={v}"]
        r = compute(ap.parse_args(argv + overrides), SCENARIO_DATE)
        status = "OK " if abs(r["sum"] - float(sc["total"])) < 1e-9 else "FAIL"
        ok &= status == "OK "
        extra = f"  (guide irregularity reproduced via override: {', '.join(o for o in overrides if o != '--override')})" if overrides else ""
        print(f"{status} {sc['name']:<36} expected {float(sc['total']):>6.1f}  got {r['sum']:>6.1f}{extra}")
    sys.exit(0 if ok else 1)


def main():
    ap = build_parser()
    a = ap.parse_args()
    if a.selftest:
        selftest()
    r = compute(a, a.as_of)
    print(f"as_of: {a.as_of or 'now'}")
    for k, v in sorted(r["parts"].items(), key=lambda kv: -kv[1]):
        print(f"  {k:<24}{v:>+8.1f}%")
    print(f"  {'-' * 32}\n  {'sum':<24}{r['sum']:>+8.1f}%")
    if r["total"] != r["sum"]:
        print(f"  {'floored total':<24}{r['total']:>+8.1f}%  (floor {r['floor']:+.0f}%)")
    for n in r["notes"]:
        print(f"NOTE: {n}")
    for w in r["warnings"]:
        print(f"WARNING: {w}")
    print("STRATEGY (Romanian community, not a game rule): totals below ~50% are usually considered inefficient.")


if __name__ == "__main__":
    main()
