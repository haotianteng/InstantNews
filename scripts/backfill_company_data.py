#!/usr/bin/env python3
"""US-014 — backfill ``company_data_cache`` JSON blobs into normalized tables.

Reads every row from the deprecated ``company_data_cache`` table, parses
``payload`` as JSON, maps to the appropriate Pydantic model and writes
into the per-domain repository (which goes through ``BaseRepository``
and therefore is idempotent + invalidates Redis).

Mapping table
-------------

============  ================================================================
data_type     Destination
============  ================================================================
details       ``companies`` (master) AND ``company_fundamentals`` (subset)
financials    ``company_financials`` — one row per Polygon ``.results`` entry
competitors   ``company_competitors`` — bootstraps destination master rows
institutional ``institutional_holders`` (batch append)
insiders      ``insider_transactions`` (per-row append)
earnings      SKIP — not in the 6-domain schema
positions     SKIP — 13D/G is not in the 6-domain schema
============  ================================================================

CLI flags
---------

``--dry-run``     plan-only; ZERO writes (Postgres or Redis)
``--data-type T`` scope to one ``data_type`` (incremental backfill)
``--limit N``     process only the first ``N`` rows (smoke testing)
``--source-db U`` read from a different DB than the target (defaults to
                 ``DATABASE_URL``); writes always go to ``DATABASE_URL``

Exit codes
----------

* ``0`` — success (even if some rows failed; see ``failures.log``).
* ``1`` — fatal config error (DB not reachable, Alembic head missing, …).

Failure rows are recorded under
``jojo/test_results/US-014/attempt-<N>/failures.log``. ``N`` is auto-picked
as the next non-existent ``attempt-*`` directory (1 if the per-story dir
is empty / missing). The failure log path is also printed in the final
summary.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

# Allow ``python scripts/backfill_company_data.py`` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Config
from app.database import init_db
from app.models import CompanyDataCache  # ORM
from app.models.company import Company
from app.models.competitors import Competitor
from app.models.financials import Financials
from app.models.fundamentals import Fundamentals
from app.models.institutions import InstitutionalHolder
from app.models.insiders import InsiderTransaction
from app.repositories.company_repo import CompanyRepository
from app.repositories.competitors_repo import CompetitorsRepository
from app.repositories.financials_repo import FinancialsRepository
from app.repositories.fundamentals_repo import FundamentalsRepository
from app.repositories.institutions_repo import InstitutionsRepository
from app.repositories.insiders_repo import InsidersRepository

logger = logging.getLogger("signal.backfill")

# Domains we know how to project. Anything else is skipped + counted.
SUPPORTED_DATA_TYPES: set[str] = {
    "details",
    "financials",
    "competitors",
    "institutional",
    "insiders",
}
SKIPPED_DATA_TYPES: set[str] = {"earnings", "positions"}


# --------------------------------------------------------------------------- #
# Helpers — pure conversions (also unit-test-friendly)
# --------------------------------------------------------------------------- #


def _to_decimal(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _period_end_from(fp: Any, fy: Any) -> Optional[date]:
    try:
        year = int(str(fy).strip())
    except (ValueError, TypeError):
        return None
    period = str(fp or "").upper().strip()
    if period == "Q1":
        return date(year, 3, 31)
    if period == "Q2":
        return date(year, 6, 30)
    if period == "Q3":
        return date(year, 9, 30)
    if period in ("Q4", "FY", "ANNUAL"):
        return date(year, 12, 31)
    return None


def _parse_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val:
        try:
            return date.fromisoformat(val[:10])
        except ValueError:
            return None
    return None


# --------------------------------------------------------------------------- #
# Result accounting
# --------------------------------------------------------------------------- #


class Stats:
    """Per-data_type tally of successes / failures / skips."""

    def __init__(self) -> None:
        self.succeeded: dict[str, int] = defaultdict(int)
        self.failed: dict[str, int] = defaultdict(int)
        self.skipped: dict[str, int] = defaultdict(int)

    def total_succeeded(self) -> int:
        return sum(self.succeeded.values())

    def total_failed(self) -> int:
        return sum(self.failed.values())

    def total_skipped(self) -> int:
        return sum(self.skipped.values())


# --------------------------------------------------------------------------- #
# Output dir for failure logs
# --------------------------------------------------------------------------- #


def _pick_attempt_dir(repo_root: Path) -> Path:
    """Resolve ``jojo/test_results/US-014/attempt-N/`` next-N path.

    If the per-story directory is missing or empty we use ``attempt-1``.
    Otherwise we increment past the highest existing attempt number.
    """
    base = repo_root / "jojo" / "test_results" / "US-014"
    base.mkdir(parents=True, exist_ok=True)
    attempts = [
        int(p.name.split("-", 1)[1])
        for p in base.iterdir()
        if p.is_dir() and p.name.startswith("attempt-")
        and p.name.split("-", 1)[1].isdigit()
    ]
    n = (max(attempts) + 1) if attempts else 1
    out = base / f"attempt-{n}"
    out.mkdir(parents=True, exist_ok=True)
    return out


# --------------------------------------------------------------------------- #
# Per-row processors
# --------------------------------------------------------------------------- #


def _process_details(
    symbol: str,
    payload: dict[str, Any],
    company_repo: CompanyRepository,
    fundamentals_repo: FundamentalsRepository,
    dry_run: bool,
) -> None:
    """Map a Polygon ``ticker_details`` blob → ``companies`` (+ ``company_fundamentals``)."""
    company = Company(
        ticker=symbol,
        name=str(payload.get("name") or symbol),
        description=payload.get("description") or None,
        website=payload.get("homepage_url") or None,
        sector=payload.get("sector") or payload.get("sic_description") or None,
        industry=payload.get("industry") or None,
        country=payload.get("locale") or None,
        currency=payload.get("currency_name") or None,
    )
    if dry_run:
        return
    company_repo.upsert(company)

    # Fundamentals subset present on a Polygon ticker_details payload:
    # market_cap, shares_outstanding ("share_class_shares_outstanding" or
    # "weighted_shares_outstanding"). Everything else is None.
    market_cap = _to_int(payload.get("market_cap"))
    shares = _to_int(
        payload.get("share_class_shares_outstanding")
        or payload.get("weighted_shares_outstanding")
    )
    if market_cap is None and shares is None:
        return
    fundamentals_repo.upsert(
        Fundamentals(ticker=symbol, market_cap=market_cap, shares_outstanding=shares)
    )


def _iter_financials_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of per-period financial entries from a cached payload.

    We accept three shapes seen in the wild:

    * Polygon raw ``{"results": [...]}``
    * Our flat helper ``{"fiscal_period": ..., "fiscal_year": ..., ...}``
    * A list of either of the above
    """
    if isinstance(payload, list):
        out: list[dict[str, Any]] = []
        for item in payload:
            out.extend(_iter_financials_results(item))
        return out
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("results"), list):
        return [r for r in payload["results"] if isinstance(r, dict)]
    # Flat single-period shape — wrap in a one-element list.
    if "fiscal_year" in payload or "fiscal_period" in payload:
        return [payload]
    return []


