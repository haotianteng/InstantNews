#!/usr/bin/env python3
"""Import AI backfill SQL dump into a target database.

Reads UPDATE statements from the SQL dump (export_ai_backfill.py output)
and applies them to the target DATABASE_URL, skipping articles that
already have ai_analyzed=True.

Usage:
    python scripts/import_ai_backfill.py --dry-run --input dump.sql    # validate only
    python scripts/import_ai_backfill.py --input dump.sql              # execute import
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import init_db, get_session
from app.config import Config


# Regex to parse UPDATE statements produced by export_ai_backfill.py.
# Handles multi-line reasoning fields and escaped single quotes.
_UPDATE_RE = re.compile(
    r"UPDATE news SET "
    r"sentiment_score = (NULL|[\d.eE+-]+), "
    r"sentiment_label = (NULL|'(?:[^']|'')*'), "
    r"target_asset = (NULL|'(?:[^']|'')*'), "
    r"asset_type = (NULL|'(?:[^']|'')*'), "
    r"confidence = (NULL|[\d.eE+-]+), "
    r"risk_level = (NULL|'(?:[^']|'')*'), "
    r"tradeable = (NULL|TRUE|FALSE), "
    r"reasoning = (NULL|'(?:[^']|'')*'), "
    r"ai_analyzed = (NULL|TRUE|FALSE) "
    r"WHERE link = '((?:[^']|'')*)';\s*$",
    re.DOTALL,
)


def _sql_to_python(val: str) -> Any:
    """Convert a SQL literal back to a Python value."""
    if val == "NULL":
        return None
    if val == "TRUE":
        return True
    if val == "FALSE":
        return False
    if val.startswith("'") and val.endswith("'"):
        return val[1:-1].replace("''", "'")
    try:
        if "." in val:
            return float(val)
        return int(val)
    except ValueError:
        return val


def parse_statement(stmt: str) -> dict[str, Any] | None:
    """Parse an UPDATE statement into a dict of field values and link."""
    m = _UPDATE_RE.match(stmt.strip())
    if not m:
        return None
    return {
        "sentiment_score": _sql_to_python(m.group(1)),
        "sentiment_label": _sql_to_python(m.group(2)),
        "target_asset": _sql_to_python(m.group(3)),
        "asset_type": _sql_to_python(m.group(4)),
        "confidence": _sql_to_python(m.group(5)),
        "risk_level": _sql_to_python(m.group(6)),
        "tradeable": _sql_to_python(m.group(7)),
        "reasoning": _sql_to_python(m.group(8)),
        "ai_analyzed": _sql_to_python(m.group(9)),
        "link": m.group(10).replace("''", "'"),
    }


def parse_sql_dump(sql_path: Path) -> tuple[list[dict[str, Any]], int]:
    """Parse the SQL dump, return (parsed records, parse error count).

    Handles UPDATE statements that may span multiple lines (e.g. reasoning
    fields with embedded newlines).
    """
    records: list[dict[str, Any]] = []
    parse_errors = 0
    buffer = ""

    with open(sql_path, encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip("\n")
            if buffer:
                buffer += "\n" + stripped
            elif stripped.lstrip().startswith("UPDATE news SET "):
                buffer = stripped.lstrip()
            else:
                continue

            if buffer.rstrip().endswith(";"):
                parsed = parse_statement(buffer)
                if parsed is None:
                    parse_errors += 1
                else:
                    records.append(parsed)
                buffer = ""

    if buffer:
        parse_errors += 1

    return records, parse_errors


def check_existing(
    session: Session, links: list[str]
) -> tuple[set[str], set[str]]:
    """Query target DB for existing links and which already have ai_analyzed=True.

    Returns (existing_links, already_analyzed_links).
    """
    existing: set[str] = set()
    analyzed: set[str] = set()
    batch_size = 500

    for i in range(0, len(links), batch_size):
        batch = links[i : i + batch_size]
        params = {f"l{j}": link for j, link in enumerate(batch)}
        placeholders = ", ".join(f":l{j}" for j in range(len(batch)))
        result = session.execute(
            text(
                f"SELECT link, ai_analyzed FROM news "
                f"WHERE link IN ({placeholders})"
            ),
            params,
        )
        for row in result:
            existing.add(row[0])
            if row[1]:
                analyzed.add(row[0])

    return existing, analyzed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import AI backfill SQL dump into target database"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to SQL dump file from export_ai_backfill.py",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate SQL, report counts without executing",
    )
    args = parser.parse_args()

    sql_path = Path(args.input)
    if not sql_path.exists():
        print(f"Error: file not found: {sql_path}")
        sys.exit(1)

    print(f"Parsing {sql_path}...")
    records, parse_errors = parse_sql_dump(sql_path)
    print(f"Found {len(records)} UPDATE statements ({parse_errors} parse errors)")

    if not records:
        print("No records to import")
        return

    init_db(Config.DATABASE_URL)
    session = get_session()

    try:
        links = [r["link"] for r in records]
        existing, analyzed = check_existing(session, links)

        matched = len(existing)
        skipped = len(analyzed)
        unmatched = len(links) - matched
        would_update = matched - skipped

        if args.dry_run:
            print("\n--- Dry Run Summary ---")
            print(f"  total statements: {len(records)}")
            print(f"  parse errors:     {parse_errors}")
            print(f"  matched:          {matched} (articles found in target DB)")
            print(f"  skipped:          {skipped} (already have ai_analyzed=True)")
            print(f"  would update:     {would_update}")
            print(f"  unmatched:        {unmatched} (not in target DB)")
            print(f"  errors:           {parse_errors}")
            return

        # Execute updates using parameterized query in a single transaction
        updated = 0
        exec_errors = 0
        update_sql = text(
            "UPDATE news SET "
            "sentiment_score = :sentiment_score, "
            "sentiment_label = :sentiment_label, "
            "target_asset = :target_asset, "
            "asset_type = :asset_type, "
            "confidence = :confidence, "
            "risk_level = :risk_level, "
            "tradeable = :tradeable, "
            "reasoning = :reasoning, "
            "ai_analyzed = :ai_analyzed "
            "WHERE link = :link"
        )

        for i, rec in enumerate(records):
            link = rec["link"]
            if link not in existing or link in analyzed:
                continue
            try:
                session.execute(update_sql, rec)
                updated += 1
            except Exception as e:
                exec_errors += 1
                print(f"  Error updating {link[:60]}...: {e}")

            if (updated + exec_errors) % 1000 == 0 and (updated + exec_errors) > 0:
                print(f"  Progress: {updated} updated, {exec_errors} errors...")

        session.commit()
        print("\n--- Import Summary ---")
        print(f"  matched:    {matched}")
        print(f"  updated:    {updated}")
        print(f"  skipped:    {skipped} (already had ai_analyzed=True)")
        print(f"  unmatched:  {unmatched}")
        print(f"  errors:     {parse_errors + exec_errors}")

    except Exception as e:
        session.rollback()
        print(f"Error: transaction rolled back: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
