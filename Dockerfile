FROM python:3.12-slim AS base

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY server.py .
COPY app/ app/
COPY static/ static/
COPY alembic.ini .
COPY migrations/ migrations/

# Create data directory for SQLite (dev fallback)
RUN mkdir -p data

ENV PORT=8000
EXPOSE 8000

# Default: run migrations then start gunicorn
CMD ["sh", "-c", "alembic upgrade head && gunicorn --bind 0.0.0.0:${PORT} --workers 4 --timeout 120 --access-logfile - server:app"]
