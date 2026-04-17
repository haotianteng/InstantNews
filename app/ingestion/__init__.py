"""Scheduled ingestion package — EDGAR + Polygon → normalized tables.

Functions in this package are called by APScheduler jobs registered in
:mod:`app.worker`. Each ingester:

* accepts a ticker list (no full-universe scans),
* uses the project's existing upstream clients (rate limit + cache
  intact),
* maps the response into Pydantic models,
* calls the corresponding repository's idempotent write helper,
* lets the repository invalidate the matching Redis keys.

Job-level error handling lives in ``app.worker`` — ingester functions
themselves raise on fatal errors and let the scheduler/AuditLog wrapper
record the failure.
"""
