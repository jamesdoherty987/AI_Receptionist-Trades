"""
Ensure the clients table has an email column.
The column may already exist — this script is idempotent.
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

    try:
        cursor.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS email VARCHAR(255)")
        conn.commit()
        print("Ensured email column exists on clients table")
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")

    cursor.close()
    conn.close()
    print("Done!")


if __name__ == "__main__":
    run()
