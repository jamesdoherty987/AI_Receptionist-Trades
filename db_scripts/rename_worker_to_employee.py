"""
Migration: Rename all 'worker' references to 'employee' in the database.

This renames:
- Tables: workers -> employees, worker_assignments -> employee_assignments,
          worker_accounts -> employee_accounts, worker_time_off -> employee_time_off
- Columns: worker_id -> employee_id (in multiple tables),
           workers_required -> employees_required (services),
           worker_restrictions -> employee_restrictions (services),
           assigned_worker_ids -> assigned_employee_ids (bookings),
           gcal_invite_workers -> gcal_invite_employees (companies)
- Indexes are recreated with new names.
- Messages table: worker_id -> employee_id

Run: python db_scripts/rename_worker_to_employee.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("[ERROR] DATABASE_URL not set")
    sys.exit(1)

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cursor = conn.cursor(cursor_factory=RealDictCursor)

def table_exists(name):
    cursor.execute("SELECT to_regclass(%s)", (name,))
    return cursor.fetchone()['to_regclass'] is not None

def column_exists(table, column):
    cursor.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return cursor.fetchone() is not None

try:
    print("=== Renaming worker -> employee in database ===\n")

    # 1. Rename tables
    renames = [
        ("workers", "employees"),
        ("worker_assignments", "employee_assignments"),
        ("worker_accounts", "employee_accounts"),
        ("worker_time_off", "employee_time_off"),
    ]
    for old, new in renames:
        if table_exists(old) and not table_exists(new):
            cursor.execute(f"ALTER TABLE {old} RENAME TO {new}")
            print(f"  Renamed table {old} -> {new}")
        elif table_exists(new):
            print(f"  Table {new} already exists, skipping")
        else:
            print(f"  Table {old} does not exist, skipping")

    # 2. Rename columns
    col_renames = [
        # (table, old_column, new_column)
        ("employee_assignments", "worker_id", "employee_id"),
        ("employee_accounts", "worker_id", "employee_id"),
        ("employee_time_off", "worker_id", "employee_id"),
        ("services", "workers_required", "employees_required"),
        ("services", "worker_restrictions", "employee_restrictions"),
        ("companies", "gcal_invite_workers", "gcal_invite_employees"),
        ("notifications", "worker_id", "employee_id"),
        ("messages", "worker_id", "employee_id"),
    ]

    # Also check bookings for assigned_worker_ids
    if column_exists("bookings", "assigned_worker_ids"):
        col_renames.append(("bookings", "assigned_worker_ids", "assigned_employee_ids"))

    for table, old_col, new_col in col_renames:
        if table_exists(table) and column_exists(table, old_col):
            cursor.execute(f"ALTER TABLE {table} RENAME COLUMN {old_col} TO {new_col}")
            print(f"  Renamed column {table}.{old_col} -> {new_col}")
        elif table_exists(table) and column_exists(table, new_col):
            print(f"  Column {table}.{new_col} already exists, skipping")
        else:
            print(f"  Table {table} or column {old_col} not found, skipping")

    # 3. Recreate indexes with new names
    # Drop old indexes (IF EXISTS) and create new ones
    index_migrations = [
        ("idx_worker_assignments_worker_id", "CREATE INDEX IF NOT EXISTS idx_employee_assignments_employee_id ON employee_assignments(employee_id)"),
        ("idx_worker_assignments_booking_id", "CREATE INDEX IF NOT EXISTS idx_employee_assignments_booking_id ON employee_assignments(booking_id)"),
        ("idx_workers_company_id", "CREATE INDEX IF NOT EXISTS idx_employees_company_id ON employees(company_id)"),
    ]
    for old_idx, create_sql in index_migrations:
        cursor.execute(f"DROP INDEX IF EXISTS {old_idx}")
        cursor.execute(create_sql)
        print(f"  Migrated index {old_idx}")

    # Also handle messages indexes if they reference worker_id
    cursor.execute("DROP INDEX IF EXISTS idx_messages_worker_id")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_employee_id ON messages(employee_id)")
    print("  Migrated messages index")

    # 4. Drop CHECK constraints that reference 'worker', update data, recreate with 'employee'
    # Find and drop all CHECK constraints on messages and notifications that contain 'worker'
    cursor.execute("""
        SELECT conname, conrelid::regclass AS table_name
        FROM pg_constraint
        WHERE contype = 'c'
          AND conrelid::regclass::text IN ('messages', 'notifications')
          AND pg_get_constraintdef(oid) ILIKE '%worker%'
    """)
    check_constraints = cursor.fetchall()
    for cc in check_constraints:
        cursor.execute(f"ALTER TABLE {cc['table_name']} DROP CONSTRAINT {cc['conname']}")
        print(f"  Dropped CHECK constraint {cc['conname']} on {cc['table_name']}")

    # Now update the data
    if table_exists("messages") and column_exists("messages", "sender_type"):
        cursor.execute("UPDATE messages SET sender_type = 'employee' WHERE sender_type = 'worker'")
        print(f"  Updated messages.sender_type: 'worker' -> 'employee' ({cursor.rowcount} rows)")
        # Recreate the constraint with 'employee' instead of 'worker'
        cursor.execute("""
            ALTER TABLE messages ADD CONSTRAINT messages_sender_type_check
            CHECK (sender_type IN ('owner', 'employee'))
        """)
        print("  Recreated messages_sender_type_check with 'employee'")

    # 5. Migrate data values: created_by 'worker:*' -> 'employee:*' in appointment_notes
    if table_exists("appointment_notes") and column_exists("appointment_notes", "created_by"):
        cursor.execute("UPDATE appointment_notes SET created_by = REPLACE(created_by, 'worker:', 'employee:') WHERE created_by LIKE 'worker:%'")
        print(f"  Updated appointment_notes.created_by: 'worker:*' -> 'employee:*' ({cursor.rowcount} rows)")

    # 6. Migrate data values: recipient_type 'worker' -> 'employee' in notifications
    if table_exists("notifications") and column_exists("notifications", "recipient_type"):
        cursor.execute("UPDATE notifications SET recipient_type = 'employee' WHERE recipient_type = 'worker'")
        print(f"  Updated notifications.recipient_type: 'worker' -> 'employee' ({cursor.rowcount} rows)")
        # Recreate constraint if one was dropped
        notif_constraints = [cc for cc in check_constraints if cc['table_name'] == 'notifications']
        if notif_constraints:
            cursor.execute("""
                ALTER TABLE notifications ADD CONSTRAINT notifications_recipient_type_check
                CHECK (recipient_type IN ('owner', 'employee'))
            """)
            print("  Recreated notifications_recipient_type_check with 'employee'")

    # 7. Migrate JSONB data: worker_restrictions key employee_ids (already correct key name)
    # The JSONB content uses 'employee_ids' already in the code, but old data may have 'worker_ids'
    if table_exists("services") and column_exists("services", "employee_restrictions"):
        cursor.execute("""
            UPDATE services 
            SET employee_restrictions = employee_restrictions - 'worker_ids' || jsonb_build_object('employee_ids', employee_restrictions->'worker_ids')
            WHERE employee_restrictions ? 'worker_ids'
        """)
        print(f"  Updated services.employee_restrictions JSONB keys ({cursor.rowcount} rows)")

    conn.commit()
    print("\n=== Migration complete! ===")

except Exception as e:
    conn.rollback()
    print(f"\n[ERROR] Migration failed: {e}")
    raise
finally:
    cursor.close()
    conn.close()
