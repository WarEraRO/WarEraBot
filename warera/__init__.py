"""Async client for the WarEra tRPC API (api2.warera.io).

Start with `WarEraClient`; see README.md in this folder for configuration, batching, caching and
errors. The bot's shared instance is `utils.api.warera`.
"""
from warera.batching import Call
from warera.client import DEFAULT_CACHE_TTLS, WarEraClient
from warera.exceptions import (
    AuthenticationError,
    InvalidResponseError,
    NetworkError,
    NotFoundError,
    ProcedureNotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
    WarEraAPIError,
)
from warera.transport import DEFAULT_BASE_URL, RetryPolicy

__all__ = [
    'AuthenticationError', 'Call', 'DEFAULT_BASE_URL', 'DEFAULT_CACHE_TTLS', 'InvalidResponseError', 'NetworkError',
    'NotFoundError', 'ProcedureNotFoundError', 'RateLimitError', 'RetryPolicy', 'ServerError', 'ValidationError',
    'WarEraAPIError', 'WarEraClient',
]
