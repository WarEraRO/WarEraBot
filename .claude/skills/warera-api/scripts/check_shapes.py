"""Check live WarEra API response shapes against the warera-api skill docs.

``refresh_spec.py`` only diffs procedure *lists*; this script diffs *response
keys*. It calls every documented query procedure once (GET only, about one
request per second, inputs seeded from live data: Romania, its president, an
active battle, the key owner's companies and employees, ...), records each
response's key paths, and prints two lists per procedure:

* ``NOT IN DOCS``: live keys that no doc mentions (new fields).
* ``DOCS ONLY``: keys in the domain files' JSON samples that the live
  response lacked (removed fields, or optional fields absent from one sample).

Usage (from the repo root):
    python -I .claude/skills/warera-api/scripts/check_shapes.py                 # probe + report
    python -I .claude/skills/warera-api/scripts/check_shapes.py --from s.json   # report from a saved probe
    python -I .claude/skills/warera-api/scripts/check_shapes.py --out s.json --depth 3

A key missing from **one** sample is not proof of removal: optional keys
(``buffs``, ``party.treasurer``, ``dates.lastSkillsResetAt``) are absent on many
objects. Confirm a suspected removal over 20+ objects (tRPC batch) before
documenting it. ``gameConfig.getGameConfig`` is checked by warera-config's
``check_config.py`` instead; its NOT IN DOCS lines here are expected.

The key is read from ``WARERA_API_KEY`` in ``.env`` (or ``--env``) and is never
printed. Stdlib only. Exit status: 0 when every probe answered 200, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REFS = pathlib.Path(__file__).resolve().parent.parent / "references"
API = "https://api2.warera.io/trpc/"
HEX = re.compile(r"^[0-9a-f]{24}$")
# Procedures whose shape the docs describe in another procedure's section.
SHARED = {
    "battle.getById": ["Battle object"], "battle.getBattles": ["Battle object"],
    "country.getAllCountries": ["country.getCountryById"],
    "region.getRegionsObject": ["region.getById"], "region.getAll": ["region.getById"],
    "user.getUserById": ["user.getUserLite"],
    "tournament.getLastTournament": ["tournament.getById"], "tournament.getManyPaginated": ["tournament.getById"],
    "tournamentTeam.getByTournamentId": ["tournamentTeam.getById"],
    "alliance.getByIds": ["alliance.getById"], "alliance.getManyPaginated": ["alliance.getById"],
    "mu.getManyPaginated": ["mu.getById"], "party.getManyPaginated": ["party.getById"],
    "article.getPinnedArticles": ["article.getArticlesPaginated"],
    "article.getArticleById": ["article.getArticlesPaginated"], "article.getArticleLiteById": ["article.getArticlesPaginated"],
    "mercenaryContractAuction.getActiveAuctions": ["mercenaryContractAuction.getPaginatedAuctions"],
    "election.getElections": ["election.getElection"],
}
for _p in ("getById", "getMyEmployees", "getCompanyEmployees", "getCompanyRoster", "getCompanyEstimate",
           "getManagerPointValue", "getMyWorkforceSummary"):
    SHARED["employee." + _p] = ["Employees"]
SHARED["employeeEvent.getHistory"] = ["Employees"]


class Prober:
    """Rate-limited GET client that records each response's key shape."""

    def __init__(self, key: str):
        self.key = key
        self.last = 0.0
        self.results: dict[str, dict] = {}

    def call(self, proc: str, inp: object = None) -> tuple[int, object]:
        """GET one query procedure; return ``(status, result.data or {"__error__": msg})``."""
        wait = 1.05 - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()
        url = API + proc + ("?input=" + urllib.parse.quote(json.dumps(inp)) if inp is not None else "")
        # A User-Agent is required: bare urllib gets 403 (SKILL.md, Freshness).
        headers = {"User-Agent": "Mozilla/5.0 WarEraBot-check_shapes"}
        if self.key:
            headers["X-API-Key"] = self.key
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as r:
                return r.status, json.loads(r.read())["result"].get("data")
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get("error", {}).get("message", "")
            except Exception:
                msg = ""
            return e.code, {"__error__": msg[:300]}
        except Exception as e:  # network errors are reported, not raised
            return -1, {"__error__": str(e)[:300]}

    def probe(self, proc: str, inp: object = None, label: str | None = None) -> object:
        """Call ``proc``, store its status and shape under ``label`` (default ``proc``), return the data or None."""
        status, data = self.call(proc, inp)
        ok = status == 200
        self.results[label or proc] = {
            "input": inp, "status": status, "shape": shape(data) if ok else None,
            "error": None if ok else (data or {}).get("__error__"),
        }
        print(status, label or proc, "" if ok else self.results[label or proc]["error"], file=sys.stderr, flush=True)
        return data if ok else None


