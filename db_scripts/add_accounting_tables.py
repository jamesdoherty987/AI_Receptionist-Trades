"""
Create accounting tables: expenses, quotes, and tax_settings.
Also adds invoice_number, invoice_sent_at, invoice_due_date columns to bookings.
"""
import os
import sys
import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def run():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        from dotenv import load_dotenv
        load_dotenv()
        database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # 1. Expenses table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                amount NUMERIC(10, 2) NOT NULL DEFAULT 0,
                category VARCHAR(100) NOT NULL DEFAULT 'other',
                description TEXT,
                vendor VARCHAR(255),
                date DATE NOT NULL DEFAULT CURRENT_DATE,
                receipt_url TEXT,
                is_recurring BOOLEAN DEFAULT FALSE,
                recurring_frequency VARCHAR(20),
                tax_deductible BOOLEAN DEFAULT TRUE,
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Created table: expenses")
    except Exception as e:
        conn.rollback()
        print(f"Error creating expenses table: {e}")

    # 2. Quotes / Estimates table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id SERIAL PRIMARY KEY,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                quote_number VARCHAR(50),
                title VARCHAR(255),
                description TEXT,
                line_items JSONB DEFAULT '[]',
                subtotal NUMERIC(10, 2) DEFAULT 0,
                tax_rate NUMERIC(5, 2) DEFAULT 0,
                tax_amount NUMERIC(10, 2) DEFAULT 0,
                total NUMERIC(10, 2) DEFAULT 0,
                status VARCHAR(30) DEFAULT 'draft',
                valid_until DATE,
                notes TEXT,
                converted_booking_id INTEGER REFERENCES bookings(id) ON DELETE SET NULL,
                sent_at TIMESTAMPTZ,
                accepted_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Created table: quotes")
    except Exception as e:
        conn.rollback()
        print(f"Error creating quotes table: {e}")

    # 3. Add invoice/tax columns to bookings
    invoice_columns = [
        ("invoice_number", "VARCHAR(50)"),
        ("invoice_sent_at", "TIMESTAMPTZ"),
        ("invoice_due_date", "DATE"),
        ("tax_rate", "NUMERIC(5, 2) DEFAULT 0"),
        ("tax_amount", "NUMERIC(10, 2) DEFAULT 0"),
        ("stripe_checkout_url", "TEXT"),
    ]
    for col_name, col_type in invoice_columns:
        try:
            cursor.execute(f"""
                ALTER TABLE bookings ADD COLUMN IF NOT EXISTS {col_name} {col_type}
            """)
            conn.commit()
            print(f"Added column bookings.{col_name}")
        except Exception as e:
            conn.rollback()
            print(f"Column bookings.{col_name} may already exist: {e}")

    # 4. Add tax settings columns to companies
    tax_columns = [
        ("tax_rate", "NUMERIC(5, 2) DEFAULT 0"),
        ("tax_id_number", "VARCHAR(100)"),
        ("tax_id_label", "VARCHAR(50) DEFAULT 'VAT'"),
        ("invoice_prefix", "VARCHAR(20) DEFAULT 'INV'"),
        ("invoice_next_number", "INTEGER DEFAULT 1"),
        ("invoice_payment_terms_days", "INTEGER DEFAULT 14"),
        ("invoice_footer_note", "TEXT"),
        ("default_expense_categories", "TEXT"),
    ]
    for col_name, col_type in tax_columns:
        try:
            cursor.execute(f"""
                ALTER TABLE companies ADD COLUMN IF NOT EXISTS {col_name} {col_type}
            """)
            conn.commit()
            print(f"Added column companies.{col_name}")
        except Exception as e:
            conn.rollback()
            print(f"Column companies.{col_name} may already exist: {e}")

    # 5. Indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_expenses_company ON expenses(company_id)",
        "CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)",
        "CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)",
        "CREATE INDEX IF NOT EXISTS idx_quotes_company ON quotes(company_id)",
        "CREATE INDEX IF NOT EXISTS idx_quotes_status ON quotes(status)",
        "CREATE INDEX IF NOT EXISTS idx_bookings_invoice_due ON bookings(invoice_due_date)",
    ]
    for idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
            conn.commit()
            print("Created index")
        except Exception as e:
            conn.rollback()
            print(f"Index error: {e}")

    # 6. Job sub-tasks table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_tasks (
                id SERIAL PRIMARY KEY,
                booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                status VARCHAR(30) DEFAULT 'pending',
                estimated_cost NUMERIC(10, 2) DEFAULT 0,
                assigned_worker_id INTEGER REFERENCES workers(id) ON DELETE SET NULL,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Created table: job_tasks")
    except Exception as e:
        conn.rollback()
        print(f"Error creating job_tasks table: {e}")

    # 7. Purchase orders table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id SERIAL PRIMARY KEY,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                po_number VARCHAR(50),
                supplier VARCHAR(255),
                items JSONB DEFAULT '[]',
                total NUMERIC(10, 2) DEFAULT 0,
                status VARCHAR(30) DEFAULT 'draft',
                notes TEXT,
                booking_id INTEGER REFERENCES bookings(id) ON DELETE SET NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Created table: purchase_orders")
    except Exception as e:
        conn.rollback()
        print(f"Error creating purchase_orders table: {e}")

    # Additional indexes
    extra_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_job_tasks_booking ON job_tasks(booking_id)",
        "CREATE INDEX IF NOT EXISTS idx_job_tasks_company ON job_tasks(company_id)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_orders_company ON purchase_orders(company_id)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_orders_status ON purchase_orders(status)",
    ]
    for idx_sql in extra_indexes:
        try:
            cursor.execute(idx_sql)
            conn.commit()
        except Exception as e:
            conn.rollback()

    cursor.close()
    conn.close()
    print("Done - accounting tables created.")


if __name__ == "__main__":
    run()
