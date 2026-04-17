"""Add companies master reference table.

Creates the ``companies`` table (Layer 1 of the normalized company schema
per ``tasks/todo_company_table.md`` §1) plus a nullable ``delisted_at``
column per OQ-5 in the PRD. Three indexes:

  * ``idx_companies_sector``  — lookup by sector
  * ``idx_companies_industry`` — lookup by industry
  * ``idx_companies_active``  — partial index on ``ticker WHERE delisted_at
                                 IS NULL`` (Postgres only; SQLite gets a
                                 plain index via a dialect gate so local
                                 tests don't blow up).

Revision ID: 014
Revises: 013
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("cik", sa.String(10), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("exchange", sa.String(20), nullable=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("country", sa.String(3), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.Column("ipo_date", sa.Date(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Extra per OQ-5: keep delisted tickers as rows but let scheduled
        # jobs filter them out with WHERE delisted_at IS NULL.
        sa.Column("delisted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("ticker", name="pk_companies"),
        sa.UniqueConstraint("cik", name="uq_companies_cik"),
    )

    op.create_index("idx_companies_sector", "companies", ["sector"])
    op.create_index("idx_companies_industry", "companies", ["industry"])

    # Partial index is Postgres-only. Fall back to a plain index on other
    # dialects (primarily SQLite for local dev/tests) so the migration is
    # portable — the index still helps even without the predicate.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            "idx_companies_active",
            "companies",
            ["ticker"],
            postgresql_where=sa.text("delisted_at IS NULL"),
        )
    else:
        op.create_index("idx_companies_active", "companies", ["ticker"])


def downgrade() -> None:
    op.drop_index("idx_companies_active", table_name="companies")
    op.drop_index("idx_companies_industry", table_name="companies")
    op.drop_index("idx_companies_sector", table_name="companies")
    op.drop_table("companies")
