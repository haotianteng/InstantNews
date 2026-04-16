"""Add company_data_cache table for L2 database caching.

Stores company dimension data (details, financials, earnings,
competitors, institutional holdings, positions, insider transactions)
as JSON payloads with TTL-based expiration.

Revision ID: 012
Revises: 011
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_data_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("data_type", sa.String(30), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.String(), nullable=False),
        sa.Column("ttl_seconds", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "data_type", name="uq_cache_symbol_dtype"),
    )
    op.create_index("idx_cache_symbol", "company_data_cache", ["symbol"])
    op.create_index("idx_cache_fetched", "company_data_cache", ["fetched_at"])


def downgrade() -> None:
    op.drop_index("idx_cache_fetched", table_name="company_data_cache")
    op.drop_index("idx_cache_symbol", table_name="company_data_cache")
    op.drop_table("company_data_cache")
