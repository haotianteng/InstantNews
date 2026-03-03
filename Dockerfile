FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY server.py .
COPY static/ static/

# Create data directory for SQLite
RUN mkdir -p data

# Environment
ENV PORT=8000
ENV DB_PATH=data/news_terminal.db
EXPOSE 8000

# Run with gunicorn (4 workers, 120s timeout for slow RSS fetches)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "--access-logfile", "-", "server:app"]