def shape(value: object, path: str = "", out: dict | None = None, depth: int = 0) -> dict[str, str]:
    """Flatten ``value`` into ``{key path: type}``.

    Lists become ``path[]``; dicts keyed by ObjectIds (or with >30 same-typed
    values, e.g. item-code maps) become ``path.<k>`` so their keys aren't
    treated as fields. Recursion stops at depth 7.
    """
    out = {} if out is None else out
    p = path or "$"
    if isinstance(value, dict):
        keys = list(value)
        mapish = bool(keys) and (all(HEX.match(k) for k in keys)
                                 or (len(keys) > 30 and len({type(v).__name__ for v in value.values()}) == 1))
        out[p] = "map" if mapish else "obj"
        if depth < 7:
            for k, v in (((("<k>"), v) for v in list(value.values())[:20]) if mapish else value.items()):
                shape(v, f"{path}.{k}" if path else k, out, depth + 1)
    elif isinstance(value, list):
        out.setdefault(p, "list")
        for v in value[:30]:
            shape(v, path + "[]", out, depth + 1)
    else:
        t, prev = type(value).__name__, out.get(p)
        if prev in (None, t, "NoneType"):
            out[p] = t
        elif t != "NoneType" and t not in prev.split("|"):
            out[p] = f"{prev}|{t}"
    return out


def _first(items: object, *keys: str) -> object:
    """Return the first string item, or the first truthy ``item[key]`` for ``keys``."""
    for x in items or []:
        if isinstance(x, str):
            return x
        for k in keys:
            if isinstance(x, dict) and x.get(k):
                return x[k]
    return None


def _items(data: object) -> list:
    """Return ``data['items']`` for a paginated response, else ``data`` as a list."""
    return data.get("items", []) if isinstance(data, dict) else (data or [])


