#!/usr/bin/env python3
"""Export AI backfill data to a SQL dump for production import.

Generates UPDATE statements keyed on article link (unique identifier)
for all AI-analyzed fields.

Usage:
    python scripts/export_ai_backfill.py --dry-run            # preview count only
    python scripts/export_ai_backfill.py --output dump.sql     # export to file
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from app.database import init_db, get_session
from app.config import Config
from app.models import News


def sql_value(val: object) -> str:
    """Convert a Python value to a SQL literal, handling NULLs and escaping."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    # String — escape single quotes by doubling them
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"


def build_update(article: News) -> str:
    """Build an UPDATE statement for one article's AI fields."""
    sets = ", ".join([
        f"sentiment_score = {sql_value(article.sentiment_score)}",
        f"sentiment_label = {sql_value(article.sentiment_label)}",
        f"target_asset = {sql_value(article.target_asset)}",
        f"asset_type = {sql_value(article.asset_type)}",
        f"confidence = {sql_value(article.confidence)}",
        f"risk_level = {sql_value(article.risk_level)}",
        f"tradeable = {sql_value(article.tradeable)}",
        f"reasoning = {sql_value(article.reasoning)}",
        f"ai_analyzed = {sql_value(article.ai_analyzed)}",
    ])
    link = sql_value(article.link)
    return f"UPDATE news SET {sets} WHERE link = {link};"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export AI backfill data to SQL dump"
    )
    parser.add_argument(
        "--output", type=str, default="",
        help="Output SQL file path (required unless --dry-run)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print record count without exporting",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.output:
        parser.error("--output is required unless --dry-run is specified")

    init_db(Config.DATABASE_URL)
    session = get_session()

    try:
        articles = (
            session.query(News)
            .filter(News.ai_analyzed == True)  # noqa: E712
            .order_by(News.published.desc())
            .all()
        )
        count = len(articles)

        if args.dry_run:
            print(f"Found {count} AI-analyzed articles to export")
            for a in articles[:10]:
                pub = (a.published or "")[:10]
                src = a.source or ""
                title = (a.title or "")[:70]
                ticker = a.target_asset or "-"
                print(f"  {pub} | {src:15s} | {ticker:6s} | {title}")
            if count > 10:
                print(f"  ... and {count - 10} more")
            return

        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("-- AI backfill export\n")
            f.write(f"-- {count} records\n")
            f.write("BEGIN;\n\n")
            for article in articles:
                f.write(build_update(article) + "\n")
            f.write("\nCOMMIT;\n")

        print(f"Exported {count} records to {output_path}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
