# `warera`: WarEra API client

An async client for the WarEra tRPC API (`https://api2.warera.io/trpc`). It is the only code in the
bot that talks to the API. Cogs call high-level methods and never build URLs, encode inputs or unwrap
`result.data`.

```python
from utils.api import warera          # the bot's shared instance

user = await warera.users.get(user_id)                  # dict or None
users = await warera.users.get_many(user_ids)           # {user_id: user}, batched
battles = await warera.battles.get_active()             # list or None
```

## Layout

| Module | Responsibility |
|---|---|
| `client.py` | `WarEraClient`: low-level `call` / `call_many` / `batch`, cache, endpoint groups |
| `transport.py` | aiohttp session, `X-API-Key`, timeouts, retries with jittered backoff, rate-limit pause, concurrency cap |
| `batching.py` | tRPC `httpBatchLink`: dedup, chunking, per-item results, coalescing of concurrent calls |
| `cache.py` | per-procedure TTL cache, stale-on-error, single-flight dedup |
| `exceptions.py` | the `WarEraAPIError` hierarchy and envelope parsing |
| `endpoints/` | one class per area; each method wraps one procedure (or a fixed combination) |

`utils/api.py` only creates the bot's instance from `config['api']`; `run.py` closes it on shutdown.

## Initialising and configuring

```python
from warera import WarEraClient, RetryPolicy

client = WarEraClient(
    api_key="...",                     # X-API-Key; None = anonymous (a few procedures then answer 401)
    base_url="https://api2.warera.io/trpc",
    timeout=60.0,                      # seconds per HTTP attempt
    retry=RetryPolicy(max_attempts=5, initial_backoff=1.0, backoff_factor=2.0, max_backoff=60.0),
    max_concurrency=10,                # requests in flight at once (None = no cap)
    chunk_size=50,                     # calls per batch request
    max_url_length=7000,               # a batch is split before its URL gets longer
    cache_ttls={"gameConfig.getGameConfig": 3600},   # default; {} disables caching
    session=None,                      # inject an aiohttp.ClientSession (tests, harness)
)
async with client:                     # or: await client.close()
    ...
```

No connection is opened until the first call. `close()` closes a session the client created; a
later call opens a new one. An injected session is never closed by the client.

The key goes in a per-request header, not in the session defaults, so it never reaches another host.
Third-party HTTP (for example Reddit in `cogs/tasks/reddit_monitor.py`) must still use its own session.

## Endpoint groups

Every method returns the API's `result.data` (or a dict of them) unchanged. It returns **None** when the
call failed or the result has the wrong shape. A batch method's dict **leaves out** the keys that failed
or came back empty. Failures are logged. A 404 that is an expected answer (an MU id that no longer
exists, a user with no hits in a battle) is logged at debug only. A removed procedure (404 `No procedure
found`) is always logged as an error.

| Group | Methods (procedure) |
|---|---|
| `users` | `get` (user.getUserLite) · `get_many` (batched) · `get_full` / `get_full_many` (user.getUserById; adds `skills`, which lite lost on 2026-11-07, and `stats.wealth`) · `get_equipment_many` (inventory.fetchCurrentEquipment) · `get_by_country` (user.getUsersByCountry, all pages) · `find_by_name`, `find_many_by_name`, `ids_by_name` (search.searchAnything + getUserLite, or getUserById with `full=True` when skills are needed; `username_ids` caches name → id) |
| `countries` | `get` · `get_many` (country.getCountryById) · `get_all` (country.getAllCountries) · `get_names` · `get_governments` (government.getByCountryId, batched) · `get_alliance` (alliance.getById 🧭) · `get_wars_many` (war.getById 🧭, batched) · `get_war_events_since` (event.getEventsPaginated warDeclared + peaceMade) |
| `regions` | `get` · `get_many` (region.getById) · `get_all` (region.getRegionsObject, {id: region}) |
| `mus` | `get` · `get_many` (mu.getById) · `get_all` (mu.getManyPaginated) · `get_members` (muMember.getByMu 🧭) · `get_upgrades` (upgrade.getUpgradeByTypeAndEntity, batched by type) · `get_public_orders` (tradingOrder.getPublicOrdersByOwner 🧭) |
| `battles` | `get` (battle.getById) · `get_active` · `get_active_for_country` · `get_ended_since` · `get_ended_for_country_since` (battle.getBattles) · `get_round` (round.getById) · `get_orders_many` (battleOrder.getByBattle, keyed by (battleId, side)) · `get_ranking` (all pages) · `get_ranking_pages` (battleRanking.getRanking, early stop) · `get_loot_summaries` (battleLootSummary.getByBattleAndUser) |
| `tournaments` | `get_last` · `get` (tournament.*) · `get_team` (tournamentTeam.getById) |
| `contracts` | `get_active_auctions` · `get_won_since` · `get_won_by_battles` (mercenaryContractAuction.getPaginatedAuctions) |
| `companies` | `get_many` (company.getById) · `get_owned_by` · `get_ids_owned_by_many` (company.getCompanies) · `get_production_bonuses` 🧭 · `get_rosters` (employee.getCompanyRoster 🔑) · `get_employee_work_stats` (work.getStatsByEmployee 🔑) |
| `market` | `get_prices` (itemTrading.getPrices) · `get_user_transactions` · `get_mu_transactions` (transaction.getPaginatedTransactions 🔑) |
| `game` | `get_config` (gameConfig.getGameConfig, cached 1 h) · `get_pp_money_value` · `get_equipment_averages` (gameStat.*) · `get_ranking` (ranking.getRanking) · `get_articles` (article.getArticlesPaginated) |

