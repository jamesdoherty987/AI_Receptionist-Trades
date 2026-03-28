"""
Add duration_override column to packages table.
Allows business owners to set a manual total duration instead of auto-calculating from services.
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
        "SELECT column_name FROM information_schema.columns WHERE table_name='packages' AND column_name='duration_override'"
    )
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE packages ADD COLUMN duration_override INTEGER DEFAULT NULL")
        print("[SUCCESS] Added duration_override column to packages table")
    else:
        print("Column duration_override already exists on packages table")

    conn.commit()
    cursor.close()
    conn.close()
    print("[DONE] Migration complete")


if __name__ == '__main__':
    migrate()
