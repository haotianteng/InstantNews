"""Add audit_log table for admin action tracking.

Revision ID: 007
Revises: 006
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admin_user_id", sa.Integer(), nullable=False),
        sa.Column("admin_email", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_admin", "audit_log", ["admin_user_id"])
    op.create_index("idx_audit_created", "audit_log", ["created_at"])


def downgrade():
    op.drop_table("audit_log")
