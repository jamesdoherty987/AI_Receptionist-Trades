"""
PostgreSQL Database Wrapper
Provides the same interface as SQLite Database class but uses PostgreSQL
This allows the rest of the code to work without changes
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool as psycopg2_pool
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import contextmanager


class PostgreSQLDatabaseWrapper:
    """PostgreSQL database wrapper with SQLite-compatible interface"""
    
    def __init__(self, database_url: str):
        """Initialize PostgreSQL connection pool"""
        self.database_url = database_url
        self.connection_pool = psycopg2_pool.SimpleConnectionPool(
            minconn=1,
            maxconn=20,
            dsn=database_url
        )
        self.init_database()
    
    def get_connection(self):
        """Get connection from pool (compatible with SQLite interface)"""
        return self.connection_pool.getconn()
    
    def return_connection(self, conn):
        """Return connection to pool"""
        self.connection_pool.putconn(conn)
    
    def init_database(self):
        """Initialize database tables with PostgreSQL syntax"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Clients table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT,
                    email TEXT,
                    date_of_birth DATE,
                    description TEXT,
                    first_visit DATE,
                    last_visit DATE,
                    total_appointments INTEGER DEFAULT 0,
                    address TEXT,
                    eircode TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, phone, email)
                )
            """)
            
            # Bookings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id BIGSERIAL PRIMARY KEY,
                    client_id BIGINT,
                    calendar_event_id TEXT UNIQUE,
                    appointment_time TIMESTAMP NOT NULL,
                    service_type TEXT,
                    status TEXT DEFAULT 'scheduled',
                    urgency TEXT DEFAULT 'scheduled',
                    address TEXT,
                    eircode TEXT,
                    property_type TEXT,
                    phone_number TEXT,
                    email TEXT,
                    charge REAL DEFAULT 0,
                    payment_status TEXT DEFAULT 'unpaid',
                    payment_method TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients (id)
                )
            """)
            
            # Appointment notes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS appointment_notes (
                    id BIGSERIAL PRIMARY KEY,
                    booking_id BIGINT,
                    note TEXT NOT NULL,
                    created_by TEXT DEFAULT 'system',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (booking_id) REFERENCES bookings (id)
                )
            """)
            
            # Notes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id BIGSERIAL PRIMARY KEY,
                    client_id BIGINT,
                    note TEXT NOT NULL,
                    created_by TEXT DEFAULT 'system',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients (id)
                )
            """)
            
            # Call logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS call_logs (
                    id BIGSERIAL PRIMARY KEY,
                    phone_number TEXT,
                    duration_seconds INTEGER,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Workers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workers (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT,
                    email TEXT,
                    trade_specialty TEXT,
                    status TEXT DEFAULT 'active',
                    image_url TEXT,
                    weekly_hours_expected REAL DEFAULT 40.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Companies/Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS companies (
                    id BIGSERIAL PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    owner_name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    phone TEXT,
                    trade_type TEXT,
                    address TEXT,
                    logo_url TEXT,
                    subscription_tier TEXT DEFAULT 'free',
                    subscription_status TEXT DEFAULT 'active',
                    stripe_customer_id TEXT,
                    is_verified INTEGER DEFAULT 0,
                    verification_token TEXT,
                    reset_token TEXT,
                    reset_token_expires TIMESTAMP,
                    last_login TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Worker assignments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS worker_assignments (
                    id BIGSERIAL PRIMARY KEY,
                    booking_id BIGINT NOT NULL,
                    worker_id BIGINT NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (booking_id) REFERENCES bookings (id) ON DELETE CASCADE,
                    FOREIGN KEY (worker_id) REFERENCES workers (id) ON DELETE CASCADE,
                    UNIQUE(booking_id, worker_id)
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients(phone)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_clients_email ON clients(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_client_id ON bookings(client_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_appointment_time ON bookings(appointment_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_calendar_event_id ON bookings(calendar_event_id)")
            
            conn.commit()
            print("✅ PostgreSQL database initialized")
        except Exception as e:
            conn.rollback()
            print(f"❌ Error initializing PostgreSQL database: {e}")
            raise
        finally:
            self.return_connection(conn)
    
    # The following methods proxy to the Database class methods but convert
    # SQLite placeholders (?) to PostgreSQL placeholders (%s)
    
    def _convert_query(self, query: str) -> str:
        """Convert SQLite query syntax to PostgreSQL"""
        # Replace ? with %s for parameterized queries
        return query.replace('?', '%s')
    
    def _execute_query(self, query: str, params: tuple = None, fetch_one=False, fetch_all=False):
        """Execute query with automatic connection management"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            pg_query = self._convert_query(query)
            
            if params:
                cursor.execute(pg_query, params)
            else:
                cursor.execute(pg_query)
            
            result = None
            if fetch_one:
                result = cursor.fetchone()
            elif fetch_all:
                result = cursor.fetchall()
            
            # Get lastrowid equivalent for INSERT operations
            if query.strip().upper().startswith('INSERT') and not fetch_one:
                try:
                    cursor.execute("SELECT lastval()")
                    result = cursor.fetchone()[0]
                except:
                    result = None
            
            conn.commit()
            return result, cursor
        except Exception as e:
            conn.rollback()
            raise
        finally:
            self.return_connection(conn)
    
    # Note: All the Database class methods (add_client, get_client, etc.) 
    # would need to be re-implemented here or we need to make the Database class
    # work with both SQLite and PostgreSQL by detecting the connection type.
    
    # For now, we'll import the Database class and use composition to delegate calls
    # This is a simplified approach - in production you'd want to refactor Database
    # to be database-agnostic

    def __getattr__(self, name):
        """
        Delegate method calls to Database class instance
        This allows all existing methods to work without rewriting them
        
        IMPORTANT: This uses a clever proxy pattern that intercepts get_connection()
        calls and redirects them to PostgreSQL while keeping all SQLite business logic
        """
        # Import here to avoid circular import
        from src.services.database import Database
        
        # Create a modified Database instance that uses our PostgreSQL connection
        # Use __dict__ to avoid triggering __getattr__ recursion
        if '_sqlite_db_proxy' not in self.__dict__:
            # Temporarily disable PostgreSQL to prevent infinite recursion
            original_use_postgres = os.getenv('DATABASE_URL')
            os.environ['DATABASE_URL'] = ''
            
            # Create SQLite Database instance (but we'll hijack its connection)
            self._sqlite_db_proxy = Database()
            
            # Restore DATABASE_URL
            if original_use_postgres:
                os.environ['DATABASE_URL'] = original_use_postgres
            
            # Override get_connection to use PostgreSQL instead of SQLite
            def postgres_get_connection():
                return self.get_connection()
            
            self._sqlite_db_proxy.get_connection = postgres_get_connection
        
        # Get the attribute from the proxied Database instance
        attr = getattr(self._sqlite_db_proxy, name)
        return attr
