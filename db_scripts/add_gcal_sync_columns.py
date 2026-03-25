#!/usr/bin/env python3
"""
Add gcal_synced_at and updated_at columns to bookings table.
These enable incremental sync — only push bookings that changed since last sync.

Usage:
    python db_scripts/add_gcal_sync_columns.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.services.database import get_database


def migrate():
    db = get_database()
    conn = db.get_connection()
    cursor = conn.cursor()

    columns = {
        'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
        'gcal_synced_at': 'TIMESTAMP',
    }

    for col, col_type in columns.items():
        try:
            cursor.execute(f"""
                ALTER TABLE bookings ADD COLUMN IF NOT EXISTS {col} {col_type}
            """)
            print(f"  ✅ Added column: {col}")
        except Exception as e:
            if 'already exists' in str(e).lower():
                print(f"  ⏭️  Column {col} already exists")
                conn.rollback()
            else:
                print(f"  ❌ Error adding {col}: {e}")
                conn.rollback()
                continue

    # Backfill updated_at from created_at where NULL
    try:
        cursor.execute("""
            UPDATE bookings SET updated_at = created_at WHERE updated_at IS NULL
        """)
        rows = cursor.rowcount
        print(f"  ✅ Backfilled updated_at for {rows} rows")
    except Exception as e:
        print(f"  ⚠️  Backfill error: {e}")
        conn.rollback()

    conn.commit()
    db.return_connection(conn)
    print("\nDone.")


if __name__ == "__main__":
    migrate()
