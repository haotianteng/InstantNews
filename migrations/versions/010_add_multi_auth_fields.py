"""Add multi-provider auth fields (WeChat, Cognito) and make firebase_uid/email nullable.

Revision ID: 010
Revises: 009
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("wechat_openid", sa.String(), nullable=True))
    op.add_column("users", sa.Column("wechat_unionid", sa.String(), nullable=True))
    op.add_column("users", sa.Column("cognito_sub", sa.String(), nullable=True))
    op.add_column("users", sa.Column("auth_provider", sa.String(),
                                      server_default="firebase", nullable=False))

    op.create_index("idx_wechat_openid", "users", ["wechat_openid"], unique=True)
    op.create_index("idx_cognito_sub", "users", ["cognito_sub"], unique=True)

    # Make firebase_uid and email nullable for WeChat/Cognito users
    # PostgreSQL syntax — SQLite doesn't support ALTER COLUMN, but prod is PostgreSQL
    with op.get_context().autocommit_block():
        op.alter_column("users", "firebase_uid", existing_type=sa.String(),
                        nullable=True)
        op.alter_column("users", "email", existing_type=sa.String(),
                        nullable=True)


def downgrade():
    op.alter_column("users", "email", existing_type=sa.String(), nullable=False)
    op.alter_column("users", "firebase_uid", existing_type=sa.String(), nullable=False)

    op.drop_index("idx_cognito_sub", table_name="users")
    op.drop_index("idx_wechat_openid", table_name="users")

    op.drop_column("users", "auth_provider")
    op.drop_column("users", "cognito_sub")
    op.drop_column("users", "wechat_unionid")
    op.drop_column("users", "wechat_openid")
