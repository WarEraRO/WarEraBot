"""Probe WarEra tRPC query procedures live, with or without the bot's API key.

Usage (from the repo root):
    python -I .claude/skills/warera-api/scripts/probe.py employee.getCompanyRoster '{"companyId": "<id>"}'
    python -I .claude/skills/warera-api/scripts/probe.py gameStat.getPpMoneyValue --anon
    python -I .claude/skills/warera-api/scripts/probe.py article.getPinnedArticles --chars 300

Each call is printed as ``### <procedure> <input> auth=<bool> -> <HTTP status>``
followed by the unwrapped ``result.data`` (or the error envelope), truncated to
``--chars``. Several procedures can be probed in one run by repeating
``<procedure> [json-input]`` pairs; calls are spaced about 1.1 s apart.

The key is read from ``WARERA_API_KEY`` in ``.env`` (or ``--env``) and is never
printed. Only GET requests are sent, and procedure names that don't start with
``get`` or ``search`` are refused unless ``--allow-name`` is given, as a guard
against calling a mutation (this bot is read-only; see client-discovered.md).

Stdlib only. Exit status: 0 when every call answered 2xx, 1 otherwise, 2 on
bad arguments.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api2.warera.io/trpc/"
QUERY_PREFIXES = ("get", "search")


def read_key(env_path: str) -> str | None:
    """Return ``WARERA_API_KEY`` from a dotenv file, or None if absent or unreadable."""
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("WARERA_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    except OSError:
        return None
    return None


def call(procedure: str, input_data: object | None, key: str | None) -> tuple[int, object]:
    """GET one procedure and return ``(HTTP status, parsed JSON or raw body)``.

    Args:
        procedure: ``router.procedure`` name.
        input_data: Value sent as the ``input`` query parameter, or None to send
            no input (needed for ``z.void()`` procedures such as
            ``gameStat.getPpMoneyValue``, which reject ``{}``).
        key: API key for the ``X-API-Key`` header, or None for an anonymous call.
    """
    url = BASE_URL + procedure
    if input_data is not None:
        url += "?input=" + urllib.parse.quote(json.dumps(input_data))
    # Plain urllib without a User-Agent gets 403 from the API.
    headers = {"User-Agent": "WarEraBot-probe"}
    if key:
        headers["X-API-Key"] = key
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
            status, body = r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read().decode("utf-8")
    try:
        return status, json.loads(body)
    except ValueError:
        return status, body


def main() -> int:
    """Parse arguments, probe each procedure in order and print the results."""
    # `python -I` ignores PYTHONIOENCODING; API data contains emoji that cp1252 can't print.
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Probe WarEra tRPC query procedures (GET only).")
    parser.add_argument("calls", nargs="+", help="<procedure> [json-input] pairs")
    parser.add_argument("--anon", action="store_true", help="send no API key")
    parser.add_argument("--env", default=".env", help="dotenv file holding WARERA_API_KEY")
    parser.add_argument("--chars", type=int, default=1500, help="max characters printed per result")
    parser.add_argument("--allow-name", action="store_true",
                        help="allow procedure names without a get/search prefix (still GET only)")
    args = parser.parse_args()

    pairs: list[tuple[str, object | None]] = []
    tokens = list(args.calls)
    while tokens:
        procedure = tokens.pop(0)
        input_data = None
        if tokens and tokens[0][:1] in "{[\"0123456789":
            input_data = json.loads(tokens.pop(0))
        method = procedure.rsplit(".", 1)[-1]
        if not args.allow_name and not method.startswith(QUERY_PREFIXES):
            print(f"refusing {procedure}: not a get*/search* name (pass --allow-name for a known query)")
            return 2
        pairs.append((procedure, input_data))

    key = None if args.anon else read_key(args.env)
    if not args.anon and not key:
        print(f"no WARERA_API_KEY in {args.env}; use --anon or --env")
        return 2

    all_ok = True
    for i, (procedure, input_data) in enumerate(pairs):
        if i:
            time.sleep(1.1)
        status, data = call(procedure, input_data, key)
        if isinstance(data, dict) and "result" in data:
            data = data["result"].get("data")
        shown = json.dumps(input_data) if input_data is not None else ""
        print(f"\n### {procedure} {shown} auth={key is not None} -> {status}")
        print(json.dumps(data, ensure_ascii=False)[: args.chars])
        all_ok = all_ok and 200 <= status < 300
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
