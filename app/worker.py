"""Standalone background worker for periodic feed refresh.

Usage:
    python -m app.worker

Runs independently from the web server. In production, deploy as a
separate ECS task or sidecar container.
"""

import logging
import signal
import sys
import time

from app.config import Config
from app.database import init_db, create_tables
from app.logging_config import configure_logging
from app.services.feed_refresh import refresh_feeds_parallel
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger("signal.worker")


def main():
    configure_logging()

    config = Config
    engine = init_db(config.DATABASE_URL)
    create_tables()
    session_factory = sessionmaker(bind=engine)

    interval = config.WORKER_INTERVAL_SECONDS
    logger.info("Feed worker started", extra={
        "event": "worker_start",
        "detail": f"interval={interval}s, BEDROCK_ENABLED={config.BEDROCK_ENABLED}",
    })

    running = True

    def shutdown(signum, frame):
        nonlocal running
        logger.info("Shutting down feed worker", extra={"event": "worker_shutdown"})
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while running:
        try:
            total_new, results = refresh_feeds_parallel(session_factory, config)
            logger.info("Feed refresh completed", extra={
                "event": "refresh_complete",
                "detail": f"{total_new} new items from {len(results)} sources",
            })
        except Exception:
            logger.exception("Feed refresh failed", extra={
                "event": "refresh_error",
            })

        # Sleep in small increments so we can catch shutdown signals
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    logger.info("Feed worker stopped", extra={"event": "worker_stop"})


if __name__ == "__main__":
    main()
