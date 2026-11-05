#!/usr/bin/env python3
"""WarEra progression helpers (references/formulas.md F-SKILL-COST, F-REROLL, F-PRESTIGE-*, F-RESPEC, F-SEATS, F-COMPANY-COST).

Subcommands
  skill-cost       points to raise one skill from level A to B
  reroll           cost of the next k rerolls in one mission category
  level            level, skill points and progress for a total-XP figure (wiki XP table)
  prestige         XP and level after Prestige and the resulting XP bonus
  prestige-points  Prestige Points needed to stack k bonus levels on the same skill
  respec           money cost of a full skill reset
  company          concrete cost and Companies skill needed for the k-th company
  seats            Congress seats for an active population
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wlib  # noqa: E402


def cmd_skill_cost(a):
    if not (0 <= a.frm <= a.to <= 10):
        raise SystemExit("levels must satisfy 0 <= from <= to <= 10 (above 10 needs Prestige Points)")
    pts = sum(range(a.frm + 1, a.to + 1))
    print(wlib.dump({"from": a.frm, "to": a.to, "skill_points": pts, "player_levels_equivalent": round(pts / 4, 2)}))


def cmd_reroll(a):
    table = wlib.load_data("progression-values.yaml")["missions"]["reroll_cost_by_index"]
    costs, warn = [], None
    for n in range(a.done, a.done + a.count):
        if n < len(table):
            costs.append(table[n])
        else:
            warn = f"reroll index {n} is beyond the documented table (0..{len(table) - 1}); cost unknown"
            break
    print(wlib.dump({"already_done_this_period": a.done, "next_costs": costs, "total": sum(costs), "warning": warn,
                     "rule": "first reroll per category per period is free; the k-th costs 2*(k-1); rerolling can return the same mission"}))


def xp_table():
    return wlib.load_data("progression-values.yaml")["xp_table"]["levels"]


def level_for_xp(total_xp):
    rows = xp_table()
    cur = max((r for r in rows if r["cumulative_xp"] <= total_xp), key=lambda r: r["level"])
    nxt = next((r for r in rows if r["level"] == cur["level"] + 1), None)
    return cur, nxt


def cmd_level(a):
    cur, nxt = level_for_xp(a.total_xp)
    out = {"total_xp": a.total_xp, "level": cur["level"], "total_skill_points": cur["total_skill_points"]}
    if nxt:
        out["xp_into_level"] = a.total_xp - cur["cumulative_xp"]
        out["xp_to_next_level"] = nxt["cumulative_xp"] - a.total_xp
    else:
        out["xp_above_cap"] = a.total_xp - cur["cumulative_xp"]
    print(wlib.dump(out))


def cmd_prestige(a):
    xp_pen = wlib.value("prestige.xp_penalty")
    after = a.total_xp - xp_pen
    cur, nxt = level_for_xp(after)
    new_p = a.prestige_level + 1
    print(wlib.dump({"total_xp_before": a.total_xp, "xp_after": after, "level_after": cur["level"],
                     "skill_points_after": cur["total_skill_points"],
                     "new_prestige_level": new_p, "xp_bonus_pct_after": 50 + 10 * (new_p - 1),
                     "eligible": a.level >= 50 if a.level else "check: needs level 50 (86,600 XP)",
                     "grants": ["1 Prestige Point", "free full respec", "Prestige badge"],
                     "note": "XP bonus is inactive while at level 50; lifetime XP is kept. Level from the wiki XP table."}))


def cmd_prestige_points(a):
    costs = [2 ** (k - 1) for k in range(1, a.levels + 1)]
    print(wlib.dump({"bonus_levels_on_one_skill": a.levels, "costs": costs, "total_points": sum(costs),
                     "rule": "cost doubles for each further bonus level on the same skill (guide 1/2/4/8; wiki x2 continues)"}))


def cmd_respec(a):
    per_point = float(wlib.value("respec.cost_per_skill_point"))
    points = a.points if a.points is not None else a.level * 4
    print(wlib.dump({"skill_points": points, "cost_money": points * per_point, "cooldown_days": wlib.value("respec.cooldown_days"),
                     "free_alternatives": ["Prestige grants a free full respec", "occasional free resets after major updates (never plan on them)"]}))


def cmd_company(a):
    k = a.k
    cost = 0 if k == 1 else 100 + 50 * (k - 2)
    skill = max(0, k - 2)
    print(wlib.dump({"company_number": k, "concrete_cost": cost, "companies_skill_level_needed": skill,
                     "cumulative_skill_points_for_that_level": skill * (skill + 1) // 2,
                     "note": "companies above the limit are randomly deactivated, not deleted"}))


def cmd_seats(a):
    seats = min(50, max(5, math.ceil(a.active / 20) + 2))
    print(wlib.dump({"active_population": a.active, "congress_seats": seats}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("skill-cost"); p.add_argument("--from", dest="frm", type=int, default=0); p.add_argument("--to", type=int, required=True); p.set_defaults(fn=cmd_skill_cost)
    p = sub.add_parser("reroll"); p.add_argument("--done", type=int, default=0, help="rerolls already used this period in this category"); p.add_argument("--count", type=int, default=1); p.set_defaults(fn=cmd_reroll)
    p = sub.add_parser("level"); p.add_argument("--total-xp", type=float, required=True); p.set_defaults(fn=cmd_level)
    p = sub.add_parser("prestige"); p.add_argument("--total-xp", type=float, required=True); p.add_argument("--prestige-level", type=int, default=0); p.add_argument("--level", type=int); p.set_defaults(fn=cmd_prestige)
    p = sub.add_parser("prestige-points"); p.add_argument("--levels", type=int, required=True); p.set_defaults(fn=cmd_prestige_points)
    p = sub.add_parser("respec"); p.add_argument("--points", type=int); p.add_argument("--level", type=int, default=0); p.set_defaults(fn=cmd_respec)
    p = sub.add_parser("company"); p.add_argument("--k", type=int, required=True); p.set_defaults(fn=cmd_company)
    p = sub.add_parser("seats"); p.add_argument("--active", type=int, required=True); p.set_defaults(fn=cmd_seats)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
