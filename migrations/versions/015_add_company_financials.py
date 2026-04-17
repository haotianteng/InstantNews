"""Add company_financials (append-only seasonal) table.

Layer 2 of the normalized company schema per
``tasks/todo_company_table.md`` §1. Each row is a single filing
(Q1/Q2/Q3/Q4/FY) for a ticker, identified by the composite primary key
``(ticker, period_end, period_type)``. Re-ingesting the same period is
rejected by PK violation — this is the dedup strategy (no app-side logic
needed).

Foreign key ``ticker → companies(ticker) ON DELETE RESTRICT`` preserves
history if a master row is removed. Index ``idx_financials_period`` on
``(ticker, period_end DESC)`` supports the "latest N filings" read path.

Revision ID: 015
Revises: 014
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_financials",
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("period_type", sa.String(10), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        # Income statement
        sa.Column("revenue", sa.BigInteger(), nullable=True),
        sa.Column("gross_profit", sa.BigInteger(), nullable=True),
        sa.Column("operating_income", sa.BigInteger(), nullable=True),
        sa.Column("net_income", sa.BigInteger(), nullable=True),
        sa.Column("eps_basic", sa.Numeric(10, 4), nullable=True),
        sa.Column("eps_diluted", sa.Numeric(10, 4), nullable=True),
        # Balance sheet
        sa.Column("total_assets", sa.BigInteger(), nullable=True),
        sa.Column("total_liabilities", sa.BigInteger(), nullable=True),
        sa.Column("total_equity", sa.BigInteger(), nullable=True),
        sa.Column("cash_equivalents", sa.BigInteger(), nullable=True),
        sa.Column("long_term_debt", sa.BigInteger(), nullable=True),
        # Cash flow
        sa.Column("operating_cf", sa.BigInteger(), nullable=True),
        sa.Column("investing_cf", sa.BigInteger(), nullable=True),
        sa.Column("financing_cf", sa.BigInteger(), nullable=True),
        sa.Column("free_cash_flow", sa.BigInteger(), nullable=True),
        # Metadata
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint(
            "ticker", "period_end", "period_type", name="pk_company_financials"
        ),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["companies.ticker"],
            name="fk_financials_ticker",
            ondelete="RESTRICT",
        ),
    )

    # Descending period_end lets "latest N filings" queries pick the tail
    # cheaply. Wrap columns in sa.text() so we can pass the DESC order
    # modifier dialect-agnostically (SQLite tolerates, Postgres honors).
    op.create_index(
        "idx_financials_period",
        "company_financials",
        [sa.text("ticker"), sa.text("period_end DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_financials_period", table_name="company_financials")
    op.drop_table("company_financials")
