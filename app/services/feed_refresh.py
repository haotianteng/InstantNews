"""Feed refresh orchestration — parallel fetching, storage, dedup, and AI analysis."""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from threading import Thread, Lock

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import News, Meta
from app.services.feed_parser import fetch_feed, utc_iso
from app.services.dedup import mark_new_duplicates

logger = logging.getLogger("signal.refresh")


def _store_items(session_factory, items, now_utc):
    """Store fetched items into the database. Returns (count, new_ids)."""
    session = session_factory()
    count = 0
    new_ids = []
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
                    ai_analyzed=False,
                )
                session.add(news)
                session.flush()
                new_ids.append(news.id)
                count += 1
            except IntegrityError:
                session.rollback()
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
    return count, new_ids


def fetch_single_feed_to_db(source_name, url, session_factory, config):
    """Fetch a single feed and store results. Returns (source_name, new_count, new_ids)."""
    items = fetch_feed(source_name, url, config.USER_AGENT, config.FETCH_TIMEOUT)
    if not items:
        return source_name, 0, []
    now_utc = utc_iso(datetime.now(timezone.utc))
    count, new_ids = _store_items(session_factory, items, now_utc)
    return source_name, count, new_ids


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
    all_new_ids = []
    threads = []
    result_lock = Lock()

    def worker(name, url):
        src, count, new_ids = fetch_single_feed_to_db(name, url, session_factory, config)
        with result_lock:
            results[src] = count
            all_new_ids.extend(new_ids)

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

    # Run Bedrock AI analysis on new articles (after store + dedup)
    if all_new_ids:
        _run_bedrock_analysis(session_factory, all_new_ids)

    return total_new, results


def _run_bedrock_analysis(session_factory, article_ids):
    """Run Bedrock AI analysis on newly stored articles and update the DB."""
    from app.services.bedrock_config import BEDROCK_ENABLED
    if not BEDROCK_ENABLED:
        return

    session = session_factory()
    try:
        articles = session.query(News).filter(
            News.id.in_(article_ids),
            News.ai_analyzed == False,
        ).all()

        if not articles:
            return

        batch = [
            {"id": a.id, "title": a.title, "summary": a.summary or "",
             "source": a.source or "", "published": a.published or ""}
            for a in articles
        ]
    finally:
        session.close()

    try:
        from app.services.bedrock_analysis import analyze_articles_batch
        results = analyze_articles_batch(batch)
    except Exception as e:
        logger.warning("Bedrock batch analysis failed", extra={
            "event": "bedrock_batch_error",
            "error": str(e),
            "count": len(batch),
        })
        return

    # Update articles with AI results
    session = session_factory()
    try:
        updated = 0
        for article_id, analysis in results.items():
            if analysis is None:
                continue
            article = session.query(News).filter_by(id=article_id).first()
            if not article:
                continue
            article.sentiment_score = analysis["sentiment_score"]
            article.sentiment_label = analysis["sentiment_label"]
            article.target_asset = analysis["target_asset"]
            article.asset_type = analysis["asset_type"]
            article.confidence = analysis["confidence"]
            article.risk_level = analysis["risk_level"]
            article.tradeable = analysis["tradeable"]
            article.reasoning = analysis["reasoning"]
            article.ai_analyzed = True
            updated += 1
        session.commit()
        if updated:
            logger.info("Bedrock analysis completed", extra={
                "event": "bedrock_analysis_complete",
                "analyzed": updated,
                "total": len(batch),
            })
    except Exception as e:
        session.rollback()
        logger.warning("Bedrock DB update failed", extra={
            "event": "bedrock_update_error",
            "error": str(e),
        })
    finally:
        session.close()


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
