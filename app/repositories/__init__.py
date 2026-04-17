"""Repository layer for the company-info domain.

Each repository wraps a single Postgres table (plus, where applicable, a
Redis cache) and returns Pydantic models — SQLAlchemy sessions and ORM
rows never leak past this package boundary. See
``app/repositories/base.py`` for the cache-aside ``BaseRepository[T]``
pattern that every concrete repo inherits from.
"""
