"""
Migration: Ensure all customer portal tables and columns exist.
Safe to run multiple times — uses IF NOT EXISTS / IF NOT EXISTS throughout.
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
        print("[ERROR] DATABASE_URL not set. Set it in your environment or .env file.")
        sys.exit(1)

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cursor = conn.cursor()

    # 1. customer_portal_tokens table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_portal_tokens (
                id BIGSERIAL PRIMARY KEY,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                token TEXT NOT NULL UNIQUE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                last_accessed_at TIMESTAMPTZ
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_portal_tokens_token ON customer_portal_tokens(token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_portal_tokens_client ON customer_portal_tokens(client_id, company_id)")
        print("[SUCCESS] customer_portal_tokens table ready")
    except Exception as e:
        print(f"[INFO] customer_portal_tokens: {e}")

    # 2. customer_photo_urls column on bookings
    try:
        cursor.execute("""
            ALTER TABLE bookings
            ADD COLUMN IF NOT EXISTS customer_photo_urls JSONB DEFAULT '[]'::jsonb
        """)
        print("[SUCCESS] customer_photo_urls column ready on bookings")
    except Exception as e:
        print(f"[INFO] customer_photo_urls: {e}")

    # 3. photo_urls column on bookings (worker/owner photos)
    try:
        cursor.execute("""
            ALTER TABLE bookings
            ADD COLUMN IF NOT EXISTS photo_urls JSONB DEFAULT '[]'::jsonb
        """)
        print("[SUCCESS] photo_urls column ready on bookings")
    except Exception as e:
        print(f"[INFO] photo_urls: {e}")

    # 4. logo_url on companies (used in portal header)
    try:
        cursor.execute("""
            ALTER TABLE companies
            ADD COLUMN IF NOT EXISTS logo_url TEXT DEFAULT NULL
        """)
        print("[SUCCESS] logo_url column ready on companies")
    except Exception as e:
        print(f"[INFO] logo_url: {e}")

    cursor.close()
    conn.close()
    print("\n[DONE] Customer portal migration complete.")

if __name__ == '__main__':
    run_migration()
