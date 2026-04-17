"""Add company_fundamentals + company_fundamentals_history (SCD-2).

Layer 2 of the normalized schema per ``tasks/todo_company_table.md`` §1.

Two tables:

* ``company_fundamentals`` — current snapshot, PK = ``ticker``. Callers
  always read here for "what's the latest PE ratio for AAPL?".
* ``company_fundamentals_history`` — append-only log of all previous
  snapshots, PK = ``(ticker, valid_from)``. Used for point-in-time
  queries ("what was AAPL's PE on 2025-03-01?").

The ``fn_snapshot_fundamentals_before_update`` trigger (Postgres only)
copies the OLD row from ``company_fundamentals`` into the history table
before each UPDATE — application code never needs to remember to
snapshot. On SQLite (local dev/tests) the trigger is skipped; callers
that need SCD-2 there can write the history row manually.

Revision ID: 016
Revises: 015
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_fundamentals",
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("market_cap", sa.BigInteger(), nullable=True),
        sa.Column("shares_outstanding", sa.BigInteger(), nullable=True),
        sa.Column("pe_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("pb_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("ev_ebitda", sa.Numeric(10, 4), nullable=True),
        sa.Column("dividend_yield", sa.Numeric(6, 4), nullable=True),
        sa.Column("beta", sa.Numeric(6, 4), nullable=True),
        sa.Column("next_earnings_date", sa.Date(), nullable=True),
        sa.Column("next_earnings_time", sa.String(10), nullable=True),  # BMO/AMC
        sa.Column("analyst_rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("price_target_mean", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("ticker", name="pk_company_fundamentals"),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["companies.ticker"],
            name="fk_fundamentals_ticker",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "company_fundamentals_history",
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("market_cap", sa.BigInteger(), nullable=True),
        sa.Column("shares_outstanding", sa.BigInteger(), nullable=True),
        sa.Column("pe_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("pb_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("ev_ebitda", sa.Numeric(10, 4), nullable=True),
        sa.Column("dividend_yield", sa.Numeric(6, 4), nullable=True),
        sa.Column("beta", sa.Numeric(6, 4), nullable=True),
        sa.Column("next_earnings_date", sa.Date(), nullable=True),
        sa.Column("next_earnings_time", sa.String(10), nullable=True),
        sa.Column("analyst_rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("price_target_mean", sa.Numeric(10, 2), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_to", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint(
            "ticker", "valid_from", name="pk_company_fundamentals_history"
        ),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["companies.ticker"],
            name="fk_fundamentals_history_ticker",
            ondelete="RESTRICT",
        ),
    )

    op.create_index(
        "idx_fundamentals_history_ticker_validto",
        "company_fundamentals_history",
        [sa.text("ticker"), sa.text("valid_to DESC")],
    )

    # Postgres SCD-2 trigger: copy OLD row into history before each UPDATE
    # so application code never has to remember to snapshot. SQLite cannot
    # express this pattern cleanly (PL/pgSQL, OLD/NEW aliases in the same
    # form) — skipped there; the corresponding repository will write the
    # history row manually on non-Postgres dialects.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION fn_snapshot_fundamentals_before_update()
            RETURNS TRIGGER AS $$
            BEGIN
                INSERT INTO company_fundamentals_history (
                    ticker, market_cap, shares_outstanding, pe_ratio, pb_ratio, ev_ebitda,
                    dividend_yield, beta, next_earnings_date, next_earnings_time,
                    analyst_rating, price_target_mean, updated_at,
                    valid_from, valid_to
                ) VALUES (
                    OLD.ticker, OLD.market_cap, OLD.shares_outstanding, OLD.pe_ratio, OLD.pb_ratio, OLD.ev_ebitda,
                    OLD.dividend_yield, OLD.beta, OLD.next_earnings_date, OLD.next_earnings_time,
                    OLD.analyst_rating, OLD.price_target_mean, OLD.updated_at,
                    OLD.updated_at, NOW()
                );
                NEW.updated_at := NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER fn_snapshot_fundamentals_before_update
            BEFORE UPDATE ON company_fundamentals
            FOR EACH ROW EXECUTE FUNCTION fn_snapshot_fundamentals_before_update();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    # Trigger first, then function, then tables — Postgres rejects dropping
    # a function that still has dependent triggers.
    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS fn_snapshot_fundamentals_before_update "
            "ON company_fundamentals"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS fn_snapshot_fundamentals_before_update()"
        )
    op.drop_index(
        "idx_fundamentals_history_ticker_validto",
        table_name="company_fundamentals_history",
    )
    op.drop_table("company_fundamentals_history")
    op.drop_table("company_fundamentals")
