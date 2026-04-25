"""
Create revenue_entries table for manual income tracking.
Allows businesses to record revenue outside of booked jobs
(e.g. walk-in customers, cash sales, tips, catering deposits).
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

    # 1. Revenue entries table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS revenue_entries (
                id SERIAL PRIMARY KEY,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                amount NUMERIC(10, 2) NOT NULL DEFAULT 0,
                category VARCHAR(100) NOT NULL DEFAULT 'other',
                description TEXT,
                payment_method VARCHAR(50) DEFAULT 'cash',
                date DATE NOT NULL DEFAULT CURRENT_DATE,
                notes TEXT,
                booking_id INTEGER REFERENCES bookings(id) ON DELETE SET NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Created table: revenue_entries")
    except Exception as e:
        conn.rollback()
        print(f"Error creating revenue_entries table: {e}")

    # 2. Indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_revenue_entries_company ON revenue_entries(company_id)",
        "CREATE INDEX IF NOT EXISTS idx_revenue_entries_date ON revenue_entries(date)",
        "CREATE INDEX IF NOT EXISTS idx_revenue_entries_category ON revenue_entries(category)",
        "CREATE INDEX IF NOT EXISTS idx_revenue_entries_booking ON revenue_entries(booking_id)",
    ]
    for idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
            conn.commit()
            print("Created index")
        except Exception as e:
            conn.rollback()
            print(f"Index error: {e}")

    cursor.close()
    conn.close()
    print("Done - revenue_entries table created.")


if __name__ == "__main__":
    run()
