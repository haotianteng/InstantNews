"""Add institutional_holders (13F quarterly snapshots).

Layer 3 of the normalized schema per ``tasks/todo_company_table.md`` §1.
Each row is one institution's reported holdings of one ticker on one
report date — i.e. a single line item from a 13F filing.

Append-only via UNIQUE on ``(ticker, institution_cik, report_date)`` —
re-ingesting the same 13F is rejected idempotently. Two secondary
indexes support the common read paths: "latest holders for a ticker" and
"largest holders by market value as of date".

Revision ID: 018
Revises: 017
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "institutional_holders",
        # BIGSERIAL on Postgres; SQLite maps BigInteger+autoincrement to
        # INTEGER autoinc which is fine for portability.
        sa.Column(
            "id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("institution_cik", sa.String(10), nullable=True),
        sa.Column("institution_name", sa.String(255), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("shares_held", sa.BigInteger(), nullable=True),
        sa.Column("market_value", sa.BigInteger(), nullable=True),
        sa.Column("pct_of_portfolio", sa.Numeric(6, 4), nullable=True),
        sa.Column("pct_of_company", sa.Numeric(6, 4), nullable=True),
        sa.Column("change_shares", sa.BigInteger(), nullable=True),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["companies.ticker"],
            name="fk_inst_ticker",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "ticker",
            "institution_cik",
            "report_date",
            name="uq_inst_ticker_cik_date",
        ),
    )

    op.create_index(
        "idx_inst_ticker_date",
        "institutional_holders",
        [sa.text("ticker"), sa.text("report_date DESC")],
    )
    op.create_index(
        "idx_inst_by_value",
        "institutional_holders",
        [
            sa.text("ticker"),
            sa.text("report_date DESC"),
            sa.text("market_value DESC"),
        ],
    )


def downgrade() -> None:
    op.drop_index("idx_inst_by_value", table_name="institutional_holders")
    op.drop_index("idx_inst_ticker_date", table_name="institutional_holders")
    op.drop_table("institutional_holders")
