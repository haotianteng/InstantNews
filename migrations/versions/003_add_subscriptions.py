"""Add subscriptions and stripe_events tables.

Revision ID: 003
Revises: 002
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
        sa.Column("stripe_price_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="'inactive'", nullable=False),
        sa.Column("tier", sa.String(), server_default="'free'", nullable=False),
        sa.Column("current_period_start", sa.String(), nullable=True),
        sa.Column("current_period_end", sa.String(), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default="0", nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_subscription_id"),
    )
    op.create_index("idx_sub_user", "subscriptions", ["user_id"])
    op.create_index("idx_sub_stripe_customer", "subscriptions", ["stripe_customer_id"])

    op.create_table(
        "stripe_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("processed_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("stripe_events")
    op.drop_index("idx_sub_stripe_customer", table_name="subscriptions")
    op.drop_index("idx_sub_user", table_name="subscriptions")
    op.drop_table("subscriptions")
