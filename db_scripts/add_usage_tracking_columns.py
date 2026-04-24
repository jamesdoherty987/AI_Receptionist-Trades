"""
Migration: Add usage-based pricing columns to companies table.

New columns:
  - included_minutes       INT     DEFAULT 200    (minutes included in plan)
  - overage_rate_cents     INT     DEFAULT 15     (cents per extra minute)
  - minutes_used           INT     DEFAULT 0      (minutes used this billing period)
  - usage_period_start     TIMESTAMP              (start of current billing period)
  - usage_period_end       TIMESTAMP              (end of current billing period)
  - usage_alert_sent       BOOLEAN DEFAULT FALSE  (80% usage alert sent this period)

Run:
  python db_scripts/add_usage_tracking_columns.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

def migrate():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    columns = [
        ("included_minutes",   "INTEGER DEFAULT 200"),
        ("overage_rate_cents", "INTEGER DEFAULT 12"),
        ("minutes_used",       "INTEGER DEFAULT 0"),
        ("usage_period_start", "TIMESTAMP"),
        ("usage_period_end",   "TIMESTAMP"),
        ("usage_alert_sent",   "BOOLEAN DEFAULT FALSE"),
        ("max_monthly_overage_cents", "INTEGER"),  # NULL = no cap; set to limit overage charges
    ]

    for col_name, col_def in columns:
        try:
            cur.execute(f"ALTER TABLE companies ADD COLUMN {col_name} {col_def}")
            print(f"  ✅ Added column: {col_name}")
        except psycopg2.errors.DuplicateColumn:
            conn.rollback()
            print(f"  ⏭️  Column already exists: {col_name}")

    # Create usage_history table for tracking historical monthly usage
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usage_history (
                id SERIAL PRIMARY KEY,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                period_start TIMESTAMP NOT NULL,
                period_end TIMESTAMP NOT NULL,
                minutes_used INTEGER NOT NULL,
                included_minutes INTEGER NOT NULL,
                overage_minutes INTEGER NOT NULL,
                overage_cost_cents INTEGER NOT NULL,
                plan VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_usage_history_company ON usage_history(company_id, period_start DESC)")
        conn.commit()
        print(f"  ✅ Created usage_history table")
    except Exception as e:
        conn.rollback()
        print(f"  ⚠️  usage_history table: {e}")

    # Create webhook_events table for idempotency (prevents duplicate processing)
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS webhook_events (
                event_id VARCHAR(255) PRIMARY KEY,
                event_type VARCHAR(100),
                processed_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
        print(f"  ✅ Created webhook_events table")
    except Exception as e:
        conn.rollback()
        print(f"  ⚠️  webhook_events table: {e}")
    
    # Fix enterprise accounts that may have gotten the default 12 cent overage rate
    try:
        cur.execute("""
            UPDATE companies
            SET overage_rate_cents = 0, included_minutes = 99999
            WHERE subscription_plan = 'enterprise'
              AND (overage_rate_cents = 12 OR included_minutes < 99999)
        """)
        if cur.rowcount > 0:
            print(f"  ✅ Fixed {cur.rowcount} enterprise accounts (set unlimited minutes, 0 overage)")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"  ⚠️  Enterprise fix: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("\n✅ Migration complete!")

if __name__ == "__main__":
    migrate()
