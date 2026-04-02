#!/bin/bash
set -e

# Construct DATABASE_URL from components if not set directly
if [ -z "$DATABASE_URL" ] && [ -n "$DB_HOST" ]; then
  export DATABASE_URL="postgresql://${DB_USER:-signal}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT:-5432}/${DB_NAME:-signal_news}"
  echo "Constructed DATABASE_URL from DB_* env vars"
fi

echo "Running database migrations..."
alembic upgrade head

echo "Starting Nginx + Gunicorn via Supervisor..."
exec supervisord -c /etc/supervisor/conf.d/signal.conf
