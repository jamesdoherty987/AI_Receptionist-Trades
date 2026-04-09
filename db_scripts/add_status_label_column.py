"""Add status_label column to bookings table for custom job status labels."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.db_postgres_wrapper import PostgresDatabase

def migrate():
    db = PostgresDatabase()
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS status_label VARCHAR(100)")
        conn.commit()
        cur.close()
        print("Added status_label column to bookings table")
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        db.return_connection(conn)

if __name__ == '__main__':
    migrate()
