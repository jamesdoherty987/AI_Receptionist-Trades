#!/usr/bin/env python3
"""
One-time migration: sync companies.business_hours string → business_settings.days_open.

For any company that has a business_hours string (e.g. "8 AM - 6 PM Mon-Sat"),
parse it and update the corresponding business_settings row so days_open,
opening_hours_start, and opening_hours_end match.

Safe to run multiple times — only updates rows where values differ.

Usage:
    python db_scripts/sync_business_hours.py
    python db_scripts/sync_business_hours.py --dry-run   # preview without writing
"""
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.utils.config import Config
from src.services.database import get_database
from src.services.settings_manager import get_settings_manager


def main():
    parser = argparse.ArgumentParser(description="Sync business_hours string to business_settings.days_open")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    db = get_database()
    settings_mgr = get_settings_manager()

    conn = db.get_connection()
    from psycopg2.extras import RealDictCursor
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT id, company_name, business_hours FROM companies WHERE business_hours IS NOT NULL AND business_hours != ''")
    companies = cursor.fetchall()
    db.return_connection(conn)

    print(f"Found {len(companies)} companies with business_hours set.\n")

    synced = 0
    skipped = 0

    for company in companies:
        cid = company['id']
        name = company['company_name'] or f"Company {cid}"
        hours_str = company['business_hours']

        parsed = Config.parse_business_hours_string(hours_str)
        canonical_days = parsed['days_open']
        canonical_start = parsed['start']
        canonical_end = parsed['end']

        # Get current business_settings
        bs = settings_mgr.get_business_settings(company_id=cid)
        bs_days = bs.get('days_open') or []
        if isinstance(bs_days, str):
            bs_days = json.loads(bs_days)
        bs_start = bs.get('opening_hours_start', 9)
        bs_end = bs.get('opening_hours_end', 17)

        needs_sync = (
            set(canonical_days) != set(bs_days)
            or canonical_start != bs_start
            or canonical_end != bs_end
        )

        if not needs_sync:
            print(f"  [{cid}] {name}: already in sync ({canonical_days})")
            skipped += 1
            continue

        print(f"  [{cid}] {name}:")
        print(f"       business_hours string: \"{hours_str}\"")
        print(f"       parsed → days_open={canonical_days}, start={canonical_start}, end={canonical_end}")
        print(f"       current business_settings → days_open={bs_days}, start={bs_start}, end={bs_end}")

        if args.dry_run:
            print(f"       [DRY RUN] Would sync.\n")
        else:
            sync_data = {
                'days_open': canonical_days,
                'opening_hours_start': canonical_start,
                'opening_hours_end': canonical_end,
            }
            settings_mgr.update_business_settings(sync_data, company_id=cid)
            print(f"       ✓ Synced.\n")

        synced += 1

    print(f"\nDone. Synced: {synced}, Already OK: {skipped}")
    if args.dry_run and synced > 0:
        print("(Dry run — no changes written. Run without --dry-run to apply.)")


if __name__ == "__main__":
    main()
