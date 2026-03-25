"""
Create worker_accounts table for the worker portal.
Workers get invited by the business owner and set their own password on first login.
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

    # Check if table already exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'worker_accounts'
        )
    """)
    if cursor.fetchone()[0]:
        print("Table worker_accounts already exists")
        conn.close()
        return

    cursor.execute("""
        CREATE TABLE worker_accounts (
            id SERIAL PRIMARY KEY,
            worker_id INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            email VARCHAR(255) NOT NULL,
            password_hash VARCHAR(255),
            invite_token VARCHAR(255),
            invite_expires_at TIMESTAMP,
            password_set BOOLEAN DEFAULT FALSE,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(email),
            UNIQUE(worker_id)
        )
    """)

    # Index for fast lookups
    cursor.execute("CREATE INDEX idx_worker_accounts_email ON worker_accounts(email)")
    cursor.execute("CREATE INDEX idx_worker_accounts_invite_token ON worker_accounts(invite_token)")
    cursor.execute("CREATE INDEX idx_worker_accounts_worker_id ON worker_accounts(worker_id)")

    conn.commit()
    cursor.close()
    conn.close()

    print("Created worker_accounts table successfully")


if __name__ == '__main__':
    migrate()
