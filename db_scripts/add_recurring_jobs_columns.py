"""Add recurring job columns to bookings table."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.db_postgres_wrapper import PostgresDatabase

def migrate():
    db = PostgresDatabase()
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS recurrence_pattern VARCHAR(20)")
        cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS recurrence_end_date DATE")
        cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS parent_booking_id BIGINT")
        conn.commit()
        cur.close()
        print("Added recurrence_pattern, recurrence_end_date, parent_booking_id columns to bookings")
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        db.return_connection(conn)

if __name__ == '__main__':
    migrate()
