"""Standalone background worker for periodic feed refresh.

Usage:
    python -m app.worker

Runs independently from the web server. In production, deploy as a
separate ECS task or sidecar container.
"""

import signal
import sys
import time

from app.config import Config
from app.database import init_db, create_tables
from app.services.feed_refresh import refresh_feeds_parallel
from sqlalchemy.orm import sessionmaker


def main():
    config = Config
    engine = init_db(config.DATABASE_URL)
    create_tables()
    session_factory = sessionmaker(bind=engine)

    interval = config.WORKER_INTERVAL_SECONDS
    print(f"Feed worker started (interval={interval}s)")

    running = True

    def shutdown(signum, frame):
        nonlocal running
        print("Shutting down feed worker...")
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while running:
        try:
            total_new, results = refresh_feeds_parallel(session_factory, config)
            print(f"Refreshed: {total_new} new items from {len(results)} sources")
        except Exception as e:
            print(f"Refresh error: {e}")

        # Sleep in small increments so we can catch shutdown signals
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    print("Feed worker stopped.")


if __name__ == "__main__":
    main()
