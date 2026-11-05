#!/usr/bin/env python3
"""Validate data/mechanics.yaml and cross-file references.

Checks
- required metadata on every mechanic and value entry; enum values (authority/status/confidence)
- duplicate mechanic ids and source ids; unknown source ids
- invalid dates and effective_from >= effective_to
- scheduled entries without effective_from
- more than one ACTIVE (current/disputed) value at the same instant; overlapping known windows
- disputed mechanics without a conflicts list; conflicts citing unknown sources
- authority vs id prefix (ro.* must be strategy/policy, obs.* must be observation)
- mechanic_id references in other data files exist
- combat-bonuses.yaml reference scenarios add up to their stated totals
- duplicate keys inside one mapping of any data file (YAML would silently keep the last one)

Usage:  python validate_mechanics.py [--strict] [--registry draft.yaml]   (--strict: warnings also fail)
Exit code 1 on errors.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wlib  # noqa: E402

AUTHORITIES = {"game_mechanic", "community_strategy", "romanian_policy", "community_observation"}
STATUSES = {"current", "disputed", "scheduled", "historical", "deprecated"}
CONFIDENCE = {"high", "medium", "low"}
REQUIRED_MECH = ("id", "name", "category", "authority", "unit", "values")
REQUIRED_VALUE = ("value", "status", "source", "confidence")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--registry", help="validate another registry file (e.g. a draft) instead of data/mechanics.yaml")
    args = ap.parse_args()
    if args.registry:
        wlib._REGISTRY = wlib.load_yaml(args.registry)

    errors, warnings = [], []
    reg = wlib.load_mechanics()

    for key in ("schema_version", "sources", "mechanics"):
        if key not in reg:
            errors.append(f"mechanics.yaml: missing top-level key '{key}'")

    source_ids = set()
    for s in reg.get("sources", []):
        sid = s.get("id")
        if sid in source_ids:
            errors.append(f"duplicate source id {sid}")
        source_ids.add(sid)
        for k in ("title", "date", "priority"):
            if k not in s:
                warnings.append(f"source {sid}: missing '{k}'")

    seen = set()
    for m in reg.get("mechanics", []):
        mid = m.get("id", "<no id>")
        for k in REQUIRED_MECH:
            if k not in m or m[k] in (None, "", []):
                errors.append(f"{mid}: missing '{k}'")
        if mid in seen:
            errors.append(f"duplicate mechanic id {mid}")
        seen.add(mid)
        auth = m.get("authority")
        if auth not in AUTHORITIES:
            errors.append(f"{mid}: invalid authority {auth!r}")
        if mid.startswith("ro.") and auth not in ("community_strategy", "romanian_policy"):
            errors.append(f"{mid}: ro.* ids must be community_strategy or romanian_policy, got {auth}")
        if mid.startswith("obs.") and auth != "community_observation":
            errors.append(f"{mid}: obs.* ids must be community_observation")
        if auth in ("community_strategy", "romanian_policy") and not mid.startswith("ro."):
            warnings.append(f"{mid}: strategy/policy entries should use the ro.* prefix")

        windows = []
        active_undated = 0
        for idx, e in enumerate(m.get("values") or []):
            where = f"{mid}.values[{idx}]"
            for k in REQUIRED_VALUE:
                if k not in e:
                    errors.append(f"{where}: missing '{k}'")
            st = e.get("status")
            if st not in STATUSES:
                errors.append(f"{where}: invalid status {st!r}")
            if e.get("confidence") not in CONFIDENCE:
                errors.append(f"{where}: invalid confidence {e.get('confidence')!r}")
            srcs = e.get("source") or []
            if isinstance(srcs, str):
                srcs = [srcs]
            for s in srcs:
                if s not in source_ids:
                    errors.append(f"{where}: unknown source {s!r}")
            if st in ("current", "disputed") and not e.get("last_verified"):
                warnings.append(f"{where}: active value without last_verified")
            try:
                ef = wlib.parse_dt(e.get("effective_from"))
                et = wlib.parse_dt(e.get("effective_to"))
                for k in ("last_verified", "first_observed"):
                    wlib.parse_dt(e.get(k))
            except ValueError as exc:
                errors.append(f"{where}: bad date ({exc})")
                continue
            if ef and et and ef >= et:
                errors.append(f"{where}: effective_from {ef.date()} >= effective_to {et.date()}")
            if st == "scheduled" and not ef:
                errors.append(f"{where}: scheduled value needs effective_from")
            if st in ("historical", "deprecated") and not et:
                warnings.append(f"{where}: {st} value without effective_to (time queries before the current value will be flagged uncertain)")
            if st in ("current", "disputed"):
                if not ef and not et:
                    active_undated += 1
                windows.append((ef, et, idx))
            elif st == "scheduled" or (st in ("historical", "deprecated") and et):
                windows.append((ef, et, idx))
        if active_undated > 1:
            errors.append(f"{mid}: {active_undated} simultaneous active (current/disputed) values")
        _check_overlaps(mid, windows, errors)

        if any(e.get("status") == "disputed" for e in m.get("values") or []) and not m.get("conflicts"):
            warnings.append(f"{mid}: disputed but no conflicts listed")
        for c in m.get("conflicts") or []:
            if c.get("source") not in source_ids:
                errors.append(f"{mid}: conflict cites unknown source {c.get('source')!r}")
            if "note" not in c:
                warnings.append(f"{mid}: conflict without a note")

    # cross-file mechanic_id references
    ids = seen
    for fname in ("cooldowns.yaml", "combat-bonuses.yaml"):
        data = wlib.load_data(fname)
        for ref in _find_key(data, "mechanic_id"):
            if ref not in ids:
                errors.append(f"{fname}: mechanic_id {ref!r} not in mechanics.yaml")
    cb = wlib.load_data("combat-bonuses.yaml")
    if cb.get("floor_mechanic_id") not in ids:
        errors.append("combat-bonuses.yaml: floor_mechanic_id unknown")
    for sc in cb.get("reference_scenarios", []):
        total = sum(float(v) for v in sc["parts"].values())
        if abs(total - float(sc["total"])) > 1e-9:
            errors.append(f"combat-bonuses.yaml scenario {sc['name']}: parts sum {total} != total {sc['total']}")

    # duplicate keys (text scan; both PyYAML and the mini parser keep the last value silently)
    for path in sorted(wlib.DATA_DIR.glob("*.yaml")):
        for lineno, key in _duplicate_keys(path):
            errors.append(f"{path.name}:{lineno}: duplicate key '{key}' in the same mapping")

    # resolution smoke test: every mechanic must resolve "now" unless it only has history
    for mid in ids:
        r = wlib.resolve(mid)
        if r["entry"] is None:
            warnings.append(f"{mid}: no value in force now")

    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR:   {e}")
    print(f"\n{len(ids)} mechanics, {len(source_ids)} sources: {len(errors)} error(s), {len(warnings)} warning(s)")
    if errors or (args.strict and warnings):
        sys.exit(1)


def _check_overlaps(mid, windows, errors):
    known = [(ef, et, i) for ef, et, i in windows if ef or et]
    for a in range(len(known)):
        for b in range(a + 1, len(known)):
            ef1, et1, i1 = known[a]
            ef2, et2, i2 = known[b]
            lo = max(x for x in (ef1, ef2) if x) if (ef1 or ef2) else None
            hi_candidates = [x for x in (et1, et2) if x]
            hi = min(hi_candidates) if hi_candidates else None
            starts_known = ef1 is not None and ef2 is not None
            ends_known = et1 is not None and et2 is not None
            if starts_known and ends_known and lo < hi:
                errors.append(f"{mid}: values[{i1}] and values[{i2}] have overlapping windows")


def _duplicate_keys(path):
    import re
    stack = {}
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r"^(\s*)(- )?([A-Za-z_][\w.]*):(\s|$)", line)
        if not m or line.lstrip().startswith("#"):
            continue
        ind = len(m.group(1)) + (2 if m.group(2) else 0)
        stack = {k: v for k, v in stack.items() if k < ind or (k == ind and not m.group(2))}
        if m.group(2):
            stack[ind] = set()
        keys = stack.setdefault(ind, set())
        if m.group(3) in keys:
            yield i, m.group(3)
        keys.add(m.group(3))


def _find_key(obj, key):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            else:
                yield from _find_key(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from _find_key(v, key)


if __name__ == "__main__":
    main()
