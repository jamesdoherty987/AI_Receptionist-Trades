"""
Add send_confirmation_sms and send_reminder_sms columns to companies table.
Both default to TRUE so existing users see no change.
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

    columns = {
        'send_confirmation_sms': 'BOOLEAN DEFAULT TRUE',
        'send_reminder_sms': 'BOOLEAN DEFAULT FALSE',
    }

    added = []
    for col, col_type in columns.items():
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='companies' AND column_name=%s",
            (col,)
        )
        if not cursor.fetchone():
            cursor.execute(f"ALTER TABLE companies ADD COLUMN {col} {col_type}")
            added.append(col)
        else:
            print(f"Column {col} already exists")

    conn.commit()
    cursor.close()
    conn.close()

    if added:
        print(f"Added columns: {', '.join(added)}")
    else:
        print("No columns needed to be added")


if __name__ == '__main__':
    migrate()
