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
    
    # Authentication & Company Management Methods
    
    def create_company(self, company_name: str, owner_name: str, email: str, 
                      password_hash: str, phone: str = None, address: str = None) -> int:
        """Create a new company"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO companies (company_name, owner_name, email, password_hash, phone, address)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (company_name, owner_name, email, password_hash, phone, address))
            company_id = cursor.fetchone()[0]
            conn.commit()
            return company_id
        finally:
            cursor.close()
            conn.close()
    
    def get_company_by_email(self, email: str) -> Optional[Dict]:
        """Get company by email"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM companies WHERE email = %s", (email,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            cursor.close()
            conn.close()
    
    def get_company_by_id(self, company_id: int) -> Optional[Dict]:
        """Get company by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            cursor.close()
            conn.close()
    
    def update_company_session(self, company_id: int, session_token: str) -> bool:
        """Update company session token"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE companies 
                SET session_token = %s, last_login = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (session_token, company_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
            conn.close()
    
    def get_company_by_session(self, session_token: str) -> Optional[Dict]:
        """Get company by session token"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM companies WHERE session_token = %s", (session_token,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            cursor.close()
            conn.close()
    
    def __getattr__(self, name):
        """
        Delegate unknown method calls to Database class
        This allows fallback for methods not yet implemented in PostgreSQL wrapper
        """
        # Import here to avoid circular import
        from src.services.database import Database
        
        # For missing methods, try to use the SQLite Database implementation
        # but with PostgreSQL connection hijacking
        print(f"⚠️ Method '{name}' not implemented in PostgreSQL wrapper, using SQLite fallback")
        
        # Create a Database instance if needed
        if '_sqlite_db_proxy' not in self.__dict__:
            # Temporarily clear DATABASE_URL to create SQLite instance
            original_url = os.environ.pop('DATABASE_URL', None)
            try:
                self._sqlite_db_proxy = Database()
                # Override its get_connection method
                self._sqlite_db_proxy.get_connection = self.get_connection
            finally:
                if original_url:
                    os.environ['DATABASE_URL'] = original_url
        
        return getattr(self._sqlite_db_proxy, name)
