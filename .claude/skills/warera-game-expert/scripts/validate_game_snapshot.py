#!/usr/bin/env python3
"""Validate a WarEra game-state snapshot (script/API output) against data/snapshot-schema.yaml.

It NEVER silently corrects data. It reports:
  ERROR    impossible values (hard bounds, wrong types, missing required fields)
  WARNING  suspicious values (soft bounds, cross-entity inconsistencies, disputed-mechanic ranges)
  INFO     unknown fields, percentage normalizations, derived values

Percentages: canonical unit is percentage points (37 = 37%). A value with 0 < |v| <= 1 in a percent field
is reported as a probable fraction and converted ONLY in the --normalized-out copy, with an INFO line.

Usage
  python validate_game_snapshot.py snapshot.json [--normalized-out normalized.json] [--json]
Snapshot shape: {"as_of": "...", "player": {...}, "companies": [...], "regions": [...], ...}
Exit code 1 if any ERROR.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wlib  # noqa: E402

TYPES = {"string": str, "int": int, "number": (int, float), "bool": bool, "object": dict, "list": list}


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, where, msg):
        self.items.append({"level": level, "where": where, "message": msg})

    def count(self, level):
        return sum(1 for i in self.items if i["level"] == level)


def check_field(rep, where, name, spec, value, record_norm):
    t = spec.get("type")
    if value is None:
        if spec.get("required"):
            rep.add("ERROR", where, f"{name} is required but null")
        return value
    if t == "datetime":
        try:
            wlib.parse_dt(value)
        except (ValueError, TypeError):
            rep.add("ERROR", where, f"{name}={value!r} is not an ISO datetime")
        return value
    py = TYPES.get(t)
    if py and (not isinstance(value, py) or (t in ("int", "number") and isinstance(value, bool))):
        if t == "int" and isinstance(value, float) and value.is_integer():
            rep.add("INFO", where, f"{name}={value} given as float, integer expected")
        else:
            rep.add("ERROR", where, f"{name}={value!r} has type {type(value).__name__}, expected {t}")
            return value
    if "enum" in spec and value not in spec["enum"]:
        rep.add("ERROR", where, f"{name}={value!r} not in {spec['enum']}")
    if t in ("int", "number"):
        v = float(value)
        if spec.get("unit") == "percent" and 0 < abs(v) <= 1 and (spec.get("max", 100) > 1):
            rep.add("INFO", where, f"{name}={value} looks like a fraction; canonical is percent points -> {v * 100:g} (only in normalized copy)")
            record_norm(name, v * 100)
            v = v * 100
        if "min" in spec and v < spec["min"]:
            rep.add("ERROR", where, f"{name}={value} below hard minimum {spec['min']}")
        if "max" in spec and v > spec["max"]:
            rep.add("ERROR", where, f"{name}={value} above hard maximum {spec['max']}")
        if "warn_min" in spec and v < spec["warn_min"]:
            rep.add("WARNING", where, f"{name}={v:g} below expected {spec['warn_min']} ({spec.get('note', 'suspicious')})")
        if "warn_max" in spec and v > spec["warn_max"]:
            rep.add("WARNING", where, f"{name}={v:g} above expected {spec['warn_max']} ({spec.get('note', 'suspicious')})")
    if spec.get("derived"):
        rep.add("INFO", where, f"{name} is a derived field - recompute it rather than trusting the supplied value")
    return value


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("snapshot")
    ap.add_argument("--normalized-out")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    a = ap.parse_args()

    schema = wlib.load_data("snapshot-schema.yaml")["entities"]
    plural = {spec.get("plural"): name for name, spec in schema.items() if spec.get("plural")}
    snap = json.loads(Path(a.snapshot).read_text(encoding="utf-8"))
    norm = copy.deepcopy(snap)
    rep = Report()

    as_of = snap.get("as_of")
    if not as_of:
        rep.add("WARNING", "snapshot", "no as_of timestamp: volatile fields cannot be dated; time-dependent mechanics will use 'now'")
    else:
        try:
            wlib.parse_dt(as_of)
        except ValueError:
            rep.add("ERROR", "snapshot", f"as_of={as_of!r} is not ISO")
            as_of = None

    index = {}
    for key, payload in snap.items():
        if key in ("as_of", "game_version", "source", "notes"):
            continue
        if key in schema:
            ent, records, is_list = key, [payload], False
        elif key in plural:
            ent, records, is_list = plural[key], payload, True
            if not isinstance(records, list):
                rep.add("ERROR", key, "expected a list")
                continue
        else:
            rep.add("INFO", key, "unknown top-level key (not in snapshot-schema.yaml) - ignored")
            continue
        fields = schema[ent]["fields"]
        for i, rec in enumerate(records):
            where = f"{key}[{i}]" if is_list else key
            if not isinstance(rec, dict):
                rep.add("ERROR", where, "record is not an object")
                continue
            target = norm[key][i] if is_list else norm[key]

            def record_norm(fname, v, target=target):
                target[fname] = v

            for fname, spec in fields.items():
                if fname not in rec:
                    if spec.get("required"):
                        rep.add("ERROR", where, f"missing required field {fname}")
                    continue
                check_field(rep, where, fname, spec, rec[fname], record_norm)
            for fname in rec:
                if fname not in fields:
                    rep.add("INFO", where, f"unknown field {fname!r}")
            index.setdefault(ent, []).append((where, rec))

    cross_checks(rep, index, as_of)

    if a.normalized_out:
        Path(a.normalized_out).write_text(json.dumps(norm, indent=2), encoding="utf-8")
        rep.add("INFO", "snapshot", f"normalized copy written to {a.normalized_out}")

    if a.json:
        print(wlib.dump({"errors": rep.count("ERROR"), "warnings": rep.count("WARNING"), "items": rep.items}))
    else:
        for it in rep.items:
            print(f"{it['level']:<8}{it['where']}: {it['message']}")
        print(f"\n{rep.count('ERROR')} error(s), {rep.count('WARNING')} warning(s), {rep.count('INFO')} info")
    sys.exit(1 if rep.count("ERROR") else 0)


def _pct(v):
    if v is None:
        return None
    v = float(v)
    return v * 100 if 0 < abs(v) <= 1 else v


def cross_checks(rep, index, as_of):
    skills = wlib.load_data("progression-values.yaml")["skills"]
    storage = wlib.value("company.storage_levels", as_of)
    region_ids = {r.get("id") for _, r in index.get("region", [])}
    regions = {r.get("id"): r for _, r in index.get("region", [])}

    for where, p in index.get("player", []):
        lvl = p.get("level")
        for sk, sl in (p.get("skills") or {}).items():
            spec = skills.get(sk)
            if spec is None:
                rep.add("INFO", where, f"skills.{sk}: unknown skill code")
                continue
            if isinstance(sl, (int, float)):
                if sl < 0:
                    rep.add("ERROR", where, f"skills.{sk}={sl} negative")
                elif sl > 10:
                    rep.add("WARNING", where, f"skills.{sk}={sl} above normal max 10 - only possible with Prestige Points (prestige_level={p.get('prestige_level')})")
                if lvl and sl > 0 and lvl < spec["unlock"]:
                    rep.add("WARNING", where, f"skills.{sk} > 0 but player level {lvl} < unlock level {spec['unlock']}")
        if lvl and p.get("skills"):
            spent = sum(sum(range(1, int(v) + 1)) for v in p["skills"].values() if isinstance(v, (int, float)) and 0 < v <= 10)
            if spent > lvl * 4:
                rep.add("WARNING", where, f"skills cost {spent} points but level {lvl} grants only {lvl * 4} (prestige bonus levels not counted)")
        if p.get("pill_consumed_at"):
            try:
                t0 = wlib.parse_dt(p["pill_consumed_at"])
                now = wlib.parse_dt(as_of) if as_of else wlib.utcnow()
                h = (now - t0).total_seconds() / 3600
                pill = wlib.value("consumables.pill", as_of)
                buff, debuff = float(pill["buff_hours"]), float(pill["debuff_hours"])
                phase = "buff" if 0 <= h < buff else "debuff" if buff <= h < buff + debuff else "none"
                rep.add("INFO", where, f"derived pill_phase={phase} ({h:.1f} h since pill)")
                if p.get("pill_phase") and p["pill_phase"] != phase:
                    rep.add("WARNING", where, f"supplied pill_phase={p['pill_phase']} disagrees with derived {phase}")
            except (ValueError, TypeError):
                pass

    for where, c in index.get("company", []):
        sl = c.get("storage_level")
        if isinstance(sl, int) and f"L{sl}" in storage and c.get("stored_pp") is not None:
            cap = storage[f"L{sl}"]["capacity"]
            if c["stored_pp"] > cap:
                rep.add("ERROR", where, f"stored_pp {c['stored_pp']} exceeds storage L{sl} capacity {cap}")
            elif c["stored_pp"] >= cap:
                rep.add("WARNING", where, "storage FULL - production (engine, self-work, employees) is stopped")
        if region_ids and c.get("region_id") and c["region_id"] not in region_ids:
            rep.add("INFO", where, f"region_id {c['region_id']} not present in snapshot regions (cannot cross-check bonus)")
        r = regions.get(c.get("region_id"))
        if r and r.get("deposit_item") and r.get("deposit_item") == c.get("product") and r.get("deposit_bonus_percent") is not None:
            rep.add("INFO", where, f"deposit for {c['product']} in region: +{_pct(r['deposit_bonus_percent']):g}% (live value overrides generic 20-40% / 30% reference)")

    for where, b in index.get("battle", []):
        for side in ("attacker", "defender"):
            t = b.get(f"terrain_{side}")
            if isinstance(t, (int, float)) and t >= 300 and not b.get("ended_at"):
                rep.add("WARNING", where, f"terrain_{side}={t} reached 300 but round/battle not marked ended")
        ra, rd = b.get("rounds_won_attacker"), b.get("rounds_won_defender")
        if isinstance(ra, int) and isinstance(rd, int) and ra >= 2 and rd >= 2:
            rep.add("ERROR", where, "both sides have 2 rounds won - impossible")
        if b.get("round") and isinstance(b["round"], int) and b["round"] > 3:
            rep.add("WARNING", where, f"round={b['round']} > 3: guide says best-of-three, config maxRounds=15 (disputed mechanic battle.max_rounds)")

    for where, o in index.get("battle_order", []):
        if o.get("rank") and o.get("priority"):
            rep.add("INFO", where, "remember: rank (#) is display order only; bonus comes from priority")

    for where, al in index.get("alliance", []):
        s = al.get("world_development_share_percent")
        if s is not None and _pct(s) > 10:
            rep.add("WARNING", where, f"alliance share {_pct(s):g}% > 10%: alliance bonus is reduced (disputed curve, see bonus.alliance)")

    for where, t in index.get("transaction", []):
        if t.get("price") and t.get("reference_price"):
            ratio = float(t["price"]) / float(t["reference_price"]) if float(t["reference_price"]) else None
            if ratio is not None and (ratio < 0.5 or ratio > 2):
                rep.add("WARNING", where, f"price is {ratio:.2f}x the reference market price - possible manipulated trade (review, do not conclude)")


if __name__ == "__main__":
    main()
