"""
List all accounts in the database
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.services.database import get_database


def list_accounts():
    db = get_database()
    conn = db.get_connection()

    from psycopg2.extras import RealDictCursor
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("""
            SELECT id, email, company_name, owner_name, subscription_tier, created_at
            FROM companies
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()

        print(f"\n📊 Total accounts: {len(rows)}\n")
        print(f"{'ID':<40} {'Email':<35} {'Company':<25} {'Owner':<20} {'Tier':<12} {'Created'}")
        print("-" * 170)

        for row in rows:
            created = str(row.get('created_at', 'N/A'))[:19]
            print(
                f"{row['id']:<40} "
                f"{row['email']:<35} "
                f"{(row.get('company_name') or 'N/A'):<25} "
                f"{(row.get('owner_name') or 'N/A'):<20} "
                f"{(row.get('subscription_tier') or 'N/A'):<12} "
                f"{created}"
            )
    finally:
        cursor.close()
        db.return_connection(conn)


if __name__ == "__main__":
    list_accounts()
