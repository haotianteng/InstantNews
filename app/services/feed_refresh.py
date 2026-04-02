"""Feed refresh orchestration — parallel fetching, storage, and dedup."""

import json
import time
from datetime import datetime, timedelta, timezone
from threading import Thread, Lock

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import News, Meta
from app.services.feed_parser import fetch_feed, utc_iso
from app.services.dedup import mark_new_duplicates


def _store_items(session_factory, items, now_utc):
    """Store fetched items into the database. Returns count of new items."""
    session = session_factory()
    count = 0
    try:
        for item in items:
            try:
                news = News(
                    title=item["title"],
                    link=item["link"],
                    source=item["source"],
                    published=item["published"],
                    fetched_at=now_utc,
                    summary=item["summary"],
                    sentiment_score=item["sentiment_score"],
                    sentiment_label=item["sentiment_label"],
                )
                session.add(news)
                session.flush()
                count += 1
            except IntegrityError:
                session.rollback()
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
    return count


def fetch_single_feed_to_db(source_name, url, session_factory, config):
    """Fetch a single feed and store results. Returns (source_name, new_count)."""
    items = fetch_feed(source_name, url, config.USER_AGENT, config.FETCH_TIMEOUT)
    if not items:
        return source_name, 0
    now_utc = utc_iso(datetime.now(timezone.utc))
    count = _store_items(session_factory, items, now_utc)
    return source_name, count


def cleanup_old_entries(session, max_age_days):
    """Remove entries older than max_age_days."""
    cutoff = utc_iso(datetime.now(timezone.utc) - timedelta(days=max_age_days))
    session.query(News).filter(News.published < cutoff).delete()
    session.commit()


def refresh_feeds_parallel(session_factory, config):
    """Fetch all feeds in parallel using threads.

    Returns (total_new_count, per_source_status_dict).
    """
    results = {}
    threads = []
    result_lock = Lock()

    def worker(name, url):
        src, count = fetch_single_feed_to_db(name, url, session_factory, config)
        with result_lock:
            results[src] = count

    for name, url in config.FEEDS.items():
        t = Thread(target=worker, args=(name, url))
        t.daemon = True
        threads.append(t)
        t.start()

    deadline = time.time() + 20
    for t in threads:
        remaining = max(0.1, deadline - time.time())
        t.join(timeout=remaining)

    total_new = sum(results.values())

    session = session_factory()
    try:
        now_utc = utc_iso(datetime.now(timezone.utc))
        # Update last_refresh
        existing = session.query(Meta).filter_by(key="last_refresh").first()
        if existing:
            existing.value = now_utc
        else:
            session.add(Meta(key="last_refresh", value=now_utc))

        # Update source_status
        existing_status = session.query(Meta).filter_by(key="source_status").first()
        if existing_status:
            existing_status.value = json.dumps(results)
        else:
            session.add(Meta(key="source_status", value=json.dumps(results)))

        session.commit()

        cleanup_old_entries(session, config.MAX_AGE_DAYS)

        if total_new > 0:
            try:
                mark_new_duplicates(session, config.DEDUP_THRESHOLD)
            except Exception:
                pass
    finally:
        session.close()

    return total_new, results


def maybe_refresh(session_factory, config):
    """Refresh feeds if data is stale (older than STALE_SECONDS).

    Returns True if a refresh was triggered.
    """
    session = session_factory()
    try:
        row = session.query(Meta).filter_by(key="last_refresh").first()
        if row:
            try:
                last = datetime.fromisoformat(row.value)
                now = datetime.now(timezone.utc)
                if (now - last).total_seconds() < config.STALE_SECONDS:
                    return False
            except Exception:
                pass
    finally:
        session.close()

    refresh_feeds_parallel(session_factory, config)
    return True