def run_probes(pr: Prober) -> None:
    """Probe every documented query procedure, seeding ids from earlier responses."""
    P = pr.probe
    countries = P("country.getAllCountries") or []
    ro = next(c for c in countries if c["name"] == "Romania")
    cid, owner = ro["_id"], None
    P("country.getCountryById", {"countryId": cid})
    gov = P("government.getByCountryId", {"countryId": cid}) or {}
    uid = gov.get("president")
    regs = P("region.getRegionsObject") or {}
    rid = (next((k for k, v in regs.items() if v.get("country") == cid), None)
           or next((k for k, v in regs.items() if v.get("initialCountry") == cid), None) or next(iter(regs)))
    P("region.getById", {"regionId": rid})
    P("region.getAll")
    P("upgrade.getUpgradeByTypeAndEntity", {"upgradeType": "bunker", "regionId": rid})
    P("event.getEventsPaginated", {"limit": 30})
    P("upgradeConstruction.getMapConstructions")
    P("upgradeConstruction.getRegionConstructions", {"regionId": rid})
    P("upgradeConstruction.listConstructions", {"countryId": cid, "limit": 5})
    P("gameStat.getWorldDevelopment")
    P("countryDiplomacy.getByCountry", {"countryId": cid})
    if ro.get("allianceId"):
        P("alliance.getById", {"allianceId": ro["allianceId"]})
        P("alliance.getByIds", {"ids": [ro["allianceId"]]})
    P("alliance.getManyPaginated", {"limit": 3})
    P("country.getUnrestData", {"countryId": cid})
    P("contribution.getCountryUnrestContributions", {"countryId": cid})
    P("contribution.getRegionContributions", {"regionId": rid})
    if ro.get("rulingParty"):
        P("party.getById", {"partyId": ro["rulingParty"]})
    P("party.getManyPaginated", {"limit": 3, "countryId": cid})
    eid = _first(_items(P("election.getElections", {"countryId": cid, "limit": 3})), "_id")
    if eid:
        P("election.getElection", {"electionId": eid})
    P("sanction.getPaginated", {"limit": 3})
    P("user.getUserLite", {"userId": uid})
    user = P("user.getUserById", {"userId": uid}) or {}
    P("user.getUsersByCountry", {"countryId": cid, "limit": 5})
    P("search.searchAnything", {"searchText": "Romania"})
    P("inventory.fetchCurrentEquipment", {"userId": uid})
    P("search.searchUsers", {"searchText": "dan"})
    P("search.searchMus", {"searchText": "romania"})
    for proc in ("shop.getLastGifts", "shop.getSubscribedUsers", "shop.getTopGiftGivers"):
        P(proc)
    P("giveaway.getManyPaginated", {"limit": 3})
    bid = _first(_items(P("battle.getBattles", {"isActive": True, "limit": 5})), "_id")
    if bid:
        b = P("battle.getById", {"battleId": bid}) or {}
        P("battle.getLiveBattleData", {"battleId": bid})
        rounds = b.get("rounds") or []
        rnd = (rounds[-1] if rounds and isinstance(rounds[-1], str) else _first(rounds, "_id")) or b.get("currentRound")
        if rnd:
            P("round.getById", {"roundId": rnd})
            P("round.getLastHits", {"roundId": rnd})
        rk = P("battleRanking.getRanking", {"battleId": bid, "dataType": "damage", "type": "user", "side": "merged"})
        P("battleOrder.getByBattle", {"battleId": bid, "side": "attacker"})
        rows = next((rk[k] for k in ("rankings", "items", "ranking") if rk.get(k)), []) if isinstance(rk, dict) else rk
        fighter = _first(rows, "user", "userId", "_id")
        fighter = fighter.get("_id") if isinstance(fighter, dict) else fighter
        if fighter:
            P("battleLootSummary.getByBattleAndUser", {"battleId": bid, "userId": fighter})
        P("battle.getViewersCount", {"battleId": bid})
    P("battle.getActiveBattlesByCountry", {"countryId": cid})
    muid = user.get("mu") or _first(_items(P("mu.getManyPaginated", {"limit": 3})), "_id")
    P("mu.getById", {"muId": muid})
    P("muMember.getByMu", {"muId": muid})
    P("mu.getReputationBuyStatus", {"muId": muid})
    # Without status getPaginatedAuctions lists only active auctions (often none).
    P("mercenaryContractAuction.getPaginatedAuctions", {"limit": 3, "status": "won"})
    P("mercenaryContractAuction.getActiveAuctions", {"limit": 3, "status": "won"})
    P("itemTrading.getPrices")
    P("tradingOrder.getTopOrders", {"itemCode": "bread", "limit": 3})
    P("tradingOrder.getTopOrdersPerItemCode", {"itemCodes": ["bread", "steel"], "limit": 2})
    P("itemTrading.getItemTrading", {"itemCode": "bread"})
    P("tradingOrder.getPublicOrdersByOwner", {"userId": uid})
    emps = P("employee.getMyEmployees") or []
    owner = emps[0]["owner"] if emps else uid
    coid = _first(_items(P("company.getCompanies", {"userId": owner, "perPage": 5})), "_id")
    if coid:
        P("company.getById", {"companyId": coid})
        P("company.getProductionBonus", {"companyId": coid})
        for proc in ("managerOffer.getByCompanyId", "manager.getByCompanyId", "employee.getCompanyRoster",
                     "employee.getCompanyEmployees", "employee.getCompanyEstimate", "employee.getManagerPointValue"):
            P(proc, {"companyId": coid})
        P("work.getStatsByCompany", {"companyId": coid, "days": 3})
    P("company.getRecommendedRegionIdsByItemCode", {"itemCode": "bread"})
    P("managerOffer.getManyPaginated", {"limit": 3})
    P("managerOffer.getWageStats")
    emp = _first(emps, "_id")
    if emp:
        P("employee.getById", {"employeeId": emp})
        P("employeeEvent.getHistory", {"employeeId": emp})
        P("work.getLastByEmployee", {"employeeId": emp, "limit": 3})
        P("work.getStatsByEmployee", {"employeeId": emp, "days": 3})
    for proc in ("employee.getMyWorkforceSummary", "employeeEvent.getMine", "employeeEvent.getPendingCount"):
        P(proc)
    P("work.getStatsByUserId", {"userId": owner, "days": 3})
    P("transaction.getPaginatedTransactions", {"limit": 5, "countryId": cid})
    P("donation.getManyPaginated", {"countryId": cid, "limit": 3})
    P("donation.getTotalDonations", {"countryId": cid})
    P("gameStat.getPpMoneyValue")
    P("gameStat.getPpMoneyValueByItem")
    P("ranking.getRanking", {"rankingType": "userDamages"})
    aid = _first(_items(P("article.getArticlesPaginated", {"type": "last", "limit": 3})), "_id")
    if aid:
        for proc in ("article.getArticleById", "article.getArticleLiteById",
                     "articleInteraction.getArticleLikers", "articleInteraction.getArticleTippers"):
            P(proc, {"articleId": aid})
    P("article.getWelcomeArticleByCountryId", {"countryId": cid})
    for proc in ("article.getPinnedArticles", "gameConfig.getDates", "gameConfig.getGameConfig", "gameConfig.getMaxBountyRate"):
        P(proc)
    P("gameStat.getEquipmentAvgByCode", {"itemCode": "helmet3"})
    tid = (P("tournament.getLastTournament") or {}).get("_id")
    P("tournament.getManyPaginated", {"limit": 3})
    if tid:
        P("tournament.getById", {"tournamentId": tid})
        ttid = _first(_items(P("tournamentTeam.getByTournamentId", {"tournamentId": tid})), "_id")
        if ttid:
            P("tournamentTeam.getById", {"tournamentTeamId": ttid})
    for proc in ("upgrade.getMapUpgrades", "gameStat.getBadgeStats", "gameStat.getMilestoneStats", "assetSale.getLastSkinGifts"):
        P(proc)


