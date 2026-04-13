"""
Add subscription_plan column to companies table.
Tracks which plan the user subscribed to: 'dashboard' or 'pro'.
Existing pro users default to 'pro' plan.
Trial users get full access (pro-level) during trial.
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

    # subscription_plan: 'dashboard' or 'pro' — which product the user pays for
    # Existing pro users default to 'pro'
    cursor.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='companies' AND column_name='subscription_plan'"
    )
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE companies ADD COLUMN subscription_plan VARCHAR(20) DEFAULT 'pro'")
        print("Added column: subscription_plan")
    else:
        print("Column subscription_plan already exists")

    conn.commit()
    cursor.close()
    conn.close()
    print("Migration complete")


if __name__ == '__main__':
    migrate()
