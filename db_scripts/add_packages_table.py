"""
Add packages table and package_only column to services table.
Packages allow business owners to bundle multiple services into ordered sequences.
"""
import os
import sys
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()


def migrate():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # 1. Create packages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS packages (
            id TEXT PRIMARY KEY,
            company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT,
            services JSONB NOT NULL DEFAULT '[]',
            price_override REAL DEFAULT NULL,
            price_max_override REAL DEFAULT NULL,
            use_when_uncertain BOOLEAN DEFAULT FALSE,
            clarifying_question TEXT DEFAULT NULL,
            active INTEGER DEFAULT 1,
            image_url TEXT,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("[SUCCESS] Created packages table (if not exists)")

    # 2. Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packages_company ON packages(company_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packages_active ON packages(company_id, active)")
    print("[SUCCESS] Created packages indexes")

    # 3. Add package_only column to services table
    cursor.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='services' AND column_name='package_only'"
    )
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE services ADD COLUMN package_only BOOLEAN DEFAULT FALSE")
        print("[SUCCESS] Added package_only column to services table")
    else:
        print("Column package_only already exists on services table")

    conn.commit()
    cursor.close()
    conn.close()
    print("[DONE] Packages migration complete")


if __name__ == '__main__':
    migrate()
