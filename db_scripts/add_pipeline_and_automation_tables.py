"""
Migration: Add tables for deal pipeline, follow-up sequences, workflow automations,
customer portal tokens, and post-job survey automation.
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def run_migration():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        from dotenv import load_dotenv
        load_dotenv()
        database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("[ERROR] DATABASE_URL not set.")
        sys.exit(1)

    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        # 1. Quote pipeline stages — extend quotes table
        try:
            cursor.execute("ALTER TABLE quotes ADD COLUMN IF NOT EXISTS pipeline_stage TEXT DEFAULT 'draft'")
            cursor.execute("ALTER TABLE quotes ADD COLUMN IF NOT EXISTS won_at TIMESTAMPTZ")
            cursor.execute("ALTER TABLE quotes ADD COLUMN IF NOT EXISTS lost_at TIMESTAMPTZ")
            cursor.execute("ALTER TABLE quotes ADD COLUMN IF NOT EXISTS lost_reason TEXT")
            cursor.execute("ALTER TABLE quotes ADD COLUMN IF NOT EXISTS follow_up_count INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE quotes ADD COLUMN IF NOT EXISTS last_follow_up_at TIMESTAMPTZ")
            cursor.execute("ALTER TABLE quotes ADD COLUMN IF NOT EXISTS accept_token TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_pipeline ON quotes(company_id, pipeline_stage)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_accept_token ON quotes(accept_token)")
            print("[SUCCESS] Extended quotes table with pipeline columns")
        except Exception as e:
            print(f"[INFO] quotes extension: {e}")

        # 2. Follow-up sequences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS follow_up_sequences (
                id BIGSERIAL PRIMARY KEY,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                trigger_type TEXT NOT NULL DEFAULT 'quote_sent',
                enabled BOOLEAN DEFAULT true,
                steps JSONB DEFAULT '[]',
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sequences_company ON follow_up_sequences(company_id)")
        print("[SUCCESS] follow_up_sequences table created")

        # 3. Follow-up log (tracks sent messages)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS follow_up_log (
                id BIGSERIAL PRIMARY KEY,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                sequence_id BIGINT REFERENCES follow_up_sequences(id) ON DELETE SET NULL,
                quote_id BIGINT REFERENCES quotes(id) ON DELETE CASCADE,
                booking_id BIGINT,
                step_index INTEGER NOT NULL DEFAULT 0,
                channel TEXT NOT NULL DEFAULT 'email',
                sent_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'sent'
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_followup_log_quote ON follow_up_log(quote_id)")
        print("[SUCCESS] follow_up_log table created")

        # 4. Workflow automations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_automations (
                id BIGSERIAL PRIMARY KEY,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                enabled BOOLEAN DEFAULT true,
                trigger_type TEXT NOT NULL,
                trigger_config JSONB DEFAULT '{}',
                actions JSONB DEFAULT '[]',
                run_count INTEGER DEFAULT 0,
                last_run_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflows_company ON workflow_automations(company_id)")
        print("[SUCCESS] workflow_automations table created")

        # 5. Customer portal tokens
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_portal_tokens (
                id BIGSERIAL PRIMARY KEY,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                token TEXT NOT NULL UNIQUE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                last_accessed_at TIMESTAMPTZ,
                expires_at TIMESTAMPTZ
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_portal_token ON customer_portal_tokens(token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_portal_client ON customer_portal_tokens(client_id)")
        print("[SUCCESS] customer_portal_tokens table created")

        # 6. Review automation settings (per-company)
        try:
            cursor.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS review_auto_send BOOLEAN DEFAULT true")
            cursor.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS review_delay_hours INTEGER DEFAULT 24")
            cursor.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS review_google_url TEXT")
            cursor.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS google_review_threshold INTEGER DEFAULT 4")
            print("[SUCCESS] Added review automation columns to companies")
        except Exception as e:
            print(f"[INFO] review columns: {e}")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback; traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    run_migration()
