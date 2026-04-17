"""US-015 — 13F filing-window calendar.

Pure functions that compute whether ``now`` falls inside a 14-day window
around a 13F filing deadline. SEC publishes deadlines ~45 days after each
calendar quarter ends:

* Q4 (Dec 31)  → mid-Feb deadline
* Q1 (Mar 31)  → mid-May deadline
* Q2 (Jun 30)  → mid-Aug deadline
* Q3 (Sep 30)  → mid-Nov deadline

We hardcode the deadline date for each quarter and override it from
Redis if the monthly :func:`probe_13f_deadline_for_quarter` job has
written a more accurate one. ``edgar_13f_intensive`` (US-015 scheduler)
calls :func:`get_active_13f_window` every hour and no-ops outside the
window — ~96% of the year is a no-op, ~4% is the polling burst.

Redis key convention::

    edgar:13f:deadline:{YYYY}-Q{n}   →   ISO date string (UTF-8 bytes)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from app.cache.redis_client import get_redis

logger = logging.getLogger("signal.edgar.calendar")

# Quarter-of-year → (month, day-of-month) deadline. The Q4 deadline lives
# in the *following* calendar year (45 days past Dec 31).
HARDCODED_DEADLINES: dict[str, tuple[int, int]] = {
    "Q4": (2, 14),    # Q4 of year N filed by mid-Feb of year N+1
    "Q1": (5, 15),    # Q1 of year N
    "Q2": (8, 14),    # Q2 of year N
    "Q3": (11, 14),   # Q3 of year N
}

WINDOW_DAYS_BEFORE = 14
WINDOW_DAYS_AFTER = 1

# Redis key namespacing for calendar overrides.
DEADLINE_KEY_PREFIX = "edgar:13f:deadline"


def deadline_redis_key(year: int, quarter: str) -> str:
    """Return the Redis key for a per-(year, quarter) deadline override.

    ``quarter`` is ``"Q1"|"Q2"|"Q3"|"Q4"``; ``year`` is the year of the
    quarter being filed (e.g. Q4 of 2025 → key ``edgar:13f:deadline:2025-Q4``,
    even though the deadline date lives in 2026).
    """
    return f"{DEADLINE_KEY_PREFIX}:{year}-{quarter}"


def get_redis_deadline_override(year: int, quarter: str) -> Optional[date]:
    """Return the override deadline for (year, quarter), or ``None`` on miss.

    Swallows any Redis error and returns ``None`` — the calendar always
    falls back to hardcoded values, so a Redis outage is not fatal.
    """
    try:
        r = get_redis()
        raw = r.get(deadline_redis_key(year, quarter))
    except Exception as e:
        logger.warning("redis deadline override read failed %s-%s: %s", year, quarter, e)
        return None
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        logger.warning("redis deadline override unparseable %s-%s: %r", year, quarter, raw)
        return None


def set_redis_deadline_override(
    year: int, quarter: str, deadline: date, ttl_seconds: int = 60 * 60 * 24 * 365,
) -> bool:
    """Persist a probed deadline. Returns ``True`` on success, ``False`` otherwise."""
    try:
        r = get_redis()
        r.setex(deadline_redis_key(year, quarter), ttl_seconds, deadline.isoformat().encode("utf-8"))
        return True
    except Exception as e:
        logger.warning("redis deadline override write failed %s-%s: %s", year, quarter, e)
        return False


def _hardcoded_deadline(year: int, quarter: str) -> Optional[date]:
    """Return the hardcoded deadline ``date`` for a given (year, quarter).

    For Q4, the year passed in is the *quarter's* year (e.g. 2025); the
    actual deadline date lives in the following calendar year (Feb 14
    of 2026). Q1-Q3 deadlines fall in the same calendar year.
    """
    md = HARDCODED_DEADLINES.get(quarter)
    if md is None:
        return None
    month, day = md
    deadline_year = year + 1 if quarter == "Q4" else year
    try:
        return date(deadline_year, month, day)
    except ValueError:
        return None


def get_active_13f_window(now: datetime) -> Optional[tuple[date, date]]:
    """Return the (window_start, window_end) inclusive if ``now`` is in a 13F window.

    A window is ``[deadline - 14d, deadline + 1d]``. We check every quarter
    whose deadline could fall close to ``now`` (the current calendar year
    plus the previous year's Q4, which is filed in February of the
    current year). Override values from Redis take precedence over the
    hardcoded date.
    """
    today = now.date()

    candidates: list[tuple[int, str]] = [
        # Last year's Q4 → deadline this year (Feb)
        (now.year - 1, "Q4"),
        # This year's quarters
        (now.year, "Q1"),
        (now.year, "Q2"),
        (now.year, "Q3"),
        (now.year, "Q4"),
    ]
    for year, quarter in candidates:
        override = get_redis_deadline_override(year, quarter)
        deadline = override or _hardcoded_deadline(year, quarter)
        if deadline is None:
            continue
        window_start = deadline - timedelta(days=WINDOW_DAYS_BEFORE)
        window_end = deadline + timedelta(days=WINDOW_DAYS_AFTER)
        if window_start <= today <= window_end:
            return (window_start, window_end)
    return None


def probe_13f_deadline_for_quarter(quarter: str, year: int) -> Optional[date]:
    """Best-effort SEC calendar probe for an authoritative deadline.

    The SEC does not expose a clean machine-readable deadline calendar;
    historically the rule is "45 calendar days after the quarter end".
    For now this function returns the rule-derived deadline so the job
    has *some* answer to persist. A future revision can plug in a real
    EDGAR fetch — the signature stays the same.

    Returns ``None`` if ``quarter`` is unrecognized.
    """
    quarter = quarter.upper().strip()
    quarter_end_md = {"Q1": (3, 31), "Q2": (6, 30), "Q3": (9, 30), "Q4": (12, 31)}
    if quarter not in quarter_end_md:
        logger.warning("probe_13f_deadline: unknown quarter %r", quarter)
        return None
    m, d = quarter_end_md[quarter]
    try:
        quarter_end = date(year, m, d)
    except ValueError:
        return None
    return quarter_end + timedelta(days=45)
