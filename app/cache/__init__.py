"""Cache subpackage — Redis client and key builders for the company info layer."""

from app.cache.redis_client import get_redis

__all__ = ["get_redis"]
