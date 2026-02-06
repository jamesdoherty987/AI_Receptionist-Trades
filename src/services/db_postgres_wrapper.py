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
        # Connection pool sized for free tier - keeps connections warm
        self.connection_pool = psycopg2_pool.SimpleConnectionPool(
            minconn=2,  # Keep 2 connections always open
            maxconn=20,  # Allow up to 20 concurrent connections
            dsn=database_url
        )
        self.use_postgres = True  # Flag for compatibility
        print(f"✅ PostgreSQL connection pool initialized (2-20 connections)")
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
            
            # Companies/Users table (includes API configurations per company)
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
                    business_hours TEXT DEFAULT '8 AM - 6 PM Mon-Sat (24/7 emergency available)',
                    subscription_tier TEXT DEFAULT 'free',
                    subscription_status TEXT DEFAULT 'active',
                    stripe_customer_id TEXT,
                    is_verified INTEGER DEFAULT 0,
                    verification_token TEXT,
                    reset_token TEXT,
                    reset_token_expires TIMESTAMP,
                    last_login TIMESTAMP,
                    -- Twilio phone number assigned from pool
                    twilio_phone_number TEXT UNIQUE,
                    -- Legacy fields (no longer used - kept for backwards compatibility)
                    openai_api_key TEXT,
                    deepgram_api_key TEXT,
                    elevenlabs_api_key TEXT,
                    elevenlabs_voice_id TEXT,
                    google_calendar_id TEXT,
                    google_credentials_json TEXT,
                    ai_enabled BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Twilio Phone Numbers Pool
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS twilio_phone_numbers (
                    id BIGSERIAL PRIMARY KEY,
                    phone_number TEXT UNIQUE NOT NULL,
                    assigned_to_company_id BIGINT REFERENCES companies(id) ON DELETE SET NULL,
                    assigned_at TIMESTAMP,
                    status TEXT DEFAULT 'available',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK (status IN ('available', 'assigned'))
                )
            """)
            
            # Index for quick lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_twilio_phone_status 
                ON twilio_phone_numbers(status)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_twilio_phone_company 
                ON twilio_phone_numbers(assigned_to_company_id)
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
            
            # Services table (formerly in services_menu.json)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    duration_minutes INTEGER DEFAULT 60,
                    price REAL DEFAULT 0,
                    emergency_price REAL,
                    currency TEXT DEFAULT 'EUR',
                    active INTEGER DEFAULT 1,
                    image_url TEXT,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Business settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS business_settings (
                    id BIGSERIAL PRIMARY KEY,
                    business_name TEXT,
                    phone TEXT,
                    email TEXT,
                    address TEXT,
                    country_code TEXT DEFAULT '+353',
                    calendar_id TEXT,
                    working_hours JSONB,
                    logo_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Developer settings table (deprecated - kept for backwards compatibility)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS developer_settings (
                    id BIGSERIAL PRIMARY KEY,
                    openai_api_key TEXT,
                    deepgram_api_key TEXT,
                    elevenlabs_api_key TEXT,
                    elevenlabs_voice_id TEXT,
                    google_credentials_json TEXT,
                    stripe_secret_key TEXT,
                    stripe_price_id TEXT,
                    public_url TEXT,
                    ws_public_url TEXT,
                    ai_enabled BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            result = cursor.fetchone()
            company_id = result['id'] if result else None
            conn.commit()
            return company_id
        except Exception as e:
            # Email already exists or other error
            conn.rollback()
            print(f"Error creating company: {e}")
            return None
        finally:
            self.return_connection(conn)
    
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
            self.return_connection(conn)
    
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
            self.return_connection(conn)
    
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
            self.return_connection(conn)
    
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
            self.return_connection(conn)
    
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
            self.return_connection(conn)
    
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
            self.return_connection(conn)
    
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
            self.return_connection(conn)
    
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
            self.return_connection(conn)
    
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
            self.return_connection(conn)
        try:
            cursor.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            cursor.close()
            self.return_connection(conn)
    
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
            self.return_connection(conn)
    
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
            self.return_connection(conn)
    
    def get_all_clients(self) -> List[Dict]:
        """Get all clients"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM clients ORDER BY created_at DESC")
            rows = cursor.fetchall()
            
            return [{
                'id': row['id'],
                'name': row['name'],
                'phone': row['phone'],
                'email': row['email'],
                'first_visit': row.get('first_visit'),
                'last_visit': row.get('last_visit'),
                'total_appointments': row.get('total_appointments', 0),
                'created_at': row.get('created_at'),
                'updated_at': row.get('updated_at'),
                'date_of_birth': row.get('date_of_birth'),
                'description': row.get('description'),
                'address': row.get('address'),
                'eircode': row.get('eircode')
            } for row in rows]
        finally:
            self.return_connection(conn)
    
    def get_all_bookings(self) -> List[Dict]:
        """Get all bookings"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT 
                    b.id, b.client_id, b.calendar_event_id, b.appointment_time, 
                    b.service_type, b.status, b.phone_number, b.email, b.created_at,
                    b.charge, b.payment_status, b.payment_method, b.urgency, 
                    b.address, b.eircode, b.property_type,
                    c.name as client_name, c.phone as client_phone, c.email as client_email
                FROM bookings b
                LEFT JOIN clients c ON b.client_id = c.id
                ORDER BY b.appointment_time DESC
            """)
            rows = cursor.fetchall()
            
            return [{
                'id': row['id'],
                'client_id': row['client_id'],
                'calendar_event_id': row['calendar_event_id'],
                'appointment_time': row['appointment_time'],
                'service_type': row['service_type'],
                'service': row['service_type'],  # Alias for compatibility
                'status': row['status'],
                'phone_number': row['phone_number'],
                'phone': row['phone_number'] or row['client_phone'],  # Use booking phone or client phone as fallback
                'email': row['email'] or row['client_email'],  # Use booking email or client email as fallback
                'created_at': row['created_at'],
                'charge': row['charge'],
                'estimated_charge': row['charge'],  # Alias for compatibility
                'payment_status': row['payment_status'],
                'payment_method': row['payment_method'],
                'urgency': row['urgency'],
                'address': row['address'],
                'job_address': row['address'],  # Alias for compatibility
                'eircode': row['eircode'],
                'property_type': row['property_type'],
                'customer_name': row['client_name'],
                'client_name': row['client_name'],  # Alias for compatibility
                'notes': ''  # Will be fetched separately if needed
            } for row in rows]
        finally:
            self.return_connection(conn)
    
    def get_all_workers(self) -> List[Dict]:
        """Get all workers"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM workers ORDER BY name ASC")
            rows = cursor.fetchall()
            
            return [{
                'id': row['id'],
                'name': row['name'],
                'phone': row['phone'],
                'email': row['email'],
                'trade_specialty': row['trade_specialty'],
                'status': row['status'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'image_url': row.get('image_url'),
                'weekly_hours_expected': row.get('weekly_hours_expected', 40.0)
            } for row in rows]
        finally:
            self.return_connection(conn)
    
    def add_client(self, name: str, phone: str = None, email: str = None, 
                   date_of_birth: str = None, description: str = None) -> Optional[int]:
        """Add a new client"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO clients (name, phone, email, date_of_birth, description, first_visit)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (name, phone, email, date_of_birth, description, datetime.now()))
            
            result = cursor.fetchone()
            client_id = result['id'] if result else None
            conn.commit()
            return client_id
        except Exception as e:
            # Client already exists or other error
            conn.rollback()
            print(f"Error adding client: {e}")
            # Try to find existing client
            try:
                cursor.execute("""
                    SELECT id FROM clients 
                    WHERE name = %s AND (phone = %s OR email = %s)
                """, (name, phone, email))
                row = cursor.fetchone()
                return row['id'] if row else None
            except:
                return None
        finally:
            self.return_connection(conn)
    
    def find_or_create_client(self, name: str, phone: str = None, email: str = None, date_of_birth: str = None) -> int:
        """Find existing client or create new one"""
        if not phone and not email:
            raise ValueError("Client must have either phone number or email address")
        
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            name = name.lower().strip()
            
            # First priority: Try to find by name + DOB if DOB is provided
            if date_of_birth:
                cursor.execute("""
                    SELECT id FROM clients WHERE name = %s AND date_of_birth = %s
                """, (name, date_of_birth))
                row = cursor.fetchone()
                if row:
                    print(f"✅ Found existing client by name + DOB: {name} (ID: {row['id']})")
                    return row['id']
                else:
                    # DOB provided but no match found - create new client
                    print(f"✅ Creating NEW client (same name, different DOB): {name} (DOB: {date_of_birth})")
                    return self.add_client(name, phone, email, date_of_birth)
            
            # No DOB provided - fall back to matching by name + contact info
            if phone:
                cursor.execute("""
                    SELECT id FROM clients WHERE name = %s AND phone = %s
                """, (name, phone))
            elif email:
                cursor.execute("""
                    SELECT id FROM clients WHERE name = %s AND email = %s
                """, (name, email))
            
            row = cursor.fetchone()
            
            if row:
                return row['id']
            else:
                return self.add_client(name, phone, email, date_of_birth)
        finally:
            self.return_connection(conn)
    
    def get_available_phone_numbers(self) -> List[Dict]:
        """Get list of all available phone numbers"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cursor.execute("""
                SELECT phone_number, created_at 
                FROM twilio_phone_numbers 
                WHERE status = 'available'
                ORDER BY created_at
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            cursor.close()
            self.return_connection(conn)
    
    def assign_phone_number(self, company_id: int, phone_number: str = None):
        """Assign a phone number to a company (either specific number or first available)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            if not phone_number:
                # Get first available number if none specified
                cursor.execute("""
                    SELECT phone_number FROM twilio_phone_numbers 
                    WHERE status = 'available'
                    ORDER BY created_at
                    LIMIT 1
                """)
                result = cursor.fetchone()
                
                if not result:
                    self.return_connection(conn)
                    raise Exception("No available phone numbers in pool")
                
                phone_number = result[0]
            else:
                # Verify the specific number is available
                cursor.execute("""
                    SELECT phone_number FROM twilio_phone_numbers 
                    WHERE phone_number = %s AND status = 'available'
                """, (phone_number,))
                result = cursor.fetchone()
                
                if not result:
                    self.return_connection(conn)
                    raise Exception(f"Phone number {phone_number} is not available")
            
            # Update phone number status
            cursor.execute("""
                UPDATE twilio_phone_numbers 
                SET assigned_to_company_id = %s, 
                    assigned_at = CURRENT_TIMESTAMP,
                    status = 'assigned'
                WHERE phone_number = %s
            """, (company_id, phone_number))
            
            # Update company with phone number
            cursor.execute("""
                UPDATE companies 
                SET twilio_phone_number = %s
                WHERE id = %s
            """, (phone_number, company_id))
            
            conn.commit()
            self.return_connection(conn)
            
            print(f"✅ Assigned {phone_number} to company {company_id}")
            return phone_number
        except Exception as e:
            self.return_connection(conn)
            print(f"❌ Error assigning phone number: {e}")
            raise
    
    def get_clients_by_name(self, name: str) -> List[Dict]:
        """Get all clients with a given name (case-insensitive)"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            name = name.lower().strip()
            cursor.execute("SELECT * FROM clients WHERE name = %s", (name,))
            rows = cursor.fetchall()
            
            return [{
                'id': row['id'],
                'name': row['name'],
                'phone': row['phone'],
                'email': row['email'],
                'first_visit': row.get('first_visit'),
                'last_visit': row.get('last_visit'),
                'total_appointments': row.get('total_appointments', 0),
                'created_at': row.get('created_at'),
                'updated_at': row.get('updated_at'),
                'date_of_birth': row.get('date_of_birth'),
                'description': row.get('description')
            } for row in rows]
        finally:
            self.return_connection(conn)
    
    def get_client(self, client_id: int) -> Optional[Dict]:
        """Get client by ID"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row['id'],
                    'name': row['name'],
                    'phone': row['phone'],
                    'email': row['email'],
                    'first_visit': row.get('first_visit'),
                    'last_visit': row.get('last_visit'),
                    'total_appointments': row.get('total_appointments', 0),
                    'created_at': row.get('created_at'),
                    'updated_at': row.get('updated_at'),
                    'date_of_birth': row.get('date_of_birth'),
                    'description': row.get('description'),
                    'address': row.get('address'),
                    'eircode': row.get('eircode')
                }
            return None
        finally:
            self.return_connection(conn)
    
    def update_client(self, client_id: int, **kwargs):
        """Update client information"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            fields = []
            values = []
            for key, value in kwargs.items():
                if key in ['name', 'phone', 'email', 'date_of_birth', 'description', 'address', 'eircode']:
                    fields.append(f"{key} = %s")
                    values.append(value)
            
            if fields:
                values.append(datetime.now())
                values.append(client_id)
                cursor.execute(f"""
                    UPDATE clients 
                    SET {', '.join(fields)}, updated_at = %s
                    WHERE id = %s
                """, values)
                conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error updating client: {e}")
        finally:
            self.return_connection(conn)
    
    def update_client_description(self, client_id: int, description: str):
        """Update client description (AI-generated summary)"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                UPDATE clients 
                SET description = %s, updated_at = %s
                WHERE id = %s
            """, (description, datetime.now(), client_id))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error updating client description: {e}")
        finally:
            self.return_connection(conn)
    
    def add_booking(self, client_id: int, calendar_event_id: str, appointment_time: str,
                    service_type: str, phone_number: str = None, email: str = None,
                    urgency: str = None, address: str = None, eircode: str = None,
                    property_type: str = None, charge: float = None) -> Optional[int]:
        """Add a new booking"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # If phone/email not provided, get from client record
            if not phone_number and not email:
                cursor.execute("SELECT phone, email FROM clients WHERE id = %s", (client_id,))
                client = cursor.fetchone()
                if client:
                    phone_number = client.get('phone')
                    email = client.get('email')
            
            # Insert booking
            if charge is not None:
                cursor.execute("""
                    INSERT INTO bookings (client_id, calendar_event_id, appointment_time, 
                                        service_type, phone_number, email, urgency, address,
                                        eircode, property_type, charge)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (client_id, calendar_event_id, appointment_time, service_type, 
                      phone_number, email, urgency, address, eircode, property_type, charge))
            else:
                cursor.execute("""
                    INSERT INTO bookings (client_id, calendar_event_id, appointment_time, 
                                        service_type, phone_number, email, urgency, address,
                                        eircode, property_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (client_id, calendar_event_id, appointment_time, service_type, 
                      phone_number, email, urgency, address, eircode, property_type))
            
            result = cursor.fetchone()
            booking_id = result['id'] if result else None
            
            # Update client stats
            cursor.execute("""
                UPDATE clients 
                SET total_appointments = total_appointments + 1,
                    last_visit = %s,
                    updated_at = %s
                WHERE id = %s
            """, (appointment_time, datetime.now(), client_id))
            
            conn.commit()
            return booking_id
        except Exception as e:
            conn.rollback()
            print(f"Error adding booking: {e}")
            return None
        finally:
            self.return_connection(conn)
    
    def update_booking(self, booking_id: int, **kwargs) -> bool:
        """Update booking information"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            field_mapping = {
                'estimated_charge': 'charge',
                'job_address': 'address',
                'customer_name': None,
                'phone': 'phone_number',
            }
            
            fields = []
            values = []
            customer_name = None
            
            for key, value in kwargs.items():
                db_field = field_mapping.get(key, key)
                
                if db_field is None:
                    if key == 'customer_name':
                        customer_name = value
                    continue
                
                if db_field in ['calendar_event_id', 'appointment_time', 'service_type', 
                          'status', 'phone_number', 'email', 'charge', 'payment_status', 
                          'payment_method', 'urgency', 'address', 'eircode', 'property_type']:
                    fields.append(f"{db_field} = %s")
                    values.append(value)
            
            success = False
            
            if fields:
                values.append(booking_id)
                query = f"UPDATE bookings SET {', '.join(fields)} WHERE id = %s"
                cursor.execute(query, values)
                conn.commit()
                success = cursor.rowcount > 0
            
            if customer_name:
                cursor.execute("SELECT client_id FROM bookings WHERE id = %s", (booking_id,))
                row = cursor.fetchone()
                if row and row['client_id']:
                    cursor.execute("UPDATE clients SET name = %s WHERE id = %s", (customer_name, row['client_id']))
                    conn.commit()
                    success = True
            
            return success
        except Exception as e:
            conn.rollback()
            print(f"Error updating booking: {e}")
            return False
        finally:
            self.return_connection(conn)
    
    def delete_booking(self, booking_id: int) -> bool:
        """Delete a booking completely from the database"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Delete associated appointment notes first (foreign key constraint)
            cursor.execute("DELETE FROM appointment_notes WHERE booking_id = %s", (booking_id,))
            # Delete the booking
            cursor.execute("DELETE FROM bookings WHERE id = %s", (booking_id,))
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                print(f"✅ Deleted booking from database (ID: {booking_id})")
            return success
        except Exception as e:
            print(f"❌ Failed to delete booking: {e}")
            conn.rollback()
            return False
        finally:
            self.return_connection(conn)
    
    def get_client_bookings(self, client_id: int) -> List[Dict]:
        """Get all bookings for a client"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT * FROM bookings 
                WHERE client_id = %s 
                ORDER BY appointment_time DESC
            """, (client_id,))
            rows = cursor.fetchall()
            
            bookings = []
            for row in rows:
                booking = dict(row)
                booking['notes'] = self.get_appointment_notes(booking['id'])
                bookings.append(booking)
            
            return bookings
        finally:
            self.return_connection(conn)
    
    def get_client_notes(self, client_id: int) -> List[Dict]:
        """Get all notes for a client"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT * FROM notes 
                WHERE client_id = %s 
                ORDER BY created_at DESC
            """, (client_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            self.return_connection(conn)
    
    def add_note(self, client_id: int, note: str, created_by: str = "system") -> int:
        """Add a note to a client"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO notes (client_id, note, created_by)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (client_id, note, created_by))
            
            result = cursor.fetchone()
            note_id = result['id'] if result else None
            conn.commit()
            return note_id
        except Exception as e:
            conn.rollback()
            print(f"Error adding note: {e}")
            return None
        finally:
            self.return_connection(conn)
    
    def get_appointment_notes(self, booking_id: int) -> List[Dict]:
        """Get all notes for a specific appointment"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT * FROM appointment_notes 
                WHERE booking_id = %s 
                ORDER BY created_at DESC
            """, (booking_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            self.return_connection(conn)
    
    def add_appointment_note(self, booking_id: int, note: str, created_by: str = "system") -> int:
        """Add a note to a specific appointment"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO appointment_notes (booking_id, note, created_by)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (booking_id, note, created_by))
            
            result = cursor.fetchone()
            note_id = result['id'] if result else None
            conn.commit()
            return note_id
        except Exception as e:
            conn.rollback()
            print(f"Error adding appointment note: {e}")
            return None
        finally:
            self.return_connection(conn)
    
    def update_appointment_note(self, note_id: int, note: str) -> bool:
        """Update an appointment note"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                UPDATE appointment_notes 
                SET note = %s, updated_at = %s
                WHERE id = %s
            """, (note, datetime.now(), note_id))
            
            rows_affected = cursor.rowcount
            conn.commit()
            return rows_affected > 0
        except Exception as e:
            conn.rollback()
            print(f"Error updating appointment note: {e}")
            return False
        finally:
            self.return_connection(conn)
    
    def delete_appointment_note(self, note_id: int) -> bool:
        """Delete an appointment note"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("DELETE FROM appointment_notes WHERE id = %s", (note_id,))
            
            rows_affected = cursor.rowcount
            conn.commit()
            return rows_affected > 0
        except Exception as e:
            conn.rollback()
            print(f"Error deleting appointment note: {e}")
            return False
        finally:
            self.return_connection(conn)
    
    def delete_appointment_notes_by_booking(self, booking_id: int) -> bool:
        """Delete all notes for a specific booking"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("DELETE FROM appointment_notes WHERE booking_id = %s", (booking_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error deleting appointment notes: {e}")
            return False
        finally:
            self.return_connection(conn)
    
    def get_financial_stats(self) -> Dict:
        """Get financial statistics"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Total revenue
            cursor.execute("""
                SELECT SUM(charge) FROM bookings 
                WHERE status != 'cancelled'
            """)
            total_revenue = cursor.fetchone()['sum'] or 0
            
            # Payment breakdown
            cursor.execute("""
                SELECT payment_status, SUM(charge)
                FROM bookings
                WHERE status != 'cancelled'
                GROUP BY payment_status
            """)
            payment_breakdown = cursor.fetchall()
            
            # Monthly revenue
            cursor.execute("""
                SELECT TO_CHAR(appointment_time, 'YYYY-MM') as month,
                       SUM(charge) as revenue,
                       COUNT(*) as appointments
                FROM bookings 
                WHERE status != 'cancelled'
                GROUP BY month
                ORDER BY month DESC
                LIMIT 12
            """)
            monthly_revenue = cursor.fetchall()
            
            # Revenue by payment method
            cursor.execute("""
                SELECT payment_method, SUM(charge), COUNT(*)
                FROM bookings
                WHERE status != 'cancelled' AND payment_method IS NOT NULL
                GROUP BY payment_method
            """)
            payment_methods = cursor.fetchall()
            
            breakdown_dict = {'paid': 0, 'unpaid': 0}
            for row in payment_breakdown:
                status = row['payment_status'] or 'unpaid'
                amount = float(row['sum'] or 0)
                if status in breakdown_dict:
                    breakdown_dict[status] = amount
            
            return {
                'total_revenue': float(total_revenue),
                'payment_breakdown': breakdown_dict,
                'monthly_revenue': [
                    {'month': row['month'], 'revenue': float(row['revenue'] or 0), 'appointments': row['appointments']}
                    for row in monthly_revenue
                ],
                'payment_methods': {
                    row['payment_method']: float(row['sum'] or 0)
                    for row in payment_methods
                }
            }
        finally:
            self.return_connection(conn)
    
    def add_worker(self, name: str, phone: str = None, email: str = None, 
                   trade_specialty: str = None, image_url: str = None, weekly_hours_expected: float = 40.0) -> int:
        """Add a new worker"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO workers (name, phone, email, trade_specialty, image_url, weekly_hours_expected)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (name, phone, email, trade_specialty, image_url, weekly_hours_expected))
            
            result = cursor.fetchone()
            worker_id = result['id'] if result else None
            conn.commit()
            return worker_id
        except Exception as e:
            conn.rollback()
            print(f"Error adding worker: {e}")
            return None
        finally:
            self.return_connection(conn)
    
    def get_worker(self, worker_id: int) -> Optional[Dict]:
        """Get worker by ID"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM workers WHERE id = %s", (worker_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            self.return_connection(conn)
    
    def update_worker(self, worker_id: int, **kwargs):
        """Update worker information"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            field_mapping = {
                'specialty': 'trade_specialty'
            }
            
            fields = []
            values = []
            for key, value in kwargs.items():
                db_key = field_mapping.get(key, key)
                if db_key in ['name', 'phone', 'email', 'trade_specialty', 'status', 'image_url']:
                    fields.append(f"{db_key} = %s")
                    values.append(value)
            
            if fields:
                values.append(datetime.now())
                values.append(worker_id)
                query = f"UPDATE workers SET {', '.join(fields)}, updated_at = %s WHERE id = %s"
                cursor.execute(query, values)
                conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error updating worker: {e}")
        finally:
            self.return_connection(conn)
    
    def delete_worker(self, worker_id: int) -> bool:
        """Delete a worker"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("DELETE FROM workers WHERE id = %s", (worker_id,))
            
            rows_affected = cursor.rowcount
            conn.commit()
            return rows_affected > 0
        except Exception as e:
            conn.rollback()
            print(f"Error deleting worker: {e}")
            return False
        finally:
            self.return_connection(conn)
    
    def assign_worker_to_job(self, booking_id: int, worker_id: int) -> Dict:
        """Assign a worker to a job"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO worker_assignments (booking_id, worker_id)
                VALUES (%s, %s)
                RETURNING id
            """, (booking_id, worker_id))
            
            result = cursor.fetchone()
            assignment_id = result['id'] if result else None
            conn.commit()
            
            return {
                "success": True,
                "assignment_id": assignment_id,
                "message": "Worker assigned successfully"
            }
        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            self.return_connection(conn)
    
    def remove_worker_from_job(self, booking_id: int, worker_id: int) -> bool:
        """Remove a worker assignment from a job"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                DELETE FROM worker_assignments
                WHERE booking_id = %s AND worker_id = %s
            """, (booking_id, worker_id))
            
            rows_affected = cursor.rowcount
            conn.commit()
            return rows_affected > 0
        except Exception as e:
            conn.rollback()
            print(f"Error removing worker from job: {e}")
            return False
        finally:
            self.return_connection(conn)
    
    def get_job_workers(self, booking_id: int) -> List[Dict]:
        """Get all workers assigned to a specific job"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT w.id, w.name, w.phone, w.email, w.trade_specialty, wa.assigned_at
                FROM worker_assignments wa
                JOIN workers w ON wa.worker_id = w.id
                WHERE wa.booking_id = %s
            """, (booking_id,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            self.return_connection(conn)
    
    def get_worker_jobs(self, worker_id: int, include_completed: bool = False) -> List[Dict]:
        """Get all jobs assigned to a specific worker"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            query = """
                SELECT b.id, b.appointment_time, c.name as client_name, b.service_type, 
                       b.status, b.address, b.phone_number, wa.assigned_at
                FROM worker_assignments wa
                JOIN bookings b ON wa.booking_id = b.id
                LEFT JOIN clients c ON b.client_id = c.id
                WHERE wa.worker_id = %s
            """
            
            if not include_completed:
                query += " AND b.status != 'completed' AND b.status != 'cancelled'"
            
            query += " ORDER BY b.appointment_time ASC"
            
            cursor.execute(query, (worker_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            self.return_connection(conn)
    
    def get_worker_schedule(self, worker_id: int, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Get worker's schedule within a date range"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            query = """
                SELECT b.id, b.appointment_time, c.name as client_name, b.service_type, 
                       b.status, b.address
                FROM worker_assignments wa
                JOIN bookings b ON wa.booking_id = b.id
                LEFT JOIN clients c ON b.client_id = c.id
                WHERE wa.worker_id = %s
                AND b.status != 'cancelled'
            """
            
            params = [worker_id]
            
            if start_date:
                query += " AND b.appointment_time >= %s"
                params.append(start_date)
            
            if end_date:
                query += " AND b.appointment_time <= %s"
                params.append(end_date)
            
            query += " ORDER BY b.appointment_time ASC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            self.return_connection(conn)
    
    def get_worker_hours_this_week(self, worker_id: int) -> float:
        """Calculate hours worked by a worker this week"""
        from datetime import timedelta
        
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            today = datetime.now()
            start_of_week = today - timedelta(days=today.weekday())
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_week = start_of_week + timedelta(days=7)
            
            query = """
                SELECT COUNT(*) as job_count
                FROM worker_assignments wa
                JOIN bookings b ON wa.booking_id = b.id
                WHERE wa.worker_id = %s
                AND b.appointment_time >= %s
                AND b.appointment_time < %s
                AND b.status = 'completed'
            """
            
            cursor.execute(query, (worker_id, start_of_week.isoformat(), end_of_week.isoformat()))
            result = cursor.fetchone()
            
            job_count = result['job_count'] if result else 0
            hours_worked = job_count * 2.0
            
            return hours_worked
        finally:
            self.return_connection(conn)
    
    # Service management methods
    def add_service(self, service_id: str, category: str, name: str, 
                   description: str = None, duration_minutes: int = 60,
                   price: float = 0, emergency_price: float = None,
                   currency: str = 'EUR', active: bool = True,
                   image_url: str = None, sort_order: int = 0) -> bool:
        """Add a new service"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO services (id, category, name, description, duration_minutes,
                                    price, emergency_price, currency, active, image_url, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (service_id, category, name, description, duration_minutes,
                  price, emergency_price, currency, 1 if active else 0, image_url, sort_order))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"❌ Error adding service: {e}")
            return False
        finally:
            self.return_connection(conn)
    
    def get_all_services(self, active_only: bool = True) -> List[Dict]:
        """Get all services"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            if active_only:
                cursor.execute("SELECT * FROM services WHERE active = 1 ORDER BY sort_order, category, name")
            else:
                cursor.execute("SELECT * FROM services ORDER BY sort_order, category, name")
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            self.return_connection(conn)
    
    def get_service(self, service_id: str) -> Optional[Dict]:
        """Get service by ID"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cursor.execute("SELECT * FROM services WHERE id = %s", (service_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            self.return_connection(conn)
    
    def update_service(self, service_id: str, **kwargs) -> bool:
        """Update service information"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            allowed_fields = ['category', 'name', 'description', 'duration_minutes',
                             'price', 'emergency_price', 'currency', 'active',
                             'image_url', 'sort_order']
            
            fields = []
            values = []
            for key, value in kwargs.items():
                if key in allowed_fields:
                    if key == 'active' and isinstance(value, bool):
                        value = 1 if value else 0
                    fields.append(f"{key} = %s")
                    values.append(value)
            
            if fields:
                values.append(datetime.now())
                values.append(service_id)
                query = f"UPDATE services SET {', '.join(fields)}, updated_at = %s WHERE id = %s"
                cursor.execute(query, values)
                conn.commit()
                success = cursor.rowcount > 0
            else:
                success = False
            
            return success
        except Exception as e:
            conn.rollback()
            print(f"❌ Error updating service: {e}")
            return False
        finally:
            self.return_connection(conn)
    
    def delete_service(self, service_id: str) -> bool:
        """Delete a service"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM services WHERE id = %s", (service_id,))
            rows_affected = cursor.rowcount
            conn.commit()
            return rows_affected > 0
        finally:
            self.return_connection(conn)
    
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
