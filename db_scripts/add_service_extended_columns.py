"""
Migration: Add extended columns to services table.
These columns support tags, capacity, deposits, warranty, seasonal,
AI notes, follow-up services, default materials, and custom categories.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.database import get_database


def migrate():
    db = get_database()
    conn = db.get_connection()
    cursor = conn.cursor()

    columns = [
        ("default_materials", "JSONB DEFAULT '[]'"),
        ("tags", "JSONB DEFAULT NULL"),
        ("capacity_min", "INTEGER DEFAULT NULL"),
        ("capacity_max", "INTEGER DEFAULT NULL"),
        ("area", "TEXT DEFAULT NULL"),
        ("requires_deposit", "BOOLEAN DEFAULT FALSE"),
        ("deposit_amount", "REAL DEFAULT NULL"),
        ("warranty", "TEXT DEFAULT NULL"),
        ("seasonal", "BOOLEAN DEFAULT FALSE"),
        ("seasonal_months", "JSONB DEFAULT NULL"),
        ("ai_notes", "TEXT DEFAULT NULL"),
        ("follow_up_service_id", "TEXT DEFAULT NULL"),
    ]

    try:
        for col_name, col_def in columns:
            cursor.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name='services' AND column_name='{col_name}') THEN
                        ALTER TABLE services ADD COLUMN {col_name} {col_def};
                    END IF;
                END $$;
            """)
            print(f"  ✓ {col_name}")

        # Also create the service_categories table for per-company custom categories
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_categories (
                id BIGSERIAL PRIMARY KEY,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                color TEXT DEFAULT NULL,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_id, name)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_svc_cat_company ON service_categories(company_id)")
        print("  ✓ service_categories table")

        conn.commit()
        print("[SUCCESS] All service extended columns added")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Migration failed: {e}")
    finally:
        db.return_connection(conn)


if __name__ == "__main__":
    migrate()
