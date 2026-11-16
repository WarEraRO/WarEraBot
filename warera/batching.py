"""tRPC httpBatchLink batching: many query calls in one GET.

`GET /trpc/a.x,a.x,b.y?batch=1&input={"0":{...},"1":{...},"2":{...}}` answers a JSON array with one
envelope per call, in order. Behaviour observed on api2.warera.io:

- A batch costs 1 rate-limit unit whatever its size (5, 25, 50 and 100 calls each cost 1 [observed
  2026-10-09]), so batching is the main defence against one-call-per-member loops.
- When some calls fail, the response is HTTP 207 and each failed slot holds an `{"error": ...}`
  envelope [observed 2026-10-12]; the other slots keep their data.
- When every call of a batch fails with the same 4xx, the whole response is that status instead
  [observed 2026-10-14].
- Calls of different procedures can share one batch [observed, gameConfig.getDates + itemTrading.getPrices].
"""
import asyncio
import json
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from warera.exceptions import InvalidResponseError, ServerError, WarEraAPIError, error_from_envelope

logger = logging.getLogger(__name__)

# 50 calls of a 24-hex id keep the URL around 4.5 KB; a 100-call batch (~9 KB) also worked.
DEFAULT_CHUNK_SIZE = 50
DEFAULT_MAX_URL_LENGTH = 7000


