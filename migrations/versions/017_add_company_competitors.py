"""Add company_competitors (directional similarity graph).

Layer 3 of the normalized schema per ``tasks/todo_company_table.md`` §1.
One row per ``(ticker, competitor_ticker)`` pair with a 0-1
``similarity_score``. The graph is directional — AAPL→MSFT can be weighted
differently than MSFT→AAPL.

Composite PK on ``(ticker, competitor_ticker)``; CHECK constraint rejects
self-references; both columns FK to ``companies(ticker)``.

Revision ID: 017
Revises: 016
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_competitors",
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("competitor_ticker", sa.String(10), nullable=False),
        sa.Column("similarity_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint(
            "ticker", "competitor_ticker", name="pk_company_competitors"
        ),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["companies.ticker"],
            name="fk_competitors_ticker",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["competitor_ticker"],
            ["companies.ticker"],
            name="fk_competitors_competitor_ticker",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "ticker != competitor_ticker", name="ck_competitors_no_self"
        ),
    )

    op.create_index(
        "idx_competitors_score",
        "company_competitors",
        [sa.text("ticker"), sa.text("similarity_score DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_competitors_score", table_name="company_competitors")
    op.drop_table("company_competitors")
