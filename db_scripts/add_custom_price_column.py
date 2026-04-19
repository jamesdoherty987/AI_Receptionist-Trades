"""
Add custom_stripe_price_id and custom_monthly_price columns to companies table.
Allows per-account custom pricing for subscriptions.
When set, the checkout session uses this price instead of the global default.
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

    # custom_stripe_price_id: override the default Stripe price for this account
    cursor.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='companies' AND column_name='custom_stripe_price_id'"
    )
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE companies ADD COLUMN custom_stripe_price_id TEXT")
        print("Added column: custom_stripe_price_id")
    else:
        print("Column custom_stripe_price_id already exists")

    # custom_monthly_price: display price override (in EUR) so frontend shows the right number
    cursor.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='companies' AND column_name='custom_monthly_price'"
    )
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE companies ADD COLUMN custom_monthly_price NUMERIC(10,2)")
        print("Added column: custom_monthly_price")
    else:
        print("Column custom_monthly_price already exists")

    conn.commit()
    cursor.close()
    conn.close()
    print("Migration complete")


if __name__ == '__main__':
    migrate()
