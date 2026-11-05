"""Refresh the WarEra API snapshots and regenerate the generated input reference.

Usage (from the repo root):
    python .claude/skills/warera-api/scripts/refresh_spec.py          # fetch, diff, regenerate
    python .claude/skills/warera-api/scripts/refresh_spec.py --check  # fetch + diff only, write nothing

Two sources are tracked:
1. Official OpenAPI spec: https://api2.warera.io/openapi.json (the same document
   embedded in https://api2.warera.io/docs/swagger-ui-init.js). Snapshot:
   references/openapi.snapshot.json.
2. Community API explorer: https://warera.realmarijn.nl/api-explorer (a third-party
   site that documents extra procedures the official spec omits). Its HTML cards
   are parsed into references/explorer.snapshot.json.

For each source it diffs against the snapshot (added/removed procedures, changed
inputs), regenerates references/endpoint-inputs.generated.md, and lists
procedures missing from the hand-written references/endpoints-index.md so a
human/agent can add `Use when` guidance.

Stdlib only; no project dependencies required.
"""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from pathlib import Path

SPEC_URL = "https://api2.warera.io/openapi.json"
EXPLORER_URL = "https://warera.realmarijn.nl/api-explorer"
SKILL_DIR = Path(__file__).resolve().parent.parent
REF_DIR = SKILL_DIR / "references"
SNAPSHOT = REF_DIR / "openapi.snapshot.json"
EXPLORER_SNAPSHOT = REF_DIR / "explorer.snapshot.json"
GENERATED = REF_DIR / "endpoint-inputs.generated.md"
INDEX = REF_DIR / "endpoints-index.md"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 warera-api-skill-refresh"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


# ── Official spec ─────────────────────────────────────────────────────────────

def procedures(spec: dict) -> dict[str, dict]:
    """Map procedure name (e.g. 'battle.getById') -> operation object."""
    out = {}
    for path, methods in spec.get("paths", {}).items():
        for _method, op in methods.items():
            out[path.lstrip("/")] = op
    return out


def input_schema(op: dict) -> dict:
    return (
        op.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    ) or {}


def describe_type(prop: dict) -> str:
    if "anyOf" in prop:
        return " | ".join(describe_type(p) for p in prop["anyOf"])
    if "const" in prop:
        return f'"{prop["const"]}"'
    if "enum" in prop:
        return "enum(" + ", ".join(prop["enum"]) + ")"
    t = prop.get("type", "any")
    if t == "array":
        return f"array<{describe_type(prop.get('items', {}))}>"
    return t


def describe_constraints(prop: dict) -> str:
    parts = []
    for key in ("minLength", "minimum", "exclusiveMinimum", "maximum", "pattern", "default"):
        if key in prop:
            parts.append(f"{key}={prop[key]}")
    return ", ".join(parts)


def diff_spec(old: dict, new: dict) -> list[str]:
    msgs = []
    ov, nv = old.get("info", {}).get("version"), new.get("info", {}).get("version")
    if ov != nv:
        msgs.append(f"VERSION: {ov} -> {nv}")
    op, np_ = procedures(old), procedures(new)
    for name in sorted(np_.keys() - op.keys()):
        msgs.append(f"ADDED: {name} — {np_[name].get('summary')}")
    for name in sorted(op.keys() - np_.keys()):
        msgs.append(f"REMOVED: {name}")
    for name in sorted(op.keys() & np_.keys()):
        if input_schema(op[name]) != input_schema(np_[name]):
            msgs.append(f"INPUT CHANGED: {name}")
        if op[name].get("description") != np_[name].get("description"):
            msgs.append(f"DESCRIPTION CHANGED: {name}")
    return msgs


# ── Community explorer ────────────────────────────────────────────────────────

