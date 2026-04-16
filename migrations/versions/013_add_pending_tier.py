"""Add pending_tier column to subscriptions for scheduled downgrades.

Revision ID: 013
Revises: 012
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("subscriptions")]
    if "pending_tier" not in columns:
        op.add_column("subscriptions", sa.Column("pending_tier", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("subscriptions", "pending_tier")
