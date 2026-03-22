"""
Add requires_callout column to services table.
Defaults to FALSE so existing services are unaffected.
Also renames existing 'General Service' to 'General Callout' for all companies.
"""
import os
import sys
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()


def migrate():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # Add requires_callout column to services
    cursor.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='services' AND column_name='requires_callout'"
    )
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE services ADD COLUMN requires_callout BOOLEAN DEFAULT FALSE")
        print("Added requires_callout column to services table")
    else:
        print("Column requires_callout already exists on services")

    # Rename 'General Service' to 'General Callout' for all companies
    cursor.execute("UPDATE services SET name = 'General Callout' WHERE name = 'General Service'")
    updated = cursor.rowcount
    if updated:
        print(f"Renamed {updated} 'General Service' entries to 'General Callout'")
    else:
        print("No 'General Service' entries found to rename")

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == '__main__':
    migrate()
