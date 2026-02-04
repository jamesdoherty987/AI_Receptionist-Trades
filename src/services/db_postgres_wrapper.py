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
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
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
            cursor = conn.cursor(cursor_factory=RealDictCursor)
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
                      password_hash: str, phone: str = None, trade_type: str = None) -> Optional[int]:
        """Create a new company account"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO companies (company_name, owner_name, email, password_hash, phone, trade_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (company_name, owner_name, email.lower().strip(), password_hash, phone, trade_type))
            company_id = cursor.fetchone()[0]
            conn.commit()
            return company_id
        except Exception as e:
            # Email already exists or other error
            conn.rollback()
            print(f"Error creating company: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    def get_company_by_email(self, email: str) -> Optional[Dict]:
        """Get company by email"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
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
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            cursor.close()
            conn.close()
    
    def get_company(self, company_id: int) -> Optional[Dict]:
        """Get company by ID (alias for get_company_by_id)"""
        return self.get_company_by_id(company_id)
    
    def update_company(self, company_id: int, **kwargs) -> bool:
        """Update company information"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            allowed_fields = ['company_name', 'owner_name', 'phone', 'trade_type', 
                              'address', 'logo_url', 'subscription_tier', 'subscription_status',
                              'stripe_customer_id', 'is_verified', 'verification_token',
                              'reset_token', 'reset_token_expires', 'last_login']
            
            fields = []
            values = []
            for key, value in kwargs.items():
                if key in allowed_fields:
                    fields.append(f"{key} = %s")
                    values.append(value)
            
            if fields:
                values.append(datetime.now())
                values.append(company_id)
                query = f"UPDATE companies SET {', '.join(fields)}, updated_at = %s WHERE id = %s"
                cursor.execute(query, values)
                conn.commit()
                success = cursor.rowcount > 0
            else:
                success = False
            
            return success
        finally:
            cursor.close()
            conn.close()
    
    def update_company_password(self, company_id: int, password_hash: str) -> bool:
        """Update company password"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cursor.execute("""
                UPDATE companies SET password_hash = %s, updated_at = %s WHERE id = %s
            """, (password_hash, datetime.now(), company_id))
            
            conn.commit()
            success = cursor.rowcount > 0
            return success
        finally:
            cursor.close()
            conn.close()
    
    def update_last_login(self, company_id: int):
        """Update the last login timestamp"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cursor.execute("""
                UPDATE companies SET last_login = %s WHERE id = %s
            """, (datetime.now(), company_id))
            
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    # Booking Methods
    
    def get_booking_by_calendar_event_id(self, calendar_event_id: str) -> Optional[Dict]:
        """Get booking by calendar event ID"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cursor.execute("SELECT * FROM bookings WHERE calendar_event_id = %s", (calendar_event_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            cursor.close()
            conn.close()
    
    def get_booking(self, booking_id: int) -> Optional[Dict]:
        """Get booking by ID"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cursor.execute("SELECT * FROM bookings WHERE id = %s", (booking_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            cursor.close()
            conn.close()
    
    def get_conflicting_bookings(self, start_time: str, end_time: str, exclude_statuses: list = None) -> List[Dict]:
        """Get bookings that conflict with a time range"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            if exclude_statuses is None:
                exclude_statuses = ['cancelled', 'completed']
            
            # Use ANY for PostgreSQL array matching
            cursor.execute("""
                SELECT id, client_id, appointment_time, service_type
                FROM bookings
                WHERE status != ALL(%s)
                AND appointment_time BETWEEN %s AND %s
            """, (exclude_statuses, start_time, end_time))
            
            rows = cursor.fetchall()
            bookings = []
            for row in rows:
                bookings.append({
                    'id': row[0],
                    'client_id': row[1],
                    'appointment_time': row[2],
                    'service_type': row[3]
                })
            return bookings
        finally:
            cursor.close()
            conn.close()
    
    def get_client_last_booking_with_address(self, client_id: int) -> Optional[Dict]:
        """Get most recent booking for client that has address/eircode/property_type"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cursor.execute("""
                SELECT address, eircode, property_type
                FROM bookings
                WHERE client_id = %s 
                AND (address IS NOT NULL OR eircode IS NOT NULL OR property_type IS NOT NULL)
                ORDER BY appointment_time DESC
                LIMIT 1
            """, (client_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'address': row[0],
                    'eircode': row[1],
                    'property_type': row[2]
                }
            return None
        finally:
            cursor.close()
            conn.close()
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
        cursor = conn.cursor(cursor_factory=RealDictCursor)
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
        cursor = conn.cursor(cursor_factory=RealDictCursor)
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
        
        WARNING: This fallback mechanism is fragile and should only be used for
        read-only operations or simple methods that don't rely on database-specific syntax.
        """
        # Import here to avoid circular import
        from src.services.database import Database
        
        print(f"⚠️ Method '{name}' not implemented in PostgreSQL wrapper, attempting fallback")
        
        # Create a Database instance if needed (for method delegation only)
        if '_sqlite_db_proxy' not in self.__dict__:
            # Temporarily clear DATABASE_URL to create SQLite instance
            original_url = os.environ.pop('DATABASE_URL', None)
            original_supabase = os.environ.pop('SUPABASE_DB_URL', None)
            
            try:
                # Create Database with a temporary path (won't actually be used for data)
                self._sqlite_db_proxy = Database(db_path="data/.temp_postgres_proxy.db")
                
                # CRITICAL: Override get_connection to use PostgreSQL
                # This redirects all database operations to PostgreSQL while keeping SQLite business logic
                original_get_connection = self.get_connection
                self._sqlite_db_proxy.get_connection = lambda: original_get_connection()
                
            except Exception as e:
                print(f"❌ Failed to create fallback proxy: {e}")
                raise AttributeError(f"Method '{name}' not implemented in PostgreSQL wrapper and fallback failed")
            finally:
                # Restore environment variables
                if original_url:
                    os.environ['DATABASE_URL'] = original_url
                if original_supabase:
                    os.environ['SUPABASE_DB_URL'] = original_supabase
        
        # Get the attribute from the proxied Database instance
        try:
            return getattr(self._sqlite_db_proxy, name)
        except AttributeError:
            raise AttributeError(f"Method '{name}' not found in PostgreSQL wrapper or SQLite Database")