def _process_financials(
    symbol: str,
    payload: dict[str, Any],
    company_repo: CompanyRepository,
    financials_repo: FinancialsRepository,
    dry_run: bool,
) -> int:
    """Map a financials payload → one or more ``company_financials`` rows.

    Returns the number of rows projected (0 if none persisted). Caller
    counts the parent cache row as ``succeeded`` only if at least one
    result row was written successfully.
    """
    rows = _iter_financials_results(payload)
    written = 0
    for r in rows:
        fy = r.get("fiscal_year")
        fp = r.get("fiscal_period")
        period_end = _period_end_from(fp, fy)
        try:
            fy_int = int(str(fy).strip())
        except (ValueError, TypeError):
            continue
        if period_end is None:
            continue
        period_type = str(fp or "").upper().strip() or "Q4"

        # Both flat and Polygon-nested shapes — try both.
        income = (
            r.get("financials", {}).get("income_statement", {})
            if isinstance(r.get("financials"), dict)
            else {}
        )
        revenue = _to_int(
            r.get("revenue")
            if r.get("revenue") is not None
            else income.get("revenues", {}).get("value")
            if isinstance(income.get("revenues"), dict)
            else None
        )
        net_income = _to_int(
            r.get("net_income")
            if r.get("net_income") is not None
            else income.get("net_income_loss", {}).get("value")
            if isinstance(income.get("net_income_loss"), dict)
            else None
        )
        eps_basic = _to_decimal(
            r.get("eps")
            if r.get("eps") is not None
            else income.get("basic_earnings_per_share", {}).get("value")
            if isinstance(income.get("basic_earnings_per_share"), dict)
            else None
        )

        fin = Financials(
            ticker=symbol,
            period_end=period_end,
            period_type=period_type,
            fiscal_year=fy_int,
            revenue=revenue,
            net_income=net_income,
            eps_basic=eps_basic,
            source="company_data_cache_backfill",
        )
        if dry_run:
            written += 1
            continue
        # Bootstrap master row to satisfy FK.
        if company_repo.get(symbol) is None:
            company_repo.upsert(Company(ticker=symbol, name=symbol))
        financials_repo.append(fin)
        written += 1
    return written


