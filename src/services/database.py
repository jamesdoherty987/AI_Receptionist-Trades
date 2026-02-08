"""
Database module for AI Trades Receptionist
Uses PostgreSQL via DATABASE_URL environment variable
"""
import os
import threading
from typing import Optional


# Ensure PostgreSQL is configured
_DATABASE_URL = os.getenv('DATABASE_URL')
if not _DATABASE_URL:
    raise EnvironmentError(
        "DATABASE_URL environment variable is required. "
        "Set it to your PostgreSQL connection string."
    )

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    print(f"✅ Using PostgreSQL database")
    db_url = _DATABASE_URL
    print(f"   Database: {db_url[:30]}..." if db_url else "   No URL found")
except ImportError as e:
    raise ImportError(
        f"psycopg2 is required for PostgreSQL: {e}. "
        "Install it with: pip install psycopg2-binary"
    )


# Global database instance
_db = None
_db_lock = threading.Lock()


def get_database():
    """
    Get or create global database instance (thread-safe)
    Uses PostgreSQL via DATABASE_URL
    """
    global _db
    if _db is None:
        with _db_lock:
            # Double-check locking pattern
            if _db is None:
                from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
                db_url = os.getenv('DATABASE_URL')
                try:
                    _db = PostgreSQLDatabaseWrapper(db_url)
                    print("✅ Connected to PostgreSQL database")
                except Exception as e:
                    print(f"⚠️ PostgreSQL init_database had an issue: {e}")
                    print("   Retrying with skip_init...")
                    # Create wrapper without init (tables likely already exist)
                    wrapper = object.__new__(PostgreSQLDatabaseWrapper)
                    wrapper.database_url = db_url
                    wrapper._pool_lock = threading.Lock()
                    from psycopg2 import pool as psycopg2_pool
                    wrapper.connection_pool = psycopg2_pool.ThreadedConnectionPool(
                        minconn=1, maxconn=10, dsn=db_url
                    )
                    wrapper.use_postgres = True
                    _db = wrapper
                    print("✅ Connected to PostgreSQL database (skipped init)")
    return _db
