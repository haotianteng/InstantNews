"""Add insider_transactions (SEC Form 4 / Form 5 events).

Layer 3 of the normalized schema per ``tasks/todo_company_table.md`` §1.
Each row is a single insider transaction reported via Form 4 (insider
buy/sell) or Form 5 (annual amendment).

Dedup beyond spec: UNIQUE on
``(ticker, insider_name, transaction_date, transaction_type, shares,
form_type)`` per the PRD's Q6 resolution — this makes re-ingesting the
same Form 4 a no-op via UNIQUE violation. We intentionally do not include
``price_per_share`` in the key because prices can differ by a cent
between data providers for the exact same transaction (SEC publishes to
4 decimals, some redistributors round).

Revision ID: 019
Revises: 018
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "insider_transactions",
        sa.Column(
            "id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("insider_name", sa.String(255), nullable=True),
        sa.Column("insider_title", sa.String(100), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=True),
        sa.Column("shares", sa.BigInteger(), nullable=True),
        sa.Column("price_per_share", sa.Numeric(10, 4), nullable=True),
        sa.Column("total_value", sa.BigInteger(), nullable=True),
        sa.Column("shares_owned_after", sa.BigInteger(), nullable=True),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("form_type", sa.String(10), nullable=True),
        sa.Column("sec_url", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["companies.ticker"],
            name="fk_insider_ticker",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "ticker",
            "insider_name",
            "transaction_date",
            "transaction_type",
            "shares",
            "form_type",
            name="uq_insider_txn_idempotent",
        ),
    )

    op.create_index(
        "idx_insider_ticker_date",
        "insider_transactions",
        [sa.text("ticker"), sa.text("transaction_date DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_insider_ticker_date", table_name="insider_transactions"
    )
    op.drop_table("insider_transactions")
