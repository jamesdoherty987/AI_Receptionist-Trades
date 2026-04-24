"""
Add inventory tracking columns to materials table:
- stock_on_hand: current quantity in stock
- reorder_level: threshold for low-stock alerts
- sku: optional stock-keeping unit code
- notes: optional notes about the item
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
        ("stock_on_hand", "NUMERIC(10, 2) DEFAULT NULL"),
        ("reorder_level", "NUMERIC(10, 2) DEFAULT NULL"),
        ("sku", "VARCHAR(100) DEFAULT NULL"),
        ("notes", "TEXT DEFAULT NULL"),
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

    # Index on company_id + stock for low-stock queries
    try:
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_materials_low_stock
            ON materials(company_id, stock_on_hand, reorder_level)
            WHERE stock_on_hand IS NOT NULL AND reorder_level IS NOT NULL
        """)
        conn.commit()
        print("Created index: idx_materials_low_stock")
    except Exception as e:
        conn.rollback()
        print(f"Index error: {e}")

    cursor.close()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    run()
