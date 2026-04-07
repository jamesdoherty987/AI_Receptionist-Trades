"""
List all accounts in the database
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def list_accounts():
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return
    
    print(f"Connecting to: {database_url[:30]}...")
    conn = psycopg2.connect(database_url, connect_timeout=10)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("""
            SELECT id, email, company_name, owner_name, subscription_tier, created_at
            FROM companies
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()

        print(f"\n📊 Total accounts: {len(rows)}\n")
        print(f"{'ID':<6} {'Email':<35} {'Company':<25} {'Owner':<20} {'Tier':<12} {'Created'}")
        print("-" * 120)

        for row in rows:
            created = str(row.get('created_at', 'N/A'))[:19]
            print(
                f"{row['id']:<6} "
                f"{row['email']:<35} "
                f"{(row.get('company_name') or 'N/A'):<25} "
                f"{(row.get('owner_name') or 'N/A'):<20} "
                f"{(row.get('subscription_tier') or 'N/A'):<12} "
                f"{created}"
            )
    except Exception as e:
        print(f"[ERROR] Failed to list accounts: {e}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    list_accounts()
