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
    # Bedrock AI analysis fields
    target_asset = Column(String, nullable=True)       # ticker symbol
    asset_type = Column(String, nullable=True)         # STOCK, FUTURE, ETF, CURRENCY
    confidence = Column(Float, nullable=True)          # 0.0 to 1.0
    risk_level = Column(String, nullable=True)         # LOW, MEDIUM, HIGH
    tradeable = Column(Boolean, nullable=True)         # AI recommendation
    reasoning = Column(Text, nullable=True)            # AI reasoning chain
    ai_analyzed = Column(Boolean, default=False)       # whether Bedrock analysis completed

    __table_args__ = (
        UniqueConstraint("title", "source", name="idx_dedup_title_source"),
        Index("idx_published", published.desc()),
        Index("idx_fetched", fetched_at.desc()),
        Index("idx_source", "source"),
        Index("idx_sentiment", "sentiment_label"),
    )

    def to_dict(self):
        d = {
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
        if self.ai_analyzed:
            d["target_asset"] = self.target_asset
            d["asset_type"] = self.asset_type
            d["confidence"] = self.confidence
            d["risk_level"] = self.risk_level
            d["tradeable"] = self.tradeable
            d["reasoning"] = self.reasoning
        return d


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    firebase_uid = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    tier = Column(String, default="free", nullable=False)
    role = Column(String, default="user", nullable=False)  # user, admin, superadmin
    is_test_account = Column(Boolean, default=False, nullable=False)
    test_tier_override = Column(String, nullable=True)
    disabled = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(String, nullable=True)
    notes = Column(Text, nullable=True)        # admin notes (test accounts)
    expires_at = Column(String, nullable=True)  # auto-expire for test accounts
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "photo_url": self.photo_url,
            "tier": self.test_tier_override or self.tier if self.is_test_account else self.tier,
            "is_test_account": self.is_test_account,
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
        result = {
            "id": self.id,
            "status": self.status,
            "tier": self.tier,
            "current_period_start": self.current_period_start,
            "current_period_end": self.current_period_end,
            "cancel_at_period_end": self.cancel_at_period_end,
        }

        # Build a human-readable status label
        if self.status == "trialing":
            label = "Trial"
            if self.current_period_end:
                label += f" (ends {self.current_period_end[:10]})"
            result["status_label"] = label
            result["trial_end"] = self.current_period_end
        elif self.cancel_at_period_end and self.status == "active":
            label = "Canceling"
            if self.current_period_end:
                label += f" (access until {self.current_period_end[:10]})"
            result["status_label"] = label
            result["cancel_at"] = self.current_period_end
        elif self.status == "active":
            result["status_label"] = "Active"
        elif self.status == "past_due":
            result["status_label"] = "Past Due"
        elif self.status == "canceled":
            result["status_label"] = "Canceled"
        else:
            result["status_label"] = self.status.capitalize() if self.status else "Inactive"

        return result


class StripeEvent(Base):
    """Track processed Stripe webhook events for idempotency."""
    __tablename__ = "stripe_events"

    id = Column(String, primary_key=True)  # Stripe event ID (evt_...)
    type = Column(String, nullable=False)
    processed_at = Column(String, nullable=False)


class ApiKey(Base):
    """User-generated API keys for programmatic access."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False, default="Default")
    key_prefix = Column(String(8), nullable=False)      # first 8 chars, for display
    key_hash = Column(String, nullable=False, unique=True)  # SHA-256 hash
    created_at = Column(String, nullable=False)
    last_used_at = Column(String, nullable=True)

    __table_args__ = (
        Index("idx_apikey_user", "user_id"),
        Index("idx_apikey_hash", "key_hash"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
        }


class ApiUsage(Base):
    """Per-user API request counts, bucketed by date."""
    __tablename__ = "api_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    request_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_usage_user_date"),
        Index("idx_usage_user_date", "user_id", "date"),
    )


class AuditLog(Base):
    """Tracks all admin actions for compliance and debugging."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_user_id = Column(Integer, nullable=False)
    admin_email = Column(String, nullable=False)
    action = Column(String, nullable=False)  # e.g. "create_test_account", "update_tier", "update_role"
    target_user_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)   # JSON string with action details
    ip_address = Column(String, nullable=True)
    created_at = Column(String, nullable=False)

    __table_args__ = (
        Index("idx_audit_admin", "admin_user_id"),
        Index("idx_audit_created", "created_at"),
    )


class Meta(Base):
    __tablename__ = "meta"

    key = Column(String, primary_key=True)
    value = Column(Text)
