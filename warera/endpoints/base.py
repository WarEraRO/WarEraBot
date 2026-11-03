"""Shared plumbing for the endpoint groups: safe single calls, keyed batches and cursor pagination.

High-level endpoint methods never raise. They return None (or, for batches, leave the failed keys out
of the dict) and log the failure, which is the contract the cogs were written against; `guarded` also
turns an unexpected exception into that result, logged with its traceback. Code that needs the
exception calls `WarEraClient.call` directly.
"""
import functools
import logging

from warera.exceptions import NotFoundError, ProcedureNotFoundError, WarEraAPIError

logger = logging.getLogger('warera')


def guarded(default=None):
    """Decorate an endpoint method so an unexpected exception is logged with its traceback and gives `default()`.

    This covers the method's own parsing: when the game changes a response shape (as v0.27 did), a
    KeyError or TypeError there must not escape and stop a `discord.ext.tasks` loop. `default` is a
    zero-argument factory (`dict`, `list`) or None. Cancellation is never caught.
    """
    def decorate(method):
        @functools.wraps(method)
        async def wrapper(self, *args, **kwargs):
            try:
                return await method(self, *args, **kwargs)
            except Exception:
                logger.exception('%s.%s crashed', type(self).__name__, method.__name__)
                return default() if default is not None else None
        return wrapper
    return decorate

def log_failure(where, error, expected=()):
    """Log a failed call at debug when its error class is in `expected`, else at error.

    A removed procedure (`ProcedureNotFoundError`) is always an error: every feature built on it
    would otherwise fall back to its "unavailable" message without anyone noticing.
    """
    if isinstance(error, expected) and not isinstance(error, ProcedureNotFoundError):
        logger.debug('%s: %s', where, error)
    else:
        logger.error('%s failed: %s', where, error)


def _accept(value, kind, allow_empty):
    if kind is not None and not isinstance(value, kind):
        return False
    if isinstance(value, bool):
        return kind is bool
    return allow_empty or bool(value)


class Endpoint:
    """Base of an endpoint group; `self.client` is the owning `WarEraClient`."""

    def __init__(self, client):
        """Bind the group to `client`."""
        self.client = client

    async def _get(self, procedure, input=None, *, kind=dict, allow_empty=False, expected=(NotFoundError,)):
        """`result.data` of one call, or None when it failed, is not a `kind` (None: any type) or is empty.

        `allow_empty` keeps an empty dict or list. Failures of the `expected` classes are logged at debug.
        """
        try:
            data = await self.client.call(procedure, input)
        except WarEraAPIError as error:
            log_failure(procedure, error, expected)
            return None
        return data if _accept(data, kind, allow_empty) else None

    async def _get_keyed(self, procedure, keys, make_input, *, kind=dict, expected=(NotFoundError,)):
        """Batched calls of `procedure`, one per distinct key: {key: data} for the calls that resolved.

        `make_input(key)` builds each call's input. A failed call, or a result that is empty or not a
        `kind`, leaves its key out, so callers can't tell "missing" from "failed", as before.
        """
        keys = list(dict.fromkeys(keys))
        if not keys:
            return {}
        values = await self.client.call_many(procedure, [make_input(key) for key in keys])
        result = {}
        failures = []
        for key, value in zip(keys, values):
            if isinstance(value, WarEraAPIError):
                failures.append(value)
            elif _accept(value, kind, False):
                result[key] = value
        unexpected = [e for e in failures if not isinstance(e, expected) or isinstance(e, ProcedureNotFoundError)]
        if unexpected:
            logger.error('%s: %d of %d calls failed, first: %s', procedure, len(unexpected), len(keys), unexpected[0])
        return result

    async def _pages(self, procedure, input, *, stop_page=None, max_items=None):
        """Every page's items, following `nextCursor`, as (items, error, pages_read).

        Paging stops after a page for which `stop_page(page_items)` is true, or once `max_items` items
        were read. `stop_page` must be a pure predicate: it is not called for the last page. `error` is the `WarEraAPIError` of the page that failed, or None when paging ended
        normally; `items` then holds the pages read before it.
        """
        data = dict(input)
        items = []
        pages_read = 0
        while True:
            try:
                page = await self.client.call(procedure, data)
            except WarEraAPIError as error:
                return items, error, pages_read
            pages_read += 1
            page = page if isinstance(page, dict) else {}
            page_items = page.get('items') or []
            items += page_items
            cursor = page.get('nextCursor')
            if not cursor or (stop_page and stop_page(page_items)) or (max_items is not None and len(items) >= max_items):
                return items, None, pages_read
            data['cursor'] = cursor

    async def _collect(self, procedure, input, *, partial, stop_page=None, max_items=None):
        """`_pages` as a list, or None when the first page failed (or any page, unless `partial`).

        With `partial`, a later page that fails ends the list early; the failure is still logged.
        """
        items, error, pages_read = await self._pages(procedure, input, stop_page=stop_page, max_items=max_items)
        if error is None:
            return items
        log_failure(procedure, error)
        return items if partial and pages_read else None

    async def _collect_since(self, procedure, input, created_after):
        """Items created at or after `created_after` (ISO string) from a newest-first listing; None if any page fails.

        Paging stops at the first older item, so a partial list never hides items.
        """
        def reached_older(page_items):
            return any(str(item.get('createdAt') or '') < created_after for item in page_items)

        items, error, _ = await self._pages(procedure, input, stop_page=reached_older)
        if error is not None:
            log_failure(procedure, error)
            return None
        recent = []
        for item in items:
            if str(item.get('createdAt') or '') < created_after:
                break
            recent.append(item)
        return recent
