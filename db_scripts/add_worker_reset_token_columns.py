"""
Add reset_token and reset_token_expires columns to worker_accounts table
to support worker password reset flow.
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

    # Check if columns already exist
    cursor.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'worker_accounts' AND column_name = 'reset_token'
    """)
    if cursor.fetchone():
        print("Column reset_token already exists in worker_accounts")
        conn.close()
        return

    cursor.execute("""
        ALTER TABLE worker_accounts
        ADD COLUMN reset_token VARCHAR(255),
        ADD COLUMN reset_token_expires TIMESTAMP
    """)
    cursor.execute("CREATE INDEX idx_worker_accounts_reset_token ON worker_accounts(reset_token)")

    conn.commit()
    print("Added reset_token and reset_token_expires columns to worker_accounts")
    cursor.close()
    conn.close()


if __name__ == '__main__':
    migrate()
