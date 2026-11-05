# WarEra API — overview

Source labels: **[spec]** official OpenAPI · **[observed]** live calls on 2026-10-03 · **[project]** this codebase · **[assumption]** unverified.

## Where things live

| What | URL |
|---|---|
| Human docs (Swagger UI) | https://api2.warera.io/docs/ |
| OpenAPI 3.0 document | https://api2.warera.io/openapi.json **[observed]** (identical to the `swaggerDoc` embedded in `/docs/swagger-ui-init.js`) |
| Server base | `https://api2.warera.io/trpc` **[spec]** (`servers: [{url: "/trpc"}]`) |
| Game web app (for user-facing links) | `https://app.warera.io/{user,country,mu,battle,article}/<id>` **[project]** |

| Community API explorer (third party) | https://warera.realmarijn.nl/api-explorer: documents **80** procedures, the 40 official ones plus 40 the official spec omits. Saved example outputs: `https://warera.realmarijn.nl/api/example/<procedure>` → `{ok, saved_at, data}`. Its "Run" button proxies through that site, not your key. |

Probed but non-existent: `/docs/openapi.json`, `/swagger.json`, `/docs/swagger.json`, `/api/openapi.json` (404).

### Two sources, ranked
1. **Live behaviour of api2.warera.io** always wins.
2. **Official spec** (`openapi.json`): authoritative for the 40 procedures it lists.
3. **Community explorer**: the only documentation for the other 40, all of which were verified live on 2026-10-03 (marked 🧭 in the index). Its param docs are sometimes wrong or stale, though. Its `mercenaryContractAuction` params (`page`, `forCountry`, `sortBy`, …), `alliance.getManyPaginated.page` and `contribution.*.limit` are silently ignored live. It also omits some spec params, such as `battleRanking.cursor`/`limit`/`side: "merged"`. Prefer the spec where both document the same procedure.

## Transport — tRPC queries

- The API is a tRPC router. Procedure path = `<router>.<procedure>`, e.g. `/trpc/battle.getById`. **[spec]**
- Spec info string: *"⚠️ Please notice that every call is in GET and not POST."* — although the paths are rendered as `post` with a JSON request body. **[spec]**
- Correct call shape: `GET /trpc/<proc>?input=<URL-encoded JSON of the request body schema>` **[spec+observed]**. Procedures with no input are called with no `input` param.
- POST with a JSON body also returned 200 for `gameConfig.getDates` and `government.getByCountryId` **[observed]** — do not rely on it; the docs say GET.
- All 40 documented procedures are **queries (read-only)**. There are no mutation/action endpoints in the public spec. **[spec]**

```python
# Project idiom (warera/ client; utils.api.warera is the bot's instance)
battle = await warera.battles.get(battle_id)                     # result.data, or None on failure
raw = await warera.call("battle.getById", {"battleId": battle_id})  # same data; raises WarEraAPIError
```

### Batching (tRPC httpBatchLink) [observed + project]

Several procedures can be combined in one HTTP request:

```
GET /trpc/gameConfig.getDates,itemTrading.getPrices?batch=1&input={"0":{},"1":{}}
→ 200 [ {"result":{"data":…}}, {"result":{"data":…}} ]
```