def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def parse_explorer(page: str) -> list[dict]:
    """Parse the explorer's server-rendered `api-card` blocks into dicts."""
    first_group = page.find('<div class="api-group"')
    script = page.find("<script", first_group)
    body = page[:script] if script != -1 else page
    cards = []
    for m in re.finditer(r'<div class="api-card" id="card-[^"]+"', body):
        nxt = [x for x in (body.find('<div class="api-card" id="card-', m.end()),
                           body.find('<div class="api-group" ', m.end())) if x != -1]
        card = body[m.start():min(nxt) if nxt else len(body)]
        groups = re.findall(r'<div class="api-group" data-group="([^"]+)"', body[:m.start()])
        summ = re.search(r'<span class="summary">(.*?)</span>', card, re.S)
        desc = re.search(r'<p class="api-desc">(.*?)</p>', card, re.S)
        params = []
        for pm in re.finditer(r'<div class="api-param">(.*?)(?=<div class="api-param">|<div class="api-card-footer">)', card, re.S):
            p = pm.group(1)
            label = re.search(r"<label[^>]*>(.*?)</label>", p, re.S).group(1)
            type_hint = re.search(r'<span class="type-hint">(.*?)</span>', label, re.S)
            pdesc = re.search(r'<span class="param-desc">(.*?)</span>', p, re.S)
            options = [html.unescape(o) for o in re.findall(r'<option value="([^"]+)"', p)]
            options += re.findall(r'type="checkbox"[^>]*value="([^"]*)"', p)
            default = re.search(r'<input[^>]*\svalue="([^"]+)"', p)
            params.append({
                "name": _text(re.sub(r"<span.*", "", label, flags=re.S)),
                "required": 'class="req"' in label,
                "type": _text(type_hint.group(1)) if type_hint else None,
                "description": _text(pdesc.group(1)) if pdesc else None,
                "options": options or None,
                "default": html.unescape(default.group(1)) if default else None,
            })
        cards.append({
            "procedure": _text(re.search(r'<span class="procedure">(.*?)</span>', card, re.S).group(1)),
            "group": groups[-1] if groups else None,
            "summary": _text(summ.group(1)) if summ else None,
            "description": _text(desc.group(1)) if desc else None,
            "params": params,
        })
    return cards


def diff_explorer(old: list[dict], new: list[dict]) -> list[str]:
    o = {c["procedure"]: c for c in old}
    n = {c["procedure"]: c for c in new}
    msgs = [f"EXPLORER ADDED: {p} — {n[p]['summary']}" for p in sorted(n.keys() - o.keys())]
    msgs += [f"EXPLORER REMOVED: {p}" for p in sorted(o.keys() - n.keys())]
    for p in sorted(o.keys() & n.keys()):
        if o[p]["params"] != n[p]["params"]:
            msgs.append(f"EXPLORER INPUT CHANGED: {p}")
        if o[p]["description"] != n[p]["description"]:
            msgs.append(f"EXPLORER DESCRIPTION CHANGED: {p}")
    return msgs


# ── Rendering ─────────────────────────────────────────────────────────────────

