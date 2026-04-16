"""Backward-compatible entry point.

Usage:
    Development:  python server.py
    Production:   gunicorn -w 4 -b 0.0.0.0:8000 server:app
    Docker:       docker compose up -d
"""

import logging
import os
from pathlib import Path

# Load .env file for local development (no-op if python-dotenv not installed)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    logger = logging.getLogger("signal")
    port = int(os.environ.get("PORT", "8000"))
    logger.info("Starting SIGNAL News Terminal on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False)
