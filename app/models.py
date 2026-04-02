"""SQLAlchemy models for the news database."""

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Index,
)

from app.database import Base


class News(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    link = Column(String, unique=True)
    source = Column(String)
    published = Column(String)  # ISO 8601 text for backward compat
    fetched_at = Column(String)
    summary = Column(Text)
    sentiment_score = Column(Float, default=0.0)
    sentiment_label = Column(String, default="neutral")
    tags = Column(String, default="")
    duplicate = Column(Integer, default=0)
    embedding = Column(LargeBinary, nullable=True)

    __table_args__ = (
        UniqueConstraint("title", "source", name="idx_dedup_title_source"),
        Index("idx_published", published.desc()),
        Index("idx_fetched", fetched_at.desc()),
        Index("idx_source", "source"),
        Index("idx_sentiment", "sentiment_label"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "source": self.source,
            "published": self.published,
            "fetched_at": self.fetched_at,
            "summary": self.summary,
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
            "tags": self.tags,
            "duplicate": self.duplicate,
        }


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    firebase_uid = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    tier = Column(String, default="free", nullable=False)
    created_at = Column(String, nullable=False)  # ISO 8601
    updated_at = Column(String, nullable=False)  # ISO 8601

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "photo_url": self.photo_url,
            "tier": self.tier,
            "created_at": self.created_at,
        }


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, unique=True, nullable=True)
    stripe_price_id = Column(String, nullable=True)
    status = Column(String, default="inactive", nullable=False)  # active, past_due, canceled, inactive
    tier = Column(String, default="free", nullable=False)
    current_period_start = Column(String, nullable=True)  # ISO 8601
    current_period_end = Column(String, nullable=True)    # ISO 8601
    cancel_at_period_end = Column(Boolean, default=False)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    __table_args__ = (
        Index("idx_sub_user", "user_id"),
        Index("idx_sub_stripe_customer", "stripe_customer_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "tier": self.tier,
            "current_period_start": self.current_period_start,
            "current_period_end": self.current_period_end,
            "cancel_at_period_end": self.cancel_at_period_end,
        }


class StripeEvent(Base):
    """Track processed Stripe webhook events for idempotency."""
    __tablename__ = "stripe_events"

    id = Column(String, primary_key=True)  # Stripe event ID (evt_...)
    type = Column(String, nullable=False)
    processed_at = Column(String, nullable=False)


class Meta(Base):
    __tablename__ = "meta"

    key = Column(String, primary_key=True)
    value = Column(Text)
