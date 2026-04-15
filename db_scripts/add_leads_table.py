"""
Migration: Add leads table for CRM lead pipeline tracking.
Leads can be auto-created from lost jobs/enquiries in call logs,
or manually added by the business owner.
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def run_migration():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        from dotenv import load_dotenv
        load_dotenv()
        database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("[ERROR] DATABASE_URL not set. Set it in your environment or .env file.")
        sys.exit(1)

    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id BIGSERIAL PRIMARY KEY,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
                call_log_id BIGINT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                address TEXT,
                source TEXT DEFAULT 'manual',
                stage TEXT DEFAULT 'new',
                notes TEXT,
                service_interest TEXT,
                estimated_value REAL,
                lost_reason TEXT,
                follow_up_date DATE,
                converted_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_company ON leads(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(company_id, stage)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_client ON leads(client_id)")
        print("[SUCCESS] leads table created")

        # Add tags column to clients for CRM segmentation
        try:
            cursor.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}'")
            print("[SUCCESS] Added tags column to clients")
        except Exception as e:
            print(f"[INFO] tags column may already exist: {e}")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    run_migration()
