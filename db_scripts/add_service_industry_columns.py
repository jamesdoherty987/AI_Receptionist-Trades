"""
Add industry-specific columns to the services table.

New columns:
  - category        TEXT     — service category (e.g., Plumbing, Dinner, Haircuts)
  - tags            JSONB    — array of tags/certifications
  - capacity_min    INT      — min capacity/party size (restaurant)
  - capacity_max    INT      — max capacity/party size (restaurant)
  - area            TEXT     — dining area / section (restaurant)
  - requires_deposit BOOLEAN — whether a deposit is required
  - deposit_amount  NUMERIC  — deposit amount in currency
  - warranty        TEXT     — warranty/guarantee text (trades)
  - seasonal        BOOLEAN  — whether service is seasonal
  - seasonal_months JSONB    — array of month indices (0-11)
  - ai_notes        TEXT     — free-text notes injected into AI prompt
  - follow_up_service_id UUID — links to another service as follow-up
"""

import os
import sys
import psycopg2

def run():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cur = conn.cursor()

    columns = [
        ("category", "TEXT"),
        ("tags", "JSONB DEFAULT '[]'::jsonb"),
        ("capacity_min", "INTEGER"),
        ("capacity_max", "INTEGER"),
        ("area", "TEXT"),
        ("requires_deposit", "BOOLEAN DEFAULT FALSE"),
        ("deposit_amount", "NUMERIC(10,2)"),
        ("warranty", "TEXT"),
        ("seasonal", "BOOLEAN DEFAULT FALSE"),
        ("seasonal_months", "JSONB DEFAULT '[]'::jsonb"),
        ("ai_notes", "TEXT"),
        ("follow_up_service_id", "UUID"),
    ]

    for col_name, col_type in columns:
        try:
            cur.execute(f"""
                ALTER TABLE services ADD COLUMN IF NOT EXISTS {col_name} {col_type};
            """)
            print(f"  ✓ Added column: services.{col_name}")
        except Exception as e:
            print(f"  ⚠ Column services.{col_name}: {e}")

    # Add index on category for filtering
    try:
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_services_category ON services(category) WHERE category IS NOT NULL;
        """)
        print("  ✓ Added index: idx_services_category")
    except Exception as e:
        print(f"  ⚠ Index idx_services_category: {e}")

    # Add index on seasonal for filtering
    try:
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_services_seasonal ON services(seasonal) WHERE seasonal = TRUE;
        """)
        print("  ✓ Added index: idx_services_seasonal")
    except Exception as e:
        print(f"  ⚠ Index idx_services_seasonal: {e}")

    cur.close()
    conn.close()
    print("\nDone! Service industry columns added.")

if __name__ == '__main__':
    run()
