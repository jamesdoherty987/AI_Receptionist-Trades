"""
Backfill setup_wizard_complete for legacy accounts.

Legacy accounts (created before the setup wizard existed) have used a trial
or have an active subscription but never had setup_wizard_complete set to true.
This script sets it for all such accounts so they don't see the wizard.
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

    # Find legacy accounts: have used a trial or have a subscription, but setup_wizard_complete is false
    cursor.execute("""
        UPDATE companies
        SET setup_wizard_complete = true
        WHERE (setup_wizard_complete IS NULL OR setup_wizard_complete = false)
          AND (has_used_trial = 1 OR trial_start IS NOT NULL OR stripe_subscription_id IS NOT NULL)
        RETURNING id, email
    """)

    updated = cursor.fetchall()
    conn.commit()

    if updated:
        print(f"Backfilled setup_wizard_complete for {len(updated)} legacy accounts:")
        for company_id, email in updated:
            print(f"  - Company {company_id}: {email}")
    else:
        print("No legacy accounts needed backfilling.")

    cursor.close()
    conn.close()


if __name__ == '__main__':
    migrate()
