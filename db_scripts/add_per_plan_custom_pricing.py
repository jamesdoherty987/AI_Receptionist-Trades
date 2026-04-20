"""
Add per-plan custom pricing columns to companies table.
Allows setting different custom prices for dashboard vs pro plans.
The existing custom_monthly_price / custom_stripe_price_id remain as the
"active" price used at checkout. These new columns store the per-plan values
so the admin can set both and the correct one is applied based on the account's plan.
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

    columns = [
        ("custom_dashboard_price", "NUMERIC(10,2)"),
        ("custom_dashboard_stripe_price_id", "TEXT"),
        ("custom_pro_price", "NUMERIC(10,2)"),
        ("custom_pro_stripe_price_id", "TEXT"),
    ]

    for col_name, col_type in columns:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='companies' AND column_name=%s",
            (col_name,)
        )
        if not cursor.fetchone():
            cursor.execute(f"ALTER TABLE companies ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        else:
            print(f"Column {col_name} already exists")

    conn.commit()
    cursor.close()
    conn.close()
    print("Migration complete")


if __name__ == '__main__':
    migrate()
