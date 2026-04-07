"""
Add easy_setup column to companies table.

When easy_setup = false, the account was set up by the admin (managed onboarding).
When easy_setup = true (default), the user self-serves through the onboarding wizard.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

def migrate():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Add easy_setup column (defaults to true for existing self-service accounts)
    try:
        cursor.execute("""
            ALTER TABLE companies
            ADD COLUMN IF NOT EXISTS easy_setup BOOLEAN DEFAULT true
        """)
        conn.commit()
        print("✅ Added easy_setup column to companies table")
    except Exception as e:
        conn.rollback()
        print(f"⚠️  easy_setup column may already exist: {e}")

    # Add owner_invite_token and owner_invite_expires columns for managed setup password flow
    try:
        cursor.execute("""
            ALTER TABLE companies
            ADD COLUMN IF NOT EXISTS owner_invite_token TEXT,
            ADD COLUMN IF NOT EXISTS owner_invite_expires TIMESTAMP
        """)
        conn.commit()
        print("✅ Added owner_invite_token and owner_invite_expires columns")
    except Exception as e:
        conn.rollback()
        print(f"⚠️  owner invite columns may already exist: {e}")

    cursor.close()
    conn.close()
    print("\nMigration complete.")

if __name__ == "__main__":
    migrate()
