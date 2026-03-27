"""
Add bypass_numbers column to companies table.
Stores a JSON array of phone numbers (with names) that should always
be forwarded to the fallback number, bypassing the AI receptionist.
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

    cursor.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='companies' AND column_name='bypass_numbers'"
    )
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE companies ADD COLUMN bypass_numbers TEXT DEFAULT '[]'")
        print("Added bypass_numbers column")
    else:
        print("Column bypass_numbers already exists")

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == '__main__':
    migrate()
