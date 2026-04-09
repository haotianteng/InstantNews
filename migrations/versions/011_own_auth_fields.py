"""Add own email/password auth fields, remove Cognito.

- Add password_hash, email_verified columns
- Rename auth_provider → auth_method
- Drop cognito_sub column
- Set auth_method='google' for existing Firebase users

Revision ID: 011
Revises: 010
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))
    op.add_column("users", sa.Column("email_verified", sa.Boolean(),
                                      server_default="false", nullable=False))

    # Rename auth_provider → auth_method (add new, migrate data, drop old)
    op.add_column("users", sa.Column("auth_method", sa.String(),
                                      server_default="email", nullable=False))

    # Existing users with firebase_uid are Google OAuth users
    op.execute("UPDATE users SET auth_method = 'google' WHERE firebase_uid IS NOT NULL")
    # Existing WeChat users
    op.execute("UPDATE users SET auth_method = 'wechat' WHERE wechat_openid IS NOT NULL")
    # Mark existing Google users as email-verified (they used Google OAuth)
    op.execute("UPDATE users SET email_verified = true WHERE firebase_uid IS NOT NULL")

    # Drop old columns
    op.drop_column("users", "auth_provider")
    op.drop_index("idx_cognito_sub", table_name="users")
    op.drop_column("users", "cognito_sub")


def downgrade():
    op.add_column("users", sa.Column("cognito_sub", sa.String(), nullable=True))
    op.create_index("idx_cognito_sub", "users", ["cognito_sub"], unique=True)
    op.add_column("users", sa.Column("auth_provider", sa.String(),
                                      server_default="firebase", nullable=False))
    op.execute("UPDATE users SET auth_provider = auth_method")

    op.drop_column("users", "auth_method")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "password_hash")
