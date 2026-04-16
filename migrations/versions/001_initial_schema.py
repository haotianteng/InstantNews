"""Initial schema — news and meta tables.

Revision ID: 001
Revises:
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("link", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("published", sa.String(), nullable=True),
        sa.Column("fetched_at", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("sentiment_score", sa.Float(), server_default="0", nullable=True),
        sa.Column("sentiment_label", sa.String(), server_default="'neutral'", nullable=True),
        sa.Column("tags", sa.String(), server_default="''", nullable=True),
        sa.Column("duplicate", sa.Integer(), server_default="0", nullable=True),
        sa.Column("embedding", sa.LargeBinary(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("link"),
        sa.UniqueConstraint("title", "source", name="idx_dedup_title_source"),
    )
    op.create_index("idx_published", "news", [sa.text("published DESC")])
    op.create_index("idx_fetched", "news", [sa.text("fetched_at DESC")])
    op.create_index("idx_source", "news", ["source"])
    op.create_index("idx_sentiment", "news", ["sentiment_label"])

    op.create_table(
        "meta",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("meta")
    op.drop_index("idx_sentiment", table_name="news")
    op.drop_index("idx_source", table_name="news")
    op.drop_index("idx_fetched", table_name="news")
    op.drop_index("idx_published", table_name="news")
    op.drop_table("news")
