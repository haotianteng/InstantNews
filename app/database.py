"""Database engine and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


_engine = None
_SessionFactory = None


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

    # Limit connection pool for PostgreSQL (db.t3.micro has ~25 max connections)
    if database_url.startswith("postgresql"):
        kwargs["pool_size"] = 2
        kwargs["max_overflow"] = 3
        kwargs["pool_recycle"] = 300

    _engine = create_engine(
        database_url,
        connect_args=connect_args,
        **kwargs,
    )
    _SessionFactory = sessionmaker(bind=_engine)
    return _engine


def get_engine():
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine


def get_session() -> Session:
    """Create a new session. Caller is responsible for closing it."""
    if _SessionFactory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionFactory()


def create_tables():
    """Create all tables from model metadata. For dev bootstrap only."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    Base.metadata.create_all(_engine)
