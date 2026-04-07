#!/usr/bin/env python3
"""Seed the first superadmin user.

Usage:
    python scripts/seed_admin.py <email>
    python scripts/seed_admin.py havens.teng@gmail.com

The user must already exist in the DB (i.e., they've signed in at least once).
This script promotes them to superadmin.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from app.database import init_db, get_session
from app.config import Config
from app.models import User
from app.services.feed_parser import utc_iso
from datetime import datetime, timezone


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_admin.py <email>")
        print("  Promotes an existing user to superadmin.")
        sys.exit(1)

    email = sys.argv[1].strip()
    init_db(Config.DATABASE_URL)
    session = get_session()

    user = session.query(User).filter_by(email=email).first()
    if not user:
        print(f"Error: User '{email}' not found in database.")
        print("  The user must sign in at least once before being promoted.")
        session.close()
        sys.exit(1)

    old_role = user.role if hasattr(user, "role") else "user"
    user.role = "superadmin"
    user.updated_at = utc_iso(datetime.now(timezone.utc))
    session.commit()

    print(f"Done: {email} promoted to superadmin (was: {old_role})")
    print(f"  User ID: {user.id}")
    print(f"  They can now access /admin and manage all users.")

    session.close()


if __name__ == "__main__":
    main()
