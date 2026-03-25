"""
Add show_insights_tab column to companies table.
Defaults to TRUE so existing users see the new tab.
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
        "SELECT column_name FROM information_schema.columns WHERE table_name='companies' AND column_name='show_insights_tab'"
    )
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE companies ADD COLUMN show_insights_tab BOOLEAN DEFAULT TRUE")
        conn.commit()
        print("Added column: show_insights_tab")
    else:
        print("Column show_insights_tab already exists")

    cursor.close()
    conn.close()


if __name__ == '__main__':
    migrate()
