#!/usr/bin/env python3
"""US-017 — One-shot S&P 500 seed.

Reads :file:`data/sp500_tickers.txt` and runs the full ingestion sequence
for every ticker:

1. ``companies`` row UPSERT (basic details from Polygon
   ``get_ticker_details``)
2. :func:`app.ingestion.edgar_ingester.ingest_10q_10k` (1-ticker call)
3. :func:`app.ingestion.market_data_ingester.refresh_fundamentals`
4. :func:`app.ingestion.edgar_ingester.ingest_13f`
5. :func:`app.ingestion.edgar_ingester.ingest_form4`
6. Competitors via :meth:`PolygonClient.get_related_companies` →
   :meth:`CompetitorsRepository.upsert_batch` (FK-safe — bootstraps
   destination master rows per the US-013 tester finding).

Rate limiting
-------------
Token-bucket pattern (``TokenBucket``) — NOT naive ``time.sleep`` — to
keep traffic ≤ 8 req/sec for SEC EDGAR and ≤ 4 req/sec for Polygon. Each
ingester call is wrapped at the call site (one acquire per call); the
internal client throttles continue to act as a second-line defence.

Resumability
------------
Per-ticker progress is persisted to :file:`data/seed_progress.json` after
every ticker completes (success / partial / failure). On startup the
``completed`` set is loaded and matching tickers are skipped. Atomic
write via ``write to temp + os.replace``.

CLI flags
---------

``--dry-run``  print tickers that would be processed; no API calls
``--reset``    delete ``data/seed_progress.json`` and start fresh
``--limit N``  process only the first ``N`` tickers (smoke test)

Audit
-----
On clean completion an ``AuditLog`` row is written with
``action='ingestion_complete'`` and ``details`` containing the final
counts plus ``event_type=sp500_seed_complete``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional

# Allow ``python scripts/seed_sp500.py`` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Config
from app.database import get_session, init_db
from app.models.company import Company
from app.models.competitors import Competitor
from app.repositories.company_repo import CompanyRepository
from app.repositories.competitors_repo import CompetitorsRepository

logger = logging.getLogger("signal.seed_sp500")


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TICKERS_PATH = REPO_ROOT / "data" / "sp500_tickers.txt"
DEFAULT_PROGRESS_PATH = REPO_ROOT / "data" / "seed_progress.json"


# --------------------------------------------------------------------------- #
# TokenBucket — simple thread-safe rate limiter
# --------------------------------------------------------------------------- #


class TokenBucket:
    """A minimal token bucket rate limiter.

    Tokens regenerate at ``rate_per_sec`` per second, with a small fixed
    burst capacity of 1 token so the long-run rate AND the burst rate
    both stay bounded. Each :meth:`acquire` consumes one token; if none
    are available the call sleeps until the next token is ready.

    The capacity-of-1 choice (rather than ``capacity == rate``) is
    deliberate — for an upstream API gated at e.g. 8 req/sec, a burst
    of 8 instantaneous calls would briefly exceed the gate. Smoothing
    to one call per ``1/rate`` seconds keeps us strictly under the
    limit from the very first call.

    Thread-safe: callers from multiple worker threads share the bucket.
    """

    BURST_CAPACITY = 1.0

    def __init__(self, rate_per_sec: float) -> None:
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be positive")
        self.rate = float(rate_per_sec)
        self.capacity = self.BURST_CAPACITY
        # Start with a single token so the very first acquire is free
        # but the second is paced.
        self.tokens = self.BURST_CAPACITY
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        """Block until one token is available, then consume it."""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last = now
            if self.tokens < 1.0:
                sleep_time = (1.0 - self.tokens) / self.rate
                time.sleep(sleep_time)
                # Account for the token we're about to consume after sleep.
                self.tokens = 0.0
                self.last = time.monotonic()
            else:
                self.tokens -= 1.0


# Module-level buckets — re-used across tickers within one process.
edgar_bucket = TokenBucket(8.0)   # SEC EDGAR allows 10 req/sec; stay under.
polygon_bucket = TokenBucket(4.0)  # Polygon free tier is 5 req/sec; stay under.


# --------------------------------------------------------------------------- #
# Progress persistence
# --------------------------------------------------------------------------- #


@dataclass
class SeedProgress:
    """JSON-serialisable progress state."""

    completed: list[str] = field(default_factory=list)
    failed: list[dict[str, str]] = field(default_factory=list)
    partial: list[dict[str, Any]] = field(default_factory=list)
    started_at: Optional[str] = None
    last_updated: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "completed": list(self.completed),
            "failed": list(self.failed),
            "partial": list(self.partial),
            "started_at": self.started_at,
            "last_updated": self.last_updated,
        }

    @property
    def completed_set(self) -> set[str]:
        return set(self.completed)


def load_progress(path: Path) -> SeedProgress:
    if not path.exists():
        return SeedProgress()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        logger.warning("seed_progress.json unreadable (%s); starting fresh", e)
        return SeedProgress()
    return SeedProgress(
        completed=list(raw.get("completed") or []),
        failed=list(raw.get("failed") or []),
        partial=list(raw.get("partial") or []),
        started_at=raw.get("started_at"),
        last_updated=raw.get("last_updated"),
    )


def save_progress(path: Path, progress: SeedProgress) -> None:
    """Atomic write — temp file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    progress.last_updated = datetime.now(tz=timezone.utc).isoformat()
    tmp.write_text(json.dumps(progress.to_dict(), indent=2), encoding="utf-8")
    os.replace(tmp, path)


