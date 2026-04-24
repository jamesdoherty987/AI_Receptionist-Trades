"""
Add enhanced inventory columns to materials table:
- cost_price: purchase/cost price (for margin tracking)
- location: storage location (e.g., "Van 1", "Fridge 1", "Warehouse")
- ideal_stock: ideal/par level to have on hand
- expiry_date: expiry date for perishable items (restaurants)
- batch_number: batch/lot number for traceability
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
        ("cost_price", "NUMERIC(10, 2) DEFAULT NULL"),
        ("location", "VARCHAR(255) DEFAULT NULL"),
        ("ideal_stock", "NUMERIC(10, 2) DEFAULT NULL"),
        ("expiry_date", "DATE DEFAULT NULL"),
        ("batch_number", "VARCHAR(100) DEFAULT NULL"),
    ]

    for col_name, col_def in columns:
        try:
            cursor.execute(f"""
                ALTER TABLE materials ADD COLUMN IF NOT EXISTS {col_name} {col_def}
            """)
            conn.commit()
            print(f"Added column: materials.{col_name}")
        except Exception as e:
            conn.rollback()
            print(f"Error adding {col_name}: {e}")

    # Index for expiry date queries (restaurants checking soon-to-expire items)
    try:
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_materials_expiry
            ON materials(company_id, expiry_date)
            WHERE expiry_date IS NOT NULL
        """)
        conn.commit()
        print("Created index: idx_materials_expiry")
    except Exception as e:
        conn.rollback()
        print(f"Index error: {e}")

    # Index for location-based queries
    try:
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_materials_location
            ON materials(company_id, location)
            WHERE location IS NOT NULL
        """)
        conn.commit()
        print("Created index: idx_materials_location")
    except Exception as e:
        conn.rollback()
        print(f"Index error: {e}")

    cursor.close()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    run()
