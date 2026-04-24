"""
Add work_schedule JSONB column to employees table.
Stores each employee's default weekly schedule.
Format: { "mon": {"enabled": true, "start": "09:00", "end": "17:00"}, ... }
Defaults to null (inherits company business hours).
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
    try:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'employees' AND column_name = 'work_schedule'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE employees ADD COLUMN work_schedule JSONB DEFAULT NULL")
            conn.commit()
            print("[SUCCESS] Added work_schedule column to employees table")
        else:
            print("[SKIP] work_schedule column already exists")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    run()
