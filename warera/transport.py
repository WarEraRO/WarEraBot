"""HTTP transport for the WarEra tRPC API: session, API key, timeouts, retries and rate limiting.

Every request is a GET. tRPC serves queries over GET and mutations only over POST, so this transport
cannot trigger a game action, and retrying a request can never repeat one.
"""
import asyncio
import email.utils
import json
import logging
import random
import time
from dataclasses import dataclass

import aiohttp

from warera.exceptions import (
    InvalidResponseError,
    NetworkError,
    RateLimitError,
    ServerError,
    WarEraAPIError,
    error_from_response,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = 'https://api2.warera.io/trpc'


@dataclass
class RetryPolicy:
    """When and how long to retry a request.

    `max_attempts` counts the first try. Delays grow as `initial_backoff * backoff_factor**n`, capped at
    `max_backoff` seconds, and each is scaled by a random factor in [0.5, 1] (jitter) so concurrent
    callers do not retry in lockstep. A 429's Retry-After is honoured instead, also capped.
    """

    max_attempts: int = 5
    initial_backoff: float = 1.0
    backoff_factor: float = 2.0
    max_backoff: float = 60.0

    def delay(self, attempt):
        """Return the jittered backoff in seconds before retry number `attempt` (0 for the first retry)."""
        base = min(self.initial_backoff * (self.backoff_factor ** attempt), self.max_backoff)
        return base * random.uniform(0.5, 1.0)


class RateLimiter:
    """Pauses new requests while the server's rate-limit window is exhausted.

    The API answers with `ratelimit-remaining` and `ratelimit-reset` (seconds until the window
    resets; 100 requests per 60 s were observed anonymously). When `remaining` reaches 0, or a 429
    arrives, requests wait until the reset instead of spending a 429 each. Without those headers it
    does nothing.
    """

    def __init__(self, clock=time.monotonic):
        """Start with no pause; `clock` is injectable for tests."""
        self._clock = clock
        self._resume_at = 0.0
        self.remaining = None

    def pause_for(self, seconds):
        """Hold every new request for at least `seconds` from now."""
        self._resume_at = max(self._resume_at, self._clock() + max(0.0, seconds))

    def update(self, headers):
        """Record the rate-limit headers of a response."""
        try:
            remaining = headers.get('ratelimit-remaining')
            if remaining is None:
                return
            self.remaining = int(remaining)
            if self.remaining <= 0:
                self.pause_for(float(headers.get('ratelimit-reset') or 1))
        except (TypeError, ValueError):
            return

    async def wait(self):
        """Sleep until the current pause, if any, is over."""
        # loop: another response may extend the pause while this request sleeps
        while (delay := self._resume_at - self._clock()) > 0:
            logger.info('WarEra rate limit window exhausted, waiting %.1fs', delay)
            await asyncio.sleep(delay)


def _retry_after_seconds(value):
    """Seconds from a Retry-After header (delta-seconds or HTTP date), or None when absent or unreadable."""
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(value)
        return max(0.0, when.timestamp() - time.time())
    except (TypeError, ValueError):
        return None


class Transport:
    """Sends GET requests to the tRPC server and returns the decoded JSON body.

    It owns one `aiohttp.ClientSession`, created on first use and recreated if closed. The API key goes
    in an `X-API-Key` header on each request, not in the session defaults, so it never reaches another
    host. `max_concurrency` caps requests in flight across the whole bot.
    """

    def __init__(self, base_url=DEFAULT_BASE_URL, api_key=None, *, timeout=60.0, retry=None,
                 max_concurrency=10, session=None):
        """Configure the transport.

        `timeout` is the total seconds per HTTP attempt (some responses are close to 1 MB). `session`
        injects an existing session, which `close()` then leaves open. `max_concurrency=None` removes the cap.
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.retry = retry or RetryPolicy()
        self.rate_limiter = RateLimiter()
        self._session = session
        self._owns_session = session is None
        self._semaphore = asyncio.Semaphore(max_concurrency) if max_concurrency else None
        self.request_count = 0

    @property
    def session(self):
        """The current session, creating it when there is none or it was closed."""
        if self._session is None or getattr(self._session, 'closed', False):
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
            self._owns_session = True
        return self._session

    @session.setter
    def session(self, session):
        """Use `session` from now on; the transport will not close it."""
        self._session = session
        self._owns_session = False

    async def close(self):
        """Close the session if this transport created it; a later request opens a new one.

        An injected session is left open and stays in use.
        """
        if not self._owns_session:
            return
        session, self._session = self._session, None
        if session is not None and not getattr(session, 'closed', False):
            await session.close()

    def _headers(self):
        return {'X-API-Key': self.api_key} if self.api_key else {}

    async def get(self, path, params=None, *, procedure=None):
        """GET `<base_url>/<path>` and return the decoded JSON body of a 200 or 207 response.

        `path` is one procedure or a comma-separated batch of them, `params` the query string, and
        `procedure` the name used in errors and logs. Network errors, timeouts, 429 and 5xx are retried
        per `retry`; other 4xx are raised at once.

        Raises:
            WarEraAPIError: the subclass matching the last failure (see `warera.exceptions`).
        """
        url = f'{self.base_url}/{path}'
        procedure = procedure or path
        attempt = 0
        while True:
            retry_after = None
            try:
                status, headers, body = await self._send(url, params)
            except UnicodeDecodeError as e:
                raise InvalidResponseError(f'undecodable body: {e}', procedure=procedure) from None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                error = NetworkError(f'{type(e).__name__}: {e}' if str(e) else type(e).__name__, procedure=procedure)
            else:
                if status in (200, 207):
                    try:
                        return json.loads(body)
                    except ValueError:
                        raise InvalidResponseError(f'non-JSON body: {body[:200]!r}', procedure=procedure, status=status) from None
                if status == 429:
                    retry_after = _retry_after_seconds(headers.get('Retry-After'))
                    error = error_from_response(status, body, procedure=procedure)
                    if not isinstance(error, RateLimitError):
                        error = RateLimitError(error.message, procedure=procedure, status=status)
                    error.retry_after = retry_after
                elif status >= 500:
                    error = error_from_response(status, body, procedure=procedure)
                    if not isinstance(error, ServerError):
                        error = ServerError(error.message, procedure=procedure, status=status, trpc_code=error.trpc_code)
                else:
                    raise error_from_response(status, body, procedure=procedure)

            attempt += 1
            if attempt >= self.retry.max_attempts:
                logger.warning('WarEra request failed after %d attempts: %s', attempt, error)
                raise error
            if retry_after is not None:
                wait = min(retry_after, self.retry.max_backoff)
            else:
                wait = self.retry.delay(attempt - 1)
            if isinstance(error, RateLimitError):
                self.rate_limiter.pause_for(wait)
            logger.warning('WarEra request %s failed (%s), retry %d in %.1fs', procedure, error, attempt, wait)
            await asyncio.sleep(wait)

    async def _send(self, url, params):
        """One HTTP attempt: (status, headers, body text). Waits for the concurrency cap, then the rate limiter."""
        if self._semaphore is None:
            return await self._send_now(url, params)
        async with self._semaphore:
            return await self._send_now(url, params)

    async def _send_now(self, url, params):
        # checked after taking a slot, so requests queued behind the cap still see a pause set meanwhile
        await self.rate_limiter.wait()
        self.request_count += 1
        async with self.session.get(url, params=params, headers=self._headers()) as response:
            self.rate_limiter.update(response.headers)
            body = await response.text()
            return response.status, response.headers, body


__all__ = ['DEFAULT_BASE_URL', 'RetryPolicy', 'RateLimiter', 'Transport', 'WarEraAPIError']
