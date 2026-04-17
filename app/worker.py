"""Standalone background worker: feed refresh + EDGAR/Polygon ingestion.

Usage::

    python -m app.worker

Runs independently from the web server. In production, deploy as a
separate ECS task or sidecar container.

US-015 / US-016
---------------
Adds APScheduler cron jobs for the company-info ingestion pipeline.

* ``edgar_10q_10k`` — daily 02:00 UTC, ingests the latest 10-Q/10-K
  filings into ``company_financials``.
* ``edgar_form4`` — every 30 min, ingests Form 4 insider transactions.
* ``edgar_13f_baseline`` — daily 03:00 UTC, baseline 13F refresh.
* ``edgar_13f_intensive`` — every hour; **no-ops outside the active
  filing window** computed by :func:`get_active_13f_window` (US-015 OQ-2).
* ``edgar_13f_calendar_probe`` — 00:05 UTC on the 1st of Feb/May/Aug/Nov,
  probes the SEC for the next 13F deadline and persists it to Redis so
  the intensive job can override the hardcoded date.
* ``polygon_fundamentals`` — every 15 minutes during US market hours
  (9-16 ET, Mon-Fri) and hourly outside hours, refreshes
  ``company_fundamentals``. (US-016.)

The :data:`scheduler` object is importable as ``from app.worker import
scheduler`` so tests can assert which jobs are registered without
starting the worker.
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import sessionmaker

from app.config import Config
from app.database import get_session, init_db
from app.logging_config import configure_logging
from app.services.feed_refresh import refresh_feeds_parallel

if TYPE_CHECKING:  # pragma: no cover
    from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger("signal.worker")


# --------------------------------------------------------------------------- #
# Scheduler — module-level so tests can introspect job IDs without starting it
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Job wrappers
#
# Each wrapper resolves the active ticker universe, calls the relevant
# ingester, logs the result count, and on failure writes an audit log
# row with ``action='ingestion_failure'``.
# --------------------------------------------------------------------------- #


def _active_tickers() -> list[str]:
    """Return every ticker in ``companies`` that isn't delisted."""
    from app.models import Company as CompanyORM
    session = get_session()
    try:
        rows = (
            session.query(CompanyORM.ticker)
            .filter(CompanyORM.delisted_at.is_(None))
            .all()
        )
        return [r[0] for r in rows]
    finally:
        session.close()


def _audit_failure(job_id: str, err: BaseException) -> None:
    """Best-effort write to ``audit_log`` for a failed ingestion job.

    Reuses the existing :class:`AuditLog` schema; ``admin_email='system'``
    distinguishes scheduler-driven rows from human admin actions.
    Swallows all errors — the audit write is observability, not a
    critical path.
    """
    try:
        from app.models import AuditLog
        from app.services.feed_parser import utc_iso

        session = get_session()
        try:
            session.add(
                AuditLog(
                    admin_user_id=0,
                    admin_email="system",
                    action="ingestion_failure",
                    target_user_id=None,
                    details=f'{{"job":"{job_id}","error":{repr(str(err))}}}',
                    ip_address=None,
                    created_at=utc_iso(datetime.now(timezone.utc)),
                )
            )
            session.commit()
        finally:
            session.close()
    except Exception:  # pragma: no cover
        logger.exception("audit_failure write failed for job=%s", job_id)