def _process_competitors(
    symbol: str,
    payload: dict[str, Any],
    company_repo: CompanyRepository,
    competitors_repo: CompetitorsRepository,
    dry_run: bool,
) -> int:
    """Map a competitors payload → ``company_competitors`` (FK-safe).

    Bootstraps the source AND every destination ticker as a basic
    ``companies`` row before calling ``upsert_batch`` — the FK has
    ``ondelete=RESTRICT`` and the destination tickers may not exist on a
    cold DB. This is the fix for the FK-violation finding in US-013.
    """
    # Two payload shapes:
    #   {"tickers": ["MSFT","GOOGL"]}
    #   [ {"symbol": "MSFT"}, {"symbol": "GOOGL"} ]
    candidates: list[str] = []
    if isinstance(payload, dict) and isinstance(payload.get("tickers"), list):
        candidates = [str(t).strip().upper() for t in payload["tickers"] if t]
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                sym = (item.get("symbol") or item.get("ticker") or "").strip().upper()
                if sym:
                    candidates.append(sym)
    elif isinstance(payload, dict) and isinstance(payload.get("results"), list):
        for item in payload["results"]:
            if isinstance(item, dict):
                sym = (item.get("ticker") or item.get("symbol") or "").strip().upper()
                if sym:
                    candidates.append(sym)
    # Drop self-edges + dedup while preserving order.
    seen: set[str] = set()
    cleaned: list[str] = []
    for sym in candidates:
        if sym and sym != symbol and sym not in seen:
            seen.add(sym)
            cleaned.append(sym)

    if not cleaned:
        return 0
    if dry_run:
        return len(cleaned)

    # Bootstrap source + every destination master row before touching the
    # competitors table — the FK is RESTRICT.
    if company_repo.get(symbol) is None:
        company_repo.upsert(Company(ticker=symbol, name=symbol))
    for sym in cleaned:
        if company_repo.get(sym) is None:
            company_repo.upsert(Company(ticker=sym, name=sym))

    edges: list[Competitor] = []
    for idx, sym in enumerate(cleaned):
        try:
            score = Decimal(str(max(0.1, 1.0 - idx * 0.1))).quantize(
                Decimal("0.0001")
            )
        except (InvalidOperation, ValueError, TypeError):
            score = Decimal("0.5")
        edges.append(
            Competitor(
                ticker=symbol,
                competitor_ticker=sym,
                similarity_score=score,
                source="company_data_cache_backfill",
            )
        )
    competitors_repo.upsert_batch(symbol, edges)
    return len(edges)


def _process_institutional(
    symbol: str,
    payload: Any,
    company_repo: CompanyRepository,
    institutions_repo: InstitutionsRepository,
    dry_run: bool,
) -> int:
    """Map a 13F payload → ``institutional_holders`` (batch append)."""
    items: list[dict[str, Any]] = []
    if isinstance(payload, list):
        items = [x for x in payload if isinstance(x, dict)]
    elif isinstance(payload, dict) and isinstance(payload.get("results"), list):
        items = [x for x in payload["results"] if isinstance(x, dict)]
    elif isinstance(payload, dict) and isinstance(payload.get("holders"), list):
        items = [x for x in payload["holders"] if isinstance(x, dict)]

    rows: list[InstitutionalHolder] = []
    for item in items:
        rd = _parse_date(item.get("report_date"))
        if rd is None:
            continue
        try:
            rows.append(
                InstitutionalHolder(
                    ticker=symbol,
                    institution_cik=item.get("institution_cik") or item.get("cik"),
                    institution_name=item.get("institution_name") or None,
                    report_date=rd,
                    shares_held=_to_int(item.get("shares_held")),
                    market_value=_to_int(item.get("value") or item.get("market_value")),
                    pct_of_portfolio=_to_decimal(item.get("pct_of_portfolio")),
                    pct_of_company=_to_decimal(item.get("pct_of_company")),
                    change_shares=_to_int(item.get("change_shares")),
                    filing_date=_parse_date(item.get("filing_date")),
                )
            )
        except Exception:
            continue
    if not rows:
        return 0
    if dry_run:
        return len(rows)
    if company_repo.get(symbol) is None:
        company_repo.upsert(Company(ticker=symbol, name=symbol))
    return institutions_repo.append_batch(rows)


