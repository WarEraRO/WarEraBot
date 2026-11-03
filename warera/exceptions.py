"""Exceptions raised by the WarEra API client.

Every error is a `WarEraAPIError`. `status` is the HTTP status (or a batched item's `data.httpStatus`),
and `trpc_code` is the tRPC `error.data.code` ("NOT_FOUND", "BAD_REQUEST", ...). `trpc_code` is None
when the server answered without a tRPC error envelope, for example an HTML page from a proxy, so
`is_trpc_error` tells a tRPC application error from a plain HTTP error.
"""
import json


class WarEraAPIError(Exception):
    """Base class of every error the client raises."""

    def __init__(self, message, *, procedure=None, status=None, trpc_code=None):
        """Build the error; `procedure`, `status` and `trpc_code` may be None when not known."""
        super().__init__(message)
        self.message = message
        self.procedure = procedure
        self.status = status
        self.trpc_code = trpc_code
        # True for an error read from one slot of a batched (207) response
        self.in_batch = False

    @property
    def is_trpc_error(self):
        """True when the server answered with a tRPC error envelope."""
        return self.trpc_code is not None

    def __str__(self):
        parts = [self.procedure or '?']
        if self.status is not None:
            parts.append(str(self.status))
        if self.trpc_code:
            parts.append(self.trpc_code)
        return f"{' '.join(parts)}: {self.message}"


class NetworkError(WarEraAPIError):
    """The request never got an HTTP answer: connection failure or timeout."""


class InvalidResponseError(WarEraAPIError):
    """The server answered, but not with the JSON shape tRPC uses."""


class ValidationError(WarEraAPIError):
    """400 BAD_REQUEST: the input failed the server's zod validation. `message` is the zod issue list as JSON."""


class AuthenticationError(WarEraAPIError):
    """401 or 403: the procedure needs an API key, or the key may not read it."""


class NotFoundError(WarEraAPIError):
    """404 for an entity that does not exist ("Countries not found.") or a user with no data."""


class ProcedureNotFoundError(NotFoundError):
    """404 `No procedure found on path`: the procedure does not exist, usually removed by a game patch."""


class RateLimitError(WarEraAPIError):
    """429: the rate limit was exceeded and retries ran out. `retry_after` is in seconds, or None."""

    def __init__(self, message, *, retry_after=None, **kwargs):
        """Build the error; `retry_after` is the server's Retry-After in seconds, or None."""
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ServerError(WarEraAPIError):
    """5xx: the server failed. Retried by the client before it is raised."""


_BY_TRPC_CODE = {
    'BAD_REQUEST': ValidationError,
    'PARSE_ERROR': ValidationError,
    'UNAUTHORIZED': AuthenticationError,
    'FORBIDDEN': AuthenticationError,
    'NOT_FOUND': NotFoundError,
    'TOO_MANY_REQUESTS': RateLimitError,
    'INTERNAL_SERVER_ERROR': ServerError,
}


def _class_for_status(status):
    if status == 400:
        return ValidationError
    if status in (401, 403):
        return AuthenticationError
    if status == 404:
        return NotFoundError
    if status == 429:
        return RateLimitError
    if status is not None and status >= 500:
        return ServerError
    return WarEraAPIError


def error_from_envelope(envelope, *, procedure=None, status=None):
    """Return the exception for one tRPC error envelope `{"error": {"message", "code", "data": {...}}}`.

    `status` is the HTTP status of the response; a batched item's own `data.httpStatus` wins over it.
    The class follows the tRPC code when there is one, else the status.
    """
    error = (envelope or {}).get('error') if isinstance(envelope, dict) else None
    if not isinstance(error, dict):
        error = {}
    data = error.get('data') if isinstance(error.get('data'), dict) else {}
    status = data.get('httpStatus', status)
    trpc_code = data.get('code')
    message = error.get('message') or f'HTTP {status}'
    procedure = data.get('path') or procedure
    if status == 404 and str(message).startswith('No procedure found'):
        cls = ProcedureNotFoundError
    else:
        cls = _BY_TRPC_CODE.get(trpc_code) or _class_for_status(status)
    return cls(message, procedure=procedure, status=status, trpc_code=trpc_code)


def error_from_response(status, body, *, procedure=None):
    """Return the exception for a non-2xx response whose raw text is `body`.

    A tRPC error envelope gives the message and code; any other body is kept, cut to 300 characters,
    as the message of a plain HTTP error.
    """
    try:
        parsed = json.loads(body) if body else None
    except ValueError:
        parsed = None
    if isinstance(parsed, list) and parsed:
        # a batch whose calls all failed the same way answers that status with one envelope per call
        parsed = parsed[0]
    if isinstance(parsed, dict) and isinstance(parsed.get('error'), dict):
        return error_from_envelope(parsed, procedure=procedure, status=status)
    message = (body or '').strip()[:300] or f'HTTP {status}'
    return _class_for_status(status)(message, procedure=procedure, status=status)
