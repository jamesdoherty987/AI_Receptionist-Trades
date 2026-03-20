"""
Add google_credentials_json and google_calendar_id columns to companies table.
Run this once against your production database.
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def migrate():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # Check which columns already exist
    cursor.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'companies'
    """)
    existing = {row[0] for row in cursor.fetchall()}

    added = []
    if 'google_credentials_json' not in existing:
        cursor.execute("ALTER TABLE companies ADD COLUMN google_credentials_json TEXT")
        added.append('google_credentials_json')

    if 'google_calendar_id' not in existing:
        cursor.execute("ALTER TABLE companies ADD COLUMN google_calendar_id TEXT")
        added.append('google_calendar_id')

    conn.commit()
    cursor.close()
    conn.close()

    if added:
        print(f"Added columns: {', '.join(added)}")
    else:
        print("Columns already exist, nothing to do.")

if __name__ == '__main__':
    migrate()
