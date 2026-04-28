"""
Fix orphaned services that have NULL company_id.

These services were visible to ALL accounts due to the 'OR company_id IS NULL' bug.
This script identifies them and either:
- Assigns them to the correct company if only one company exists
- Lists them for manual review if multiple companies exist

Run with: python -m db_scripts.fix_orphaned_services
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection():
    return psycopg2.connect(os.environ.get('DATABASE_URL'))


def fix_orphaned_services():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Find orphaned services
        cursor.execute("SELECT id, name, category, created_at FROM services WHERE company_id IS NULL")
        orphaned = cursor.fetchall()

        if not orphaned:
            print("[OK] No orphaned services found. Nothing to fix.")
            return

        print(f"[WARN] Found {len(orphaned)} orphaned service(s) with NULL company_id:")
        for svc in orphaned:
            print(f"  - {svc['name']} (id={svc['id']}, category={svc['category']}, created={svc['created_at']})")

        # Check how many companies exist
        cursor.execute("SELECT id, name FROM companies")
        companies = cursor.fetchall()

        if len(companies) == 1:
            company = companies[0]
            print(f"\n[INFO] Only one company exists: {company['name']} (id={company['id']})")
            print(f"[ACTION] Assigning all orphaned services to company {company['id']}...")
            cursor.execute(
                "UPDATE services SET company_id = %s WHERE company_id IS NULL",
                (company['id'],)
            )
            conn.commit()
            print(f"[OK] Updated {cursor.rowcount} services.")
        else:
            print(f"\n[INFO] Multiple companies exist ({len(companies)}). Cannot auto-assign.")
            print("[INFO] Please manually assign these services or delete duplicates.")
            print("\nTo assign to a specific company, run:")
            print("  UPDATE services SET company_id = <COMPANY_ID> WHERE id = '<SERVICE_ID>';")
            print("\nTo delete orphaned services:")
            print("  DELETE FROM services WHERE company_id IS NULL;")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    fix_orphaned_services()
