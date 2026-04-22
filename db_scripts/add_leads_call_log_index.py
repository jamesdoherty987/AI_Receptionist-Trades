"""
Migration: Add index on leads.call_log_id for dedup lookups
when auto-creating leads from AI calls.
"""
import os
import sys
import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def run_migration():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        from dotenv import load_dotenv
        load_dotenv()
        database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("[ERROR] DATABASE_URL not set.")
        sys.exit(1)

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_call_log ON leads(company_id, call_log_id)")
        print("[SUCCESS] Added idx_leads_call_log index")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_phone_recent ON leads(company_id, phone, created_at DESC)")
        print("[SUCCESS] Added idx_leads_phone_recent index")
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    run_migration()
