"""GET /api/docs — API documentation."""

from flask import Blueprint, jsonify

docs_bp = Blueprint("docs", __name__)


@docs_bp.route("/api/docs")
def api_docs():
    return jsonify({
        "api": "SIGNAL News Trading Terminal API",
        "version": "1.0",
        "endpoints": [
            {
                "method": "GET", "path": "/api/news",
                "description": "Get latest news items",
                "params": {
                    "limit": "Number of items (default 200, max 500)",
                    "source": "Filter by source name (default 'all')",
                    "sentiment": "Filter by sentiment: bullish, bearish, neutral (default 'all')",
                    "q": "Keyword search in title and summary",
                    "from": "Filter from date (ISO 8601, e.g. '2026-03-01')",
                    "to": "Filter to date (ISO 8601, e.g. '2026-03-02')",
                },
            },
            {"method": "GET", "path": "/api/sources", "description": "List all active feed sources with item counts"},
            {"method": "GET", "path": "/api/stats", "description": "Aggregated feed statistics"},
            {"method": "POST", "path": "/api/refresh", "description": "Force refresh all feeds immediately"},
            {"method": "GET", "path": "/api/docs", "description": "This API documentation"},
        ],
        "examples": [
            'curl "http://localhost:8000/api/news?limit=10&sentiment=bullish"',
            'curl "http://localhost:8000/api/sources"',
            'curl "http://localhost:8000/api/stats"',
            'curl -X POST "http://localhost:8000/api/refresh"',
        ],
    })
