"""GET /api/market/<symbol> — real-time market data, company details, and SEC filings."""

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.auth.middleware import require_auth
from app.middleware.rate_limit import limiter
from app.services.cache_manager import CompanyCache
from app.services.edgar_client import EdgarClient
from app.services.market_data import PolygonClient

logger = logging.getLogger("signal.market")

market_bp = Blueprint("market", __name__)

# Shared L2 cache + singleton clients
_cache = CompanyCache()
_polygon = PolygonClient(db_cache=_cache)
_edgar = EdgarClient(db_cache=_cache)


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
    """Return company fundamentals for a ticker symbol."""
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
    """Return earnings and financial ratios for a ticker symbol."""
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

    return jsonify({
        "symbol": symbol.upper(),
        "financials": financials,
        "earnings": earnings.get("earnings", []) if earnings else [],
    })


@market_bp.route("/api/market/<symbol>/competitors")
@require_auth
@limiter.limit("600 per minute")
def market_competitors(symbol: str):
    """Return competitor comparison data for a ticker symbol."""
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

    return jsonify({
        "symbol": symbol.upper(),
        "competitors": competitors,
    })


@market_bp.route("/api/market/<symbol>/institutions")
@require_auth
@limiter.limit("600 per minute")
def market_institutions(symbol: str):
    """Return institutional holdings (13F) and major position changes (13D/13G)."""
    holders = _edgar.get_institutional_holders(symbol)
    positions = _edgar.get_major_position_changes(symbol)

    if holders is None and positions is None:
        return jsonify({
            "error": "Ticker not found",
            "message": f"No institutional data available for symbol '{symbol.upper()}'",
        }), 404

    return jsonify({
        "symbol": symbol.upper(),
        "institutional_holders": holders or [],
        "major_position_changes": positions or [],
    })


@market_bp.route("/api/market/<symbol>/insiders")
@require_auth
@limiter.limit("600 per minute")
def market_insiders(symbol: str):
    """Return insider transactions from Form 4 filings."""
    transactions = _edgar.get_insider_transactions(symbol)

    if transactions is None:
        return jsonify({
            "error": "Ticker not found",
            "message": f"No insider transaction data available for symbol '{symbol.upper()}'",
        }), 404

    return jsonify({
        "symbol": symbol.upper(),
        "insider_transactions": transactions,
    })
