"""Tests for SQLAlchemy models."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import News, Meta


class TestNewsModel:
    def test_create_and_query(self, db_session):
        news = News(
            title="Test News",
            link="https://example.com/test",
            source="TestSource",
            published="2026-03-20T10:00:00+00:00",
            fetched_at="2026-03-20T10:01:00+00:00",
            summary="Test summary",
        )
        db_session.add(news)
        db_session.commit()

        result = db_session.query(News).filter_by(title="Test News").first()
        assert result is not None
        assert result.source == "TestSource"
        assert result.sentiment_score == 0.0
        assert result.sentiment_label == "neutral"
        assert result.duplicate == 0

    def test_link_unique_constraint(self, db_session):
        n1 = News(title="A", link="https://example.com/dup", source="S1")
        n2 = News(title="B", link="https://example.com/dup", source="S2")
        db_session.add(n1)
        db_session.commit()
        db_session.add(n2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_title_source_unique_constraint(self, db_session):
        n1 = News(title="Same Title", link="https://example.com/a", source="CNBC")
        n2 = News(title="Same Title", link="https://example.com/b", source="CNBC")
        db_session.add(n1)
        db_session.commit()
        db_session.add(n2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_to_dict(self, db_session):
        news = News(
            title="Dict Test",
            link="https://example.com/dict",
            source="S",
            published="2026-03-20T10:00:00+00:00",
            fetched_at="2026-03-20T10:01:00+00:00",
            summary="Summary",
            sentiment_score=0.5,
            sentiment_label="bullish",
            duplicate=1,
        )
        db_session.add(news)
        db_session.commit()

        d = news.to_dict()
        assert d["title"] == "Dict Test"
        assert d["sentiment_label"] == "bullish"
        assert d["duplicate"] == 1
        assert "embedding" not in d


class TestMetaModel:
    def test_crud(self, db_session):
        meta = Meta(key="test_key", value="test_value")
        db_session.add(meta)
        db_session.commit()

        result = db_session.query(Meta).filter_by(key="test_key").first()
        assert result.value == "test_value"

        result.value = "updated"
        db_session.commit()
        assert db_session.query(Meta).filter_by(key="test_key").first().value == "updated"