🧭 = not in the official spec (community explorer); 🔑 = needs the API key. The `warera-api` skill
documents every procedure, input and response shape.

## Batching

tRPC `httpBatchLink` sends many calls in one GET (`/trpc/a.x,a.x,b.y?batch=1&input={"0":…}`), and a
batch costs **one** rate-limit unit whatever its size. The client batches in two ways:

1. **Explicit:** the `*_many` methods and `client.call_many(procedure, inputs)` /
   `client.batch([Call(...), ...])`. Identical calls are sent once and every result lines up with its
   input. Calls are packed into chunks of `chunk_size` calls and at most `max_url_length` URL characters,
   and the chunks are sent concurrently.
2. **Automatic (coalescing):** calls started in the same event-loop iteration share one request:

   ```python
   battles, countries, config = await asyncio.gather(
       warera.battles.get_active(), warera.countries.get_all(), warera.game.get_config())   # 1 request
   ```

   A lone call is sent as a plain, unbatched GET. A merged call gets its result as soon as it is final,
   without waiting for another call's retries. Procedures with very large responses
   (`SOLO_PROCEDURES`: `region.getRegionsObject`, `ranking.getRanking`) are always sent on their own, so
   they don't share a timeout with small calls. Paginated listings are inherently sequential (each page
   needs the previous cursor), so their pages are not merged with each other.

Failures inside a batch are per item. The server answers 207 with an error envelope in each failed slot;
those items get their error and the others keep their data. A 5xx in a slot is re-sent with backoff, up
to the same number of attempts as an unbatched call. When every call of a request fails with the same
status, the server answers that status, and each item gets that error.

## Caching and deduplication

- **Single-flight** (always on): identical calls in flight at the same time share one request.
- **TTL cache** (opt-in per procedure): only procedures in `cache_ttls` are stored. The default caches
  `gameConfig.getGameConfig` for an hour, because it changes only with game patches. When a refresh fails,
  the expired copy is returned instead of the error. Cached objects are shared, so never mutate them.
  `client.invalidate(procedure=None)` drops entries.
- Live data (battles, prices, users, rankings) is **not** cached by the client. Cogs that tolerate staleness
  keep their own derived caches (country-name maps, MU names) with the TTLs their features need.

## Errors

```
WarEraAPIError                      .procedure .status .trpc_code .is_trpc_error .in_batch
├── NetworkError                    connection failure / timeout (retried)
├── InvalidResponseError            body is not tRPC JSON
├── ValidationError                 400 BAD_REQUEST (zod issues in .message)
├── AuthenticationError             401 / 403
├── NotFoundError                   404 entity not found
│   └── ProcedureNotFoundError      404 "No procedure found on path" (removed by a patch)
├── RateLimitError                  429 after retries (.retry_after)
└── ServerError                     5xx after retries
```

- `client.call()` raises these, and `call_many()` / `batch()` return them in place of the failed items.
  The endpoint methods catch them, which is the "None on failure" contract the cogs rely on.
- `trpc_code` is set when the server sent a tRPC error envelope. A plain HTTP error (for example a proxy's
  HTML 502) has `trpc_code=None`.
- Retried: network errors, timeouts, 429 (honouring `Retry-After`) and 5xx. Not retried: every other 4xx.
  Retries are always safe, because every request is a GET: tRPC serves mutations only over POST, so the
  client can't trigger a game action.
- The rate limiter reads `ratelimit-remaining` / `ratelimit-reset` (100 requests per 60 s were observed)
  and holds new requests while the window is exhausted, instead of spending a 429 each.
- Logs never include the API key.

## Adding an endpoint

1. Find the procedure in the `warera-api` skill (`references/endpoints-index.md`). Never guess procedure,
   input or field names.
2. Add a method to the matching class in `endpoints/` (or a new class registered in `client.py`) using the
   `Endpoint` helpers:

   ```python
   @guarded()                                    # unexpected crash -> logged, returns None
   async def get(self, war_id):
       """The war.getById object of `war_id`, or None (explorer-documented)."""
       return await self._get('war.getById', {'warId': war_id})

   @guarded(dict)                                # batched: {key: data}
   async def get_many(self, war_ids):
       """Batched war.getById: {warId: war} for the ids that resolved."""
       return await self._get_keyed('war.getById', war_ids, lambda wid: {'warId': wid})
   ```

   `_get(..., kind=list, allow_empty=True, expected=(NotFoundError,))` controls the accepted shape and
   which errors are logged at debug. Use `_collect(...)` for cursor listings (`partial=True` keeps the pages
   read before a failure) and `_collect_since(...)` for newest-first listings with a `createdAt` cutoff.
3. If the data changes rarely, add the procedure to `DEFAULT_CACHE_TTLS` with a TTL its users can tolerate.
4. Add a test in `tests/test_warera_client.py`, and add the procedure to the equivalence harness's fake world
   (`.claude/skills/warerabot-dev/scripts/equivalence/fakeworld.py`) when a cog scenario uses it.

## Testing

```
python -m unittest discover -s tests
```

The tests run the real transport against a local `aiohttp.web` server that imitates tRPC: batching,
207 partial failures, uniform failures, 429 with `Retry-After` and rate-limit headers. They never touch
the live API.
