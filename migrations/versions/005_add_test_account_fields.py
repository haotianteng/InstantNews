"""Add test account fields to users table.

Revision ID: 005
Revises: 004
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_test_account", sa.Boolean(),
                                      server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("test_tier_override", sa.String(), nullable=True))


def downgrade():
    op.drop_column("users", "test_tier_override")
    op.drop_column("users", "is_test_account")
