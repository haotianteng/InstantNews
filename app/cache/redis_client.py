"""Redis client singleton with a shared connection pool.

All repository code should call :func:`get_redis` rather than building its
own ``redis.Redis`` instance — this keeps the connection pool bounded and
gives us one place to plug in retries / TLS / sentinel config later.

The client is built lazily from ``Config.REDIS_URL`` (default
``redis://localhost:6379/0``) so tests and CLI scripts don't need a running
Redis to import app modules.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

import redis

_MAX_CONNECTIONS = 50

_client: Optional[redis.Redis] = None
_lock = threading.Lock()


def _resolve_url() -> str:
    """Resolve the Redis URL from app config / env with a safe default.

    We prefer ``Config.REDIS_URL`` so tests that set a custom ``TestConfig``
    are honored, but fall back to the env var + default for scripts and
    cold-path imports that run before ``create_app()``.
    """
    try:
        from app.config import Config

        url = getattr(Config, "REDIS_URL", None)
        if url:
            return str(url)
    except Exception:
        # During tooling imports Config may not be importable — fall through
        # to the env var path rather than crash.
        pass
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def get_redis() -> redis.Redis:
    """Return the process-wide :class:`redis.Redis` singleton.

    The client is created on first call with ``max_connections=50`` pooling
    and ``decode_responses=False`` (bytes in / bytes out — callers serialize
    JSON or msgpack explicitly).
    """
    global _client
    if _client is not None:
        return _client

    with _lock:
        if _client is None:
            pool = redis.ConnectionPool.from_url(
                _resolve_url(),
                max_connections=_MAX_CONNECTIONS,
                decode_responses=False,
            )
            _client = redis.Redis(connection_pool=pool)
    return _client


def reset_redis_client() -> None:
    """Testing helper — drop the cached singleton.

    Useful for tests that swap ``REDIS_URL`` between cases. Not called by
    production code.
    """
    global _client
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:
                pass
        _client = None
