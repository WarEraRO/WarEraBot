"""Diff the live WarEra game config against the skill's snapshot.

Usage (from the repo root):
    python .claude/skills/warera-config/scripts/check_config.py           # fetch + diff, write nothing
    python .claude/skills/warera-config/scripts/check_config.py --update  # fetch + diff, then overwrite the snapshot

Source: https://api2.warera.io/trpc/gameConfig.getGameConfig (no API key needed).
Snapshot: references/game-config.snapshot.json.

If anything changed, update references/config.md (and the quick-reference table in
SKILL.md) to match, then re-run with --update. Exit code 1 means differences were found.

Stdlib only; no project dependencies required.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

URL = "https://api2.warera.io/trpc/gameConfig.getGameConfig"
SKILL_DIR = Path(__file__).resolve().parent.parent
SNAPSHOT = SKILL_DIR / "references" / "game-config.snapshot.json"
# Client-rendering noise, not game rules.
IGNORED_KEYS = {"IconComponent", "iconImg", "fieldsToPopulate"}


def fetch() -> dict:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 warera-config-skill-check"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))["result"]["data"]


def flatten(obj, prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in IGNORED_KEYS:
                continue
            out.update(flatten(value, f"{prefix}.{key}" if prefix else key))
    else:
        out[prefix] = obj
    return out


def main() -> int:
    live = fetch()
    old = flatten(json.loads(SNAPSHOT.read_text(encoding="utf-8")))
    new = flatten(live)

    added = sorted(new.keys() - old.keys())
    removed = sorted(old.keys() - new.keys())
    changed = sorted(k for k in new.keys() & old.keys() if new[k] != old[k])

    for k in added:
        print(f"+ {k} = {json.dumps(new[k])}")
    for k in removed:
        print(f"- {k} (was {json.dumps(old[k])})")
    for k in changed:
        print(f"~ {k}: {json.dumps(old[k])} -> {json.dumps(new[k])}")

    if not (added or removed or changed):
        print("No differences: the snapshot matches the live game config.")
        return 0

    print(f"\n{len(added)} added, {len(removed)} removed, {len(changed)} changed.")
    if "--update" in sys.argv:
        SNAPSHOT.write_text(json.dumps(live, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"Snapshot updated: {SNAPSHOT}")
        print("Now update references/config.md and SKILL.md to match.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
