"""In-memory response cache with per-procedure TTLs and single-flight request deduplication."""
import asyncio
import time


class ResponseCache:
    """Caches successful call results by (procedure, canonical input) for a per-procedure TTL.

    Only procedures listed in `ttls` (seconds) are stored; the rest are never cached, so freshness is
    opt-in per procedure. An expired entry is kept so `get_stale` can stand in when a refresh fails.
    Independently of the TTL, `single_flight` makes concurrent identical calls share one request.
    Errors are never cached.
    """

    def __init__(self, ttls=None, *, clock=time.monotonic):
        """Use `ttls` ({procedure: seconds}); `clock` is injectable for tests."""
        self.ttls = dict(ttls or {})
        self._clock = clock
        self._entries = {}
        self._in_flight = {}
        self.hits = 0
        self.misses = 0

    def ttl_for(self, procedure):
        """The TTL of `procedure` in seconds, or 0 when it is not cached."""
        return self.ttls.get(procedure, 0)

    def get(self, key):
        """Return (True, value) for a fresh entry, else (False, None)."""
        entry = self._entries.get(key)
        if entry is not None and self._clock() < entry[0]:
            self.hits += 1
            return True, entry[1]
        self.misses += 1
        return False, None

    def get_stale(self, key):
        """Return (True, value) for any stored entry, fresh or expired, else (False, None)."""
        entry = self._entries.get(key)
        return (True, entry[1]) if entry is not None else (False, None)

    def set(self, key, value):
        """Store `value` under `key` when its procedure (`key[0]`) has a TTL and `value` is not empty.

        An empty answer (None, {}, []) is not cached, so the next call asks again instead of serving
        it for a whole TTL.
        """
        ttl = self.ttl_for(key[0])
        if ttl > 0 and value:
            self._entries[key] = (self._clock() + ttl, value)

    async def single_flight(self, key, fetch):
        """Await `fetch()`, sharing one in-flight call among concurrent callers with the same `key`.

        The shared task is shielded, so one caller being cancelled does not cancel the request for the
        others. The result or exception of the shared call goes to every waiter.
        """
        task = self._in_flight.get(key)
        if task is None:
            task = asyncio.ensure_future(fetch())
            self._in_flight[key] = task
            task.add_done_callback(lambda _: self._in_flight.pop(key, None))
            # mark the exception retrieved even when every waiter was cancelled ("never retrieved" log)
            task.add_done_callback(lambda done: done.cancelled() or done.exception())
        return await asyncio.shield(task)

    def invalidate(self, procedure=None):
        """Drop cached entries of `procedure`, or every entry when `procedure` is None."""
        if procedure is None:
            self._entries.clear()
        else:
            for key in [key for key in self._entries if key[0] == procedure]:
                del self._entries[key]