def _process_insiders(
    symbol: str,
    payload: Any,
    company_repo: CompanyRepository,
    insiders_repo: InsidersRepository,
    dry_run: bool,
) -> int:
    """Map a Form 4 payload → ``insider_transactions`` (per-row append)."""
    items: list[dict[str, Any]] = []
    if isinstance(payload, list):
        items = [x for x in payload if isinstance(x, dict)]
    elif isinstance(payload, dict) and isinstance(payload.get("results"), list):
        items = [x for x in payload["results"] if isinstance(x, dict)]
    elif isinstance(payload, dict) and isinstance(payload.get("transactions"), list):
        items = [x for x in payload["transactions"] if isinstance(x, dict)]

    written = 0
    bootstrap_done = False
    for item in items:
        td = _parse_date(item.get("transaction_date") or item.get("filing_date"))
        if td is None:
            continue
        fd = _parse_date(item.get("filing_date"))
        try:
            txn = InsiderTransaction(
                ticker=symbol,
                insider_name=item.get("insider_name") or None,
                insider_title=item.get("title") or item.get("insider_title") or None,
                transaction_date=td,
                transaction_type=item.get("transaction_type") or None,
                shares=_to_int(item.get("shares")),
                price_per_share=_to_decimal(item.get("price_per_share")),
                total_value=_to_int(item.get("total_value")),
                shares_owned_after=_to_int(
                    item.get("shares_held_after") or item.get("shares_owned_after")
                ),
                filing_date=fd,
                form_type=item.get("form_type") or "4",
                sec_url=item.get("sec_url") or None,
            )
        except Exception:
            continue
        if dry_run:
            written += 1
            continue
        if not bootstrap_done:
            if company_repo.get(symbol) is None:
                company_repo.upsert(Company(ticker=symbol, name=symbol))
            bootstrap_done = True
        try:
            insiders_repo.append(txn)
        except Exception:
            # Per-row dedup / FK fallback handled by caller via try/except.
            continue
        written += 1
    return written


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #


def _iter_cache_rows(
    session: Session, data_type_filter: Optional[str], limit: Optional[int]
):
    q = session.query(CompanyDataCache)
    if data_type_filter:
        q = q.filter_by(data_type=data_type_filter)
    q = q.order_by(CompanyDataCache.id.asc())
    if limit:
        q = q.limit(limit)
    return q.all()


