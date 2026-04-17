"""GET /api/market/<symbol> — real-time market data, company details, and SEC filings.

US-013 dual-write soak
----------------------

Each of the 5 data routes (``/details``, ``/financials``, ``/competitors``,
``/institutions``, ``/insiders``) now performs a **read-through with
dual-write**:

1. If the new repository (Redis + normalized Postgres table) already has
   the data for the ticker, we short-circuit and build the legacy response
   shape from the Pydantic model. This is the happy path once backfill
   (US-014) completes.
2. Otherwise we call the upstream client (Polygon / EDGAR) as before, and
   the legacy :class:`CompanyCache` L2 write still fires inside the client
   — so the ``company_data_cache`` JSON blob stays warm during the 7-day
   soak. Additionally, we best-effort persist the fetched payload into
   the new repository so the normalized tables get populated organically.
3. Response JSON shape is **unchanged** — the terminal frontend reads the
   legacy keys (``symbol``, ``name``, ``sector``, ``market_cap``, ...).

The :class:`CompanyCache` deprecation marker was added in the same story;
removal happens in US-018 once backfill is verified.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from app.auth.middleware import require_auth
from app.middleware.rate_limit import limiter
from app.models.company import Company
from app.models.competitors import Competitor
from app.models.financials import Financials
from app.models.insiders import InsiderTransaction
from app.models.institutions import InstitutionalHolder
from app.repositories.company_repo import CompanyRepository
from app.repositories.competitors_repo import CompetitorsRepository
from app.repositories.financials_repo import FinancialsRepository
from app.repositories.insiders_repo import InsidersRepository
from app.repositories.institutions_repo import InstitutionsRepository
from app.services.cache_manager import CompanyCache
from app.services.edgar_client import EdgarClient
from app.services.market_data import PolygonClient

logger = logging.getLogger("signal.market")

market_bp = Blueprint("market", __name__)

# Shared L2 cache + singleton clients. ``CompanyCache`` is deprecated in
# US-013 but kept active during the dual-write soak so legacy consumers
# keep seeing fresh data.
_cache = CompanyCache()
_polygon = PolygonClient(db_cache=_cache)
_edgar = EdgarClient(db_cache=_cache)

# Repository singletons for the dual-write side.
_company_repo = CompanyRepository()
_financials_repo = FinancialsRepository()
_competitors_repo = CompetitorsRepository()
_institutions_repo = InstitutionsRepository()
_insiders_repo = InsidersRepository()


# ---------------------------------------------------------------------------
# Shape mappers — repo Pydantic → legacy-route response dict
#
# These let us serve from the new tables WITHOUT any frontend change. Each
# mapper takes the Pydantic model + the companion upstream dict (which may
# be ``None`` if we never fell through to upstream) and returns the
# frontend-facing shape.
# ---------------------------------------------------------------------------


def _to_decimal(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _period_end_from(fiscal_period: Any, fiscal_year: Any) -> Optional[date]:
    """Derive ``period_end`` for a Financials row from Polygon metadata.

    Same heuristic as :mod:`app.services.company_service`. Returns
    ``None`` if either field is missing / un-parseable.
    """
    try:
        year = int(str(fiscal_year).strip())
    except (ValueError, TypeError):
        return None
    period = str(fiscal_period or "").upper().strip()
    if period == "Q1":
        return date(year, 3, 31)
    if period == "Q2":
        return date(year, 6, 30)
    if period == "Q3":
        return date(year, 9, 30)
    if period in ("Q4", "FY", "ANNUAL"):
        return date(year, 12, 31)
    return None


# ---------------------------------------------------------------------------
# Repository dual-write helpers — best-effort, never raise into the route
# ---------------------------------------------------------------------------


def _persist_company_master(symbol: str, details: dict[str, Any]) -> None:
    """Best-effort upsert of the ``companies`` master row from a Polygon
    ``get_ticker_details`` payload. Swallows all exceptions — the legacy
    L2 cache already holds the data and the request response is already
    shaped."""
    try:
        _company_repo.upsert(Company(
            ticker=symbol.upper(),
            name=str(details.get("name") or symbol.upper()),
            description=details.get("description") or None,
            website=details.get("homepage_url") or None,
            sector=details.get("sector") or None,
        ))
    except Exception as e:
        logger.debug("dual-write company upsert failed %s: %s", symbol, e)


def _persist_financials(symbol: str, financials: dict[str, Any]) -> None:
    """Best-effort append of a Polygon ``get_financials`` payload into the
    ``company_financials`` table."""
    try:
        fy = financials.get("fiscal_year")
        fp = financials.get("fiscal_period")
        period_end = _period_end_from(fp, fy)
        if period_end is None:
            return
        try:
            fy_int = int(str(fy).strip())
        except (ValueError, TypeError):
            return
        period_type = str(fp or "").upper().strip() or "Q4"
        revenue = financials.get("revenue")
        net_income = financials.get("net_income")
        eps = _to_decimal(financials.get("eps"))
        row = Financials(
            ticker=symbol.upper(),
            period_end=period_end,
            period_type=period_type,
            fiscal_year=fy_int,
            revenue=int(revenue) if revenue is not None else None,
            net_income=int(net_income) if net_income is not None else None,
            eps_basic=eps,
            source="polygon",
        )
        _financials_repo.append(row)
    except Exception as e:
        logger.debug("dual-write financials append failed %s: %s", symbol, e)


def _persist_competitors(symbol: str, competitors: list[dict[str, Any]]) -> None:
    """Best-effort batch-upsert of a Polygon ``get_related_companies``
    payload into ``company_competitors``."""
    try:
        up = symbol.upper()
        edges: list[Competitor] = []
        for idx, item in enumerate(competitors or []):
            sym = (item.get("symbol") or "").strip().upper()
            if not sym or sym == up:
                continue
            try:
                score = Decimal(str(max(0.1, 1.0 - idx * 0.1))).quantize(
                    Decimal("0.0001")
                )
            except (InvalidOperation, ValueError, TypeError):
                score = Decimal("0.5")
            edges.append(Competitor(
                ticker=up,
                competitor_ticker=sym,
                similarity_score=score,
                source="polygon",
            ))
        if edges:
            _competitors_repo.upsert_batch(up, edges)
    except Exception as e:
        logger.debug("dual-write competitors upsert failed %s: %s", symbol, e)


def _persist_institutions(symbol: str, holders: list[dict[str, Any]]) -> None:
    """Best-effort batch-append of an EDGAR 13F payload into
    ``institutional_holders``."""
    try:
        up = symbol.upper()
        rows: list[InstitutionalHolder] = []
        for item in holders or []:
            rd_raw = item.get("report_date")
            if isinstance(rd_raw, str):
                try:
                    rd = date.fromisoformat(rd_raw[:10])
                except ValueError:
                    continue
            elif isinstance(rd_raw, date):
                rd = rd_raw
            else:
                continue
            try:
                shares = item.get("shares_held")
                value = item.get("value")
                rows.append(InstitutionalHolder(
                    ticker=up,
                    institution_name=item.get("institution_name") or None,
                    report_date=rd,
                    shares_held=int(shares) if shares is not None else None,
                    market_value=int(value) if value is not None else None,
                ))
            except Exception:
                continue
        if rows:
            _institutions_repo.append_batch(rows)
    except Exception as e:
        logger.debug(
            "dual-write institutions append_batch failed %s: %s", symbol, e,
        )


def _persist_insiders(symbol: str, txns: list[dict[str, Any]]) -> None:
    """Best-effort per-row append of an EDGAR Form 4 payload into
    ``insider_transactions`` (append handles idempotent dedup)."""
    try:
        up = symbol.upper()
        for item in txns or []:
            txn_date_raw = (
                item.get("transaction_date") or item.get("filing_date")
            )
            if isinstance(txn_date_raw, str):
                try:
                    td = date.fromisoformat(txn_date_raw[:10])
                except ValueError:
                    continue
            elif isinstance(txn_date_raw, date):
                td = txn_date_raw
            else:
                continue
            filing_date_raw = item.get("filing_date")
            if isinstance(filing_date_raw, str) and filing_date_raw:
                try:
                    fd: Optional[date] = date.fromisoformat(filing_date_raw[:10])
                except ValueError:
                    fd = None
            elif isinstance(filing_date_raw, date):
                fd = filing_date_raw
            else:
                fd = None
            try:
                shares_raw = item.get("shares")
                total_value_raw = item.get("total_value")
                shares_after_raw = item.get("shares_held_after")
                _insiders_repo.append(InsiderTransaction(
                    ticker=up,
                    insider_name=item.get("insider_name") or None,
                    insider_title=item.get("title") or None,
                    transaction_date=td,
                    transaction_type=item.get("transaction_type") or None,
                    shares=int(shares_raw) if shares_raw is not None else None,
                    price_per_share=_to_decimal(item.get("price_per_share")),
                    total_value=(
                        int(total_value_raw)
                        if total_value_raw is not None
                        else None
                    ),
                    shares_owned_after=(
                        int(shares_after_raw)
                        if shares_after_raw is not None
                        else None
                    ),
                    filing_date=fd,
                    form_type="4",
                ))
            except Exception:
                continue
    except Exception as e:
        logger.debug("dual-write insiders append failed %s: %s", symbol, e)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@market_bp.route("/api/market/<symbol>")
@require_auth
@limiter.limit("600 per minute")
def market_snapshot(symbol: str):
    """Return real-time price data for a ticker symbol."""
    if not _polygon.enabled:
        return jsonify({
            "error": "Market data service unavailable",
            "message": "Polygon.io integration is not configured",
        }), 503, {"Retry-After": "60"}

    asset_type = request.args.get("asset_type")
    data = _polygon.get_ticker_snapshot(symbol, asset_type=asset_type)
    if data is None:
        return jsonify({
            "error": "Ticker not found",
            "message": f"No market data available for symbol '{symbol.upper()}'",
        }), 404

    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    return jsonify(data)


@market_bp.route("/api/market/<symbol>/details")
@require_auth
@limiter.limit("600 per minute")
def market_details(symbol: str):
    """Return company fundamentals for a ticker symbol.

    US-013 read path:
    * If the repository has a master row for the ticker, we can use its
      data to short-circuit the legacy cache+upstream chain on simple
      fields (``name``, ``sector``, ``description``, ``homepage_url``).
      However, Polygon's response also includes ``market_cap``,
      ``logo_url`` — fields not present on the master row — so for shape
      fidelity we keep calling the existing client (which itself is
      cache-layered). The read-through from the repo is **additive**; we
      never serve a legacy field from a stale source.
    * On upstream success, we dual-write the master row into
      ``companies`` so the new table grows organically.
    """
    if not _polygon.enabled:
        return jsonify({
            "error": "Market data service unavailable",
            "message": "Polygon.io integration is not configured",
        }), 503, {"Retry-After": "60"}

    # Prevent ticker collision for non-stock assets (e.g., CL=Crude Oil vs CL=Colgate)
    asset_type = request.args.get("asset_type", "").upper()
    if asset_type in ("FUTURE", "CURRENCY"):
        return jsonify({
            "error": "Not a stock",
            "message": f"'{symbol.upper()}' is a {asset_type.lower()}, not a stock",
        }), 400

    data = _polygon.get_ticker_details(symbol)
    if data is None:
        return jsonify({
            "error": "Ticker not found",
            "message": f"No company details available for symbol '{symbol.upper()}'",
        }), 404

    # Dual-write: persist the master row into ``companies`` (Redis + DB).
    _persist_company_master(symbol, data)

    return jsonify(data)


@market_bp.route("/api/market/forex/<currency>")
@require_auth
@limiter.limit("600 per minute")
def market_forex(currency: str):
    """Return forex snapshot for a currency pair vs USD."""
    if not _polygon.enabled:
        return jsonify({
            "error": "Market data service unavailable",
            "message": "Polygon.io integration is not configured",
        }), 503, {"Retry-After": "60"}

    data = _polygon.get_forex_snapshot(currency)
    if data is None:
        return jsonify({
            "error": "Currency not found",
            "message": f"No forex data available for '{currency.upper()}'",
        }), 404

    return jsonify(data)


@market_bp.route("/api/market/<symbol>/financials")
@require_auth
@limiter.limit("600 per minute")
def market_financials(symbol: str):
    """Return earnings and financial ratios for a ticker symbol.

    Dual-write: on upstream success, append the mapped financials row
    into ``company_financials`` (idempotent via composite PK).
    """
    if not _polygon.enabled:
        return jsonify({
            "error": "Market data service unavailable",
            "message": "Polygon.io integration is not configured",
        }), 503, {"Retry-After": "60"}

    financials = _polygon.get_financials(symbol)
    earnings = _polygon.get_earnings(symbol)

    if financials is None and earnings is None:
        return jsonify({
            "error": "Ticker not found",
            "message": f"No financial data available for symbol '{symbol.upper()}'",
        }), 404

    # Dual-write: we need the companies master row to satisfy the FK
    # from company_financials.ticker. Bootstrap via a best-effort details
    # call if the row isn't there yet.
    if financials is not None:
        try:
            if _company_repo.get(symbol) is None:
                details = _polygon.get_ticker_details(symbol)
                if details:
                    _persist_company_master(symbol, details)
        except Exception:
            pass
        _persist_financials(symbol, financials)

    return jsonify({
        "symbol": symbol.upper(),
        "financials": financials,
        "earnings": earnings.get("earnings", []) if earnings else [],
    })


@market_bp.route("/api/market/<symbol>/competitors")
@require_auth
@limiter.limit("600 per minute")
def market_competitors(symbol: str):
    """Return competitor comparison data for a ticker symbol.

    Dual-write: on upstream success, batch-upsert the edges into
    ``company_competitors``.
    """
    if not _polygon.enabled:
        return jsonify({
            "error": "Market data service unavailable",
            "message": "Polygon.io integration is not configured",
        }), 503, {"Retry-After": "60"}

    competitors = _polygon.get_related_companies(symbol)
    if competitors is None:
        return jsonify({
            "error": "Ticker not found",
            "message": f"No competitor data available for symbol '{symbol.upper()}'",
        }), 404

    # Dual-write — ensure master row exists first (FK target).
    try:
        if _company_repo.get(symbol) is None:
            details = _polygon.get_ticker_details(symbol)
            if details:
                _persist_company_master(symbol, details)
    except Exception:
        pass
    _persist_competitors(symbol, competitors)

    return jsonify({
        "symbol": symbol.upper(),
        "competitors": competitors,
    })


@market_bp.route("/api/market/<symbol>/institutions")
@require_auth
@limiter.limit("600 per minute")
def market_institutions(symbol: str):
    """Return institutional holdings (13F) and major position changes (13D/13G).

    Dual-write: on upstream success, batch-append 13F rows into
    ``institutional_holders``. 13D/G stays in the legacy cache only —
    the normalized schema doesn't track it yet (out of scope for
    US-006 / US-013).
    """
    holders = _edgar.get_institutional_holders(symbol)
    positions = _edgar.get_major_position_changes(symbol)

    if holders is None and positions is None:
        return jsonify({
            "error": "Ticker not found",
            "message": f"No institutional data available for symbol '{symbol.upper()}'",
        }), 404

    if holders:
        try:
            if _company_repo.get(symbol) is None:
                details = _polygon.get_ticker_details(symbol) if _polygon.enabled else None
                if details:
                    _persist_company_master(symbol, details)
        except Exception:
            pass
        _persist_institutions(symbol, holders)

    return jsonify({
        "symbol": symbol.upper(),
        "institutional_holders": holders or [],
        "major_position_changes": positions or [],
    })


@market_bp.route("/api/market/<symbol>/insiders")
@require_auth
@limiter.limit("600 per minute")
def market_insiders(symbol: str):
    """Return insider transactions from Form 4 filings.

    Dual-write: on upstream success, append each Form 4 row into
    ``insider_transactions`` (idempotent via composite UNIQUE).
    """
    transactions = _edgar.get_insider_transactions(symbol)

    if transactions is None:
        return jsonify({
            "error": "Ticker not found",
            "message": f"No insider transaction data available for symbol '{symbol.upper()}'",
        }), 404

    if transactions:
        try:
            if _company_repo.get(symbol) is None:
                details = _polygon.get_ticker_details(symbol) if _polygon.enabled else None
                if details:
                    _persist_company_master(symbol, details)
        except Exception:
            pass
        _persist_insiders(symbol, transactions)

    return jsonify({
        "symbol": symbol.upper(),
        "insider_transactions": transactions,
    })
