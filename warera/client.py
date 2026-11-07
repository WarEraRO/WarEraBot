"""`WarEraClient`: the single entry point for WarEra API calls.

The client is generic: it knows tRPC, not the bot. It combines the transport (session, key,
retries, rate limit), the batcher and the response cache, and exposes one attribute per
endpoint group (`client.users`, `client.battles`, ...).
"""
import logging

from warera.batching import DEFAULT_CHUNK_SIZE, DEFAULT_MAX_URL_LENGTH, Batcher, Call, Coalescer
from warera.cache import ResponseCache
from warera.endpoints import (
    BattlesAPI,
    CompaniesAPI,
    ContractsAPI,
    CountriesAPI,
    GameAPI,
    MarketAPI,
    MilitaryUnitsAPI,
    PartiesAPI,
    RegionsAPI,
    TournamentsAPI,
    UsersAPI,
)
from warera.exceptions import WarEraAPIError
from warera.transport import DEFAULT_BASE_URL, Transport

logger = logging.getLogger(__name__)

# gameConfig changes only with game patches; every cog that read it already kept it for an hour.
DEFAULT_CACHE_TTLS = {
    'gameConfig.getGameConfig': 3600,
}


class WarEraClient:
    """Async client for the WarEra tRPC API.

    Low-level methods (`call`, `call_many`, `batch`) raise or return `WarEraAPIError`; the endpoint
    groups wrap them in methods that return None or a partial dict on failure. Identical concurrent
    calls are always merged into one request; results are cached only for procedures in `cache_ttls`.

    Usage::

        client = WarEraClient(api_key=key)
        user = await client.users.get(user_id)            # None when it failed
        users = await client.users.get_many(user_ids)     # {id: user}, one request per 50 ids
        await client.close()
    """

    def __init__(self, api_key=None, *, base_url=DEFAULT_BASE_URL, timeout=60.0, retry=None, max_concurrency=10,
                 chunk_size=DEFAULT_CHUNK_SIZE, max_url_length=DEFAULT_MAX_URL_LENGTH, cache_ttls=None, session=None):
        """Configure the client; no connection is opened until the first call.

        `api_key` is sent as `X-API-Key` (None: anonymous; a few procedures then answer 401).
        `timeout`, `retry` (a `RetryPolicy`), `max_concurrency` and `session` go to the `Transport`;
        `chunk_size` and `max_url_length` bound each batch. `cache_ttls` ({procedure: seconds})
        replaces `DEFAULT_CACHE_TTLS`; pass {} to cache nothing.
        """
        self.transport = Transport(base_url, api_key, timeout=timeout, retry=retry,
                                   max_concurrency=max_concurrency, session=session)
        self.batcher = Batcher(self.transport, chunk_size=chunk_size, max_url_length=max_url_length)
        self.coalescer = Coalescer(self.batcher)
        self.cache = ResponseCache(DEFAULT_CACHE_TTLS if cache_ttls is None else cache_ttls)

        self.battles = BattlesAPI(self)
        self.companies = CompaniesAPI(self)
        self.contracts = ContractsAPI(self)
        self.countries = CountriesAPI(self)
        self.game = GameAPI(self)
        self.market = MarketAPI(self)
        self.mus = MilitaryUnitsAPI(self)
        self.parties = PartiesAPI(self)
        self.regions = RegionsAPI(self)
        self.tournaments = TournamentsAPI(self)
        self.users = UsersAPI(self)

    async def call(self, procedure, input=None):
        """Return the `result.data` of one query call.

        `input` is the procedure's input object, or None for procedures that take none. A fresh cached
        result is returned without a request, and a call identical to one already in flight waits for
        it instead of sending another. Calls started in the same event-loop iteration (for example by
        `asyncio.gather`) share one batched request. When a cached procedure fails to refresh, the
        expired result is returned instead of the error.

        Raises:
            WarEraAPIError: the subclass matching the failure, after retries where they apply.
        """
        call = Call(procedure, input)
        if self.cache.ttl_for(procedure):
            found, value = self.cache.get(call.key)
            if found:
                return value

        async def fetch():
            outcome = await self.coalescer.submit(call)
            if isinstance(outcome, WarEraAPIError):
                stale, value = self.cache.get_stale(call.key)
                if stale:
                    logger.warning('%s failed (%s); serving the expired cached result', procedure, outcome)
                    return value
                raise outcome
            self.cache.set(call.key, outcome)
            return outcome

        return await self.cache.single_flight(call.key, fetch)

    async def call_many(self, procedure, inputs):
        """Call `procedure` once per input with tRPC batching; a list aligned with `inputs`.

        Each item is the call's `result.data` or the `WarEraAPIError` it failed with; this method does
        not raise for API errors. Identical inputs are sent once.
        """
        return await self.batch([Call(procedure, input) for input in inputs])

    async def batch(self, calls):
        """Run `Call`s of any procedures in as few requests as possible; aligned list like `call_many`.

        Cached results are served without a request and successful results of cached procedures are
        stored.
        """
        calls = list(calls)
        outcomes = [None] * len(calls)
        pending = []
        for index, call in enumerate(calls):
            found, value = self.cache.get(call.key) if self.cache.ttl_for(call.procedure) else (False, None)
            if found:
                outcomes[index] = value
            else:
                pending.append(index)
        if pending:
            fetched = await self.batcher.run([calls[index] for index in pending])
            for index, value in zip(pending, fetched):
                outcomes[index] = value
                if not isinstance(value, WarEraAPIError):
                    self.cache.set(calls[index].key, value)
        return outcomes

    def invalidate(self, procedure=None):
        """Forget cached results of `procedure`, or all of them when it is None."""
        self.cache.invalidate(procedure)

    async def close(self):
        """Close the HTTP session if the client opened it. The client stays usable and reopens on demand."""
        await self.transport.close()

    async def __aenter__(self):
        """Return the client itself."""
        return self

    async def __aexit__(self, *exc_info):
        """Close the session on leaving the block."""
        await self.close()
