"""Generic cache-aside repository base class.

Every concrete repository in this package inherits from
:class:`BaseRepository` parameterized with the Pydantic model it hands
out. The base class owns:

* ``cached_get`` / ``cached_get_list`` — read-through Redis cache keyed
  by an arbitrary string, with the caller supplying a DB loader that
  runs only on cache miss.
* ``invalidate`` / ``invalidate_pattern`` — write-side eviction. The
  pattern variant uses ``SCAN`` so it is safe on a busy Redis.

Design choices:

1. **Redis is non-critical.** Every Redis call is wrapped in a
   ``try/except`` that logs a warning and falls through to the DB. A
   Redis outage degrades latency but never breaks correctness.
2. **Bytes-in / bytes-out.** The shared client has
   ``decode_responses=False`` (see ``app/cache/redis_client.py``), so we
   serialize explicitly — ``model_dump_json()`` for single items,
   ``json.dumps([x.model_dump(mode='json') for x in items])`` for lists.
3. **Sync only.** Matches the rest of the Flask app. A future async
   migration can subclass without rewriting call sites.
"""

from __future__ import annotations

import json
import logging
from typing import Callable, Generic, Type, TypeVar

from pydantic import BaseModel

from app.cache.redis_client import get_redis

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger("signal.repo")


class BaseRepository(Generic[T]):
    """Cache-aside helper for a single Pydantic model type.

    Parameters
    ----------
    model_cls:
        The Pydantic class whose JSON payloads this repository caches.
        Used to ``model_validate`` / ``model_validate_json`` cached
        entries back into typed models.
    """

    def __init__(self, model_cls: Type[T]):
        self._model_cls = model_cls

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def cached_get(
        self, key: str, ttl: int, db_loader: Callable[[], T | None]
    ) -> T | None:
        """Return a single Pydantic model, checking Redis first.

        On cache hit the value is parsed via ``model_validate_json``
        without consulting the DB. On miss — or on any Redis error — the
        ``db_loader`` callable runs; if it returns a non-``None`` value
        the result is written back to Redis with ``SETEX``. Failures to
        write the cache are logged but do not propagate.
        """
        r = get_redis()
        try:
            raw = r.get(key)
            if raw is not None:
                # ``model_validate_json`` accepts both ``bytes`` and ``str``
                return self._model_cls.model_validate_json(raw)
        except Exception as e:  # pragma: no cover - exercised in tests via mock
            logger.warning("Redis get failed for %s: %s", key, e)

        value = db_loader()
        if value is not None:
            try:
                r.setex(key, ttl, value.model_dump_json())
            except Exception as e:
                logger.warning("Redis setex failed for %s: %s", key, e)
        return value

    def cached_get_list(
        self, key: str, ttl: int, db_loader: Callable[[], list[T]]
    ) -> list[T]:
        """Return a list of Pydantic models, checking Redis first.

        The list is serialized as a single JSON array so one ``GET``
        roundtrip recovers the whole collection. An empty list is still
        cached — that's a legitimate negative result.
        """
        r = get_redis()
        try:
            raw = r.get(key)
            if raw is not None:
                arr = json.loads(raw)
                return [self._model_cls.model_validate(x) for x in arr]
        except Exception as e:
            logger.warning("Redis get failed for %s: %s", key, e)

        items = db_loader()
        try:
            payload = json.dumps([x.model_dump(mode="json") for x in items])
            r.setex(key, ttl, payload)
        except Exception as e:
            logger.warning("Redis setex failed for %s: %s", key, e)
        return items

    # ------------------------------------------------------------------
    # Write helpers (eviction)
    # ------------------------------------------------------------------

    def invalidate(self, key: str) -> None:
        """Delete a single cache key. Errors are logged, never raised."""
        try:
            get_redis().delete(key)
        except Exception as e:
            logger.warning("Redis delete failed for %s: %s", key, e)

    def invalidate_pattern(self, pattern: str) -> int:
        """Delete every key matching ``pattern`` via ``SCAN``.

        Used for scoped invalidation where the exact key suffix (e.g.
        ``top10`` vs ``top20``) is unknown — compose a pattern like
        ``"company:AAPL:competitors:top*"`` and this method walks the
        keyspace non-blockingly.

        Returns the number of keys deleted (best-effort — errors are
        logged and a partial count is returned).
        """
        r = get_redis()
        count = 0
        try:
            for key in r.scan_iter(match=pattern, count=200):
                r.delete(key)
                count += 1
        except Exception as e:
            logger.warning("Redis scan/delete failed for %s: %s", pattern, e)
        return count