# --------------------------------------------------------------------------- #
# Per-ticker work
# --------------------------------------------------------------------------- #


@dataclass
class TickerOutcome:
    ticker: str
    ok: bool
    duration_s: float
    domains_ok: list[str]
    domains_failed: list[str]
    reason: Optional[str] = None


def _seed_one_ticker(
    ticker: str,
    *,
    company_repo: CompanyRepository,
    competitors_repo: CompetitorsRepository,
) -> TickerOutcome:
    """Run the full 6-step ingest sequence for a single ticker.

    Each step is wrapped so a per-domain failure does not abort the
    whole ticker — the outcome's ``domains_failed`` list captures which
    legs went wrong. ``ok=True`` requires zero failures; partial success
    yields ``ok=False`` plus a list of failed legs.
    """
    started = time.monotonic()
    domains_ok: list[str] = []
    domains_failed: list[str] = []

    def _step(name: str, bucket: TokenBucket, fn: Callable[[], Any]) -> None:
        try:
            bucket.acquire()
            fn()
            domains_ok.append(name)
        except Exception as e:
            domains_failed.append(name)
            logger.warning("ticker=%s step=%s failed: %s", ticker, name, e)

    # Lazy imports — keeps `--dry-run` cheap.
    from app.ingestion.edgar_ingester import (
        get_polygon_client,
        ingest_10q_10k,
        ingest_13f,
        ingest_form4,
    )
    from app.ingestion.market_data_ingester import refresh_fundamentals

    polygon = get_polygon_client()

    # 1. companies UPSERT (Polygon get_ticker_details)
    def _step_company_master() -> None:
        details = polygon.get_ticker_details(ticker) if polygon.enabled else None
        company = Company(
            ticker=ticker,
            name=str((details or {}).get("name") or ticker),
            description=(details or {}).get("description") or None,
            website=(details or {}).get("homepage_url") or None,
            sector=(details or {}).get("sector")
            or (details or {}).get("sic_description")
            or None,
        )
        company_repo.upsert(company)

    _step("company_master", polygon_bucket, _step_company_master)

    # 2. ingest_10q_10k (Polygon under the hood today; counts as 1 polygon hit)
    _step("financials_10q_10k", polygon_bucket, lambda: ingest_10q_10k([ticker]))

    # 3. refresh_fundamentals (1 polygon hit per ticker)
    _step("fundamentals", polygon_bucket, lambda: refresh_fundamentals([ticker]))

    # 4. ingest_13f (EDGAR)
    _step("institutions_13f", edgar_bucket, lambda: ingest_13f([ticker]))

    # 5. ingest_form4 (EDGAR)
    _step("insiders_form4", edgar_bucket, lambda: ingest_form4([ticker]))

    # 6. Competitors via Polygon get_related_companies
    def _step_competitors() -> None:
        if not polygon.enabled:
            raise RuntimeError("polygon disabled (no API key)")
        related = polygon.get_related_companies(ticker) or []
        # Drop self-references and dedup while preserving Polygon's order.
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in related:
            sym = (item.get("symbol") or item.get("ticker") or "").strip().upper()
            if sym and sym != ticker and sym not in seen:
                seen.add(sym)
                cleaned.append(sym)
        if not cleaned:
            return
        # Bootstrap destination master rows (US-013 finding) — destination
        # FK is RESTRICT, so every competitor_ticker must exist first.
        for sym in cleaned:
            if company_repo.get(sym) is None:
                company_repo.upsert(Company(ticker=sym, name=sym))
        edges: list[Competitor] = []
        for idx, sym in enumerate(cleaned):
            score = Decimal(str(max(0.1, 1.0 - idx * 0.1))).quantize(
                Decimal("0.0001")
            )
            edges.append(
                Competitor(
                    ticker=ticker,
                    competitor_ticker=sym,
                    similarity_score=score,
                    source="polygon",
                )
            )
        competitors_repo.upsert_batch(ticker, edges)

    _step("competitors", polygon_bucket, _step_competitors)

    duration = time.monotonic() - started
    ok = not domains_failed
    return TickerOutcome(
        ticker=ticker,
        ok=ok,
        duration_s=round(duration, 2),
        domains_ok=domains_ok,
        domains_failed=domains_failed,
        reason=", ".join(domains_failed) if domains_failed else None,
    )


