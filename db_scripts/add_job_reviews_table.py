"""
Migration: Add job_reviews table for customer satisfaction tracking.
Run this script to add the job_reviews table to an existing database.
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
            CREATE TABLE IF NOT EXISTS job_reviews (
                id BIGSERIAL PRIMARY KEY,
                booking_id BIGINT NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
                review_token VARCHAR(64) UNIQUE NOT NULL,
                rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                review_text TEXT,
                customer_name TEXT,
                service_type TEXT,
                email_sent_at TIMESTAMPTZ,
                submitted_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_reviews_company ON job_reviews(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_reviews_booking ON job_reviews(booking_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_reviews_token ON job_reviews(review_token)")
        print("[SUCCESS] job_reviews table created")
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    run_migration()
