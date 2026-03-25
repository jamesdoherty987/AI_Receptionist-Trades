"""
Add job time tracking columns to bookings table.

Columns:
  - job_started_at: timestamp when worker pressed "Start Job"
  - job_completed_at: timestamp when worker pressed "Mark Complete"
  - actual_duration_minutes: actual time taken (auto-calculated or manually edited)
"""
import os
import sys
import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def run():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        from dotenv import load_dotenv
        load_dotenv()
        database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    columns = [
        ("job_started_at", "TIMESTAMPTZ"),
        ("job_completed_at", "TIMESTAMPTZ"),
        ("actual_duration_minutes", "INTEGER"),
    ]

    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE bookings ADD COLUMN {col_name} {col_type}")
            conn.commit()
            print(f"Added column: {col_name}")
        except psycopg2.errors.DuplicateColumn:
            conn.rollback()
            print(f"Column already exists: {col_name}")
        except Exception as e:
            conn.rollback()
            print(f"Error adding {col_name}: {e}")

    cursor.close()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    run()