# --------------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------------- #


def _write_audit_log(summary: dict[str, Any]) -> None:
    """Best-effort audit row on completion. Never raises into caller."""
    try:
        from app.models import AuditLog
        from app.services.feed_parser import utc_iso

        details = json.dumps({"event_type": "sp500_seed_complete", **summary})
        session = get_session()
        try:
            session.add(
                AuditLog(
                    admin_user_id=0,
                    admin_email="system",
                    action="ingestion_complete",
                    target_user_id=None,
                    details=details,
                    ip_address=None,
                    created_at=utc_iso(datetime.now(timezone.utc)),
                )
            )
            session.commit()
        finally:
            session.close()
    except Exception:
        logger.exception("audit_log write failed for sp500_seed_complete")
        # Structured fallback so the event is still observable.
        logger.info(
            "sp500_seed_complete %s",
            json.dumps({"event_type": "sp500_seed_complete", **summary}),
        )


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def load_tickers(path: Path) -> list[str]:
    """Read tickers from a one-per-line text file. Skips blanks + comments."""
    if not path.exists():
        raise FileNotFoundError(f"tickers file not found: {path}")
    out: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        sym = line.strip().upper()
        if not sym or sym.startswith("#"):
            continue
        if sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


def run(
    *,
    dry_run: bool = False,
    reset: bool = False,
    limit: Optional[int] = None,
    tickers_path: Path = DEFAULT_TICKERS_PATH,
    progress_path: Path = DEFAULT_PROGRESS_PATH,
) -> dict[str, Any]:
    """Execute the seed pass. Returns a summary dict for tests / audit."""
    started_wall = time.monotonic()
    started_iso = datetime.now(tz=timezone.utc).isoformat()

    tickers = load_tickers(tickers_path)
    if limit is not None:
        tickers = tickers[: max(0, int(limit))]

    if reset and progress_path.exists():
        try:
            progress_path.unlink()
            logger.info("reset: removed %s", progress_path)
        except OSError as e:
            logger.warning("reset: failed to remove %s: %s", progress_path, e)

    progress = load_progress(progress_path)
    if not progress.started_at:
        progress.started_at = started_iso

    completed_set = progress.completed_set
    pending = [t for t in tickers if t not in completed_set]
    skipped = len(tickers) - len(pending)

    if dry_run:
        # Plan-only output. No DB / API touches.
        for t in pending:
            print(t)
        summary: dict[str, Any] = {
            "mode": "dry_run",
            "total": len(tickers),
            "would_process": len(pending),
            "skipped_already_done": skipped,
            "tickers_path": str(tickers_path),
        }
        logger.info("dry-run summary: %s", summary)
        return summary

    # Real run — initialise DB engine and repositories.
    init_db(Config.DATABASE_URL)
    company_repo = CompanyRepository()
    competitors_repo = CompetitorsRepository()

    logger.info(
        "seed start total=%d pending=%d skipped_already_done=%d",
        len(tickers),
        len(pending),
        skipped,
    )

    ok_count = 0
    partial_count = 0
    failed_count = 0

    for idx, ticker in enumerate(pending, 1):
        try:
            outcome = _seed_one_ticker(
                ticker,
                company_repo=company_repo,
                competitors_repo=competitors_repo,
            )
        except Exception as e:
            # Top-level guard — should be unreachable since _seed_one_ticker
            # internally swallows per-step failures.
            logger.exception("ticker=%s catastrophic failure", ticker)
            outcome = TickerOutcome(
                ticker=ticker,
                ok=False,
                duration_s=0.0,
                domains_ok=[],
                domains_failed=["__top_level__"],
                reason=repr(e),
            )

        if outcome.ok:
            ok_count += 1
            progress.completed.append(ticker)
            logger.info(
                "ticker=%s outcome=ok duration=%.2fs (%d/%d)",
                ticker,
                outcome.duration_s,
                idx,
                len(pending),
            )
        elif outcome.domains_ok:
            partial_count += 1
            progress.partial.append(
                {
                    "ticker": ticker,
                    "ok_domains": outcome.domains_ok,
                    "failed_domains": outcome.domains_failed,
                    "reason": outcome.reason,
                }
            )
            # Record partial as completed too — re-runs should not re-attempt
            # a ticker that succeeded on most legs. Operators can re-run with
            # --reset for a clean pass.
            progress.completed.append(ticker)
            logger.info(
                "ticker=%s outcome=partial duration=%.2fs failed=%s (%d/%d)",
                ticker,
                outcome.duration_s,
                ",".join(outcome.domains_failed),
                idx,
                len(pending),
            )
        else:
            failed_count += 1
            progress.failed.append(
                {"ticker": ticker, "reason": outcome.reason or "unknown"}
            )
            logger.warning(
                "ticker=%s outcome=failed duration=%.2fs reason=%s (%d/%d)",
                ticker,
                outcome.duration_s,
                outcome.reason,
                idx,
                len(pending),
            )

        save_progress(progress_path, progress)

    wall = time.monotonic() - started_wall
    summary = {
        "mode": "live",
        "total": len(tickers),
        "processed_this_run": len(pending),
        "skipped_already_done": skipped,
        "ok": ok_count,
        "partial": partial_count,
        "failed": failed_count,
        "wall_seconds": round(wall, 2),
        "started_at": progress.started_at,
        "tickers_path": str(tickers_path),
    }
    logger.info("seed summary: %s", summary)
    _write_audit_log(summary)
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="One-shot S&P 500 seed.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print tickers that would be processed; no API calls",
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="delete data/seed_progress.json and start fresh",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="process only the first N tickers (smoke test)",
    )
    p.add_argument(
        "--tickers-file",
        type=Path,
        default=DEFAULT_TICKERS_PATH,
        help=f"path to ticker list (default: {DEFAULT_TICKERS_PATH})",
    )
    p.add_argument(
        "--progress-file",
        type=Path,
        default=DEFAULT_PROGRESS_PATH,
        help=f"path to progress json (default: {DEFAULT_PROGRESS_PATH})",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    summary = run(
        dry_run=args.dry_run,
        reset=args.reset,
        limit=args.limit,
        tickers_path=args.tickers_file,
        progress_path=args.progress_file,
    )

    print("\n=== seed_sp500 summary ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
