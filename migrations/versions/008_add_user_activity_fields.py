"""Add user activity and test account management fields.

Revision ID: 008
Revises: 007
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("disabled", sa.Boolean(),
                                      server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("last_login_at", sa.String(), nullable=True))
    op.add_column("users", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("expires_at", sa.String(), nullable=True))


def downgrade():
    op.drop_column("users", "expires_at")
    op.drop_column("users", "notes")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "disabled")
