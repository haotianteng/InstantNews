"""GET /api/market/<symbol> — real-time market data and company details."""

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify

from app.auth.middleware import require_auth
from app.middleware.rate_limit import limiter
from app.services.market_data import PolygonClient

logger = logging.getLogger("signal.market")

market_bp = Blueprint("market", __name__)

# Singleton client — disabled gracefully when POLYGON_API_KEY is unset
_polygon = PolygonClient()


@market_bp.route("/api/market/<symbol>")
@require_auth
@limiter.limit("60 per minute")
def market_snapshot(symbol: str):
    """Return real-time price data for a ticker symbol."""
    if not _polygon.enabled:
        return jsonify({
            "error": "Market data service unavailable",
            "message": "Polygon.io integration is not configured",
        }), 503, {"Retry-After": "60"}

    data = _polygon.get_ticker_snapshot(symbol)
    if data is None:
        return jsonify({
            "error": "Ticker not found",
            "message": f"No market data available for symbol '{symbol.upper()}'",
        }), 404

    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    return jsonify(data)


@market_bp.route("/api/market/<symbol>/details")
@require_auth
@limiter.limit("60 per minute")
def market_details(symbol: str):
    """Return company fundamentals for a ticker symbol."""
    if not _polygon.enabled:
        return jsonify({
            "error": "Market data service unavailable",
            "message": "Polygon.io integration is not configured",
        }), 503, {"Retry-After": "60"}

    data = _polygon.get_ticker_details(symbol)
    if data is None:
        return jsonify({
            "error": "Ticker not found",
            "message": f"No company details available for symbol '{symbol.upper()}'",
        }), 404

    return jsonify(data)