def canonical_json(value):
    """`value` as compact JSON with sorted keys, so equal inputs give equal strings."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


@dataclass(frozen=True)
class Call:
    """One query call: a `router.procedure` name and its input (None for procedures without input)."""

    procedure: str
    input: Any = None

    @property
    def key(self):
        """Hashable identity of the call; two calls with equal procedure and input share it."""
        return self.procedure, canonical_json(self.input)


def _encoded_length(call, index):
    if call.input is None:
        return len(call.procedure) + 1
    return len(call.procedure) + 1 + len(quote(f'"{index}":{canonical_json(call.input)},'))


class Batcher:
    """Runs a list of calls with as few HTTP requests as the chunk limits allow.

    Identical calls are sent once. Calls are packed into chunks of at most `chunk_size` calls and about
    `max_url_length` URL characters; chunks are sent concurrently (the transport caps concurrency). A
    chunk of one call is sent as a plain, unbatched request. Items that failed with a 5xx inside a 207
    are re-sent with backoff, because the transport only retries whole requests; together with the
    first try that is the transport's `retry.max_attempts`, the same as an unbatched call gets.
    """

    def __init__(self, transport, *, chunk_size=DEFAULT_CHUNK_SIZE, max_url_length=DEFAULT_MAX_URL_LENGTH):
        """Use `transport` for the requests; the other arguments are the limits described on the class."""
        self.transport = transport
        self.chunk_size = max(1, chunk_size)
        self.max_url_length = max_url_length

    async def run(self, calls, on_final=None):
        """Run `calls` and return a list aligned with them.

        Each item is the call's `result.data`, or the `WarEraAPIError` it failed with (the convention of
        `asyncio.gather(return_exceptions=True)`). Never raises a `WarEraAPIError`; a whole request that
        fails gives its error to every call it carried. `on_final(key, outcome)`, when given, is called as
        soon as a call's outcome is final, so a caller need not wait for other calls' slot retries.
        """
        unique = list(dict.fromkeys(call.key for call in calls))
        by_key = {call.key: call for call in calls}
        outcomes = await self._run_unique([by_key[key] for key in unique])
        retries_left = self.transport.retry.max_attempts - 1
        for retry in range(retries_left + 1):
            # only slot errors of a 207: a whole request that failed was already retried by the transport
            failed = set() if retry == retries_left else {
                key for key in unique if isinstance(outcomes[key], ServerError) and outcomes[key].in_batch}
            if on_final is not None:
                for key in unique:
                    if key not in failed:
                        on_final(key, outcomes[key])
            unique = [key for key in unique if key in failed]
            if not unique:
                break
            await asyncio.sleep(self.transport.retry.delay(retry))
            outcomes.update(await self._run_unique([by_key[key] for key in unique]))
        self._log_failures(outcomes)
        return [outcomes[call.key] for call in calls]

    async def _run_unique(self, calls):
        chunks = self._chunks(calls)
        # return_exceptions: a bug in one chunk must not cancel the requests of the others
        results = await asyncio.gather(*(self._run_chunk(chunk) for chunk in chunks), return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException):
                raise result
        outcomes = {}
        for chunk, values in zip(chunks, results):
            for call, value in zip(chunk, values):
                outcomes[call.key] = value
        return outcomes

    def _chunks(self, calls):
        """Greedy packing by call count and estimated URL length; never an empty chunk."""
        budget = self.max_url_length - len(self.transport.base_url) - len('/?batch=1&input=%7B%7D')
        chunks, chunk, used = [], [], 0
        for call in calls:
            size = _encoded_length(call, len(chunk))
            if chunk and (len(chunk) >= self.chunk_size or used + size > budget):
                chunks.append(chunk)
                chunk, used = [], 0
                size = _encoded_length(call, 0)
            chunk.append(call)
            used += size
        if chunk:
            chunks.append(chunk)
        return chunks

    async def _run_chunk(self, chunk):
        label = chunk[0].procedure if len({call.procedure for call in chunk}) == 1 else 'batch'
        try:
            if len(chunk) == 1:
                return [await self._single(chunk[0])]
            path = ','.join(call.procedure for call in chunk)
            # like tRPC's own httpBatchLink, a call without input has no key, which the server reads as undefined
            params = {'batch': '1', 'input': json.dumps(
                {str(i): call.input for i, call in enumerate(chunk) if call.input is not None})}
            body = await self.transport.get(path, params, procedure=f'{label} x{len(chunk)}')
        except WarEraAPIError as error:
            return [error] * len(chunk)
        if not isinstance(body, list) or len(body) != len(chunk):
            error = InvalidResponseError(f'expected a list of {len(chunk)} envelopes', procedure=label)
            return [error] * len(chunk)
        return [_unwrap(envelope, call.procedure) for envelope, call in zip(body, chunk)]

    async def _single(self, call):
        params = {'input': json.dumps(call.input)} if call.input is not None else None
        body = await self.transport.get(call.procedure, params, procedure=call.procedure)
        return _unwrap(body, call.procedure, status=200)

    @staticmethod
    def _log_failures(outcomes):
        errors = [value for value in outcomes.values() if isinstance(value, WarEraAPIError)]
        if not errors:
            return
        counts = Counter(f'{e.procedure} {e.status or type(e).__name__}' for e in errors)
        logger.debug('WarEra batch: %d of %d calls failed: %s', len(errors), len(outcomes), dict(counts))


def _unwrap(envelope, procedure, status=207):
    """The `result.data` of one envelope, or the error it carries."""
    if not isinstance(envelope, dict):
        return InvalidResponseError('envelope is not an object', procedure=procedure, status=status)
    if 'error' in envelope:
        error = error_from_envelope(envelope, procedure=procedure, status=status)
        error.in_batch = status == 207
        return error
    result = envelope.get('result')
    if not isinstance(result, dict):
        return InvalidResponseError('envelope has neither result nor error', procedure=procedure, status=status)
    return result.get('data')


# Responses large enough (region map ~0.9 MB) that merging them would make the other calls wait for them
# and share their timeout; they are always sent on their own. ranking.getRanking left this list on
# 2026-11-16, when it stopped listing every entry (top 100 only).
SOLO_PROCEDURES = frozenset({'region.getRegionsObject'})


class Coalescer:
    """Merges calls made in the same event-loop iteration into one `Batcher.run`.

    `asyncio.gather(client.battles.get_active(), client.countries.get_all(), ...)` then costs one
    request instead of one per call, without the caller knowing about batching. A call waits at most
    until the loop has run the other ready tasks once, and gets its result as soon as it is final, not
    after other calls' retries. A lone call, and any call in `SOLO_PROCEDURES`, is sent on its own.
    """

    def __init__(self, batcher):
        """Flush through `batcher`."""
        self.batcher = batcher
        self._pending = []
        self._tasks = set()  # running flushes; the event loop keeps only weak references to tasks

    async def submit(self, call):
        """Queue `call` for the next flush and return its outcome (data or `WarEraAPIError`)."""
        future = asyncio.get_running_loop().create_future()
        if call.procedure in SOLO_PROCEDURES:
            self._start([(call, future)])
            return await future
        self._pending.append((call, future))
        if len(self._pending) == 1:
            # call_soon runs after every task that is already ready, so their calls join this batch
            asyncio.get_running_loop().call_soon(self._flush)
        return await future

    def _flush(self):
        pending, self._pending = self._pending, []
        self._start(pending)

    def _start(self, pending):
        task = asyncio.ensure_future(self._run(pending))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, pending):
        futures = {}
        for call, future in pending:
            futures.setdefault(call.key, []).append(future)

        def resolve(key, outcome):
            for future in futures.get(key, ()):
                if not future.done():
                    future.set_result(outcome)

        try:
            await self.batcher.run([call for call, _ in pending], on_final=resolve)
        except BaseException as error:  # a bug, not an API error: hand it to every caller still waiting
            for _, future in pending:
                if not future.done():
                    future.set_exception(error)
            if not isinstance(error, Exception):
                raise
