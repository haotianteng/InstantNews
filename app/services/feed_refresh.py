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


def fetch_social_sources_to_db(session_factory, config):
    """Fetch Twitter (FM watchlist) + Truth Social (Trump) and store in News table.

    Returns dict: {"Twitter": count, "TruthSocial": count, "_new_ids": [...]}.
    Safe to call even when TWITTER_BEARER_TOKEN is unset — twitter side silently no-ops.
    """
    if not getattr(config, "SOCIAL_SOURCES_ENABLED", True):
        return {}

    from app.services.diplomatic_watchlist import twitter_handles
    from app.services.twitter_source import fetch_diplomatic_tweets
    from app.services.truth_social_source import fetch_truth_social_posts

    now_utc = utc_iso(datetime.now(timezone.utc))
    results = {}
    new_ids: list[int] = []

    # Twitter
    tw_rows: list = []
    try:
        handles = twitter_handles()
        tw_rows = fetch_diplomatic_tweets(
            getattr(config, "X_API_BEARER_TOKEN", "") or "",
            handles,
            max_results=getattr(config, "TWITTER_MAX_RESULTS_PER_RUN", 100),
        )
    except Exception:
        logger.exception("Twitter source fetch failed")
    if tw_rows:
        count, ids = _store_items(session_factory, tw_rows, now_utc)
        results["Twitter"] = count
        new_ids.extend(ids)

    # Truth Social
    try:
        ts_rows = fetch_truth_social_posts(timeout_seconds=config.FETCH_TIMEOUT * 3)
    except Exception:
        logger.exception("Truth Social source fetch failed")
        ts_rows = []
    if ts_rows:
        count, ids = _store_items(session_factory, ts_rows, now_utc)
        results["TruthSocial"] = count
        new_ids.extend(ids)

    results["_new_ids"] = new_ids
    return results


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

    # Social sources in their own thread (X API + Truth Social CNN mirror)
    social_results_holder = {}

    def social_worker():
        try:
            social_results_holder.update(fetch_social_sources_to_db(session_factory, config))
        except Exception:
            logger.exception("Social sources worker failed")

    if getattr(config, "SOCIAL_SOURCES_ENABLED", True):
        st = Thread(target=social_worker, daemon=True)
        threads.append(st)
        st.start()

    # Tight deadline: slow feeds (rsshub redirects, Google News search, etc.)
    # shouldn't dominate the tick. FETCH_TIMEOUT already caps per-feed at 5s;
    # 12s here allows some stragglers without pushing the next tick.
    deadline = time.time() + 12
    for t in threads:
        remaining = max(0.1, deadline - time.time())
        t.join(timeout=remaining)

    # Merge social counts into per-source status so /api/sources surfaces them
    if social_results_holder:
        social_new_ids = social_results_holder.pop("_new_ids", [])
        with result_lock:
            for key, count in social_results_holder.items():
                results[key] = count
            all_new_ids.extend(social_new_ids)

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

    # Run Bedrock AI analysis asynchronously so the scheduler tick can return
    # quickly. AI results land on News rows over the next several seconds/minutes
    # and the /api/news polling surfaces them as soon as they're committed.
    if all_new_ids:
        analysis_thread = Thread(
            target=_run_bedrock_analysis,
            args=(session_factory, all_new_ids),
            daemon=True,
            name=f"bedrock-{len(all_new_ids)}",
        )
        analysis_thread.start()

    return total_new, results


def _run_bedrock_analysis(session_factory, article_ids):
    """Run Bedrock AI analysis on newly stored articles and update the DB."""
    from app.services.bedrock_config import BEDROCK_ENABLED
    if not BEDROCK_ENABLED:
        logger.info("AI analysis skipped (BEDROCK_ENABLED=false)", extra={
            "event": "bedrock_skipped",
            "article_count": len(article_ids),
        })
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

    batch_size = len(batch)
    logger.info("AI analysis started", extra={
        "event": "bedrock_analysis_start",
        "batch_size": batch_size,
        "article_ids_sample": article_ids[:5],
    })

    start_time = time.time()
    try:
        from app.services.bedrock_analysis import analyze_articles_batch
        results = analyze_articles_batch(batch)
    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        logger.warning("Bedrock batch analysis failed", extra={
            "event": "bedrock_batch_error",
            "error": str(e),
            "batch_size": batch_size,
            "elapsed_seconds": elapsed,
        })
        return

    # Update articles with AI results
    session = session_factory()
    try:
        success_count = 0
        failure_count = 0
        for article_id, analysis in results.items():
            if analysis is None:
                failure_count += 1
                continue
            article = session.query(News).filter_by(id=article_id).first()
            if not article:
                failure_count += 1
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
            success_count += 1
        session.commit()
        elapsed = round(time.time() - start_time, 2)
        logger.info("AI analysis completed", extra={
            "event": "bedrock_analysis_complete",
            "batch_size": batch_size,
            "success_count": success_count,
            "failure_count": failure_count,
            "elapsed_seconds": elapsed,
        })

        # Proactive warm-up: pre-fetch company data for tagged tickers
        symbols_to_warm = {
            a["target_asset"] for a in results.values()
            if a and a.get("target_asset")
        }
        if symbols_to_warm:
            _warm_company_cache(symbols_to_warm)

    except Exception as e:
        session.rollback()
        elapsed = round(time.time() - start_time, 2)
        logger.warning("Bedrock DB update failed", extra={
            "event": "bedrock_update_error",
            "error": str(e),
            "batch_size": batch_size,
            "elapsed_seconds": elapsed,
        })
    finally:
        session.close()


def _warm_company_cache(symbols):
    """Background warm-up of company data cache for ticker symbols."""
    def _do_warm():
        try:
            from app.services.cache_manager import CompanyCache
            from app.services.market_data import PolygonClient
            cache = CompanyCache()
            client = PolygonClient(db_cache=cache)
            if not client.enabled:
                return
            stale = cache.warm(symbols, ["details", "financials"])
            for symbol, data_type in stale:
                try:
                    if data_type == "details":
                        client.get_ticker_details(symbol)
                    elif data_type == "financials":
                        client.get_financials(symbol)
                except Exception:
                    pass  # best-effort
        except Exception as e:
            logger.warning("Cache warm-up error: %s", e)

    t = Thread(target=_do_warm, daemon=True)
    t.start()


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
