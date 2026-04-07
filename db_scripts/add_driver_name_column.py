"""Add driver_name column to mileage_logs table."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import psycopg2

def migrate():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        from dotenv import load_dotenv
        load_dotenv()
        database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return
    conn = psycopg2.connect(database_url)
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE mileage_logs ADD COLUMN IF NOT EXISTS driver_name TEXT")
        conn.commit()
        cur.close()
        print("✅ Added driver_name column to mileage_logs")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
