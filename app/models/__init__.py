"""SQLAlchemy models for the news database.

This module is a package (see ``app/models/__init__.py``). All legacy ORM
models live here so that ``from app.models import User, News, Subscription,
...`` continues to resolve unchanged after the package conversion.

Domain-specific **Pydantic** schemas live as sibling modules (e.g.
``app.models.company``) and are intentionally not re-exported from this
``__init__`` to keep the ORM/Pydantic namespaces separate. Import them
explicitly from their submodule::

    from app.models.company import Company   # Pydantic schema
    from app.models import Company           # SQLAlchemy ORM (defined below)
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
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
            "ai_analyzed": self.ai_analyzed or False,
            "target_asset": self.target_asset,
            "asset_type": self.asset_type,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "tradeable": self.tradeable,
            "reasoning": self.reasoning,
        }


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    firebase_uid = Column(String, unique=True, nullable=True)
    email = Column(String, unique=True, nullable=True)
    display_name = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    tier = Column(String, default="free", nullable=False)
    role = Column(String, default="user", nullable=False)  # user, admin, superadmin
    auth_method = Column(String, default="email", nullable=False)  # email, google, wechat
    password_hash = Column(String, nullable=True)      # bcrypt, only for auth_method="email"
    email_verified = Column(Boolean, default=False, nullable=False)
    wechat_openid = Column(String, unique=True, nullable=True)
    wechat_unionid = Column(String, nullable=True)
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
            "auth_method": self.auth_method,
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
    pending_tier = Column(String, nullable=True)  # scheduled downgrade tier
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
            "pending_tier": self.pending_tier,
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
        elif self.pending_tier and self.status == "active":
            label = f"Downgrading to {self.pending_tier.title()}"
            if self.current_period_end:
                label += f" (on {self.current_period_end[:10]})"
            result["status_label"] = label
            result["pending_downgrade"] = self.pending_tier
            result["downgrade_date"] = self.current_period_end
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


class CompanyDataCache(Base):
    __tablename__ = "company_data_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    data_type = Column(String(30), nullable=False)
    payload = Column(Text, nullable=False)
    fetched_at = Column(String, nullable=False)
    ttl_seconds = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "data_type", name="uq_cache_symbol_dtype"),
        Index("idx_cache_symbol", "symbol"),
        Index("idx_cache_fetched", "fetched_at"),
    )


class Company(Base):
    """Master reference row for a tradable company.

    Mirrors ``migrations/versions/014_add_companies_table.py``. Stable
    per-ticker data only — time-series metrics live in sibling tables
    (``company_financials``, ``company_fundamentals``, etc.).

    ``delisted_at`` is nullable — set it when a ticker is delisted so active
    scans (all scheduled jobs) can filter ``WHERE delisted_at IS NULL``
    without deleting historical rows. This matches OQ-5 in the PRD.
    """

    __tablename__ = "companies"

    ticker = Column(String(10), primary_key=True)
    cik = Column(String(10), unique=True, nullable=True)
    name = Column(String(255), nullable=False)
    exchange = Column(String(20), nullable=True)
    sector = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    country = Column(String(3), nullable=True)
    currency = Column(String(3), nullable=True)
    description = Column(Text, nullable=True)
    website = Column(String(255), nullable=True)
    employee_count = Column(Integer, nullable=True)
    founded_year = Column(Integer, nullable=True)
    ipo_date = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true", default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now())
    delisted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_companies_sector", "sector"),
        Index("idx_companies_industry", "industry"),
        # Partial index idx_companies_active is Postgres-specific and is
        # created by the Alembic migration under a dialect gate (SQLite
        # gets a plain index). Declaring it here would emit it through
        # Base.metadata.create_all for non-Postgres dialects, which is the
        # desired fallback; however we intentionally do NOT declare it here
        # because ``create_all`` is only used for SQLite test bootstraps
        # (tests/conftest.py) where a partial index on a non-populated
        # table is redundant. The Alembic migration is the source of truth
        # for index DDL against Postgres.
    )

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "cik": self.cik,
            "name": self.name,
            "exchange": self.exchange,
            "sector": self.sector,
            "industry": self.industry,
            "country": self.country,
            "currency": self.currency,
            "description": self.description,
            "website": self.website,
            "employee_count": self.employee_count,
            "founded_year": self.founded_year,
            "ipo_date": self.ipo_date.isoformat() if self.ipo_date else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "delisted_at": self.delisted_at.isoformat() if self.delisted_at else None,
        }


class CompanyFinancials(Base):
    """Append-only quarterly / annual filing row for a ticker.

    Mirrors ``migrations/versions/015_add_company_financials.py``. Composite
    primary key ``(ticker, period_end, period_type)`` is the dedup key;
    re-ingesting the same filing is rejected with a PK violation. All metric
    columns are nullable — upstream filings (EDGAR XBRL, Polygon) populate
    different subsets depending on the company.
    """

    __tablename__ = "company_financials"

    ticker = Column(String(10), nullable=False)
    period_end = Column(Date, nullable=False)
    period_type = Column(String(10), nullable=False)  # Q1/Q2/Q3/Q4/FY
    fiscal_year = Column(Integer, nullable=False)

    # Income statement
    revenue = Column(BigInteger, nullable=True)
    gross_profit = Column(BigInteger, nullable=True)
    operating_income = Column(BigInteger, nullable=True)
    net_income = Column(BigInteger, nullable=True)
    eps_basic = Column(Numeric(10, 4), nullable=True)
    eps_diluted = Column(Numeric(10, 4), nullable=True)

    # Balance sheet
    total_assets = Column(BigInteger, nullable=True)
    total_liabilities = Column(BigInteger, nullable=True)
    total_equity = Column(BigInteger, nullable=True)
    cash_equivalents = Column(BigInteger, nullable=True)
    long_term_debt = Column(BigInteger, nullable=True)

    # Cash flow
    operating_cf = Column(BigInteger, nullable=True)
    investing_cf = Column(BigInteger, nullable=True)
    financing_cf = Column(BigInteger, nullable=True)
    free_cash_flow = Column(BigInteger, nullable=True)

    # Metadata
    filing_date = Column(Date, nullable=True)
    source = Column(String(50), nullable=True)
    ingested_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        PrimaryKeyConstraint(
            "ticker", "period_end", "period_type", name="pk_company_financials"
        ),
        ForeignKeyConstraint(
            ["ticker"],
            ["companies.ticker"],
            name="fk_financials_ticker",
            ondelete="RESTRICT",
        ),
        # The Alembic migration creates idx_financials_period with a DESC
        # modifier on period_end. We intentionally do not re-declare it here
        # so ``Base.metadata.create_all`` (used only for SQLite test
        # bootstraps) doesn't try to emit dialect-specific index DDL.
    )


class CompanyFundamentals(Base):
    """Current-view fundamentals snapshot for a ticker.

    Mirrors ``migrations/versions/016_add_company_fundamentals.py``. PK is
    just ``ticker`` — there is one row per ticker. On each UPDATE, the
    Postgres trigger ``fn_snapshot_fundamentals_before_update`` copies the
    OLD row into ``company_fundamentals_history`` with the prior
    ``updated_at`` as ``valid_from`` and NOW() as ``valid_to``.
    """

    __tablename__ = "company_fundamentals"

    ticker = Column(String(10), primary_key=True)
    market_cap = Column(BigInteger, nullable=True)
    shares_outstanding = Column(BigInteger, nullable=True)
    pe_ratio = Column(Numeric(10, 4), nullable=True)
    pb_ratio = Column(Numeric(10, 4), nullable=True)
    ev_ebitda = Column(Numeric(10, 4), nullable=True)
    dividend_yield = Column(Numeric(6, 4), nullable=True)
    beta = Column(Numeric(6, 4), nullable=True)
    next_earnings_date = Column(Date, nullable=True)
    next_earnings_time = Column(String(10), nullable=True)  # BMO/AMC
    analyst_rating = Column(Numeric(3, 2), nullable=True)
    price_target_mean = Column(Numeric(10, 2), nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["ticker"],
            ["companies.ticker"],
            name="fk_fundamentals_ticker",
            ondelete="RESTRICT",
        ),
    )


class CompanyFundamentalsHistory(Base):
    """Append-only SCD-2 history rows for ``company_fundamentals``.

    Populated automatically by the Postgres trigger. Each row represents a
    snapshot that was valid during ``[valid_from, valid_to)``. PK is
    ``(ticker, valid_from)``; lookups are typically indexed by
    ``(ticker, valid_to DESC)``.
    """

    __tablename__ = "company_fundamentals_history"

    ticker = Column(String(10), nullable=False)
    market_cap = Column(BigInteger, nullable=True)
    shares_outstanding = Column(BigInteger, nullable=True)
    pe_ratio = Column(Numeric(10, 4), nullable=True)
    pb_ratio = Column(Numeric(10, 4), nullable=True)
    ev_ebitda = Column(Numeric(10, 4), nullable=True)
    dividend_yield = Column(Numeric(6, 4), nullable=True)
    beta = Column(Numeric(6, 4), nullable=True)
    next_earnings_date = Column(Date, nullable=True)
    next_earnings_time = Column(String(10), nullable=True)
    analyst_rating = Column(Numeric(3, 2), nullable=True)
    price_target_mean = Column(Numeric(10, 2), nullable=True)
    updated_at = Column(DateTime, nullable=True)
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "ticker", "valid_from", name="pk_company_fundamentals_history"
        ),
        ForeignKeyConstraint(
            ["ticker"],
            ["companies.ticker"],
            name="fk_fundamentals_history_ticker",
            ondelete="RESTRICT",
        ),
        # idx_fundamentals_history_ticker_validto (DESC) created by the
        # Alembic migration; not duplicated here for the same reason as
        # CompanyFinancials.
    )
