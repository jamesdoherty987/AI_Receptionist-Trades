"""
Add requires_quote column to services and bookings tables.
Defaults to FALSE so existing records are unaffected.
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

    # Add requires_quote column to services
    cursor.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='services' AND column_name='requires_quote'"
    )
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE services ADD COLUMN requires_quote BOOLEAN DEFAULT FALSE")
        print("Added requires_quote column to services table")
    else:
        print("Column requires_quote already exists on services")

    # Add requires_quote column to bookings
    cursor.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name='requires_quote'"
    )
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE bookings ADD COLUMN requires_quote BOOLEAN DEFAULT FALSE")
        print("Added requires_quote column to bookings table")
    else:
        print("Column requires_quote already exists on bookings")

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == '__main__':
    migrate()
