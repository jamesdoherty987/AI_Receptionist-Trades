"""
Add accounting integration columns to companies table.
Supports Xero and QuickBooks OAuth connections, plus ability to disable built-in accounting.
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

    columns = {
        'accounting_provider': "VARCHAR(50) DEFAULT 'builtin'",
        'accounting_sync_enabled': 'BOOLEAN DEFAULT FALSE',
        'last_accounting_sync': 'TIMESTAMPTZ',
        'xero_tenant_id': 'VARCHAR(255)',
        'xero_credentials_json': 'TEXT',
        'quickbooks_realm_id': 'VARCHAR(255)',
        'quickbooks_credentials_json': 'TEXT',
    }

    added = []
    for col, col_type in columns.items():
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'companies' AND column_name = %s",
            (col,)
        )
        if not cursor.fetchone():
            cursor.execute(f'ALTER TABLE companies ADD COLUMN {col} {col_type}')
            conn.commit()
            added.append(col)
            print(f"  Added column: {col}")
        else:
            print(f"  Column already exists: {col}")

    if added:
        print(f"\nMigration complete. Added {len(added)} column(s).")
    else:
        print("\nNo changes needed — all columns already exist.")

    cursor.close()
    conn.close()


if __name__ == '__main__':
    migrate()
