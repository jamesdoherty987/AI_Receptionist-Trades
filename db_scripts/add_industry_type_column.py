"""
Add industry_type column to companies table.
Defaults to 'trades' so all existing accounts keep working unchanged.
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

    # Check if column already exists
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='companies' AND column_name='industry_type'"
    )
    if cursor.fetchone():
        print("Column industry_type already exists")
    else:
        cursor.execute(
            "ALTER TABLE companies ADD COLUMN industry_type TEXT DEFAULT 'trades'"
        )
        print("Added column: industry_type (default='trades')")

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == '__main__':
    migrate()
