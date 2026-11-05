"""Shared helpers for the warera-game-expert scripts.

- load_yaml(): uses PyYAML when installed, otherwise a small parser for the YAML subset used in data/
  (block maps/lists, flow [..]/{..}, quoted/plain scalars, comments). Keep data files inside that subset.
- Mechanic registry access with time-aware resolution (resolve()).

No game formulas live here; formulas belong to the calculators and must be sourced (references/formulas.md).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = SKILL_DIR / "data"

# --------------------------------------------------------------------------- YAML loading


def load_yaml(path):
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
    except ImportError:
        data = MiniYaml(text).parse()
    return _normalize_dates(data)


def _normalize_dates(obj):
    """PyYAML turns unquoted dates into date objects; the mini parser does not. Make both return strings."""
    if isinstance(obj, dict):
        return {_normalize_dates(k): _normalize_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_dates(v) for v in obj]
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    return obj


class MiniYamlError(ValueError):
    pass


class MiniYaml:
    """Minimal YAML subset parser (no anchors, no multi-line scalars, no tags)."""

    def __init__(self, text):
        self.lines = []
        for raw in text.splitlines():
            stripped = self._strip_comment(raw)
            if not stripped.strip() or stripped.strip() == "---":
                continue
            indent = len(stripped) - len(stripped.lstrip(" "))
            self.lines.append([indent, stripped.strip()])

    @staticmethod
    def _strip_comment(line):
        out, quote, i = [], None, 0
        prev = " "
        while i < len(line):
            ch = line[i]
            if quote:
                out.append(ch)
                if quote == '"' and ch == "\\" and i + 1 < len(line):
                    out.append(line[i + 1])
                    i += 1
                elif ch == quote:
                    quote = None
            else:
                if ch in "\"'" and prev in " \t[{,:":
                    quote = ch
                    out.append(ch)
                elif ch == "#" and prev in " \t":
                    break
                else:
                    out.append(ch)
            prev = ch
            i += 1
        return "".join(out).rstrip()

    def parse(self):
        if not self.lines:
            return None
        value, i = self._node(0, self.lines[0][0])
        if i != len(self.lines):
            raise MiniYamlError(f"unexpected content at line {i}: {self.lines[i][1]!r}")
        return value

    @staticmethod
    def _is_seq(text):
        return text == "-" or text.startswith("- ")

    def _node(self, i, indent):
        if self._is_seq(self.lines[i][1]):
            return self._seq(i, indent)
        return self._map(i, indent)

    def _map(self, i, indent):
        result = {}
        while i < len(self.lines) and self.lines[i][0] == indent and not self._is_seq(self.lines[i][1]):
            key, rest = self._split_key(self.lines[i][1])
            if key is None:
                raise MiniYamlError(f"expected 'key: value', got {self.lines[i][1]!r}")
            if rest == "":
                nxt = i + 1
                if nxt < len(self.lines) and self.lines[nxt][0] > indent:
                    val, i = self._node(nxt, self.lines[nxt][0])
                elif nxt < len(self.lines) and self.lines[nxt][0] == indent and self._is_seq(self.lines[nxt][1]):
                    val, i = self._seq(nxt, indent)
                else:
                    val, i = None, nxt
            else:
                val, i = self._scalar(rest), i + 1
            result[key] = val
        return result, i

    def _seq(self, i, indent):
        result = []
        while i < len(self.lines) and self.lines[i][0] == indent and self._is_seq(self.lines[i][1]):
            text = self.lines[i][1]
            content = text[1:].strip()
            if content == "":
                nxt = i + 1
                if nxt < len(self.lines) and self.lines[nxt][0] > indent:
                    val, i = self._node(nxt, self.lines[nxt][0])
                else:
                    val, i = None, nxt
            elif content[0] not in "[{\"'" and self._split_key(content)[0] is not None:
                offset = indent + (len(text) - len(text[1:].lstrip()))
                self.lines[i] = [offset, content]
                val, i = self._map(i, offset)
            else:
                val, i = self._scalar(content), i + 1
            result.append(val)
        return result, i

    @staticmethod
    def _split_key(text):
        quote, depth = None, 0
        for idx, ch in enumerate(text):
            if quote:
                if ch == quote:
                    quote = None
                continue
            if ch in "\"'" and idx == 0:
                quote = ch
            elif ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            elif ch == ":" and depth == 0 and (idx + 1 == len(text) or text[idx + 1] == " "):
                key = text[:idx].strip()
                if len(key) >= 2 and key[0] == key[-1] and key[0] in "\"'":
                    key = key[1:-1]
                else:
                    key = MiniYaml._convert(key)
                return key, text[idx + 1 :].strip()
        return None, None

    def _scalar(self, s):
        s = s.strip()
        if s[:1] in "[{":
            val, pos = self._flow(s, 0)
            if s[pos:].strip():
                raise MiniYamlError(f"trailing data in flow value {s!r}")
            return val
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
            return self._unquote(s)
        return self._convert(s)

    @staticmethod
    def _unquote(s):
        if s[0] == "'":
            return s[1:-1].replace("''", "'")
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")

    @staticmethod
    def _convert(s):
        low = s.lower()
        if low in ("null", "~", ""):
            return None
        if low == "true":
            return True
        if low == "false":
            return False
        if re.fullmatch(r"[-+]?\d+", s):
            return int(s)
        if re.fullmatch(r"[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?", s):
            return float(s)
        return s

    def _flow(self, s, pos):
        pos = self._ws(s, pos)
        ch = s[pos]
        if ch == "[":
            out, pos = [], pos + 1
            while True:
                pos = self._ws(s, pos)
                if s[pos] == "]":
                    return out, pos + 1
                val, pos = self._flow(s, pos)
                out.append(val)
                pos = self._ws(s, pos)
                if s[pos] == ",":
                    pos += 1
                elif s[pos] != "]":
                    raise MiniYamlError(f"bad list near {s[pos:]!r}")
        if ch == "{":
            out, pos = {}, pos + 1
            while True:
                pos = self._ws(s, pos)
                if s[pos] == "}":
                    return out, pos + 1
                key, pos = self._plain_or_quoted(s, pos, stop=":")
                if s[pos] != ":":
                    raise MiniYamlError(f"expected ':' in {s!r}")
                val, pos = self._flow(s, pos + 1)
                out[key] = val
                pos = self._ws(s, pos)
                if s[pos] == ",":
                    pos += 1
                elif s[pos] != "}":
                    raise MiniYamlError(f"bad map near {s[pos:]!r}")
        return self._plain_or_quoted(s, pos, stop=",]}")

    def _plain_or_quoted(self, s, pos, stop):
        pos = self._ws(s, pos)
        if s[pos] in "\"'":
            q, end = s[pos], pos + 1
            while end < len(s):
                if s[end] == "\\" and q == '"':
                    end += 2
                    continue
                if s[end] == q:
                    break
                end += 1
            return self._unquote(s[pos : end + 1]), end + 1
        end = pos
        while end < len(s) and s[end] not in stop:
            if stop == ":" and s[end] == ":" :
                break
            end += 1
        return self._convert(s[pos:end].strip()), end

    @staticmethod
    def _ws(s, pos):
        while pos < len(s) and s[pos] in " \t":
            pos += 1
        if pos >= len(s):
            raise MiniYamlError(f"unexpected end of flow value {s!r}")
        return pos


# --------------------------------------------------------------------------- dates


def parse_dt(value):
    """Parse an ISO date/datetime string into an aware UTC datetime. None stays None."""
    if value in (None, ""):
        return None
    if isinstance(value, _dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=_dt.timezone.utc)
    s = str(value).strip().replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        s += "T00:00:00+00:00"
    d = _dt.datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def utcnow():
    return _dt.datetime.now(_dt.timezone.utc)


# --------------------------------------------------------------------------- mechanics registry

_REGISTRY = None


def load_mechanics():
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = load_yaml(DATA_DIR / "mechanics.yaml")
    return _REGISTRY


def mechanics_by_id():
    return {m["id"]: m for m in load_mechanics().get("mechanics", [])}


ACTIVE = ("current", "disputed")


def resolve(mechanic_id, as_of=None):
    """Return {'value', 'entry', 'warnings'} for the value in force at `as_of` (default: now).

    Rules (see references/versioned-mechanics.md):
    - current/disputed entries without effective_from implicitly start where the latest closed
      historical window ends;
    - scheduled entries apply only once effective_from has passed;
    - historical entries apply only inside a known window; if an earlier value exists but its
      window is unknown, the answer for dates before the current entry's verification is flagged.
    """
    mech = mechanics_by_id().get(mechanic_id)
    if mech is None:
        raise KeyError(f"unknown mechanic id: {mechanic_id}")
    when = parse_dt(as_of) if as_of else utcnow()
    entries = mech.get("values", [])
    warnings = []

    closed_ends = [parse_dt(e.get("effective_to")) for e in entries if e.get("status") in ("historical", "deprecated") and e.get("effective_to")]
    implicit_from = max(closed_ends) if closed_ends else None

    active_entries = [e for e in entries if e.get("status") in ACTIVE]
    verified_dates = [parse_dt(e.get("first_observed") or e.get("last_verified")) for e in active_entries]
    verified = min((d for d in verified_dates if d), default=None)

    candidates = []
    for e in entries:
        st = e.get("status")
        ef, et = parse_dt(e.get("effective_from")), parse_dt(e.get("effective_to"))
        if st in ACTIVE:
            start = ef or implicit_from
            if start and when < start:
                continue
            if et and when >= et:
                continue
            candidates.append((start, e))
        elif st == "scheduled":
            if ef and when >= ef and (not et or when < et):
                candidates.append((ef, e))
        elif st in ("historical", "deprecated"):
            if et and when < et and (not ef or when >= ef):
                candidates.append((ef, e))
            elif ef and not et and when >= ef and (verified is None or when < verified):
                # open-ended history: known start, unknown end -> the best answer before the current value was verified
                candidates.append((ef, e))

    if not candidates:
        return {"value": None, "entry": None, "warnings": [f"{mechanic_id}: no value known for {when.isoformat()}"]}

    # latest start wins; on equal start an open-ended historical entry (known to have applied) beats an
    # active entry whose start is only implied
    candidates.sort(key=lambda t: (t[0] or _dt.datetime.min.replace(tzinfo=_dt.timezone.utc),
                                   1 if t[1].get("status") in ("historical", "deprecated") else 0))
    entry = candidates[-1][1]
    if entry.get("status") in ("historical", "deprecated") and not entry.get("effective_to"):
        newer = "; ".join(str(e.get("value")) for e in active_entries)
        warnings.append(
            f"{mechanic_id}: {entry.get('value')} applied from {entry.get('effective_from')}, but was replaced by "
            f"[{newer}] at an unknown date before {verified.date() if verified else 'today'} - the answer for {when.date()} is uncertain"
        )

    if entry.get("status") == "disputed":
        alts = "; ".join(f"{c.get('source')}={c.get('value')}" for c in mech.get("conflicts", []))
        warnings.append(f"{mechanic_id} is DISPUTED (using {entry.get('source')}={entry.get('value')}; alternatives: {alts})")
    undated_history = [e for e in entries if e.get("status") in ("historical", "deprecated") and not e.get("effective_to") and e is not entry]
    if undated_history and verified and when < verified and entry.get("status") in ACTIVE:
        olds = "; ".join(str(e.get("value")) for e in undated_history)
        warnings.append(
            f"{mechanic_id}: earlier value(s) [{olds}] existed with unknown end date; "
            f"the value for {when.date()} is not certain (current value verified {verified.date()})"
        )
    if entry.get("confidence") == "low":
        warnings.append(f"{mechanic_id}: low-confidence value")
    return {"value": entry.get("value"), "entry": entry, "warnings": warnings}


def value(mechanic_id, as_of=None):
    return resolve(mechanic_id, as_of)["value"]


def load_data(name):
    return load_yaml(DATA_DIR / name)


def dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=True, default=str)


def pct_to_fraction(p):
    """Canonical percent = points (37 -> 0.37)."""
    return None if p is None else float(p) / 100.0