def run(
    *,
    dry_run: bool,
    data_type_filter: Optional[str],
    limit: Optional[int],
    source_db_url: Optional[str],
    failures_log_path: Path,
) -> Stats:
    """Execute the backfill pass. Pure function for tests."""
    if data_type_filter and data_type_filter not in (
        SUPPORTED_DATA_TYPES | SKIPPED_DATA_TYPES
    ):
        logger.warning(
            "unknown --data-type %s (will still scan rows; nothing will match)",
            data_type_filter,
        )

    # Target DB (writes go here). Always use Config.DATABASE_URL via init_db
    # so the repositories' module-level get_session() works as expected.
    init_db(Config.DATABASE_URL)

    # Source DB — defaults to the same as target.
    src_url = source_db_url or Config.DATABASE_URL
    src_engine = create_engine(src_url, pool_pre_ping=True)
    SrcSession = sessionmaker(bind=src_engine)
    src_session = SrcSession()

    company_repo = CompanyRepository()
    fundamentals_repo = FundamentalsRepository()
    financials_repo = FinancialsRepository()
    competitors_repo = CompetitorsRepository()
    institutions_repo = InstitutionsRepository()
    insiders_repo = InsidersRepository()

    stats = Stats()
    rows_processed = 0
    last_log_ts = time.monotonic()

    failures_log_path.parent.mkdir(parents=True, exist_ok=True)
    failures_fh = failures_log_path.open("w", encoding="utf-8")

    try:
        rows = _iter_cache_rows(src_session, data_type_filter, limit)
        total = len(rows)
        logger.info("backfill start rows=%d dry_run=%s", total, dry_run)

        for row in rows:
            rows_processed += 1
            symbol = (row.symbol or "").strip().upper()
            data_type = (row.data_type or "").strip().lower()

            if not symbol:
                stats.skipped[data_type or "unknown"] += 1
                failures_fh.write(
                    f"row_id={row.id} reason=empty_symbol data_type={data_type}\n"
                )
                continue

            if data_type in SKIPPED_DATA_TYPES:
                stats.skipped[data_type] += 1
                continue

            if data_type not in SUPPORTED_DATA_TYPES:
                stats.skipped[data_type or "unknown"] += 1
                failures_fh.write(
                    f"row_id={row.id} symbol={symbol} reason=unknown_data_type "
                    f"data_type={data_type}\n"
                )
                continue

            try:
                payload = json.loads(row.payload) if row.payload else None
            except (ValueError, TypeError) as e:
                stats.failed[data_type] += 1
                failures_fh.write(
                    f"row_id={row.id} symbol={symbol} data_type={data_type} "
                    f"reason=json_parse err={e!r}\n"
                )
                continue
            if payload is None:
                stats.skipped[data_type] += 1
                continue

            try:
                if data_type == "details":
                    if isinstance(payload, dict):
                        _process_details(
                            symbol, payload, company_repo, fundamentals_repo, dry_run
                        )
                        stats.succeeded[data_type] += 1
                    else:
                        stats.skipped[data_type] += 1
                elif data_type == "financials":
                    n = _process_financials(
                        symbol,
                        payload if isinstance(payload, dict) else {"results": payload},
                        company_repo,
                        financials_repo,
                        dry_run,
                    )
                    if n > 0:
                        stats.succeeded[data_type] += 1
                    else:
                        stats.skipped[data_type] += 1
                elif data_type == "competitors":
                    n = _process_competitors(
                        symbol,
                        payload if isinstance(payload, dict) else {"tickers": payload},
                        company_repo,
                        competitors_repo,
                        dry_run,
                    )
                    if n > 0:
                        stats.succeeded[data_type] += 1
                    else:
                        stats.skipped[data_type] += 1
                elif data_type == "institutional":
                    n = _process_institutional(
                        symbol, payload, company_repo, institutions_repo, dry_run
                    )
                    if n > 0:
                        stats.succeeded[data_type] += 1
                    else:
                        stats.skipped[data_type] += 1
                elif data_type == "insiders":
                    n = _process_insiders(
                        symbol, payload, company_repo, insiders_repo, dry_run
                    )
                    if n > 0:
                        stats.succeeded[data_type] += 1
                    else:
                        stats.skipped[data_type] += 1
            except Exception as e:
                stats.failed[data_type] += 1
                failures_fh.write(
                    f"row_id={row.id} symbol={symbol} data_type={data_type} "
                    f"reason=processor_error err={e!r}\n"
                )
                logger.warning(
                    "row %d (%s/%s) failed: %s", row.id, symbol, data_type, e
                )

            # Heartbeat every 100 rows OR every 5s, whichever comes first.
            now = time.monotonic()
            if rows_processed % 100 == 0 or (now - last_log_ts) >= 5.0:
                logger.info(
                    "processed %d/%d rows, succeeded=%d failed=%d skipped=%d",
                    rows_processed,
                    total,
                    stats.total_succeeded(),
                    stats.total_failed(),
                    stats.total_skipped(),
                )
                last_log_ts = now

        logger.info(
            "backfill done rows_processed=%d succeeded=%d failed=%d skipped=%d",
            rows_processed,
            stats.total_succeeded(),
            stats.total_failed(),
            stats.total_skipped(),
        )
        # Per-data_type summary
        all_keys = sorted(
            set(stats.succeeded) | set(stats.failed) | set(stats.skipped)
        )
        for k in all_keys:
            logger.info(
                "  %-14s succeeded=%d failed=%d skipped=%d",
                k,
                stats.succeeded.get(k, 0),
                stats.failed.get(k, 0),
                stats.skipped.get(k, 0),
            )
        logger.info("failures log: %s", failures_log_path)
        return stats
    finally:
        failures_fh.close()
        src_session.close()


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Backfill company_data_cache JSON blobs into normalized tables."
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan; make ZERO writes (Postgres or Redis).",
    )
    p.add_argument(
        "--data-type",
        dest="data_type",
        default=None,
        help="Scope to one data_type (details, financials, competitors, institutional, insiders).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N rows (smoke testing).",
    )
    p.add_argument(
        "--source-db",
        dest="source_db",
        default=None,
        help="Read cache rows from a different DB URL (defaults to DATABASE_URL).",
    )
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    attempt_dir = _pick_attempt_dir(repo_root)
    failures_log = attempt_dir / "failures.log"

    try:
        run(
            dry_run=args.dry_run,
            data_type_filter=args.data_type,
            limit=args.limit,
            source_db_url=args.source_db,
            failures_log_path=failures_log,
        )
    except Exception as e:
        logger.error("fatal config error: %s", e, exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
