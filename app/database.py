"""Database engine and session management."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


_engine = None
_replica_engine = None
_SessionFactory = None
_ReplicaSessionFactory = None


def init_db(database_url: str):
    """Initialize the database engine and session factory."""
    global _engine, _SessionFactory

    connect_args = {}
    kwargs = {"pool_pre_ping": True}

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # For in-memory SQLite, use StaticPool so all connections share
        # the same database (required for tests and single-process use)
        if ":memory:" in database_url or database_url == "sqlite://":
            kwargs["poolclass"] = StaticPool

    # Connection pool for PostgreSQL — sized for 4 Gunicorn workers with
    # up to 10 ECS tasks.  db.t3.small supports ~150 max_connections, so
    # 10 pool + 20 overflow per worker (4 workers × 30 = 120) stays safe.
    # Configurable via DB_POOL_SIZE / DB_MAX_OVERFLOW env vars.
    if database_url.startswith("postgresql"):
        kwargs["pool_size"] = int(os.environ.get("DB_POOL_SIZE", "10"))
        kwargs["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", "20"))
        kwargs["pool_recycle"] = 300  # 5 min — prevent stale connections

    _engine = create_engine(
        database_url,
        connect_args=connect_args,
        **kwargs,
    )
    _SessionFactory = sessionmaker(bind=_engine)
    return _engine


def init_replica_db(database_url: str):
    """Initialize a read-only replica connection (for admin/analytics)."""
    global _replica_engine, _ReplicaSessionFactory

    kwargs = {"pool_pre_ping": True}
    if database_url.startswith("postgresql"):
        kwargs["pool_size"] = int(os.environ.get("DB_REPLICA_POOL_SIZE", "5"))
        kwargs["max_overflow"] = int(os.environ.get("DB_REPLICA_MAX_OVERFLOW", "10"))
        kwargs["pool_recycle"] = 300

    _replica_engine = create_engine(database_url, **kwargs)
    _ReplicaSessionFactory = sessionmaker(bind=_replica_engine)
    return _replica_engine


def get_engine():
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine


def get_session() -> Session:
    """Create a new session (primary DB). Caller is responsible for closing it."""
    if _SessionFactory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionFactory()


def get_replica_session() -> Session:
    """Create a read-only session (replica DB). Falls back to primary if no replica configured."""
    if _ReplicaSessionFactory is not None:
        return _ReplicaSessionFactory()
    return get_session()


def create_tables():
    """Create all tables from model metadata. For dev bootstrap only."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    Base.metadata.create_all(_engine)
