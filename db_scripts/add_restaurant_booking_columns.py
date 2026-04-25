"""
Add restaurant-specific columns to bookings table:
table_number, party_size, dining_area, special_requests, course_status
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
        ("table_number", "VARCHAR(20)"),
        ("party_size", "INTEGER"),
        ("dining_area", "VARCHAR(50)"),
        ("special_requests", "TEXT"),
        ("course_status", "VARCHAR(30) DEFAULT 'not_started'"),
    ]

    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE bookings ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            conn.commit()
            print(f"Added column bookings.{col_name}")
        except Exception as e:
            conn.rollback()
            print(f"Column bookings.{col_name} may already exist: {e}")

    # Indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_bookings_table_number ON bookings(table_number)",
        "CREATE INDEX IF NOT EXISTS idx_bookings_dining_area ON bookings(dining_area)",
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
    print("Done - restaurant booking columns added.")


if __name__ == "__main__":
    run()
