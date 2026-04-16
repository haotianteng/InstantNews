"""Seed superadmin role for initial admin account.

Revision ID: 009
Revises: 008
Create Date: 2026-04-07
"""
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE users SET role = 'superadmin' WHERE email = 'havens.teng@gmail.com'"
    )


def downgrade():
    op.execute(
        "UPDATE users SET role = 'user' WHERE email = 'havens.teng@gmail.com'"
    )
