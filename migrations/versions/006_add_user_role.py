"""Add role column to users table.

Revision ID: 006
Revises: 005
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("role", sa.String(),
                                      server_default="user", nullable=False))


def downgrade():
    op.drop_column("users", "role")
