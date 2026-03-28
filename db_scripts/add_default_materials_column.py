"""
Add default_materials JSONB column to services and packages tables.
This allows business owners to attach typical materials to services/packages
so they auto-populate when a job is created.

default_materials format: [{"material_id": 1, "name": "Copper pipe", "unit_price": 12.50, "unit": "m", "quantity": 2}, ...]
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

    # Add default_materials to services table
    try:
        cursor.execute("""
            ALTER TABLE services ADD COLUMN IF NOT EXISTS default_materials JSONB DEFAULT '[]'
        """)
        conn.commit()
        print("[SUCCESS] Added default_materials column to services table")
    except Exception as e:
        conn.rollback()
        print(f"Error adding default_materials to services: {e}")

    # Add default_materials to packages table
    try:
        cursor.execute("""
            ALTER TABLE packages ADD COLUMN IF NOT EXISTS default_materials JSONB DEFAULT '[]'
        """)
        conn.commit()
        print("[SUCCESS] Added default_materials column to packages table")
    except Exception as e:
        conn.rollback()
        print(f"Error adding default_materials to packages: {e}")

    cursor.close()
    conn.close()
    print("Migration complete.")


if __name__ == '__main__':
    run()