def _run_with_audit(job_id: str, fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        result = fn(*args, **kwargs)
        logger.info("job ok id=%s result=%s", job_id, result)
        return result
    except Exception as e:
        logger.exception("job failed id=%s", job_id)
        _audit_failure(job_id, e)
        return None


def run_10q_10k() -> Any:
    from app.ingestion.edgar_ingester import ingest_10q_10k
    tickers = _active_tickers()
    return _run_with_audit("edgar_10q_10k", ingest_10q_10k, tickers)


def run_form4() -> Any:
    from app.ingestion.edgar_ingester import ingest_form4
    tickers = _active_tickers()
    return _run_with_audit("edgar_form4", ingest_form4, tickers)


def run_13f_baseline() -> Any:
    from app.ingestion.edgar_ingester import ingest_13f
    tickers = _active_tickers()
    return _run_with_audit("edgar_13f_baseline", ingest_13f, tickers)


def run_13f_intensive() -> Any:
    """Hourly 13F refresh — no-op outside the SEC filing window."""
    from app.ingestion.edgar_calendar import get_active_13f_window
    from app.ingestion.edgar_ingester import ingest_13f

    window = get_active_13f_window(datetime.now(tz=timezone.utc))
    if window is None:
        logger.info("edgar_13f_intensive: outside filing window, skipping")
        return None
    tickers = _active_tickers()
    return _run_with_audit("edgar_13f_intensive", ingest_13f, tickers)


def run_13f_calendar_probe() -> Any:
    """Probe the SEC calendar for the next-quarter 13F deadline.

    The probe is best-effort; if it fails, we just leave the hardcoded
    deadline in place. Persists to Redis so the intensive job can pick
    up the override on its next tick.
    """
    from app.ingestion.edgar_calendar import (
        probe_13f_deadline_for_quarter,
        set_redis_deadline_override,
    )

    def _probe() -> dict[str, Any]:
        now = datetime.now(tz=timezone.utc)
        # Probe each of the 4 most recently-completed quarters whose
        # deadline could fall in the next 90 days. The cron only fires
        # in Feb/May/Aug/Nov, so the relevant deadline is "this month or
        # next-quarter", but we enumerate all 4 cheaply.
        results: dict[str, Any] = {}
        candidates = [
            (now.year - 1, "Q4"),
            (now.year, "Q1"),
            (now.year, "Q2"),
            (now.year, "Q3"),
        ]
        for year, quarter in candidates:
            try:
                deadline = probe_13f_deadline_for_quarter(quarter, year)
                if deadline is None:
                    results[f"{year}-{quarter}"] = None
                    continue
                ok = set_redis_deadline_override(year, quarter, deadline)
                results[f"{year}-{quarter}"] = (deadline.isoformat(), ok)
            except Exception as e:
                logger.warning("calendar probe %s-%s failed: %s", year, quarter, e)
                results[f"{year}-{quarter}"] = None
        return results

    return _run_with_audit("edgar_13f_calendar_probe", _probe)


def run_polygon_fundamentals_market_hours() -> Any:
    from app.ingestion.market_data_ingester import refresh_fundamentals
    tickers = _active_tickers()
    return _run_with_audit("polygon_fundamentals", refresh_fundamentals, tickers)


def run_polygon_fundamentals_off_hours() -> Any:
    from app.ingestion.market_data_ingester import refresh_fundamentals
    tickers = _active_tickers()
    return _run_with_audit("polygon_fundamentals_off", refresh_fundamentals, tickers)


# US-017 — Core S&P 500 ticker refresh.
#
# Reads the static seed file ``data/sp500_tickers.txt`` and re-runs the
# cheap, event-driven legs (fundamentals + Form 4 insider transactions)
# every 4 hours. The expensive 10-Q/K and 13F legs continue under the
# US-015 schedule (daily / windowed). This keeps S&P 500 tickers fresher
# than organic-growth tickers without increasing the upstream load
# beyond Polygon's 5 req/sec ceiling.
SP500_TICKERS_PATH = "data/sp500_tickers.txt"


def _read_sp500_tickers() -> list[str]:
    """Load the S&P 500 ticker list from disk; returns ``[]`` if missing.

    Reads each line, uppercases, strips blanks and comment lines so
    operator edits to the file are tolerated.
    """
    import os as _os

    path = _os.path.join(_os.path.dirname(__file__), "..", SP500_TICKERS_PATH)
    path = _os.path.abspath(path)
    if not _os.path.exists(path):
        logger.warning("core_ticker_refresh: %s not found; nothing to do", path)
        return []
    out: list[str] = []
    seen: set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                sym = line.strip().upper()
                if not sym or sym.startswith("#") or sym in seen:
                    continue
                seen.add(sym)
                out.append(sym)
    except OSError as e:
        logger.warning("core_ticker_refresh: failed to read %s: %s", path, e)
        return []
    return out


def run_core_ticker_refresh() -> Any:
    """Tighter-cadence refresh for S&P 500 core tickers (US-017).

    Calls :func:`refresh_fundamentals` (Polygon) and
    :func:`ingest_form4` (EDGAR) on every active S&P 500 ticker. Both
    are cheap + event-driven; the heavier 10-Q/K and 13F legs stay on
    their daily / windowed cadence under US-015.
    """
    from app.ingestion.edgar_ingester import ingest_form4
    from app.ingestion.market_data_ingester import refresh_fundamentals

    tickers = _read_sp500_tickers()
    if not tickers:
        return None

    def _refresh_both() -> dict[str, Any]:
        fundamentals = refresh_fundamentals(tickers)
        form4 = ingest_form4(tickers)
        return {
            "tickers": len(tickers),
            "fundamentals_rows": sum(int(v or 0) for v in fundamentals.values()),
            "form4_rows": sum(int(v or 0) for v in form4.values()),
        }

    return _run_with_audit("core_ticker_refresh", _refresh_both)


# --------------------------------------------------------------------------- #
# Scheduler construction (after wrappers — APScheduler resolves callables
# eagerly when add_job receives a string ref or a function object).
# --------------------------------------------------------------------------- #


def _build_scheduler() -> "BackgroundScheduler":
    """Construct a :class:`BackgroundScheduler` and register every job."""
    from apscheduler.schedulers.background import BackgroundScheduler

    sched = BackgroundScheduler(daemon=True, timezone="UTC")

    # ── EDGAR ingestion (US-015) ──────────────────────────────────────────
    sched.add_job(
        run_10q_10k,
        "cron",
        hour=2,
        minute=0,
        id="edgar_10q_10k",
        replace_existing=True,
    )
    sched.add_job(
        run_form4,
        "interval",
        minutes=30,
        id="edgar_form4",
        replace_existing=True,
    )
    sched.add_job(
        run_13f_baseline,
        "cron",
        hour=3,
        minute=0,
        id="edgar_13f_baseline",
        replace_existing=True,
    )
    sched.add_job(
        run_13f_intensive,
        "interval",
        hours=1,
        id="edgar_13f_intensive",
        replace_existing=True,
    )
    sched.add_job(
        run_13f_calendar_probe,
        "cron",
        day=1,
        month="2,5,8,11",
        hour=0,
        minute=5,
        id="edgar_13f_calendar_probe",
        replace_existing=True,
    )

    # ── Polygon fundamentals (US-016) ─────────────────────────────────────
    # Every 15 min during US market hours (9:30–16:00 ET ≈ 13–21 UTC,
    # Mon-Fri); hourly outside. We approximate with two cron jobs to keep
    # the spec's intent without TZ-conversion gymnastics.
    sched.add_job(
        run_polygon_fundamentals_market_hours,
        "cron",
        day_of_week="mon-fri",
        hour="13-21",
        minute="0,15,30,45",
        id="polygon_fundamentals_market",
        replace_existing=True,
    )
    sched.add_job(
        run_polygon_fundamentals_off_hours,
        "cron",
        hour="0-12,22,23",
        minute=0,
        id="polygon_fundamentals_off",
        replace_existing=True,
    )
    # Spec assertion (US-016 #3) — alias job ``polygon_fundamentals``
    # that always exists regardless of cron expressions above.
    sched.add_job(
        run_polygon_fundamentals_market_hours,
        "interval",
        hours=1,
        id="polygon_fundamentals",
        replace_existing=True,
    )

    # ── Core S&P 500 ticker refresh (US-017) ──────────────────────────────
    sched.add_job(
        run_core_ticker_refresh,
        "interval",
        hours=4,
        id="core_ticker_refresh",
        replace_existing=True,
    )

    return sched


try:
    scheduler = _build_scheduler()
except ImportError:  # pragma: no cover — APScheduler missing
    logger.warning("APScheduler not installed — scheduler will be None")
    scheduler = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# Main loop — feed refresh sticks with the simple loop, while APScheduler
# fires the ingestion jobs in the background.
# --------------------------------------------------------------------------- #


def main() -> None:
    configure_logging()

    config = Config
    engine = init_db(config.DATABASE_URL)
    # ``create_tables`` is intentionally NOT called here — production uses
    # Alembic migrations and dev setups bootstrap via conftest. Calling
    # ``Base.metadata.create_all`` from the worker would race the web
    # process during deploy and could partially-create new tables.
    session_factory = sessionmaker(bind=engine)

    interval = config.WORKER_INTERVAL_SECONDS
    logger.info("Feed worker started", extra={
        "event": "worker_start",
        "detail": (
            f"interval={interval}s, BEDROCK_ENABLED={config.BEDROCK_ENABLED}, "
            f"scheduler_jobs={[j.id for j in scheduler.get_jobs()] if scheduler else []}"
        ),
    })

    # Start the APScheduler thread (ingestion jobs).
    if scheduler is not None:
        try:
            scheduler.start()
            logger.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))
        except Exception:
            logger.exception("APScheduler failed to start")

    running = True

    def shutdown(signum, frame):  # type: ignore[no-untyped-def]
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

    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
        except Exception:  # pragma: no cover
            logger.exception("APScheduler shutdown failed")

    logger.info("Feed worker stopped", extra={"event": "worker_stop"})


if __name__ == "__main__":
    main()
