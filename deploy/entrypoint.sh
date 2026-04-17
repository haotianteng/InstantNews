#!/bin/bash

# Load secrets from Secrets Manager if not already set as env vars
# This covers keys added to Secrets Manager before the next cdk deploy
if [ -z "$APP_JWT_SECRET" ] && command -v python3 &>/dev/null; then
  echo "Loading missing secrets from Secrets Manager..."
  eval "$(python3 -c "
import json, os
try:
    import boto3
    client = boto3.client('secretsmanager', region_name='us-east-1')
    resp = client.get_secret_value(SecretId='instantnews/app')
    secrets = json.loads(resp['SecretString'])
    for key in ['APP_JWT_SECRET', 'WECHAT_APP_ID', 'WECHAT_APP_SECRET']:
        val = secrets.get(key, '')
        if val and not os.environ.get(key):
            print(f'export {key}=\"{val}\"')
except Exception as e:
    print(f'# Failed to load secrets: {e}', flush=True)
" 2>/dev/null)" || true
fi

# Construct DATABASE_URL from components if not set directly
if [ -z "$DATABASE_URL" ] && [ -n "$DB_HOST" ]; then
  export DATABASE_URL="postgresql://${DB_USER:-signal}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT:-5432}/${DB_NAME:-signal_news}"
  echo "Constructed DATABASE_URL from DB_* env vars"
fi

echo "Running database migrations..."
if alembic upgrade head 2>&1; then
  echo "Migrations completed successfully"
else
  echo "WARNING: Alembic migration failed — attempting manual schema fixes"
  # Fallback: add columns and tables via raw SQL if they don't exist
  python3 -c "
from sqlalchemy import create_engine, text
import os
engine = create_engine(os.environ['DATABASE_URL'])
with engine.begin() as conn:
    # Add columns to news if missing
    for col, typ in [
        ('target_asset', 'TEXT'),
        ('asset_type', 'TEXT'),
        ('confidence', 'DOUBLE PRECISION'),
        ('risk_level', 'TEXT'),
        ('tradeable', 'BOOLEAN'),
        ('reasoning', 'TEXT'),
        ('ai_analyzed', 'BOOLEAN DEFAULT false'),
    ]:
        try:
            conn.execute(text(f'ALTER TABLE news ADD COLUMN {col} {typ}'))
            print(f'  Added column news.{col}')
        except Exception as e:
            if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                print(f'  Column news.{col} already exists')
            else:
                print(f'  Error adding news.{col}: {e}')

    # Create api_keys table
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR NOT NULL DEFAULT 'Default',
            key_prefix VARCHAR(8) NOT NULL,
            key_hash VARCHAR NOT NULL UNIQUE,
            created_at VARCHAR NOT NULL,
            last_used_at VARCHAR
        )
    '''))
    print('  Table api_keys: OK')

    # Create api_usage table
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS api_usage (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            date VARCHAR(10) NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 0,
            UNIQUE (user_id, date)
        )
    '''))
    print('  Table api_usage: OK')

    # Update alembic version to 004 so future migrations work
    conn.execute(text(\"DELETE FROM alembic_version\"))
    conn.execute(text(\"INSERT INTO alembic_version (version_num) VALUES ('004')\"))
    print('  Alembic version set to 004')

print('Manual schema fixes completed')
" 2>&1
fi

if [ $# -eq 0 ]; then
  echo "Starting Nginx + Gunicorn via Supervisor..."
  exec supervisord -c /etc/supervisor/conf.d/signal.conf
else
  echo "Starting container command: $*"
  exec "$@"
fi
