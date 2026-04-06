"""
Disable day-before reminder SMS for all companies.
Sets send_reminder_sms = FALSE for every company in the database.
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

    # Show current state
    cursor.execute("SELECT id, company_name, send_reminder_sms FROM companies ORDER BY id")
    rows = cursor.fetchall()
    print(f"Found {len(rows)} companies:\n")
    for row in rows:
        status = "ON" if row[2] else "OFF"
        print(f"  [{status}] Company {row[0]}: {row[1]}")

    # Update all to false
    cursor.execute("UPDATE companies SET send_reminder_sms = FALSE WHERE send_reminder_sms IS DISTINCT FROM FALSE")
    updated = cursor.rowcount

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\nUpdated {updated} companies — reminder SMS now OFF for all.")


if __name__ == '__main__':
    migrate()
