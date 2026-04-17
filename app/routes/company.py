"""GET /api/company/<ticker>/profile — unified company profile endpoint.

Thin Flask wrapper around :meth:`CompanyService.get_full_profile`. The
service layer owns the parallel fan-out, on-demand backfill, and mutex
coordination; this blueprint just marshals the result into JSON and
handles the "no data anywhere" → 404 case.

Response envelope
-----------------

Returns the serialized :class:`CompanyProfile` verbatim via
``model_dump(mode="json")`` so every Pydantic type (``Decimal`` →
string, ``date`` / ``datetime`` → ISO) becomes a JSON-safe primitive.
Top-level keys: ``company``, ``fundamentals``, ``latest_financials``,
``competitors``, ``top_institutions``, ``recent_insiders``, ``partial``,
``fetched_at``.

404 path
--------

The service returns a profile with every domain blank when the ticker
is a ghost — nothing in Postgres, nothing from Polygon/EDGAR. We detect
that and return 404 rather than an empty envelope so the terminal can
distinguish "AAPL is cold-caching" from "ZZZZZ doesn't exist". See
spec US-012 acceptance criterion 3.

Caching header
--------------

The endpoint sets ``Cache-Control: private, max-age=60`` — per-user
browser caching of 1 minute. The underlying repos hold individual
domains for much longer (TTL table in ``app/cache/cache_keys.py``); the
60s browser hint matches the "live feel" of the terminal panel.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from app.auth.middleware import require_auth
from app.middleware.rate_limit import limiter
from app.services.company_service import CompanyService

logger = logging.getLogger("signal.routes.company")

company_bp = Blueprint("company", __name__)

# Module-level singleton — the service itself is stateless apart from
# its repo/client handles, which are all thread-safe and cheap to share.
_service = CompanyService()


@company_bp.route("/api/company/<ticker>/profile")
@require_auth
@limiter.limit("600 per minute")
def company_profile(ticker: str):
    """Return the full :class:`CompanyProfile` JSON for a ticker."""
    up = ticker.upper()
    profile = _service.get_full_profile(up)

    # "Ghost ticker" detection: no master row AND every list empty AND
    # no financials/fundamentals — ZZZZZ, not AAPL. 404.
    if (
        profile.company is None
        and profile.fundamentals is None
        and profile.latest_financials is None
        and not profile.competitors
        and not profile.top_institutions
        and not profile.recent_insiders
    ):
        return jsonify({
            "error": "Ticker not found",
            "ticker": up,
        }), 404

    resp = jsonify(profile.model_dump(mode="json"))
    resp.headers["Cache-Control"] = "private, max-age=60"
    return resp, 200