def render_generated(spec: dict, explorer: list[dict]) -> str:
    info = spec.get("info", {})
    official = procedures(spec)
    lines = [
        "# Endpoint inputs (GENERATED — do not edit by hand)",
        "",
        "Generated by `scripts/refresh_spec.py`.",
        f"- Part 1: official spec `{SPEC_URL}` — {info.get('title')} version **{info.get('version')}** ({len(official)} procedures).",
        f"- Part 2: procedures that appear **only** in the community explorer `{EXPLORER_URL}` (not in the official spec).",
        "",
        "Every procedure is called as `GET https://api2.warera.io/trpc/<procedure>?input=<url-encoded JSON>`.",
        "Both sources render them as POST with a JSON body; that body is the `input` object below.",
        "Neither source has response schemas — see the domain files for observed shapes.",
        "Unknown input keys are silently ignored by the server, so a documented-but-ignored param fails silently.",
        "",
        "# Part 1 — official spec",
        "",
    ]
    by_tag: dict[str, list[tuple[str, dict]]] = {}
    for name, op in official.items():
        by_tag.setdefault((op.get("tags") or ["untagged"])[0], []).append((name, op))
    for tag in sorted(by_tag):
        lines += [f"## {tag}", ""]
        for name, op in by_tag[tag]:
            schema = input_schema(op)
            props, required = schema.get("properties", {}), set(schema.get("required", []))
            lines.append(f"### `{name}`")
            lines.append(f"{op.get('summary', '')} — {op.get('description', '')}".strip(" —"))
            lines.append("")
            if not props:
                lines.append("_No input._ Call without `input`.")
            else:
                lines += ["| field | req | type | constraints | description |", "|---|---|---|---|---|"]
                for field, prop in props.items():
                    lines.append(
                        f"| `{field}` | {'yes' if field in required else 'no'} | {describe_type(prop)} "
                        f"| {describe_constraints(prop)} | {prop.get('description', '')} |"
                    )
            lines.append("")

    extra = [c for c in explorer if c["procedure"] not in official]
    lines += ["# Part 2 — explorer-only procedures (NOT in the official spec)", "",
              "Source is a third-party site; verify live before relying on a param. "
              "Type hints are the explorer's own wording.", ""]
    by_group: dict[str, list[dict]] = {}
    for c in extra:
        by_group.setdefault(c["group"] or "untagged", []).append(c)
    for group in sorted(by_group):
        lines += [f"## {group}", ""]
        for c in by_group[group]:
            lines.append(f"### `{c['procedure']}`")
            lines.append(f"{c['summary'] or ''} — {c['description'] or ''}".strip(" —"))
            lines.append("")
            if not c["params"]:
                lines.append("_No input._ Call without `input`.")
            else:
                lines += ["| field | req | type | default | options | description |", "|---|---|---|---|---|---|"]
                for p in c["params"]:
                    opts = ", ".join(p["options"]) if p["options"] else ""
                    lines.append(
                        f"| `{p['name']}` | {'yes' if p['required'] else 'no'} | {p['type'] or ''} "
                        f"| {p['default'] or ''} | {opts} | {p['description'] or ''} |"
                    )
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    check_only = "--check" in sys.argv

    new_spec = json.loads(fetch(SPEC_URL))
    old_spec = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
    changes = diff_spec(old_spec, new_spec) if old_spec else ["(no previous spec snapshot)"]

    try:
        new_explorer = parse_explorer(fetch(EXPLORER_URL))
    except Exception as exc:  # third-party site may be down; official spec still refreshes
        print(f"WARNING: could not fetch/parse explorer ({exc}); keeping old explorer snapshot")
        new_explorer = None
    old_explorer = json.loads(EXPLORER_SNAPSHOT.read_text(encoding="utf-8")) if EXPLORER_SNAPSHOT.exists() else []
    if new_explorer is not None:
        changes += diff_explorer(old_explorer, new_explorer) if old_explorer else ["(no previous explorer snapshot)"]
    explorer = new_explorer if new_explorer is not None else old_explorer

    print("Changes vs snapshots:" if changes else "Spec and explorer unchanged vs snapshots.")
    for msg in changes:
        print("  " + msg)

    all_procs = set(procedures(new_spec)) | {c["procedure"] for c in explorer}
    index_text = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
    missing = sorted(n for n in all_procs if f"`{n}`" not in index_text)
    if missing:
        print("Procedures missing from endpoints-index.md (add Use-when guidance):")
        for n in missing:
            print("  " + n)

    if check_only:
        return 1 if (changes or missing) else 0

    REF_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(new_spec, indent=1, ensure_ascii=False), encoding="utf-8")
    if new_explorer is not None:
        EXPLORER_SNAPSHOT.write_text(json.dumps(new_explorer, indent=1, ensure_ascii=False), encoding="utf-8")
    GENERATED.write_text(render_generated(new_spec, explorer), encoding="utf-8")
    print(f"Wrote snapshots and {GENERATED.relative_to(SKILL_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
