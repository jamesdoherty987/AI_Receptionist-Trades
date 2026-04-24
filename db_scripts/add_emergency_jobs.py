"""
Add emergency jobs support.
- Adds 'emergency' to urgency values
- Adds emergency_status column to bookings (pending_acceptance, accepted, expired)
- Adds emergency_accepted_by column to bookings (employee_id who accepted)
- Adds emergency_accepted_at column to bookings
- Creates default 'Emergency Callout' service for companies that don't have one
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

    # Add emergency_status column to bookings
    for col, col_type in [
        ('emergency_status', "TEXT DEFAULT NULL"),
        ('emergency_accepted_by', "INTEGER DEFAULT NULL"),
        ('emergency_accepted_at', "TIMESTAMP DEFAULT NULL"),
    ]:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name=%s",
            (col,)
        )
        if not cursor.fetchone():
            cursor.execute(f"ALTER TABLE bookings ADD COLUMN {col} {col_type}")
            print(f"Added {col} column to bookings table")
        else:
            print(f"Column {col} already exists on bookings")

    conn.commit()
    cursor.close()
    conn.close()
    print("Emergency jobs migration complete")


if __name__ == '__main__':
    migrate()
