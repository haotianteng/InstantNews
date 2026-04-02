"""Backward-compatible entry point.

Usage:
    Development:  python server.py
    Production:   gunicorn -w 4 -b 0.0.0.0:8000 server:app
    Docker:       docker compose up -d
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "8000"))
    print(f"Starting SIGNAL News Terminal on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
