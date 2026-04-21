"""
Add admin_tab_visibility JSONB column to companies table.
Stores which tabs are enabled/disabled by admin for each company.
Defaults to all tabs ON (empty JSON = all enabled).
Backfills existing companies with all tabs enabled.
"""
import os
import sys
import json
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

# All dashboard tabs — default is all enabled
DEFAULT_TAB_VISIBILITY = {
    'jobs': True,
    'calls': True,
    'calendar': True,
    'workers': True,
    'crm': True,
    'services': True,
    'materials': True,
    'finances': True,
    'insights': True,
    'reviews': True,
}


def migrate():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # Add column if it doesn't exist
    cursor.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='companies' AND column_name='admin_tab_visibility'"
    )
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE companies ADD COLUMN admin_tab_visibility JSONB DEFAULT '{}'::jsonb")
        conn.commit()
        print("Added column: admin_tab_visibility")
    else:
        print("Column admin_tab_visibility already exists")

    # Backfill existing companies that have NULL or empty
    default_json = json.dumps(DEFAULT_TAB_VISIBILITY)
    cursor.execute(
        "UPDATE companies SET admin_tab_visibility = %s WHERE admin_tab_visibility IS NULL OR admin_tab_visibility = '{}'::jsonb",
        (default_json,)
    )
    updated = cursor.rowcount
    conn.commit()
    print(f"Backfilled {updated} companies with default tab visibility")

    cursor.close()
    conn.close()
    print("Done!")


if __name__ == '__main__':
    migrate()
