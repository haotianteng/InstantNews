"""Structured JSON logging for CloudWatch compatibility.

Produces one JSON line per log entry so CloudWatch Logs Insights can
parse fields like ``user_id``, ``endpoint``, ``latency_ms``, and ``tier``
without custom metric filters.
"""

import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON for CloudWatch."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Merge extra fields attached by request middleware or callers
        for key in ("request_id", "method", "path", "status", "latency_ms",
                     "user_id", "tier", "ip", "user_agent", "endpoint",
                     "event", "detail"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def configure_logging(app_name: str = "signal", level: str = "INFO") -> logging.Logger:
    """Set up structured JSON logging on the root logger.

    Returns the application logger (``signal``).
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove any existing handlers to avoid duplicate lines
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for name in ("urllib3", "botocore", "apscheduler", "werkzeug"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return logging.getLogger(app_name)
