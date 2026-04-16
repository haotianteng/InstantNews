"""Shared test fixtures."""

from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app.config import TestConfig
from app.database import Base, get_engine
from app.models import News, Meta
from app.services.feed_parser import utc_iso


@pytest.fixture
def app():
    """Create a test Flask app with in-memory SQLite."""
    application = create_app(TestConfig)
    yield application

    # Clean up tables between tests since StaticPool shares the DB
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def session_factory(app):
    """Session factory bound to the test database."""
    return app.config["SESSION_FACTORY"]


@pytest.fixture
def db_session(session_factory):
    """A database session for direct DB manipulation in tests."""
    session = session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_news(session_factory):
    """Insert sample news items for query testing.

    Uses relative dates (today, yesterday, etc.) so tests don't break
    due to the free tier's 7-day history limit.
    """
    now = datetime.now(timezone.utc)
    today = utc_iso(now)
    yesterday = utc_iso(now - timedelta(hours=12))
    two_days = utc_iso(now - timedelta(days=2))
    three_days = utc_iso(now - timedelta(days=3))

    session = session_factory()
    items = [
        News(
            title="S&P 500 Surges to Record High",
            link="https://example.com/1",
            source="CNBC",
            published=today,
            fetched_at=today,
            summary="The S&P 500 rallied strongly on earnings.",
            sentiment_score=1.0,
            sentiment_label="bullish",
            tags="",
            duplicate=0,
        ),
        News(
            title="Oil Prices Crash Amid Recession Fears",
            link="https://example.com/2",
            source="Reuters_Business",
            published=yesterday,
            fetched_at=yesterday,
            summary="Oil declined sharply as recession fears mount.",
            sentiment_score=-1.0,
            sentiment_label="bearish",
            tags="",
            duplicate=0,
        ),
        News(
            title="Fed Holds Rates Steady",
            link="https://example.com/3",
            source="CNBC",
            published=two_days,
            fetched_at=two_days,
            summary="The Federal Reserve kept rates unchanged.",
            sentiment_score=0.0,
            sentiment_label="neutral",
            tags="",
            duplicate=0,
        ),
        News(
            title="Tech Stocks Jump on Strong Earnings",
            link="https://example.com/4",
            source="MarketWatch",
            published=three_days,
            fetched_at=three_days,
            summary="Technology sector climbed after better-than-expected results.",
            sentiment_score=0.5,
            sentiment_label="bullish",
            tags="",
            duplicate=0,
        ),
        News(
            title="S&P 500 Surges to Record High",
            link="https://example.com/5",
            source="MarketWatch",
            published=today,
            fetched_at=today,
            summary="Duplicate of CNBC story.",
            sentiment_score=1.0,
            sentiment_label="bullish",
            tags="",
            duplicate=1,
        ),
    ]
    for item in items:
        session.add(item)
    session.commit()
    session.close()
    return items
