#!/usr/bin/env python3
"""Backfill AI sentiment analysis for existing news articles.

Usage:
    python scripts/backfill_ai.py                  # all unanalyzed articles
    python scripts/backfill_ai.py --limit 100      # first 100 unanalyzed
    python scripts/backfill_ai.py --all             # re-analyze everything (overwrite)
    python scripts/backfill_ai.py --since 2026-04-01  # only articles after date
    python scripts/backfill_ai.py --dry-run         # preview without calling AI
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from app.database import init_db, get_session
from app.config import Config
from app.models import News
import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
# Show AI fallback messages
logging.getLogger("signal.ai").setLevel(logging.INFO)

from app.services.bedrock_analysis import analyze_article, _get_backend
from app.services.bedrock_config import MINIMAX_MODEL_ID, ANTHROPIC_MODEL_ID, BEDROCK_MODEL_ID


def main():
    parser = argparse.ArgumentParser(description="Backfill AI analysis for news articles")
    parser.add_argument("--limit", type=int, default=0, help="Max articles to process (0 = all)")
    parser.add_argument("--all", action="store_true", help="Re-analyze all articles (overwrite existing)")
    parser.add_argument("--since", type=str, default="", help="Only articles published after this date (YYYY-MM-DD)")
    parser.add_argument("--batch-size", type=int, default=50, help="Concurrent articles per batch (default: 50)")
    parser.add_argument("--delay", type=float, default=0.1, help="Seconds between batches (default: 0.1)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without calling AI")
    args = parser.parse_args()

    # Init DB
    init_db(Config.DATABASE_URL)
    session = get_session()

    # Determine backend
    backend = _get_backend()
    model = MINIMAX_MODEL_ID if backend == "minimax" else (ANTHROPIC_MODEL_ID if backend == "anthropic" else BEDROCK_MODEL_ID)
    print(f"Backend: {backend} | Model: {model}")

    # Query articles
    q = session.query(News)
    if not args.all:
        q = q.filter(News.ai_analyzed == False)
    if args.since:
        q = q.filter(News.published >= args.since)
    q = q.order_by(News.published.desc())
    if args.limit > 0:
        q = q.limit(args.limit)

    articles = q.all()
    total = len(articles)
    print(f"Found {total} articles to process")

    if total == 0:
        print("Nothing to do.")
        session.close()
        return

    if args.dry_run:
        for a in articles[:10]:
            print(f"  [{a.id}] {a.published[:10]} | {a.source:15s} | {a.title[:80]}")
        if total > 10:
            print(f"  ... and {total - 10} more")
        print("\nDry run — no AI calls made.")
        session.close()
        return

    # Process in concurrent batches
    # AI calls run in threads; DB writes happen on the main thread after each batch
    from concurrent.futures import ThreadPoolExecutor, as_completed

    processed = 0
    failed = 0
    start_time = time.time()

    # Detach article data for thread-safe AI calls (don't pass ORM objects to threads)
    article_data = [
        {"id": a.id, "title": a.title, "summary": a.summary or "",
         "source": a.source or "", "published": a.published or ""}
        for a in articles
    ]
    # Build id -> ORM object lookup for DB updates
    article_map = {a.id: a for a in articles}

    for i in range(0, total, args.batch_size):
        batch = article_data[i:i + args.batch_size]
        batch_start = time.time()

        # Run AI calls concurrently (thread-safe — only reads plain dicts)
        batch_results = {}
        with ThreadPoolExecutor(max_workers=min(args.batch_size, 50)) as pool:
            futures = {}
            for item in batch:
                future = pool.submit(
                    analyze_article,
                    item["title"], item["summary"],
                    item["source"], item["published"],
                )
                futures[future] = item["id"]

            for future in as_completed(futures):
                aid = futures[future]
                try:
                    batch_results[aid] = future.result()
                except Exception as e:
                    batch_results[aid] = None
                    print(f"  ERROR id={aid}: {str(e)[:80]}")

        # Write results to DB on main thread
        for aid, result in batch_results.items():
            article = article_map[aid]
            if result:
                article.sentiment_score = result["sentiment_score"]
                article.sentiment_label = result["sentiment_label"]
                article.target_asset = result["target_asset"]
                article.asset_type = result["asset_type"]
                article.confidence = result["confidence"]
                article.risk_level = result["risk_level"]
                article.tradeable = result["tradeable"]
                article.reasoning = result["reasoning"]
                article.ai_analyzed = True
                processed += 1

                ticker = result["target_asset"] or "—"
                score = result["sentiment_score"]
                label = result["sentiment_label"]
                print(f"  [{processed + failed}/{total}] {article.source:12s} | {label:7s} {score:+.2f} | {ticker:6s} | {article.title[:60]}")
            else:
                failed += 1
                print(f"  [{processed + failed}/{total}] FAILED | {article_map[aid].title[:60]}")

        batch_elapsed = time.time() - batch_start
        print(f"  --- batch {i // args.batch_size + 1}: {len(batch)} in {batch_elapsed:.1f}s ---")

        # Commit after each batch
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"  DB commit error: {e}")

        # Rate limit delay between batches
        if i + args.batch_size < total:
            time.sleep(args.delay)

    elapsed = time.time() - start_time
    rate = processed / elapsed if elapsed > 0 else 0

    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Processed: {processed}/{total}")
    print(f"  Failed:    {failed}")
    print(f"  Rate:      {rate:.1f} articles/sec")

    session.close()


if __name__ == "__main__":
    main()
