# Database Migrations Guide

## Overview

InstantNews uses **Alembic** for database schema migrations. Migrations are versioned scripts in `migrations/versions/` that apply incremental schema changes.

- **Dev**: SQLite (`sqlite:///data/news_terminal.db`)
- **Prod**: PostgreSQL on RDS (private subnet, only accessible from ECS)

## Creating a New Migration

### 1. Write the migration script

```bash
# Create a new file in migrations/versions/
# Use sequential numbering: 005, 006, etc.
```

Example: `migrations/versions/005_add_new_feature.py`

```python
"""Add new feature table.

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
    # Add columns to existing table
    op.add_column("news", sa.Column("new_field", sa.String(), nullable=True))

    # Create new table
    op.create_table(
        "new_table",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )


def downgrade():
    op.drop_table("new_table")
    op.drop_column("news", "new_field")
```

### 2. Test locally against SQLite

```bash
# From project root
DATABASE_URL=sqlite:///data/test_migration.db alembic upgrade head
```

### 3. Test against PostgreSQL

```bash
# Start a test PostgreSQL
docker run --rm -d --name test_pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=testdb -p 5433:5432 postgres:15-alpine

# Wait a few seconds, then run migrations
sleep 3
DATABASE_URL=postgresql://postgres:test@localhost:5433/testdb alembic upgrade head

# Verify
DATABASE_URL=postgresql://postgres:test@localhost:5433/testdb alembic current

# Test downgrade + re-upgrade (idempotency)
DATABASE_URL=postgresql://postgres:test@localhost:5433/testdb alembic downgrade -1
DATABASE_URL=postgresql://postgres:test@localhost:5433/testdb alembic upgrade head

# Cleanup
docker stop test_pg
```

### 4. Deploy to production

Migrations run automatically on container start via `deploy/entrypoint.sh`:

```bash
# Build and push Docker image
cd frontend && npx vite build
docker build -f Dockerfile.prod -t instantnews:latest .
docker tag instantnews:latest 596080539716.dkr.ecr.us-east-1.amazonaws.com/instantnews:latest
docker push 596080539716.dkr.ecr.us-east-1.amazonaws.com/instantnews:latest

# Deploy (migration runs on container start)
aws ecs update-service --cluster instantnews \
  --service InstantNewsStack-WebService5EA589E6-CfUW4VYKPEtz \
  --desired-count 2 --force-new-deployment
```

The entrypoint runs `alembic upgrade head` before starting the app. If the migration fails, the entrypoint falls back to raw SQL to ensure the app can start.

## Best Practices

### PostgreSQL Compatibility
- Use `sa.text("false")` for boolean server defaults, not `"false"`
- Use `sa.PrimaryKeyConstraint("id")` instead of `primary_key=True` in `create_table`
- Use `sa.ForeignKeyConstraint(["col"], ["table.col"])` instead of `sa.ForeignKey()`
- Always test against PostgreSQL before deploying (not just SQLite)

### Migration Safety
- **Always write downgrade()** — allows rollback if something goes wrong
- **One logical change per migration** — don't mix unrelated schema changes
- **Never modify existing migrations** — create a new one instead
- **Test idempotency** — downgrade then re-upgrade should work cleanly
- **Use `nullable=True`** for new columns on existing tables (avoids data issues)

### Production Considerations
- RDS is in a private subnet — can't run migrations from local machine
- Migrations run inside the ECS container on startup
- Both web and worker containers run migrations (first one wins, second is a no-op)
- If migration fails, check CloudWatch logs: `/ecs/instantnews-web`
- The entrypoint has a fallback that applies raw SQL if alembic fails

### Current Migration History

| Version | Description | Date |
|---------|-------------|------|
| 001 | Initial schema (news, meta) | 2026-03 |
| 002 | Add users table | 2026-03 |
| 003 | Add subscriptions, stripe_events | 2026-03 |
| 004 | Add AI analysis columns, api_keys, api_usage | 2026-04 |

## Useful Commands

```bash
# Check current version
alembic current

# Show migration history
alembic history

# Upgrade to latest
alembic upgrade head

# Upgrade to specific version
alembic upgrade 004

# Downgrade one step
alembic downgrade -1

# Downgrade to specific version
alembic downgrade 003

# Show SQL without executing (dry run)
alembic upgrade head --sql
```