- Response is a JSON **array**, one envelope per call, in order.
- `input` is an object keyed by call index (`"0"`, `"1"`, …).
- Implemented in `warera/batching.py`: `warera.call_many(procedure, inputs)`, `warera.batch([Call(...)])` and every `*_many` client method. Calls started in the same event-loop iteration (e.g. `asyncio.gather`) are coalesced into one batch automatically **[project]**.
- **Errors inside a batch [observed 2026-10-12, `government.getByCountryId`]:** a batched item's `result.data` is identical to the single call. If any call fails, the batch returns **HTTP 207** with an `{"error": …}` envelope in that item's slot, both for a mix of good and bad ids and for a batch whose items fail with different codes (400 and 404). The client returns that item's error (`in_batch=True`) and keeps the other items; a 5xx in a slot is re-sent with backoff like a single call would be retried, and failed slots are logged per procedure **[project]**.
- **When every call of a chunk fails with the same 4xx, the whole request is that status, not 207** **[observed 2026-10-14, `battleLootSummary.getByBattleAndUser`, 404 for users with no hits]**. The client gives every item of the chunk that error. For procedures where that 4xx is an expected answer, the endpoint passes `expected=(NotFoundError,)` so it's logged at debug only. See `warera.battles.get_loot_summaries`.
- **Calls without input in a batch:** leaving their index out of `input` (what tRPC's own `httpBatchLink` does for an undefined input) works: `country.getAllCountries`, `itemTrading.getPrices`, `gameConfig.getGameConfig` and `battle.getBattles` in one batch all answered correctly **[observed 2026-11-02, with the bot key]**.
- **A batch counts as one request against the rate limit [observed 2026-10-09, anonymous]:** batches of 5, 25, 50 and 100 `user.getUserLite` calls each lowered `ratelimit-remaining` by exactly 1, and all results came back. A 100-call batch is a ~9 KB URL; the project chunks at 50 (~4.5 KB). With an API key: not measured. This makes batching the main tool against N+1 per-member loops.

## Authentication

- The spec declares **no** `securitySchemes`. **[spec]**
- Most procedures work anonymously. **[observed]**
- These returned `401 {"error":{"message":"API token required","code":-32001,"data":{"code":"UNAUTHORIZED",…}}}` without a key **[observed]**:
  - `transaction.getPaginatedTransactions`
  - `company.getRecommendedRegionIdsByItemCode` 🧭
  - `work.getStatsByUserId`, `work.getStatsByCompany`, `work.getStatsByEmployee` 🧭 (message `"Unauthorized"`). The explorer says these need a **WarEra Premium** account behind the key, but `getStatsByUserId` answered with the bot key **[observed 2026-10-26]**.
  - `work.getLastByEmployee` 🧭 (message `"Unauthorized"`) **[observed 2026-10-28]**.
  - The ten 🕵️ employee queries, `employee.*` and `employeeEvent.*` (see domain-economy.md → Employees) **[observed 2026-10-28]**. Until 2026-10-26 they answered 403 even with a key.
  - (`worker.getWorkers`, `worker.getTotalWorkersCount`, `work.getStatsByWorker` and `work.getStatsByWorkerAndCompany` were in this list until v0.27 removed them.)
- All other 🧭 procedures worked anonymously.
- The project sends header **`X-API-Key: <WARERA_API_KEY>`** on every request, added per request by `warera/transport.py` (env var `WARERA_API_KEY` → `config['api']` in `config.py` → `utils/api.py`). **[project]** — header name is not documented in the spec; it is what the project uses successfully.
- Not probed with a key: `itemOffer.getById` auth status, and whether a key raises rate limits — **unknown**.

## Rate limits [observed]

Response headers on anonymous calls:

```
ratelimit-limit: 100
ratelimit-policy: 100;w=60
ratelimit-remaining: 99
ratelimit-reset: 60
```

→ ~100 requests per 60-second window. Not documented in the spec. With the bot's API key, `ratelimit-remaining` read **485** after 10 requests **[observed 2026-11-02]**, so the keyed window is much larger (exact limit and window not recorded). The client honours `Retry-After` on `429` (else jittered exponential backoff), pauses new requests while `ratelimit-remaining` is 0, and caps requests in flight at 10 (`warera/transport.py`). Some cogs still throttle fan-out with `asyncio.Semaphore` (e.g. `TRANSACTION_CONCURRENCY = 5` in `top_user_weekly_donations.py`).

**Design consequence:** N+1 patterns (one call per citizen/member) burn the budget fast. Prefer list/ranking endpoints that already include the field you need.

## Response envelope

Success (single call):

```json
{"result": {"data": <payload>}}
```

`<payload>` may be an object, array, number (e.g. undocumented `gameStat.getEquipmentAvgByCode` → `1.38`), or a map.

## Errors [observed]

tRPC error envelope (HTTP status mirrors `data.httpStatus`):

```json
{"error": {"message": "...", "code": -32600, "data": {"code": "BAD_REQUEST", "httpStatus": 400, "path": "user.getUserLite"}}}
```

| HTTP | tRPC `data.code` | JSON-RPC `code` | Seen when |
|---|---|---|---|
| 400 | `BAD_REQUEST` | -32600 | Input fails zod validation. `message` is a **JSON string** of zod issues, e.g. `[{"validation":"regex","code":"invalid_string","message":"Invalid user id","path":["userId"]}]`; missing input → `"expected":"object","received":"undefined"` |
| 401 | `UNAUTHORIZED` | -32001 | Auth-only procedure without key (`"API token required"`) |
| 500 | `INTERNAL_SERVER_ERROR` | -32603 | Some input-validation failures in 🧭 procedures, e.g. `election.getElections` without `countryId`/`partyId` (`"Either countryId or partyId must be provided"`), and a non-ObjectId `cursor` in `upgradeConstruction.listConstructions` **[explorer]**. **The client retries 5xx up to 5 attempts with backoff**, so a bad input here costs ~30s and 5 requests. Validate inputs before calling |
| 404 | `NOT_FOUND` | -32004 | Unknown procedure (`No procedure found on path "foo.bar"`) **or** entity not found (`"Countries not found."`, `"Workoffers not found."`, `"Battlelootsummaries not found."`) |
| 429 | — | — | Rate limited (handled by project; body shape not observed) |
| 5xx | — | — | Retried by project |

Notes:
- **Not-found is a 404, not `data: null`.** Client methods return `None` for both "not found" and "bad input"; `warera.call()` tells them apart (`NotFoundError` vs `ValidationError`, `ProcedureNotFoundError` for a removed procedure). **[project]**
- Every input schema says `additionalProperties: false` **[spec]**, but unknown keys are **silently ignored**, not rejected: `country.getCountryById` with an extra `bogus` key and `itemTrading.getPrices` with `{"itemCode":"bread"}` both returned 200 **[observed]**. Consequence: a misspelled *optional* filter (e.g. `countryID`) fails silently and returns unfiltered data. Double-check field names against `endpoint-inputs.generated.md`.

## Pagination [spec + observed]

Cursor-based. Request fields vary by procedure:

| Field | Meaning |
|---|---|
| `limit` (or `perPage` for `company.getCompanies`) | page size; usually 1–100, default 10/20; `mercenaryContractAuction` max 50 |
| `cursor` | opaque string from previous response (`"v2.<base64>"`) |
| `direction` | only `battle.getBattles`: `forward`/`backward` |

Response: `{"items": [...], "nextCursor": "<string>"|absent}`. `battleRanking.getRanking` also returns `itemCount`. Loop until `nextCursor` is falsy (project pattern).

**Second style: page-based** (only `contribution.getCountryUnrestContributions` and `contribution.getRegionContributions`) **[observed]**. Request `page` (1-based); response `{results: [...], count, page, pages, nextPage, limit}`. `limit` is ignored (always 10). Loop while `nextPage`.

**`page` params that do nothing:** the explorer documents `page` for `alliance.getManyPaginated` and `mercenaryContractAuction.getPaginatedAuctions`, but both ignore it and return `nextCursor`. Use the cursor.

**Unpaginated arrays (🧭):** `muMember.getByMu`, `tournamentTeam.getByTournamentId` (443 teams), `region.getAll` (742 on 2026-11-02), `search.searchUsers`/`searchMus` (≤5 IDs), `shop.*`.

**Not paginated even though large:** `ranking.getRanking` (returns *all* entries, ~14k for `weeklyUserDamages`), `region.getRegionsObject` (~742 regions, ~0.9 MB), `country.getAllCountries` (~180).

## Common data conventions [observed]

- IDs are 24-hex Mongo ObjectIds in `_id`; references to other entities are bare ID strings (`country`, `user`, `region`, `mu`, `battle`…). `user.getUserLite` enforces `^[a-f\d]{24}$`.
- Timestamps are ISO-8601 UTC strings (`"2026-10-03T05:47:00.701Z"`). Project parses with `datetime.fromisoformat(s.replace('Z', '+00:00'))`.
- Mongo internals leak through: `__v`, `createdAt`, `updatedAt`.
- `rankings` sub-objects on user/country/mu: `{<rankingType>: {value, rank, tier}}` where `tier ∈ bronze|silver|gold|platinum|diamond|master` (observed values).
- Money is a float (game currency); item quantities are numbers.
- Item codes (`itemCode`): see `gameConfig.getGameConfig().items` keys — e.g. `bread`, `steak`, `cookedFish`, `lightAmmo`, `ammo`, `heavyAmmo`, `knife`, `gun`, `rifle`, `sniper`, `tank`, `jet`, `helmet1..6`, `chest1..6`, `boots1..6`, `gloves1..6`, `pants1..6`, `case1`, `case2`, `woodenCase`, `scraps`, raw materials.