def _live_keys(results: dict[str, dict], procs: list[str]) -> set[str]:
    """Return every key-path segment seen in the responses of ``procs``."""
    return {seg for p in procs if (results.get(p) or {}).get("shape")
            for path in results[p]["shape"] for seg in re.split(r"[.\[\]]+", path) if seg}


def report(results: dict[str, dict], depth: int) -> None:
    """Print live keys no doc mentions (per procedure), then doc-sample keys missing live (per doc section)."""
    idx = (REFS / "endpoints-index.md").read_text("utf-8")
    domains = {p.name: p.read_text("utf-8") for p in sorted(REFS.glob("domain-*.md"))}
    everything = idx + "".join(domains.values())
    print("# Live keys that no doc mentions (new fields?)")
    for proc, r in results.items():
        if not r["shape"]:
            print(f"## {proc}: HTTP {r['status']} {r['error'] or ''}")
            continue
        new = []
        for path, typ in r["shape"].items():
            segs = [s for s in re.split(r"[.\[\]]+", path) if s not in ("", "$", "<k>")]
            if segs and path.count(".") + path.count("[]") <= depth and not re.search(r"\b" + re.escape(segs[-1]) + r"\b", everything):
                new.append(f"{path}:{typ}")
        if new:
            print(f"## {proc}\n  NOT IN DOCS:", ", ".join(new))
    # Sections are matched by full procedure names in their heading (bare method
    # names like getById would match unrelated sections), plus the keyword
    # sections that describe a shared object.
    keyword = {}
    for proc, kws in SHARED.items():
        for kw in kws:
            if "." not in kw:
                keyword.setdefault(kw, []).append(proc)
    print("\n# Keys in doc JSON samples missing live (removed, or optional: verify over many samples)")
    for fname, text in domains.items():
        for sec in re.split(r"\n(?=#{2,4} )", text):
            head = sec.split("\n", 1)[0]
            procs = re.findall(r"`([a-zA-Z]+\.[a-zA-Z]+)`", head) + [p for kw, ps in keyword.items() if kw in head for p in ps]
            live = _live_keys(results, procs)
            if not live:
                continue
            code = "\n".join(re.findall(r"```[a-z]*\n(.*?)```", sec, re.S))
            gone = sorted(k for k in set(re.findall(r'"([A-Za-z_]\w*)"\s*:', code)) if k not in live)
            if gone:
                print(f"## {fname} | {head.lstrip('# ')[:70]}\n  DOCS ONLY:", ", ".join(gone))


def main() -> int:
    """Parse arguments, probe (or load a saved probe), print the report; return the exit status."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--env", default=".env", help="dotenv file holding WARERA_API_KEY")
    ap.add_argument("--out", help="save the probe results (JSON) here")
    ap.add_argument("--from", dest="src", help="skip probing and report from saved results")
    ap.add_argument("--depth", type=int, default=2, help="max key-path depth reported as new (default 2)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # python -I ignores PYTHONIOENCODING
    if args.src:
        results = json.loads(pathlib.Path(args.src).read_text("utf-8"))
    else:
        env = pathlib.Path(args.env)
        key = next((line.split("=", 1)[1].strip().strip("\"'") for line in env.read_text("utf-8").splitlines()
                    if line.startswith("WARERA_API_KEY=")), "") if env.exists() else ""
        prober = Prober(key)
        run_probes(prober)
        results = prober.results
        if args.out:
            pathlib.Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), "utf-8")
    report(results, args.depth)
    return 0 if all(r["status"] == 200 for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
