"""
Add gcal_invite_workers column to companies table.
Defaults to FALSE so existing users don't get surprise invitation emails.
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

    col = 'gcal_invite_workers'
    col_type = 'BOOLEAN DEFAULT FALSE'

    cursor.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='companies' AND column_name=%s",
        (col,)
    )
    if not cursor.fetchone():
        cursor.execute(f"ALTER TABLE companies ADD COLUMN {col} {col_type}")
        print(f"Added column: {col}")
    else:
        print(f"Column {col} already exists")

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == '__main__':
    migrate()
