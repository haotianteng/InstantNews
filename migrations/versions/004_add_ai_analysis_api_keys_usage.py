"""Add AI analysis columns to news, api_keys and api_usage tables.

Revision ID: 004
Revises: 003
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    # New columns on news table for AI analysis
    op.add_column("news", sa.Column("target_asset", sa.String(), nullable=True))
    op.add_column("news", sa.Column("asset_type", sa.String(), nullable=True))
    op.add_column("news", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("news", sa.Column("risk_level", sa.String(), nullable=True))
    op.add_column("news", sa.Column("tradeable", sa.Boolean(), nullable=True))
    op.add_column("news", sa.Column("reasoning", sa.Text(), nullable=True))
    op.add_column("news", sa.Column("ai_analyzed", sa.Boolean(), server_default=sa.text("false"), nullable=True))

    # API keys table
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False, server_default="Default"),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("last_used_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("idx_apikey_user", "api_keys", ["user_id"])
    op.create_index("idx_apikey_hash", "api_keys", ["key_hash"])

    # API usage tracking table
    op.create_table(
        "api_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("request_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "date", name="uq_usage_user_date"),
    )
    op.create_index("idx_usage_user_date", "api_usage", ["user_id", "date"])


def downgrade():
    op.drop_table("api_usage")
    op.drop_table("api_keys")
    op.drop_column("news", "ai_analyzed")
    op.drop_column("news", "reasoning")
    op.drop_column("news", "tradeable")
    op.drop_column("news", "risk_level")
    op.drop_column("news", "confidence")
    op.drop_column("news", "asset_type")
    op.drop_column("news", "target_asset")
