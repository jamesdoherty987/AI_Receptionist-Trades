"""
PostgreSQL Database Wrapper
Primary database layer for the application using PostgreSQL
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool as psycopg2_pool
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
import threading


class PostgreSQLDatabaseWrapper:
    """PostgreSQL database wrapper"""
    
    def __init__(self, database_url: str):
        """Initialize PostgreSQL connection pool"""
        self.database_url = database_url
        self._pool_lock = threading.Lock()
        
        # Add connection options for resilience
        # - connect_timeout: fail fast on initial connect
        # - keepalives: detect dead connections
        # - application_name: for monitoring
        connect_options = {
            'connect_timeout': 10,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5,
            'application_name': 'ai_receptionist'
        }
        
        # Build DSN with options
        if '?' in database_url:
            dsn = database_url
        else:
            option_str = '&'.join(f'{k}={v}' for k, v in connect_options.items())
            dsn = f"{database_url}?{option_str}"
        
        # Use ThreadedConnectionPool for thread-safety with gevent workers
        self.connection_pool = psycopg2_pool.ThreadedConnectionPool(
            minconn=2,  # Keep connections warm for each worker
            maxconn=10,  # Reasonable for Starter tier
            dsn=dsn
        )
        self.use_postgres = True  # Flag for compatibility
        print(f"[SUCCESS] PostgreSQL ThreadedConnectionPool initialized (1-10 connections)")
        self.init_database()
    
    def get_connection(self):
        """Get connection from pool with timeout to prevent indefinite blocking"""
        import time as time_module
        max_wait = 5.0  # Max seconds to wait for a connection
        start_time = time_module.time()
        
        while True:
            try:
                conn = self.connection_pool.getconn()
                # Test connection is still alive
                try:
                    conn.cursor().execute("SELECT 1")
                except (psycopg2.OperationalError, psycopg2.InterfaceError):
                    # Connection is dead, close and get fresh one
                    try:
                        self.connection_pool.putconn(conn, close=True)
                    except Exception:
                        pass
                    conn = self.connection_pool.getconn()
                return conn
            except psycopg2_pool.PoolError as e:
                elapsed = time_module.time() - start_time
                if elapsed > max_wait:
                    # Pool exhausted and timeout reached - create direct connection as fallback
                    print(f"[WARNING] Connection pool exhausted after {elapsed:.1f}s, creating direct connection: {e}")
                    return psycopg2.connect(self.database_url, connect_timeout=10)
                # Brief sleep before retry
                time_module.sleep(0.1)
    
    def return_connection(self, conn):
        """Return connection to pool"""
        try:
            self.connection_pool.putconn(conn)
        except Exception as e:
            # Connection might not belong to pool (fallback connection)
            try:
                conn.close()
            except Exception:
                pass
    
    def init_database(self):
        """Initialize database tables with PostgreSQL syntax"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Set a statement timeout so DDL never blocks forever
            # (e.g. if another connection holds a lock)
            cursor.execute("SET statement_timeout = '15s'")
            
            # Companies/Users table MUST be created first (other tables reference it)
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
                    subscription_tier TEXT DEFAULT 'none',
                    subscription_status TEXT DEFAULT 'inactive',
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    stripe_connect_account_id TEXT,
                    stripe_connect_status TEXT DEFAULT 'not_connected',
                    stripe_connect_onboarding_complete INTEGER DEFAULT 0,
                    trial_start TIMESTAMP,
                    trial_end TIMESTAMP,
                    has_used_trial INTEGER DEFAULT 0,
                    subscription_current_period_end TIMESTAMP,
                    subscription_cancel_at_period_end INTEGER DEFAULT 0,
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
                    -- Feature toggles
                    show_finances_tab BOOLEAN DEFAULT true,
                    show_insights_tab BOOLEAN DEFAULT true,
                    show_invoice_buttons BOOLEAN DEFAULT true,
                    send_confirmation_sms BOOLEAN DEFAULT true,
                    send_reminder_sms BOOLEAN DEFAULT false,
                    gcal_invite_workers BOOLEAN DEFAULT false,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Clients table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    id BIGSERIAL PRIMARY KEY,
                    company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE,
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
                    UNIQUE(company_id, name, phone, email)
                )
            """)
            
            # Bookings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id BIGSERIAL PRIMARY KEY,
                    company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE,
                    client_id BIGINT,
                    calendar_event_id TEXT UNIQUE,
                    appointment_time TIMESTAMP NOT NULL,
                    duration_minutes INTEGER DEFAULT 1440,
                    service_type TEXT,
                    status TEXT DEFAULT 'scheduled',
                    urgency TEXT DEFAULT 'scheduled',
                    address TEXT,
                    eircode TEXT,
                    property_type TEXT,
                    phone_number TEXT,
                    email TEXT,
                    charge REAL DEFAULT 0,
                    charge_max REAL DEFAULT NULL,
                    payment_status TEXT DEFAULT 'unpaid',
                    payment_method TEXT,
                    requires_callout BOOLEAN DEFAULT FALSE,
                    requires_quote BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    gcal_synced_at TIMESTAMP,
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
                    company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE,
                    phone_number TEXT,
                    caller_name TEXT,
                    address TEXT,
                    eircode TEXT,
                    duration_seconds INTEGER,
                    call_outcome TEXT DEFAULT 'no_action',
                    ai_summary TEXT,
                    summary TEXT,
                    call_sid TEXT,
                    is_lost_job BOOLEAN DEFAULT FALSE,
                    lost_job_reason TEXT,
                    recording_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Workers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workers (
                    id BIGSERIAL PRIMARY KEY,
                    company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE,
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
                    duration_minutes INTEGER DEFAULT 1440,
                    price REAL DEFAULT 0,
                    price_max REAL DEFAULT NULL,
                    emergency_price REAL,
                    currency TEXT DEFAULT 'EUR',
                    active INTEGER DEFAULT 1,
                    image_url TEXT,
                    sort_order INTEGER DEFAULT 0,
                    workers_required INTEGER DEFAULT 1,
                    worker_restrictions JSONB DEFAULT NULL,
                    requires_callout BOOLEAN DEFAULT FALSE,
                    requires_quote BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add worker_restrictions column if it doesn't exist (migration)
            cursor.execute("""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='services' AND column_name='worker_restrictions') THEN
                        ALTER TABLE services ADD COLUMN worker_restrictions JSONB DEFAULT NULL;
                    END IF;
                END $$;
            """)
            
            # Add requires_callout column if it doesn't exist (migration)
            cursor.execute("""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='services' AND column_name='requires_callout') THEN
                        ALTER TABLE services ADD COLUMN requires_callout BOOLEAN DEFAULT FALSE;
                    END IF;
                END $$;
            """)
            
            # Add package_only column if it doesn't exist (migration)
            cursor.execute("""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='services' AND column_name='package_only') THEN
                        ALTER TABLE services ADD COLUMN package_only BOOLEAN DEFAULT FALSE;
                    END IF;
                END $$;
            """)
            
            # Add requires_quote column if it doesn't exist (migration)
            cursor.execute("""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='services' AND column_name='requires_quote') THEN
                        ALTER TABLE services ADD COLUMN requires_quote BOOLEAN DEFAULT FALSE;
                    END IF;
                END $$;
            """)
            
            # Packages table (bundles of multiple services)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS packages (
                    id TEXT PRIMARY KEY,
                    company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    description TEXT,
                    services JSONB NOT NULL DEFAULT '[]',
                    price_override REAL DEFAULT NULL,
                    price_max_override REAL DEFAULT NULL,
                    duration_override INTEGER DEFAULT NULL,
                    use_when_uncertain BOOLEAN DEFAULT FALSE,
                    clarifying_question TEXT DEFAULT NULL,
                    active INTEGER DEFAULT 1,
                    image_url TEXT,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_packages_company ON packages(company_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_packages_active ON packages(company_id, active)")
            
            # Add duration_override column if missing (migration)
            try:
                cursor.execute("""
                    ALTER TABLE packages ADD COLUMN IF NOT EXISTS duration_override INTEGER DEFAULT NULL
                """)
            except Exception:
                pass
            
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
                    buffer_time_minutes INTEGER DEFAULT 15,
                    default_duration_minutes INTEGER DEFAULT 1440,
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
            
            # Run migrations for new columns
            self._run_migrations(cursor)
            
            conn.commit()
            print("[SUCCESS] PostgreSQL database initialized")
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Error initializing PostgreSQL database: {e}")
            raise
        finally:
            self.return_connection(conn)
    
    def _run_migrations(self, cursor):
        """Run database migrations to add new columns if they don't exist"""
        print("[INFO] Running database migrations...")
        
        # ============================================
        # CRITICAL: Add company_id to data tables for multi-tenancy
        # ============================================
        
        # Add company_id to clients table
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'clients' AND column_name = 'company_id'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE clients ADD COLUMN company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_clients_company_id ON clients(company_id)")
                print("[SUCCESS] Added company_id column to clients table")
            except Exception as e:
                print(f"[WARNING] Could not add company_id to clients: {e}")
        
        # Add company_id to bookings table
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'bookings' AND column_name = 'company_id'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_company_id ON bookings(company_id)")
                print("[SUCCESS] Added company_id column to bookings table")
            except Exception as e:
                print(f"[WARNING] Could not add company_id to bookings: {e}")
        
        # Add duration_minutes to bookings table for service duration tracking
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'bookings' AND column_name = 'duration_minutes'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN duration_minutes INTEGER DEFAULT 1440")
                print("[SUCCESS] Added duration_minutes column to bookings table")
            except Exception as e:
                print(f"[WARNING] Could not add duration_minutes to bookings: {e}")
        
        # Add company_id to workers table
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'workers' AND column_name = 'company_id'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE workers ADD COLUMN company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_workers_company_id ON workers(company_id)")
                print("[SUCCESS] Added company_id column to workers table")
            except Exception as e:
                print(f"[WARNING] Could not add company_id to workers: {e}")
        
        # Add company_id to notes table
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'notes' AND column_name = 'company_id'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE notes ADD COLUMN company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_company_id ON notes(company_id)")
                print("[SUCCESS] Added company_id column to notes table")
            except Exception as e:
                print(f"[WARNING] Could not add company_id to notes: {e}")
        
        # Add company_id to appointment_notes table
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'appointment_notes' AND column_name = 'company_id'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE appointment_notes ADD COLUMN company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointment_notes_company_id ON appointment_notes(company_id)")
                print("[SUCCESS] Added company_id column to appointment_notes table")
            except Exception as e:
                print(f"[WARNING] Could not add company_id to appointment_notes: {e}")
        
        # Add company_id to call_logs table
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'call_logs' AND column_name = 'company_id'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE call_logs ADD COLUMN company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_call_logs_company_id ON call_logs(company_id)")
                print("[SUCCESS] Added company_id column to call_logs table")
            except Exception as e:
                print(f"[WARNING] Could not add company_id to call_logs: {e}")
        
        # Add company_id to services table
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'services' AND column_name = 'company_id'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE services ADD COLUMN company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_services_company_id ON services(company_id)")
                print("[SUCCESS] Added company_id column to services table")
            except Exception as e:
                print(f"[WARNING] Could not add company_id to services: {e}")
        
        # Add company_id to business_settings table
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'business_settings' AND column_name = 'company_id'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE business_settings ADD COLUMN company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_business_settings_company_id ON business_settings(company_id)")
                print("[SUCCESS] Added company_id column to business_settings table")
            except Exception as e:
                print(f"[WARNING] Could not add company_id to business_settings: {e}")
        
        # Add company_id to developer_settings table
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'developer_settings' AND column_name = 'company_id'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE developer_settings ADD COLUMN company_id BIGINT REFERENCES companies(id) ON DELETE CASCADE")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_developer_settings_company_id ON developer_settings(company_id)")
                print("[SUCCESS] Added company_id column to developer_settings table")
            except Exception as e:
                print(f"[WARNING] Could not add company_id to developer_settings: {e}")
        
        # ============================================
        # End of multi-tenancy migrations
        # ============================================
        
        # Check existing columns in companies table
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'companies'
        """)
        existing_columns = [row['column_name'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
        
        # New subscription-related columns to add to companies table
        # This ensures all columns used in the code exist in the database
        migrations = {
            # Stripe subscription columns
            'stripe_subscription_id': 'TEXT',
            'stripe_connect_account_id': 'TEXT',
            'stripe_connect_status': "TEXT DEFAULT 'not_connected'",
            'stripe_connect_onboarding_complete': 'INTEGER DEFAULT 0',
            # Trial and subscription dates
            'trial_start': 'TIMESTAMP',
            'trial_end': 'TIMESTAMP',
            'has_used_trial': 'INTEGER DEFAULT 0',
            'subscription_current_period_end': 'TIMESTAMP',
            'subscription_cancel_at_period_end': 'INTEGER DEFAULT 0',
            # Bank/payment details for invoices
            'bank_iban': 'TEXT',
            'bank_bic': 'TEXT',
            'bank_name': 'TEXT',
            'bank_account_holder': 'TEXT',
            'revolut_phone': 'TEXT',
            # AI receptionist context
            'company_context': 'TEXT',
            # Coverage area for AI receptionist
            'coverage_area': 'TEXT',
            # Feature flags
            'remove_stripe_connect': 'BOOLEAN DEFAULT false',
            # Dashboard feature toggles
            'show_finances_tab': 'BOOLEAN DEFAULT true',
            'show_insights_tab': 'BOOLEAN DEFAULT true',
            'show_invoice_buttons': 'BOOLEAN DEFAULT true',
            # SMS toggles
            'send_confirmation_sms': 'BOOLEAN DEFAULT true',
            'send_reminder_sms': 'BOOLEAN DEFAULT false',
            # Google Calendar
            'gcal_invite_workers': 'BOOLEAN DEFAULT false',
            # Business settings (may have been missed in original schema)
            'business_hours': "TEXT DEFAULT '8 AM - 6 PM Mon-Sat (24/7 emergency available)'",
            'trade_type': 'TEXT',
            'address': 'TEXT',
            'logo_url': 'TEXT',
            'ai_enabled': 'BOOLEAN DEFAULT true',
            'ai_schedule': 'TEXT DEFAULT NULL',
            'ai_schedule_override': 'BOOLEAN DEFAULT false',
            # Setup wizard completion flag — once true, wizard never shows again
            'setup_wizard_complete': 'BOOLEAN DEFAULT false',
            # Managed setup flag — false means admin set up the account
            'easy_setup': 'BOOLEAN DEFAULT true',
            # Owner invite token for managed setup password flow
            'owner_invite_token': 'TEXT',
            'owner_invite_expires': 'TIMESTAMP',
        }
        
        # Also migrate business_settings table for bank details
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'business_settings'
        """)
        bs_existing = [row['column_name'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
        
        bs_migrations = {
            'bank_iban': 'TEXT',
            'bank_bic': 'TEXT',
            'bank_name': 'TEXT',
            'bank_account_holder': 'TEXT',
            'revolut_phone': 'TEXT',
            'city': 'TEXT',
            'country': 'TEXT',
            'website': 'TEXT',
            'timezone': 'TEXT',
            'currency': "TEXT DEFAULT 'EUR'",
            'business_type': 'TEXT',
            'default_charge': 'REAL',
            'business_hours': 'TEXT',
            'opening_hours_start': 'INTEGER DEFAULT 9',
            'opening_hours_end': 'INTEGER DEFAULT 17',
            'days_open': 'TEXT',
            'services': 'TEXT',
            'payment_methods': 'TEXT',
            'cancellation_policy': 'TEXT',
            'reminder_hours_before': 'INTEGER DEFAULT 24',
            'auto_confirm_bookings': 'INTEGER DEFAULT 1',
            'fallback_phone_number': 'TEXT',
            'appointment_duration': 'INTEGER DEFAULT 1440',
            'max_booking_days_ahead': 'INTEGER DEFAULT 30',
            'allow_weekend_booking': 'INTEGER DEFAULT 1',
            'buffer_time_minutes': 'INTEGER DEFAULT 15',
            'default_duration_minutes': 'INTEGER DEFAULT 1440',
        }
        
        for col_name, col_type in bs_migrations.items():
            if col_name not in bs_existing:
                try:
                    cursor.execute(f"ALTER TABLE business_settings ADD COLUMN {col_name} {col_type}")
                    print(f"[SUCCESS] Added {col_name} column to business_settings table")
                except Exception as e:
                    print(f"[WARNING] Could not add {col_name} to business_settings: {e}")
        
        for column_name, column_type in migrations.items():
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE companies ADD COLUMN {column_name} {column_type}")
                    print(f"[SUCCESS] Added {column_name} column to companies table")
                except Exception as e:
                    print(f"[WARNING] Could not add {column_name} column: {e}")
        
        # ============================================
        # Add workers_required column to services table
        # ============================================
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'services' AND column_name = 'workers_required'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE services ADD COLUMN workers_required INTEGER DEFAULT 1")
                print("[SUCCESS] Added workers_required column to services table")
            except Exception as e:
                print(f"[WARNING] Could not add workers_required to services: {e}")
        
        # ============================================
        # Ensure all companies have a General Service
        # ============================================
        try:
            # Get all companies
            cursor.execute("SELECT id FROM companies")
            companies = cursor.fetchall()
            
            for company_row in companies:
                company_id = company_row['id'] if isinstance(company_row, dict) else company_row[0]
                
                # Check if this company has a General service
                cursor.execute("""
                    SELECT id FROM services 
                    WHERE company_id = %s AND (LOWER(name) LIKE '%%general%%' OR LOWER(category) = 'general')
                """, (company_id,))
                
                if not cursor.fetchone():
                    # Create General service for this company
                    try:
                        cursor.execute("""
                            INSERT INTO services (id, category, name, description, duration_minutes, 
                                                price, currency, active, sort_order, company_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            f"general_{company_id}",
                            "General",
                            "General Service",
                            "Default service for general jobs and appointments that don't match a specific service category",
                            1440,  # 1 day (24 hours)
                            0,
                            'EUR',
                            1,
                            9999,
                            company_id
                        ))
                        print(f"[SUCCESS] Created General Service for company {company_id}")
                    except Exception as e:
                        print(f"[WARNING] Could not create General Service for company {company_id}: {e}")
        except Exception as e:
            print(f"[WARNING] Could not run General Service migration: {e}")
        
        # Add address_audio_url column to bookings table
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name='address_audio_url'")
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN address_audio_url TEXT")
                print("[SUCCESS] Added address_audio_url column to bookings table")
            except Exception as e:
                print(f"[WARNING] Could not add address_audio_url column: {e}")
        
        # Add reminder_sent column to bookings table (prevents duplicate SMS on redeploy)
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name='reminder_sent'")
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN reminder_sent BOOLEAN DEFAULT FALSE")
                print("[SUCCESS] Added reminder_sent column to bookings table")
            except Exception as e:
                print(f"[WARNING] Could not add reminder_sent column: {e}")
        
        # Add requires_callout column to bookings table
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name='requires_callout'")
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN requires_callout BOOLEAN DEFAULT FALSE")
                print("[SUCCESS] Added requires_callout column to bookings table")
            except Exception as e:
                print(f"[WARNING] Could not add requires_callout column: {e}")
        
        # Add requires_quote column to bookings table
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name='requires_quote'")
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN requires_quote BOOLEAN DEFAULT FALSE")
                print("[SUCCESS] Added requires_quote column to bookings table")
            except Exception as e:
                print(f"[WARNING] Could not add requires_quote column: {e}")
        
        # Add updated_at and gcal_synced_at columns to bookings table (incremental sync)
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name='updated_at'")
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                cursor.execute("UPDATE bookings SET updated_at = created_at WHERE updated_at IS NULL")
                print("[SUCCESS] Added updated_at column to bookings table")
            except Exception as e:
                print(f"[WARNING] Could not add updated_at column: {e}")
        
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name='gcal_synced_at'")
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN gcal_synced_at TIMESTAMP")
                print("[SUCCESS] Added gcal_synced_at column to bookings table")
            except Exception as e:
                print(f"[WARNING] Could not add gcal_synced_at column: {e}")
        
        # Add price_max column to services table (price ranges)
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='services' AND column_name='price_max'")
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE services ADD COLUMN price_max REAL DEFAULT NULL")
                print("[SUCCESS] Added price_max column to services table")
            except Exception as e:
                print(f"[WARNING] Could not add price_max column: {e}")
        
        # Add charge_max column to bookings table (price ranges)
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name='charge_max'")
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN charge_max REAL DEFAULT NULL")
                print("[SUCCESS] Added charge_max column to bookings table")
            except Exception as e:
                print(f"[WARNING] Could not add charge_max column: {e}")
        
        # ============================================
        # Call logs table expansion for call tracking feature
        # ============================================
        call_log_columns = {
            'caller_name': 'TEXT',
            'address': 'TEXT',
            'eircode': 'TEXT',
            'call_outcome': "TEXT DEFAULT 'no_action'",
            'ai_summary': 'TEXT',
            'call_sid': 'TEXT',
            'is_lost_job': 'BOOLEAN DEFAULT FALSE',
            'lost_job_reason': 'TEXT',
            'recording_url': 'TEXT',
        }
        for col_name, col_type in call_log_columns.items():
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='call_logs' AND column_name=%s",
                (col_name,)
            )
            if not cursor.fetchone():
                try:
                    cursor.execute(f"ALTER TABLE call_logs ADD COLUMN {col_name} {col_type}")
                    print(f"[SUCCESS] Added {col_name} column to call_logs table")
                except Exception as e:
                    print(f"[WARNING] Could not add {col_name} to call_logs: {e}")
        
        # ============================================
        # Accounting tables: expenses, quotes, invoice/tax columns
        # ============================================
        
        # Expenses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id BIGSERIAL PRIMARY KEY,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_company ON expenses(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")
        
        # Quotes / Estimates table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id BIGSERIAL PRIMARY KEY,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
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
                converted_booking_id BIGINT REFERENCES bookings(id) ON DELETE SET NULL,
                sent_at TIMESTAMPTZ,
                accepted_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_company ON quotes(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_status ON quotes(status)")
        
        # Invoice/tax columns on bookings
        booking_acct_cols = {
            'invoice_number': 'VARCHAR(50)',
            'invoice_sent_at': 'TIMESTAMPTZ',
            'invoice_due_date': 'DATE',
            'tax_rate': 'NUMERIC(5, 2) DEFAULT 0',
            'tax_amount': 'NUMERIC(10, 2) DEFAULT 0',
            'stripe_checkout_url': 'TEXT',
            'stripe_checkout_session_id': 'TEXT',
        }
        for col_name, col_type in booking_acct_cols.items():
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='bookings' AND column_name=%s",
                (col_name,)
            )
            if not cursor.fetchone():
                try:
                    cursor.execute(f"ALTER TABLE bookings ADD COLUMN {col_name} {col_type}")
                    print(f"[SUCCESS] Added {col_name} column to bookings table")
                except Exception as e:
                    print(f"[WARNING] Could not add {col_name} to bookings: {e}")
        
        # Tax/invoice settings on companies
        company_acct_cols = {
            'tax_rate': 'NUMERIC(5, 2) DEFAULT 0',
            'tax_id_number': 'VARCHAR(100)',
            'tax_id_label': "VARCHAR(50) DEFAULT 'VAT'",
            'invoice_prefix': "VARCHAR(20) DEFAULT 'INV'",
            'invoice_next_number': 'INTEGER DEFAULT 1',
            'invoice_payment_terms_days': 'INTEGER DEFAULT 14',
            'invoice_footer_note': 'TEXT',
            'default_expense_categories': 'TEXT',
        }
        for col_name, col_type in company_acct_cols.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE companies ADD COLUMN {col_name} {col_type}")
                    print(f"[SUCCESS] Added {col_name} column to companies table")
                except Exception as e:
                    print(f"[WARNING] Could not add {col_name} to companies: {e}")
        
        print("[INFO] Accounting migrations complete")
        
        # ============================================
        # Job sub-tasks table
        # ============================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_tasks (
                id BIGSERIAL PRIMARY KEY,
                booking_id BIGINT NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                status VARCHAR(30) DEFAULT 'pending',
                estimated_cost NUMERIC(10, 2) DEFAULT 0,
                assigned_worker_id BIGINT REFERENCES workers(id) ON DELETE SET NULL,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_tasks_booking ON job_tasks(booking_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_tasks_company ON job_tasks(company_id)")
        
        # Purchase orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id BIGSERIAL PRIMARY KEY,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                po_number VARCHAR(50),
                supplier VARCHAR(255),
                items JSONB DEFAULT '[]',
                total NUMERIC(10, 2) DEFAULT 0,
                status VARCHAR(30) DEFAULT 'draft',
                notes TEXT,
                booking_id BIGINT REFERENCES bookings(id) ON DELETE SET NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_orders_company ON purchase_orders(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_orders_status ON purchase_orders(status)")
        
        print("[INFO] Sub-tasks and purchase orders migrations complete")
        
        # Mileage logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mileage_logs (
                id BIGSERIAL PRIMARY KEY,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                date DATE NOT NULL DEFAULT CURRENT_DATE,
                from_location TEXT,
                to_location TEXT,
                distance_km NUMERIC(8, 2) DEFAULT 0,
                rate_per_km NUMERIC(6, 4) DEFAULT 0.338,
                cost NUMERIC(10, 2) DEFAULT 0,
                booking_id BIGINT REFERENCES bookings(id) ON DELETE SET NULL,
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mileage_company ON mileage_logs(company_id)")
        
        # Credit notes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS credit_notes (
                id BIGSERIAL PRIMARY KEY,
                company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                credit_note_number VARCHAR(50),
                client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
                booking_id BIGINT REFERENCES bookings(id) ON DELETE SET NULL,
                amount NUMERIC(10, 2) NOT NULL DEFAULT 0,
                reason TEXT,
                notes TEXT,
                stripe_refund_id TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_credit_notes_company ON credit_notes(company_id)")
        
        print("[INFO] Mileage and credit notes migrations complete")
    
    def _convert_query(self, query: str) -> str:
        """Convert ? placeholders to %s for parameterized queries"""
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
            
            # Create default "General" service for the new company
            if company_id:
                try:
                    self.add_service(
                        service_id=f"general_{company_id}",
                        category="General",
                        name="General Callout",
                        description="Default callout service — used when a job requires an initial site visit before the full work is scheduled",
                        duration_minutes=240,  # 4 hours
                        price=100,
                        emergency_price=None,
                        currency='EUR',
                        active=True,
                        image_url=None,
                        sort_order=9999,  # Put at the end
                        company_id=company_id
                    )
                    print(f"[SUCCESS] Created default 'General Callout' for company {company_id}")
                except Exception as e:
                    print(f"[WARNING] Could not create default service for company {company_id}: {e}")
            
            # Create default "General Quote" service for the new company
            if company_id:
                try:
                    self.add_service(
                        service_id=f"quote_{company_id}",
                        category="General",
                        name="General Quote",
                        description="Default quote service — used when a job requires a free quote visit before the full work is scheduled",
                        duration_minutes=240,  # 4 hours
                        price=0,
                        emergency_price=None,
                        currency='EUR',
                        active=True,
                        image_url=None,
                        sort_order=9998,  # Put near the end, before callout
                        company_id=company_id
                    )
                    print(f"[SUCCESS] Created default 'General Quote' for company {company_id}")
                except Exception as e:
                    print(f"[WARNING] Could not create default quote service for company {company_id}: {e}")
            
            return company_id
        except Exception as e:
            # Email already exists or other error
            conn.rollback()
            print(f"Error creating company: {e}")
            return None
        finally:
            cursor.close()
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
    
    def get_company_by_stripe_customer_id(self, stripe_customer_id: str) -> Optional[Dict]:
        """Get company by Stripe customer ID"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM companies WHERE stripe_customer_id = %s", (stripe_customer_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            cursor.close()
            self.return_connection(conn)
    
    def get_company_by_stripe_subscription_id(self, stripe_subscription_id: str) -> Optional[Dict]:
        """Get company by Stripe subscription ID"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM companies WHERE stripe_subscription_id = %s", (stripe_subscription_id,))
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
            allowed_fields = ['company_name', 'owner_name', 'phone', 'email', 'trade_type', 
                              'address', 'logo_url', 'business_hours', 'ai_enabled',
                              'password_hash',
                              'subscription_tier', 'subscription_status',
                              'stripe_customer_id', 'stripe_subscription_id',
                              'stripe_connect_account_id', 'stripe_connect_status',
                              'stripe_connect_onboarding_complete',
                              'is_verified', 
                              'verification_token', 'reset_token', 'reset_token_expires', 
                              'last_login', 'trial_start', 'trial_end',
                              'subscription_current_period_end', 'subscription_cancel_at_period_end',
                              'bank_iban', 'bank_bic', 'bank_name', 'bank_account_holder',
                              'revolut_phone', 'company_context', 'coverage_area', 'remove_stripe_connect',
                              'twilio_phone_number',
                              'google_credentials_json', 'google_calendar_id',
                              'show_finances_tab', 'show_invoice_buttons',
                              'show_insights_tab',
                              'send_confirmation_sms', 'send_reminder_sms',
                              'gcal_invite_workers',
                              'bypass_numbers',
                              'setup_wizard_complete',
                              'has_used_trial',
                              'ai_schedule',
                              'ai_schedule_override',
                              'easy_setup',
                              'owner_invite_token',
                              'owner_invite_expires']
            
            # Get actual columns that exist in the database
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'companies'
            """)
            existing_columns = {row['column_name'] for row in cursor.fetchall()}
            
            fields = []
            values = []
            skipped_fields = []
            for key, value in kwargs.items():
                if key in allowed_fields:
                    if key in existing_columns:
                        fields.append(f"{key} = %s")
                        values.append(value)
                    else:
                        skipped_fields.append(key)
                else:
                    pass  # Field not in allowed_fields
            
            if skipped_fields:
                print(f"[DB_UPDATE] Skipped fields not in database: {skipped_fields}")
            
            if fields:
                values.append(datetime.now())
                values.append(company_id)
                query = f"UPDATE companies SET {', '.join(fields)}, updated_at = %s WHERE id = %s"
                try:
                    cursor.execute(query, values)
                    conn.commit()
                    success = cursor.rowcount > 0
                except Exception as e:
                    conn.rollback()
                    print(f"[DB_UPDATE] ERROR: {e}")
                    raise
            else:
                success = False
            
            return success
        finally:
            cursor.close()
            self.return_connection(conn)
    
    def get_company_by_reset_token(self, token: str) -> Optional[Dict]:
        """Get company by password reset token"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM companies WHERE reset_token = %s", (token,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
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
    
    def delete_company(self, company_id: int) -> bool:
        """
        Delete a company and all associated data.
        This is a destructive operation that removes all company-related records
        across every table, respecting foreign key constraints.
        
        Returns True if successful, False otherwise.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            booking_subq = "SELECT id FROM bookings WHERE company_id = %s"
            client_subq = "SELECT id FROM clients WHERE company_id = %s"
            
            # All tables that may reference bookings/workers/clients/services
            # and need to be deleted before the core tables.
            # Uses savepoints so missing tables (un-migrated) don't abort the txn.
            optional_deletes = [
                # Tables referencing bookings(id)
                ("job_materials", f"booking_id IN ({booking_subq})"),
                ("job_tasks", f"booking_id IN ({booking_subq})"),
                ("job_workers", f"booking_id IN ({booking_subq})"),
                ("worker_assignments", f"booking_id IN ({booking_subq})"),
                ("appointment_notes", f"booking_id IN ({booking_subq})"),
                # Tables referencing clients(id)
                ("notes", f"client_id IN ({client_subq})"),
                # Tables with company_id that may not exist
                ("quotes", "company_id = %s"),
                ("credit_notes", "company_id = %s"),
                ("mileage_logs", "company_id = %s"),
                ("purchase_orders", "company_id = %s"),
                ("expenses", "company_id = %s"),
                ("materials", "company_id = %s"),
                ("messages", "company_id = %s"),
                ("worker_accounts", "company_id = %s"),
                ("worker_time_off", "company_id = %s"),
                ("notifications", "company_id = %s"),
                ("packages", "company_id = %s"),
            ]
            
            print(f"[DELETE_ACCOUNT] Starting cascading delete for company {company_id} (v2)")
            for table, where_clause in optional_deletes:
                cursor.execute("SAVEPOINT sp_del")
                try:
                    cursor.execute(f"DELETE FROM {table} WHERE {where_clause}", (company_id,))
                    cursor.execute("RELEASE SAVEPOINT sp_del")
                except Exception:
                    cursor.execute("ROLLBACK TO SAVEPOINT sp_del")
            
            # --- Core tables (these always exist) ---
            cursor.execute("DELETE FROM bookings WHERE company_id = %s", (company_id,))
            cursor.execute("DELETE FROM workers WHERE company_id = %s", (company_id,))
            cursor.execute("DELETE FROM clients WHERE company_id = %s", (company_id,))
            cursor.execute("DELETE FROM services WHERE company_id = %s", (company_id,))
            
            # Release the phone number back to the pool
            cursor.execute("UPDATE twilio_phone_numbers SET assigned_to_company_id = NULL, status = 'available' WHERE assigned_to_company_id = %s", (company_id,))
            
            # Finally, delete the company (cascades to call_logs, business_settings, developer_settings)
            cursor.execute("DELETE FROM companies WHERE id = %s", (company_id,))
            
            conn.commit()
            print(f"[SUCCESS] Deleted company {company_id} and all associated data")
            return True
        except Exception as e:
            conn.rollback()
            import traceback
            print(f"[ERROR] Failed to delete company {company_id}: {e}")
            traceback.print_exc()
            return False
        finally:
            cursor.close()
            self.return_connection(conn)
    
    # Booking Methods
    
    def get_booking_by_calendar_event_id(self, calendar_event_id: str, company_id: int = None) -> Optional[Dict]:
        """Get booking by calendar event ID, optionally filtered by company_id for security"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # CRITICAL: Filter by company_id when provided for multi-tenant data isolation
            if company_id:
                cursor.execute("SELECT * FROM bookings WHERE calendar_event_id = %s AND company_id = %s", (calendar_event_id, company_id))
            else:
                cursor.execute("SELECT * FROM bookings WHERE calendar_event_id = %s", (calendar_event_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            cursor.close()
            self.return_connection(conn)
    
    def get_booking(self, booking_id: int, company_id: int = None) -> Optional[Dict]:
        """Get booking by ID, optionally filtered by company_id for security
        
        SECURITY: When company_id is provided, ALWAYS filter by it.
        If company_id is 0 or None when explicitly passed, return None for safety.
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            if company_id:
                cursor.execute("SELECT * FROM bookings WHERE id = %s AND company_id = %s", (booking_id, company_id))
            else:
                # Backwards compatibility: allow unfiltered query only when company_id not passed
                cursor.execute("SELECT * FROM bookings WHERE id = %s", (booking_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                result['company_id'] = row.get('company_id')
                # Convert datetime to ISO string to prevent Flask's "GMT" serialization
                if hasattr(result.get('appointment_time'), 'isoformat'):
                    result['appointment_time'] = result['appointment_time'].isoformat()
                return result
            return None
        finally:
            cursor.close()
            self.return_connection(conn)
    
    def get_conflicting_bookings(self, start_time: str, end_time: str, exclude_statuses: list = None, company_id: int = None) -> List[Dict]:
        """Get bookings that conflict with a time range.
        
        Handles multi-day jobs correctly: a booking conflicts if its time span
        (appointment_time to appointment_time + duration) overlaps with the
        query range (start_time to end_time).
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            if exclude_statuses is None:
                exclude_statuses = ['cancelled', 'completed']
            
            # Fetch bookings that could possibly overlap with the query range:
            # 1. Bookings starting within the range (original logic)
            # 2. Bookings starting BEFORE the range but with enough duration to extend into it
            # We use a wide net: any booking starting before end_time that hasn't been completed/cancelled
            if company_id:
                cursor.execute("""
                    SELECT id, client_id, appointment_time, service_type, duration_minutes
                    FROM bookings
                    WHERE status != ALL(%s)
                    AND appointment_time < %s
                    AND company_id = %s
                """, (exclude_statuses, end_time, company_id))
            else:
                cursor.execute("""
                    SELECT id, client_id, appointment_time, service_type, duration_minutes
                    FROM bookings
                    WHERE status != ALL(%s)
                    AND appointment_time < %s
                """, (exclude_statuses, end_time))
            
            rows = cursor.fetchall()
            bookings = []
            
            from datetime import datetime as dt, timedelta
            
            # Get business hours for accurate multi-day job end time calculation
            try:
                from src.utils.config import config
                business_hours = config.get_business_hours(company_id=company_id)
                biz_start = business_hours.get('start', 9)
                biz_end = business_hours.get('end', 17)
            except Exception:
                biz_start = 9
                biz_end = 17
            
            # Parse the query range
            if isinstance(start_time, str):
                try:
                    range_start = dt.fromisoformat(start_time.replace('Z', '+00:00')).replace(tzinfo=None)
                except ValueError:
                    range_start = dt.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            else:
                range_start = start_time
            
            for row in rows:
                appt_time = row['appointment_time']
                if isinstance(appt_time, str):
                    try:
                        appt_time = dt.fromisoformat(appt_time.replace('Z', '+00:00')).replace(tzinfo=None)
                    except ValueError:
                        appt_time = dt.strptime(appt_time, '%Y-%m-%d %H:%M:%S')
                elif hasattr(appt_time, 'tzinfo') and appt_time.tzinfo is not None:
                    appt_time = appt_time.replace(tzinfo=None)
                
                duration = row.get('duration_minutes') or 60
                
                # Use business-day end time for multi-day jobs (with company-specific hours)
                # No buffer here — conflict detection should use actual job end times.
                # The 15-min buffer is a scheduling preference handled separately.
                booking_end = self._calculate_job_end_time(appt_time, duration, biz_start, biz_end, buffer_minutes=0, company_id=company_id)
                
                # Check true overlap: booking overlaps range if booking_end > range_start
                if booking_end > range_start:
                    bookings.append({
                        'id': row['id'],
                        'client_id': row['client_id'],
                        'appointment_time': row['appointment_time'],
                        'service_type': row['service_type']
                    })
            return bookings
        finally:
            cursor.close()
            self.return_connection(conn)
    
    def get_client_last_booking_with_address(self, client_id: int) -> Optional[Dict]:
        """Get most recent booking for client that has address/eircode/property_type.
        Also returns address_audio_url if one exists (may come from a different booking)."""
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
            if not row:
                return None
            
            result = {
                'address': row['address'],
                'eircode': row['eircode'],
                'property_type': row['property_type'],
                'address_audio_url': None
            }
            
            # Address audio may have been captured on a different call than the
            # most recent address booking.  Fetch the latest non-null audio URL
            # across ALL of this client's bookings so returning customers always
            # have their recording attached.
            cursor.execute("""
                SELECT address_audio_url
                FROM bookings
                WHERE client_id = %s
                AND address_audio_url IS NOT NULL
                ORDER BY appointment_time DESC
                LIMIT 1
            """, (client_id,))
            audio_row = cursor.fetchone()
            if audio_row:
                result['address_audio_url'] = audio_row['address_audio_url']
                print(f"[DB] Found previous address audio for client {client_id}: {audio_row['address_audio_url']}")
            
            return result
        finally:
            cursor.close()
            self.return_connection(conn)
    
    def get_all_clients(self, company_id: int = None) -> List[Dict]:
        """Get all clients for a specific company"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if company_id:
                cursor.execute("SELECT * FROM clients WHERE company_id = %s ORDER BY created_at DESC", (company_id,))
            else:
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
    
    def get_all_bookings(self, company_id: int = None) -> List[Dict]:
        """Get all bookings for a specific company, including assigned worker IDs"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if company_id:
                cursor.execute("""
                    SELECT 
                        b.id, b.client_id, b.calendar_event_id, b.appointment_time, 
                        b.service_type, b.status, b.phone_number, b.email, b.created_at,
                        b.charge, b.charge_max, b.payment_status, b.payment_method, b.urgency, 
                        b.address, b.eircode, b.property_type, b.duration_minutes,
                        b.address_audio_url, b.requires_callout, b.requires_quote,
                        b.updated_at, b.gcal_synced_at,
                        c.name as client_name, c.phone as client_phone, c.email as client_email,
                        ARRAY_AGG(wa.worker_id) FILTER (WHERE wa.worker_id IS NOT NULL) as assigned_worker_ids
                    FROM bookings b
                    LEFT JOIN clients c ON b.client_id = c.id
                    LEFT JOIN worker_assignments wa ON b.id = wa.booking_id
                    WHERE b.company_id = %s
                    GROUP BY b.id, b.client_id, b.calendar_event_id, b.appointment_time, 
                             b.service_type, b.status, b.phone_number, b.email, b.created_at,
                             b.charge, b.charge_max, b.payment_status, b.payment_method, b.urgency, 
                             b.address, b.eircode, b.property_type, b.duration_minutes,
                             b.address_audio_url, b.requires_callout, b.requires_quote,
                             b.updated_at, b.gcal_synced_at,
                             c.name, c.phone, c.email
                    ORDER BY b.appointment_time DESC
                """, (company_id,))
            else:
                cursor.execute("""
                    SELECT 
                        b.id, b.client_id, b.calendar_event_id, b.appointment_time, 
                        b.service_type, b.status, b.phone_number, b.email, b.created_at,
                        b.charge, b.charge_max, b.payment_status, b.payment_method, b.urgency, 
                        b.address, b.eircode, b.property_type, b.duration_minutes,
                        b.address_audio_url, b.requires_callout, b.requires_quote,
                        b.updated_at, b.gcal_synced_at,
                        c.name as client_name, c.phone as client_phone, c.email as client_email,
                        ARRAY_AGG(wa.worker_id) FILTER (WHERE wa.worker_id IS NOT NULL) as assigned_worker_ids
                    FROM bookings b
                    LEFT JOIN clients c ON b.client_id = c.id
                    LEFT JOIN worker_assignments wa ON b.id = wa.booking_id
                    GROUP BY b.id, b.client_id, b.calendar_event_id, b.appointment_time, 
                             b.service_type, b.status, b.phone_number, b.email, b.created_at,
                             b.charge, b.charge_max, b.payment_status, b.payment_method, b.urgency, 
                             b.address, b.eircode, b.property_type, b.duration_minutes,
                             b.address_audio_url, b.requires_callout, b.requires_quote,
                             b.updated_at, b.gcal_synced_at,
                             c.name, c.phone, c.email
                    ORDER BY b.appointment_time DESC
                """)
            rows = cursor.fetchall()
            
            return [{
                'id': row['id'],
                'client_id': row['client_id'],
                'calendar_event_id': row['calendar_event_id'],
                'appointment_time': row['appointment_time'].isoformat() if hasattr(row['appointment_time'], 'isoformat') else row['appointment_time'],
                'service_type': row['service_type'],
                'service': row['service_type'],  # Alias for compatibility
                'status': row['status'],
                'phone_number': row['phone_number'],
                'phone': row['phone_number'] or row['client_phone'],  # Use booking phone or client phone as fallback
                'email': row['email'] or row['client_email'],  # Use booking email or client email as fallback
                'created_at': row['created_at'].isoformat() if hasattr(row.get('created_at'), 'isoformat') else row['created_at'],
                'charge': row['charge'],
                'charge_max': row.get('charge_max'),
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
                'notes': '',  # Will be fetched separately if needed
                'duration_minutes': row['duration_minutes'],
                'assigned_worker_ids': row['assigned_worker_ids'] or [],  # List of assigned worker IDs
                'address_audio_url': row.get('address_audio_url'),
                'requires_callout': row.get('requires_callout', False),
                'requires_quote': row.get('requires_quote', False),
                'updated_at': row.get('updated_at'),
                'gcal_synced_at': row.get('gcal_synced_at'),
            } for row in rows]
        finally:
            self.return_connection(conn)
    
    def get_all_workers(self, company_id: int = None) -> List[Dict]:
        """Get all workers for a specific company"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if company_id:
                cursor.execute("SELECT * FROM workers WHERE company_id = %s ORDER BY name ASC", (company_id,))
            else:
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
                   date_of_birth: str = None, description: str = None, company_id: int = None) -> Optional[int]:
        """Add a new client"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO clients (name, phone, email, date_of_birth, description, first_visit, company_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (name, phone, email, date_of_birth, description, datetime.now(), company_id))
            
            result = cursor.fetchone()
            client_id = result['id'] if result else None
            conn.commit()
            return client_id
        except Exception as e:
            # Client already exists or other error
            conn.rollback()
            print(f"Error adding client: {e}")
            # Try to find existing client for this company
            try:
                if company_id:
                    cursor.execute("""
                        SELECT id FROM clients 
                        WHERE company_id = %s AND name = %s AND (phone = %s OR email = %s)
                    """, (company_id, name, phone, email))
                else:
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
    
    def find_or_create_client(self, name: str, phone: str = None, email: str = None, date_of_birth: str = None, company_id: int = None) -> int:
        """Find existing client or create new one.
        
        Uses normalized comparison for name and phone to merge duplicates:
        - Names: case-insensitive, ignores apostrophes, hyphens, extra spaces
          e.g., "John O'Brien" matches "john obrien"
        - Phones: normalized to digits only with country code
          e.g., "085-123-4567" matches "+353851234567"
        """
        from src.utils.security import normalize_name_for_comparison, normalize_phone_for_comparison
        
        if not phone and not email:
            raise ValueError("Client must have either phone number or email address")
        
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Normalize inputs for comparison
            normalized_name = normalize_name_for_comparison(name)
            normalized_phone = normalize_phone_for_comparison(phone) if phone else None
            normalized_email = email.lower().strip() if email else None
            
            # Fetch all clients for this company to do normalized comparison
            if company_id:
                cursor.execute("SELECT * FROM clients WHERE company_id = %s", (company_id,))
            else:
                cursor.execute("SELECT * FROM clients")
            
            all_clients = cursor.fetchall()
            
            # First priority: Try to find by normalized name + DOB if DOB is provided
            if date_of_birth:
                for client in all_clients:
                    client_normalized_name = normalize_name_for_comparison(client['name'])
                    if client_normalized_name == normalized_name and client.get('date_of_birth') == date_of_birth:
                        return client['id']
                
                # DOB provided but no match found - create new client
                return self.add_client(name, phone, email, date_of_birth, company_id=company_id)
            
            # No DOB provided - fall back to matching by normalized name + contact info
            for client in all_clients:
                client_normalized_name = normalize_name_for_comparison(client['name'])
                
                # Check if names match (normalized)
                if client_normalized_name != normalized_name:
                    continue
                
                # Names match - now check phone or email
                if normalized_phone:
                    client_normalized_phone = normalize_phone_for_comparison(client.get('phone') or '')
                    if client_normalized_phone == normalized_phone:
                        return client['id']
                elif normalized_email:
                    client_email = (client.get('email') or '').lower().strip()
                    if client_email == normalized_email:
                        return client['id']
            
            # No match found - create new client
            new_id = self.add_client(name, phone, email, date_of_birth, company_id=company_id)
            return new_id
        except Exception as e:
            print(f"[DB_CLIENT] ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            raise
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
                # Get first available number if none specified - lock the row immediately
                cursor.execute("""
                    SELECT phone_number FROM twilio_phone_numbers 
                    WHERE status = 'available'
                    ORDER BY created_at
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                """)
                result = cursor.fetchone()
                
                if not result:
                    conn.rollback()
                    raise Exception("No available phone numbers in pool")
                
                phone_number = result[0]
            else:
                # Verify the specific number is available and lock it
                cursor.execute("""
                    SELECT phone_number FROM twilio_phone_numbers 
                    WHERE phone_number = %s AND status = 'available'
                    FOR UPDATE SKIP LOCKED
                """, (phone_number,))
                result = cursor.fetchone()
                
                if not result:
                    conn.rollback()
                    raise Exception(f"Phone number {phone_number} is not available")
            
            # Update phone number status
            cursor.execute("""
                UPDATE twilio_phone_numbers 
                SET assigned_to_company_id = %s, 
                    assigned_at = CURRENT_TIMESTAMP,
                    status = 'assigned'
                WHERE phone_number = %s
            """, (company_id, phone_number))
            
            # Verify the update succeeded
            if cursor.rowcount == 0:
                conn.rollback()
                raise Exception(f"Failed to update phone number status")
            
            # Update company with phone number
            cursor.execute("""
                UPDATE companies 
                SET twilio_phone_number = %s
                WHERE id = %s
            """, (phone_number, company_id))
            
            # Verify company update succeeded
            if cursor.rowcount == 0:
                conn.rollback()
                raise Exception(f"Failed to update company with phone number")
            
            conn.commit()
            
            print(f"[SUCCESS] Assigned {phone_number} to company {company_id}")
            return phone_number
        except Exception as e:
            try:
                conn.rollback()
            except:
                pass
            print(f"[ERROR] Error assigning phone number: {e}")
            raise
        finally:
            cursor.close()
            self.return_connection(conn)
    
    def get_clients_by_name(self, name: str, company_id: int = None) -> List[Dict]:
        """Get all clients with a given name (case-insensitive), filtered by company_id for data isolation"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            name = name.lower().strip()
            # CRITICAL: Filter by company_id for proper multi-tenant data isolation
            # Exact match only - "Doherty" should NOT match "James Doherty"
            if company_id:
                cursor.execute("SELECT * FROM clients WHERE company_id = %s AND LOWER(name) = %s", (company_id, name))
            else:
                cursor.execute("SELECT * FROM clients WHERE LOWER(name) = %s", (name,))
            rows = cursor.fetchall()
            
            return [{
                'id': row['id'],
                'company_id': row.get('company_id'),
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
    
    def find_client_by_phone(self, phone: str, company_id: int = None) -> Optional[Dict]:
        """Find a client by phone number, optionally filtered by company_id"""
        if not phone:
            return None
        
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Normalize phone number - remove common formatting
            normalized_phone = phone.strip()
            
            if company_id:
                cursor.execute("""
                    SELECT * FROM clients 
                    WHERE company_id = %s AND phone = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, (company_id, normalized_phone))
            else:
                cursor.execute("""
                    SELECT * FROM clients 
                    WHERE phone = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, (normalized_phone,))
            
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row['id'],
                    'company_id': row.get('company_id'),
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
                }
            return None
        except Exception as e:
            print(f"[ERROR] Error finding client by phone: {e}")
            return None
        finally:
            self.return_connection(conn)
    
    def get_client(self, client_id: int, company_id: int = None) -> Optional[Dict]:
        """Get client by ID, optionally filtered by company_id for security"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if company_id:
                cursor.execute("SELECT * FROM clients WHERE id = %s AND company_id = %s", (client_id, company_id))
            else:
                cursor.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
            row = cursor.fetchone()
            
            if row:
                # Fetch notes from the notes table and aggregate them
                cursor.execute("""
                    SELECT note, created_at, created_by 
                    FROM notes 
                    WHERE client_id = %s 
                    ORDER BY created_at ASC
                """, (client_id,))
                notes_rows = cursor.fetchall()
                
                # Format notes as a single string with timestamps
                notes_text = ""
                if notes_rows:
                    note_entries = []
                    for note_row in notes_rows:
                        timestamp = note_row['created_at'].strftime('%Y-%m-%d %H:%M') if note_row['created_at'] else ''
                        note_entries.append(f"[{timestamp}] {note_row['note']}")
                    notes_text = "\n\n".join(note_entries)
                
                return {
                    'id': row['id'],
                    'company_id': row.get('company_id'),
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
                    'eircode': row.get('eircode'),
                    'notes': notes_text
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
    
    def update_client_description(self, client_id: int, description: str, company_id: int = None):
        """Update client description (AI-generated summary).
        
        SECURITY: When company_id is provided, always filter by it to prevent
        cross-tenant writes.
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if company_id:
                cursor.execute("""
                    UPDATE clients 
                    SET description = %s, updated_at = %s
                    WHERE id = %s AND company_id = %s
                """, (description, datetime.now(), client_id, company_id))
            else:
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
    
    def delete_client(self, client_id: int, company_id: int = None) -> dict:
        """
        Delete a client and all associated bookings (cascade delete).
        Returns dict with success status and count of deleted bookings.
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # First, count and delete associated bookings
            if company_id:
                cursor.execute("""
                    SELECT COUNT(*) as count FROM bookings 
                    WHERE client_id = %s AND company_id = %s
                """, (client_id, company_id))
            else:
                cursor.execute("""
                    SELECT COUNT(*) as count FROM bookings 
                    WHERE client_id = %s
                """, (client_id,))
            
            result = cursor.fetchone()
            bookings_count = result['count'] if result else 0
            
            # Delete worker assignments for those bookings first
            if company_id:
                cursor.execute("""
                    DELETE FROM worker_assignments 
                    WHERE booking_id IN (
                        SELECT id FROM bookings WHERE client_id = %s AND company_id = %s
                    )
                """, (client_id, company_id))
            else:
                cursor.execute("""
                    DELETE FROM worker_assignments 
                    WHERE booking_id IN (
                        SELECT id FROM bookings WHERE client_id = %s
                    )
                """, (client_id,))
            
            # Delete appointment notes for those bookings
            if company_id:
                cursor.execute("""
                    DELETE FROM appointment_notes 
                    WHERE booking_id IN (
                        SELECT id FROM bookings WHERE client_id = %s AND company_id = %s
                    )
                """, (client_id, company_id))
            else:
                cursor.execute("""
                    DELETE FROM appointment_notes 
                    WHERE booking_id IN (
                        SELECT id FROM bookings WHERE client_id = %s
                    )
                """, (client_id,))
            
            # Delete the bookings
            if company_id:
                cursor.execute("""
                    DELETE FROM bookings WHERE client_id = %s AND company_id = %s
                """, (client_id, company_id))
            else:
                cursor.execute("""
                    DELETE FROM bookings WHERE client_id = %s
                """, (client_id,))
            
            # Delete client notes if they exist (notes table uses client_id)
            # Use try/except in case notes table doesn't exist
            try:
                cursor.execute("DELETE FROM notes WHERE client_id = %s", (client_id,))
            except Exception:
                pass  # Notes table may not exist in all deployments
            
            # Finally delete the client
            if company_id:
                cursor.execute("""
                    DELETE FROM clients WHERE id = %s AND company_id = %s
                """, (client_id, company_id))
            else:
                cursor.execute("""
                    DELETE FROM clients WHERE id = %s
                """, (client_id,))
            
            client_deleted = cursor.rowcount > 0
            conn.commit()
            
            return {
                "success": client_deleted,
                "bookings_deleted": bookings_count
            }
        except Exception as e:
            conn.rollback()
            print(f"Error deleting client: {e}")
            return {
                "success": False,
                "error": str(e),
                "bookings_deleted": 0
            }
        finally:
            self.return_connection(conn)
    
    def add_booking(self, client_id: int, calendar_event_id: str, appointment_time: str,
                    service_type: str, phone_number: str = None, email: str = None,
                    urgency: str = None, address: str = None, eircode: str = None,
                    property_type: str = None, charge: float = None, charge_max: float = None,
                    company_id: int = None,
                    duration_minutes: int = 1440, requires_callout: bool = False, requires_quote: bool = False) -> Optional[int]:
        """Add a new booking (default 1 day duration for trades)"""
        print(f"[DB_BOOKING] ========== ADDING BOOKING ==========")
        print(f"[DB_BOOKING] client_id={client_id}, calendar_event_id={calendar_event_id}")
        print(f"[DB_BOOKING] appointment_time={appointment_time}, service_type={service_type}")
        print(f"[DB_BOOKING] phone={phone_number}, email={email}, company_id={company_id}")
        print(f"[DB_BOOKING] urgency={urgency}, address={address}, eircode={eircode}")
        print(f"[DB_BOOKING] property_type={property_type}, charge={charge}, duration={duration_minutes}")
        print(f"[DB_BOOKING] requires_callout={requires_callout}, requires_quote={requires_quote}")
        
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # If phone/email not provided, get from client record
            if not phone_number and not email:
                print(f"[DB_BOOKING] No phone/email provided, fetching from client {client_id}")
                cursor.execute("SELECT phone, email FROM clients WHERE id = %s", (client_id,))
                client = cursor.fetchone()
                if client:
                    phone_number = client.get('phone')
                    email = client.get('email')
                    print(f"[DB_BOOKING] Got from client: phone={phone_number}, email={email}")
            
            # Insert booking with company_id and duration_minutes
            if charge is not None:
                print(f"[DB_BOOKING] Inserting booking with charge...")
                cursor.execute("""
                    INSERT INTO bookings (client_id, calendar_event_id, appointment_time, 
                                        service_type, phone_number, email, urgency, address,
                                        eircode, property_type, charge, charge_max, company_id, duration_minutes, requires_callout, requires_quote)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (client_id, calendar_event_id, appointment_time, service_type, 
                      phone_number, email, urgency, address, eircode, property_type, charge, charge_max, company_id, duration_minutes, requires_callout, requires_quote))
            else:
                print(f"[DB_BOOKING] Inserting booking without charge...")
                cursor.execute("""
                    INSERT INTO bookings (client_id, calendar_event_id, appointment_time, 
                                        service_type, phone_number, email, urgency, address,
                                        eircode, property_type, company_id, duration_minutes, requires_callout, requires_quote)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (client_id, calendar_event_id, appointment_time, service_type, 
                      phone_number, email, urgency, address, eircode, property_type, company_id, duration_minutes, requires_callout, requires_quote))
            
            result = cursor.fetchone()
            booking_id = result['id'] if result else None
            print(f"[DB_BOOKING] Booking inserted with ID: {booking_id}")
            
            # Update client stats
            print(f"[DB_BOOKING] Updating client stats...")
            cursor.execute("""
                UPDATE clients 
                SET total_appointments = total_appointments + 1,
                    last_visit = %s,
                    updated_at = %s
                WHERE id = %s
            """, (appointment_time, datetime.now(), client_id))
            
            conn.commit()
            print(f"[DB_BOOKING] ✅ Booking committed successfully: ID={booking_id}")
            return booking_id
        except Exception as e:
            conn.rollback()
            # UniqueViolation on calendar_event_id is expected during sync
            # (event already imported) — log quietly without full traceback.
            if 'UniqueViolation' in type(e).__name__:
                print(f"[DB_BOOKING] ⏭️  Skipped duplicate calendar_event_id={calendar_event_id}")
            else:
                print(f"[DB_BOOKING] ❌ Error adding booking: {e}")
                print(f"[DB_BOOKING] Exception type: {type(e).__name__}")
                import traceback
                traceback.print_exc()
            return None
        finally:
            self.return_connection(conn)
    
    def update_booking(self, booking_id: int, company_id: int = None, **kwargs) -> bool:
        """Update booking information
        
        SECURITY: When company_id is provided, only update if booking belongs to that company.
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # SECURITY: Verify booking belongs to company if company_id provided
            if company_id:
                cursor.execute("SELECT id FROM bookings WHERE id = %s AND company_id = %s", (booking_id, company_id))
                if not cursor.fetchone():
                    print(f"[SECURITY] Booking {booking_id} does not belong to company {company_id}")
                    return False
            
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
                          'status', 'phone_number', 'email', 'charge', 'charge_max', 'payment_status', 
                          'payment_method', 'urgency', 'address', 'eircode', 'property_type',
                          'duration_minutes', 'address_audio_url', 'requires_callout', 'requires_quote',
                          'photo_urls', 'job_started_at', 'job_completed_at', 'actual_duration_minutes']:
                    fields.append(f"{db_field} = %s")
                    values.append(value)
            
            success = False
            
            if fields:
                # Always update the updated_at timestamp
                fields.append("updated_at = CURRENT_TIMESTAMP")
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
    
    def stamp_gcal_synced(self, booking_id: int, company_id: int = None) -> bool:
        """Mark a booking as synced to Google Calendar right now."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if company_id:
                cursor.execute(
                    "UPDATE bookings SET gcal_synced_at = CURRENT_TIMESTAMP WHERE id = %s AND company_id = %s",
                    (booking_id, company_id)
                )
            else:
                cursor.execute(
                    "UPDATE bookings SET gcal_synced_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (booking_id,)
                )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"[DB] Error stamping gcal_synced_at for booking {booking_id}: {e}")
            return False
        finally:
            self.return_connection(conn)

    def delete_booking(self, booking_id: int, company_id: int = None) -> bool:
        """Delete a booking completely from the database
        
        SECURITY: When company_id is provided, only delete if booking belongs to that company.
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # SECURITY: Verify booking belongs to company if company_id provided
            if company_id:
                cursor.execute("SELECT id FROM bookings WHERE id = %s AND company_id = %s", (booking_id, company_id))
                if not cursor.fetchone():
                    print(f"[SECURITY] Booking {booking_id} does not belong to company {company_id} - delete blocked")
                    return False
            
            # Delete associated appointment notes first (foreign key constraint)
            cursor.execute("DELETE FROM appointment_notes WHERE booking_id = %s", (booking_id,))
            # Delete the booking
            cursor.execute("DELETE FROM bookings WHERE id = %s", (booking_id,))
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                print(f"[SUCCESS] Deleted booking from database (ID: {booking_id})")
            return success
        except Exception as e:
            print(f"[ERROR] Failed to delete booking: {e}")
            conn.rollback()
            return False
        finally:
            self.return_connection(conn)
    
    def get_client_bookings(self, client_id: int, company_id: int = None) -> List[Dict]:
        """Get all bookings for a client, optionally filtered by company_id for security"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if company_id:
                cursor.execute("""
                    SELECT * FROM bookings 
                    WHERE client_id = %s AND company_id = %s
                    ORDER BY appointment_time DESC
                """, (client_id, company_id))
            else:
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
    
    def update_appointment_note(self, note_id: int, note: str, booking_id: int = None) -> bool:
        """Update an appointment note.
        
        SECURITY: When booking_id is provided, verify the note belongs to that
        booking to prevent cross-tenant note manipulation via IDOR.
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if booking_id:
                cursor.execute("""
                    UPDATE appointment_notes 
                    SET note = %s, updated_at = %s
                    WHERE id = %s AND booking_id = %s
                """, (note, datetime.now(), note_id, booking_id))
            else:
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
    
    def delete_appointment_note(self, note_id: int, booking_id: int = None) -> bool:
        """Delete an appointment note.
        
        SECURITY: When booking_id is provided, verify the note belongs to that
        booking to prevent cross-tenant note deletion via IDOR.
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if booking_id:
                cursor.execute("DELETE FROM appointment_notes WHERE id = %s AND booking_id = %s", (note_id, booking_id))
            else:
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
    
    def get_financial_stats(self, company_id: int = None) -> Dict:
        """Get financial statistics for a specific company"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Total revenue
            if company_id:
                cursor.execute("""
                    SELECT SUM(charge) FROM bookings 
                    WHERE company_id = %s AND status != 'cancelled'
                """, (company_id,))
            else:
                cursor.execute("""
                    SELECT SUM(charge) FROM bookings 
                    WHERE status != 'cancelled'
                """)
            total_revenue = cursor.fetchone()['sum'] or 0
            
            # Payment breakdown
            if company_id:
                cursor.execute("""
                    SELECT payment_status, SUM(charge)
                    FROM bookings
                    WHERE company_id = %s AND status != 'cancelled'
                    GROUP BY payment_status
                """, (company_id,))
            else:
                cursor.execute("""
                    SELECT payment_status, SUM(charge)
                    FROM bookings
                    WHERE status != 'cancelled'
                    GROUP BY payment_status
                """)
            payment_breakdown = cursor.fetchall()
            
            # Monthly revenue
            if company_id:
                cursor.execute("""
                    SELECT TO_CHAR(appointment_time, 'YYYY-MM') as month,
                           SUM(charge) as revenue,
                           COUNT(*) as appointments
                    FROM bookings 
                    WHERE company_id = %s AND status != 'cancelled'
                    GROUP BY month
                    ORDER BY month DESC
                    LIMIT 12
                """, (company_id,))
            else:
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
            if company_id:
                cursor.execute("""
                    SELECT payment_method, SUM(charge), COUNT(*)
                    FROM bookings
                    WHERE company_id = %s AND status != 'cancelled' AND payment_method IS NOT NULL
                    GROUP BY payment_method
                """, (company_id,))
            else:
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
                   trade_specialty: str = None, image_url: str = None, weekly_hours_expected: float = 40.0,
                   company_id: int = None) -> int:
        """Add a new worker"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO workers (name, phone, email, trade_specialty, image_url, weekly_hours_expected, company_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (name, phone, email, trade_specialty, image_url, weekly_hours_expected, company_id))
            
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
    
    def get_worker(self, worker_id: int, company_id: int = None) -> Optional[Dict]:
        """Get worker by ID, optionally filtered by company_id for security"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if company_id:
                cursor.execute("SELECT * FROM workers WHERE id = %s AND company_id = %s", (worker_id, company_id))
            else:
                cursor.execute("SELECT * FROM workers WHERE id = %s", (worker_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                result['company_id'] = row.get('company_id')
                return result
            return None
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
                if db_key in ['name', 'phone', 'email', 'trade_specialty', 'status', 'image_url', 'weekly_hours_expected']:
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
    
    def delete_worker(self, worker_id: int, company_id: int = None) -> dict:
        """
        Delete a worker and remove from all job assignments (cascade delete).
        Returns dict with success status and count of removed assignments.
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # First, count worker assignments
            cursor.execute("""
                SELECT COUNT(*) as count FROM worker_assignments 
                WHERE worker_id = %s
            """, (worker_id,))
            result = cursor.fetchone()
            assignments_count = result['count'] if result else 0
            
            # Delete worker assignments
            cursor.execute("DELETE FROM worker_assignments WHERE worker_id = %s", (worker_id,))
            
            # Update bookings to remove this worker from assigned_worker_ids array
            cursor.execute("""
                UPDATE bookings 
                SET assigned_worker_ids = array_remove(assigned_worker_ids, %s)
                WHERE %s = ANY(assigned_worker_ids)
            """, (worker_id, worker_id))
            
            # Delete the worker
            if company_id:
                cursor.execute("DELETE FROM workers WHERE id = %s AND company_id = %s", (worker_id, company_id))
            else:
                cursor.execute("DELETE FROM workers WHERE id = %s", (worker_id,))
            
            worker_deleted = cursor.rowcount > 0
            conn.commit()
            
            return {
                "success": worker_deleted,
                "assignments_removed": assignments_count
            }
        except Exception as e:
            conn.rollback()
            print(f"Error deleting worker: {e}")
            return {
                "success": False,
                "error": str(e),
                "assignments_removed": 0
            }
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
    
    def get_job_workers(self, booking_id: int, company_id: int = None) -> List[Dict]:
        """Get all workers assigned to a specific job, optionally filtered by company_id for security"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if company_id:
                cursor.execute("""
                    SELECT w.id, w.name, w.phone, w.email, w.trade_specialty, wa.assigned_at
                    FROM worker_assignments wa
                    JOIN workers w ON wa.worker_id = w.id
                    JOIN bookings b ON wa.booking_id = b.id
                    WHERE wa.booking_id = %s AND b.company_id = %s
                """, (booking_id, company_id))
            else:
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
    
    def get_worker_jobs(self, worker_id: int, include_completed: bool = False, company_id: int = None) -> List[Dict]:
        """Get all jobs assigned to a specific worker, optionally filtered by company_id for security"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            query = """
                SELECT b.id, b.appointment_time, c.name as client_name, b.service_type, 
                       b.status, b.address, b.phone_number, wa.assigned_at,
                       b.job_started_at, b.job_completed_at, b.actual_duration_minutes
                FROM worker_assignments wa
                JOIN bookings b ON wa.booking_id = b.id
                LEFT JOIN clients c ON b.client_id = c.id
                WHERE wa.worker_id = %s
            """
            
            params = [worker_id]
            
            if company_id:
                query += " AND b.company_id = %s"
                params.append(company_id)
            
            if not include_completed:
                query += " AND b.status != 'completed' AND b.status != 'cancelled'"
            
            query += " ORDER BY b.appointment_time ASC"
            
            cursor.execute(query, tuple(params))
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
    
    def _calculate_job_end_time(self, start_time, duration_minutes: int, 
                                 biz_start_hour: int = 9, biz_end_hour: int = 17,
                                 buffer_minutes: int = 0, company_id: int = None):
        """
        Calculate the true end time of a job, handling multi-day spans correctly.
        
        For jobs < 8 hours (480 mins): simple start + duration + buffer.
        For full-day jobs (480-1440 mins): blocks until closing time on the same day.
        For multi-day jobs (> 1440 mins): spans across multiple business days.
          Duration is interpreted as calendar-day equivalents (1440 mins = 1 day),
          so a "2 day" job (2880 mins) blocks 2 business days, not 6.
        
        Returns a datetime representing when the job (plus buffer) actually ends.
        """
        from datetime import timedelta
        
        if duration_minutes < 480:
            # Short job: exact duration + buffer
            return start_time + timedelta(minutes=duration_minutes + buffer_minutes)
        
        if duration_minutes <= 1440:
            # Single full-day job: blocks until closing time on the same day
            end = start_time.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)
            return end + timedelta(minutes=buffer_minutes)
        
        # Multi-day job (> 1 day): calculate how many business days it spans.
        # "1 week" (10080 mins) = 5 business days, not 7.
        from src.utils.duration_utils import duration_to_business_days
        biz_days_needed = duration_to_business_days(duration_minutes, company_id=company_id)
        
        # Get business days using company-specific settings
        try:
            from src.utils.config import config
            business_days = config.get_business_days_indices(company_id=company_id)
        except Exception:
            business_days = [0, 1, 2, 3, 4]
        
        # Walk forward day by day, counting business days
        current_day = start_time.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)
        days_counted = 0
        max_iterations = 365  # safety cap
        iterations = 0
        
        while days_counted < biz_days_needed and iterations < max_iterations:
            iterations += 1
            if current_day.weekday() in business_days:
                days_counted += 1
                if days_counted >= biz_days_needed:
                    # Job finishes on this day at closing time
                    end = current_day.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)
                    return end + timedelta(minutes=buffer_minutes)
            current_day += timedelta(days=1)
            current_day = current_day.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)
        
        # Fallback: if we exhausted iterations, return last day's closing
        end = current_day.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)
        return end + timedelta(minutes=buffer_minutes)
    
    def get_worker_bookings_in_range(self, worker_id: int, range_start, range_end,
                                      exclude_booking_id: int = None, company_id: int = None) -> list:
        """
        Fetch all active bookings for a worker that could overlap with a date range.
        Returns raw booking rows with appointment_time and duration_minutes.
        Used for batch availability checking to avoid N individual DB queries.
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Parse times if strings
            if isinstance(range_start, str):
                range_start = datetime.fromisoformat(range_start.replace('Z', '+00:00'))
            if isinstance(range_end, str):
                range_end = datetime.fromisoformat(range_end.replace('Z', '+00:00'))
            if hasattr(range_start, 'tzinfo') and range_start.tzinfo:
                range_start = range_start.replace(tzinfo=None)
            if hasattr(range_end, 'tzinfo') and range_end.tzinfo:
                range_end = range_end.replace(tzinfo=None)

            # Fetch bookings that START before range_end (they could overlap)
            # We fetch broadly and filter in Python for multi-day job accuracy
            query = """
                SELECT b.id, b.appointment_time, b.duration_minutes
                FROM worker_assignments wa
                JOIN bookings b ON wa.booking_id = b.id
                WHERE wa.worker_id = %s
                AND b.status NOT IN ('completed', 'cancelled')
                AND b.appointment_time < %s
            """
            params = [worker_id, range_end]

            if company_id:
                query += " AND b.company_id = %s"
                params.append(company_id)
            if exclude_booking_id:
                query += " AND b.id != %s"
                params.append(exclude_booking_id)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

            # Normalize datetimes
            result = []
            for row in rows:
                appt = row['appointment_time']
                if isinstance(appt, str):
                    try:
                        appt = datetime.fromisoformat(appt.replace('Z', '+00:00'))
                    except ValueError:
                        appt = datetime.strptime(appt, '%Y-%m-%d %H:%M:%S')
                if hasattr(appt, 'tzinfo') and appt.tzinfo:
                    appt = appt.replace(tzinfo=None)
                result.append({
                    'id': row['id'],
                    'appointment_time': appt,
                    'duration_minutes': row.get('duration_minutes') or 60
                })
            return result
        except Exception as e:
            print(f"Error fetching worker bookings in range: {e}")
            return []
        finally:
            self.return_connection(conn)

    def check_worker_availability(self, worker_id: int, appointment_time, duration_minutes: int = 1440, 
                                   exclude_booking_id: int = None, company_id: int = None) -> Dict:
        """
        Check if a worker is available at a specific time.
        
        Handles all durations from 1 hour to 1 month. Multi-day jobs block
        business hours on each spanned day. Single-day jobs use exact times.
        Also checks approved time-off requests.
        
        Args:
            worker_id: The worker to check
            appointment_time: The appointment start time (datetime or string)
            duration_minutes: Duration of the appointment in minutes (default 1 day for trades)
            exclude_booking_id: Booking ID to exclude from conflict check (for reassignments)
            company_id: Company ID for data isolation
            
        Returns:
            Dict with 'available' (bool), 'conflicts' (list of conflicting jobs), 'message' (str)
        """
        from datetime import timedelta
        from src.utils.config import config
        
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Parse appointment time if string
            if isinstance(appointment_time, str):
                try:
                    appointment_time = datetime.fromisoformat(appointment_time.replace('Z', '+00:00'))
                except ValueError:
                    appointment_time = datetime.strptime(appointment_time, '%Y-%m-%d %H:%M:%S')
            
            # Make timezone-naive for comparison
            if hasattr(appointment_time, 'tzinfo') and appointment_time.tzinfo is not None:
                appointment_time = appointment_time.replace(tzinfo=None)
            
            # --- Check approved time-off first ---
            try:
                appt_date = appointment_time.date()
                cursor.execute("""
                    SELECT id, start_date, end_date, type FROM worker_time_off
                    WHERE worker_id = %s AND status = 'approved'
                    AND start_date <= %s AND end_date >= %s
                """, (worker_id, appt_date, appt_date))
                time_off = cursor.fetchone()
                if time_off and isinstance(time_off, dict) and time_off.get('id'):
                    return {
                        'available': False,
                        'conflicts': [],
                        'message': f"Worker is on approved {time_off['type']} leave ({time_off['start_date']} to {time_off['end_date']})",
                        'on_leave': True
                    }
            except Exception:
                # Table may not exist yet — skip time-off check
                conn.rollback()
            
            # Get business hours for full-day job handling
            try:
                business_hours = config.get_business_hours(company_id=company_id)
                start_hour = business_hours.get('start', 9)
                end_hour = business_hours.get('end', 17)
            except Exception:
                start_hour = 9
                end_hour = 17
            
            # Calculate appointment end time (no artificial buffer — use actual duration
            # so conflict detection matches what the calendar availability shows)
            
            # Calculate the TRUE end time of the new appointment
            appointment_end = self._calculate_job_end_time(
                appointment_time, duration_minutes, start_hour, end_hour, buffer_minutes=0, company_id=company_id
            )
            
            # Get all active jobs assigned to this worker
            query = """
                SELECT b.id, b.appointment_time, b.duration_minutes, b.service_type,
                       c.name as client_name, b.address
                FROM worker_assignments wa
                JOIN bookings b ON wa.booking_id = b.id
                LEFT JOIN clients c ON b.client_id = c.id
                WHERE wa.worker_id = %s
                AND b.status NOT IN ('completed', 'cancelled')
            """
            params = [worker_id]
            
            if company_id:
                query += " AND b.company_id = %s"
                params.append(company_id)
            
            if exclude_booking_id:
                query += " AND b.id != %s"
                params.append(exclude_booking_id)
            
            cursor.execute(query, tuple(params))
            existing_jobs = cursor.fetchall()
            
            conflicts = []
            for job in existing_jobs:
                job_time = job['appointment_time']
                if isinstance(job_time, str):
                    try:
                        job_time = datetime.fromisoformat(job_time.replace('Z', '+00:00'))
                    except ValueError:
                        job_time = datetime.strptime(job_time, '%Y-%m-%d %H:%M:%S')
                
                if hasattr(job_time, 'tzinfo') and job_time.tzinfo is not None:
                    job_time = job_time.replace(tzinfo=None)
                
                job_duration = job.get('duration_minutes') or 60
                
                # Calculate the TRUE end time of the existing job
                job_end = self._calculate_job_end_time(
                    job_time, job_duration, start_hour, end_hour, buffer_minutes=0, company_id=company_id
                )
                
                # Check for overlap
                if appointment_time < job_end and appointment_end > job_time:
                    conflicts.append({
                        'booking_id': job['id'],
                        'time': job_time.strftime('%Y-%m-%d %H:%M'),
                        'service': job.get('service_type', 'Unknown'),
                        'client': job.get('client_name', 'Unknown'),
                        'address': job.get('address', '')
                    })
            
            if conflicts:
                conflict_times = ', '.join([c['time'] for c in conflicts])
                return {
                    'available': False,
                    'conflicts': conflicts,
                    'message': f"Worker has conflicting job(s) at: {conflict_times}"
                }
            
            return {
                'available': True,
                'conflicts': [],
                'message': "Worker is available"
            }
            
        except Exception as e:
            print(f"Error checking worker availability: {e}")
            # Return unavailable on error to prevent accidental double-booking
            return {
                'available': False,
                'conflicts': [],
                'message': f"Could not verify availability: {str(e)}. Please try again."
            }
        finally:
            self.return_connection(conn)
    
    def find_available_workers_for_slot(self, appointment_time, duration_minutes: int = 1440,
                                        company_id: int = None, trade_specialty: str = None) -> Optional[List[Dict]]:
        """
        Find all workers who are available at a specific time slot.
        """
        if not company_id:
            return []
        
        try:
            # Get all workers for this company
            all_workers = self.get_all_workers(company_id=company_id)
            
            if not all_workers:
                print(f"[WORKER_AVAIL] No workers found for company {company_id}")
                return []
            
            available_workers = []
            
            for worker in all_workers:
                worker_name = worker.get('name', 'Unknown')
                worker_status = worker.get('status', 'unknown')
                
                # Skip inactive workers
                if worker_status == 'inactive':
                    continue
                
                # Filter by trade specialty if specified
                if trade_specialty:
                    worker_specialty = (worker.get('trade_specialty') or '').lower()
                    if trade_specialty.lower() not in worker_specialty and worker_specialty not in trade_specialty.lower():
                        continue
                
                # Check availability
                availability = self.check_worker_availability(
                    worker_id=worker['id'],
                    appointment_time=appointment_time,
                    duration_minutes=duration_minutes,
                    company_id=company_id
                )
                
                if availability['available']:
                    available_workers.append({
                        'id': worker['id'],
                        'name': worker['name'],
                        'phone': worker.get('phone'),
                        'email': worker.get('email'),
                        'trade_specialty': worker.get('trade_specialty')
                    })
                else:
                    # Log why this worker is unavailable (helps debug availability mismatches)
                    print(f"[WORKER_AVAIL] {worker_name} (id={worker['id']}) NOT available at {appointment_time} for {duration_minutes}min: {availability.get('message', 'unknown')}")
            
            # Sort by least busy (fewest upcoming bookings first) to balance workload
            if len(available_workers) > 1:
                conn = None
                try:
                    worker_ids = [w['id'] for w in available_workers]
                    conn = self.get_connection()
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                    cursor.execute("""
                        SELECT wa.worker_id, COUNT(*) as upcoming_count
                        FROM worker_assignments wa
                        JOIN bookings b ON b.id = wa.booking_id
                        WHERE wa.worker_id = ANY(%s)
                          AND b.company_id = %s
                          AND b.appointment_time >= NOW()
                          AND b.status NOT IN ('cancelled', 'deleted')
                        GROUP BY wa.worker_id
                    """, (worker_ids, company_id))
                    counts = {row['worker_id']: row['upcoming_count'] for row in cursor.fetchall()}
                    # Workers with no upcoming bookings get count 0
                    available_workers.sort(key=lambda w: counts.get(w['id'], 0))
                    print(f"[WORKER_AVAIL] Sorted by least busy: {[(w['name'], counts.get(w['id'], 0)) for w in available_workers]}")
                except Exception as sort_err:
                    print(f"[WORKER_AVAIL] ⚠️ Could not sort by workload (falling back to default order): {sort_err}")
                finally:
                    if conn:
                        self.return_connection(conn)
            
            return available_workers
        except Exception as e:
            print(f"[WORKER_AVAIL] ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            # Return None on error to distinguish from "no workers available" (empty list)
            return None
    
    def has_workers(self, company_id: int) -> bool:
        """
        Check if a company has any workers configured.
        
        Args:
            company_id: Company ID to check
            
        Returns:
            True if company has at least one worker, False otherwise
        """
        if not company_id:
            return False
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM workers WHERE company_id = %s AND status != 'inactive'",
                (company_id,)
            )
            result = cursor.fetchone()
            return result[0] > 0 if result else False
        except Exception as e:
            print(f"Error checking if company has workers: {e}")
            return False
        finally:
            self.return_connection(conn)
    
    # Service management methods
    def add_service(self, service_id: str, category: str, name: str, 
                   description: str = None, duration_minutes: int = 1440,
                   price: float = 0, price_max: float = None, emergency_price: float = None,
                   currency: str = 'EUR', active: bool = True,
                   image_url: str = None, sort_order: int = 0,
                   workers_required: int = 1, worker_restrictions: dict = None,
                   requires_callout: bool = False, package_only: bool = False,
                   requires_quote: bool = False,
                   company_id: int = None, default_materials: list = None) -> bool:
        """Add a new service for a specific company (default 1 day duration for trades)"""
        import json
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Ensure workers_required is at least 1
        workers_required = max(1, workers_required or 1)
        
        # Convert worker_restrictions to JSON string if provided
        restrictions_json = json.dumps(worker_restrictions) if worker_restrictions else None
        materials_json = json.dumps(default_materials) if default_materials else '[]'
        
        try:
            cursor.execute("""
                INSERT INTO services (id, category, name, description, duration_minutes,
                                    price, price_max, emergency_price, currency, active, image_url, sort_order, workers_required, worker_restrictions, requires_callout, package_only, requires_quote, company_id, default_materials)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (service_id, category, name, description, duration_minutes,
                  price, price_max, emergency_price, currency, 1 if active else 0, image_url, sort_order, workers_required, restrictions_json, requires_callout, package_only, requires_quote, company_id, materials_json))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Error adding service: {e}")
            return False
        finally:
            self.return_connection(conn)
    
    def get_all_services(self, active_only: bool = True, company_id: int = None) -> List[Dict]:
        """Get all services for a specific company"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            if company_id:
                if active_only:
                    cursor.execute("SELECT * FROM services WHERE company_id = %s AND active = 1 ORDER BY sort_order, category, name", (company_id,))
                else:
                    cursor.execute("SELECT * FROM services WHERE company_id = %s ORDER BY sort_order, category, name", (company_id,))
            else:
                if active_only:
                    cursor.execute("SELECT * FROM services WHERE active = 1 ORDER BY sort_order, category, name")
                else:
                    cursor.execute("SELECT * FROM services ORDER BY sort_order, category, name")
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            self.return_connection(conn)
    
    def get_service(self, service_id: str, company_id: int = None) -> Optional[Dict]:
        """Get service by ID, optionally filtered by company"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            if company_id:
                cursor.execute("SELECT * FROM services WHERE id = %s AND company_id = %s", (service_id, company_id))
            else:
                cursor.execute("SELECT * FROM services WHERE id = %s", (service_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                result['company_id'] = row.get('company_id')
                return result
            return None
        finally:
            self.return_connection(conn)
    
    def update_service(self, service_id: str, company_id: int = None, **kwargs) -> bool:
        """Update service information for a specific company"""
        import json
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            allowed_fields = ['category', 'name', 'description', 'duration_minutes',
                             'price', 'price_max', 'emergency_price', 'currency', 'active',
                             'image_url', 'sort_order', 'workers_required', 'worker_restrictions',
                             'requires_callout', 'package_only', 'requires_quote', 'default_materials']
            
            fields = []
            values = []
            for key, value in kwargs.items():
                if key in allowed_fields:
                    if key == 'active' and isinstance(value, bool):
                        value = 1 if value else 0
                    # Convert worker_restrictions dict to JSON
                    if key == 'worker_restrictions' and isinstance(value, dict):
                        value = json.dumps(value)
                    # Convert default_materials list to JSON
                    if key == 'default_materials' and isinstance(value, list):
                        value = json.dumps(value)
                    fields.append(f"{key} = %s")
                    values.append(value)
            
            if fields:
                values.append(datetime.now())
                values.append(service_id)
                if company_id:
                    values.append(company_id)
                    query = f"UPDATE services SET {', '.join(fields)}, updated_at = %s WHERE id = %s AND company_id = %s"
                else:
                    query = f"UPDATE services SET {', '.join(fields)}, updated_at = %s WHERE id = %s"
                cursor.execute(query, values)
                conn.commit()
                success = cursor.rowcount > 0
            else:
                success = False
            
            return success
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Error updating service: {e}")
            return False
        finally:
            self.return_connection(conn)
    
    def delete_service(self, service_id: str, company_id: int = None) -> dict:
        """
        Delete a service for a specific company.
        Jobs using this service will have their service_type set to null.
        Returns dict with success status and count of affected jobs.
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # First get the service name to find affected jobs
            if company_id:
                cursor.execute("SELECT name FROM services WHERE id = %s AND company_id = %s", (service_id, company_id))
            else:
                cursor.execute("SELECT name FROM services WHERE id = %s", (service_id,))
            
            service = cursor.fetchone()
            service_name = service['name'] if service else None
            
            # Count jobs that use this service
            jobs_count = 0
            if service_name and company_id:
                cursor.execute("""
                    SELECT COUNT(*) as count FROM bookings 
                    WHERE service_type = %s AND company_id = %s
                """, (service_name, company_id))
                result = cursor.fetchone()
                jobs_count = result['count'] if result else 0
            
            # Delete the service
            if company_id:
                cursor.execute("DELETE FROM services WHERE id = %s AND company_id = %s", (service_id, company_id))
            else:
                cursor.execute("DELETE FROM services WHERE id = %s", (service_id,))
            
            service_deleted = cursor.rowcount > 0
            conn.commit()
            
            return {
                "success": service_deleted,
                "jobs_affected": jobs_count
            }
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Error deleting service: {e}")
            return {
                "success": False,
                "error": str(e),
                "jobs_affected": 0
            }
        finally:
            self.return_connection(conn)
    
    # ==========================================
    # Package Methods (Service Bundles)
    # ==========================================

    def get_all_packages(self, active_only: bool = True, company_id: int = None) -> List[Dict]:
        """Get all packages for a specific company"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            if company_id:
                if active_only:
                    cursor.execute("SELECT * FROM packages WHERE company_id = %s AND active = 1 ORDER BY sort_order, name", (company_id,))
                else:
                    cursor.execute("SELECT * FROM packages WHERE company_id = %s ORDER BY sort_order, name", (company_id,))
            else:
                if active_only:
                    cursor.execute("SELECT * FROM packages WHERE active = 1 ORDER BY sort_order, name")
                else:
                    cursor.execute("SELECT * FROM packages ORDER BY sort_order, name")
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            self.return_connection(conn)

    def get_package(self, package_id: str, company_id: int = None) -> Optional[Dict]:
        """Get package by ID, optionally filtered by company"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            if company_id:
                cursor.execute("SELECT * FROM packages WHERE id = %s AND company_id = %s", (package_id, company_id))
            else:
                cursor.execute("SELECT * FROM packages WHERE id = %s", (package_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                return result
            return None
        finally:
            self.return_connection(conn)

    def add_package(self, package_id: str, company_id: int, name: str,
                    description: str = None, services: list = None,
                    price_override: float = None, price_max_override: float = None,
                    duration_override: int = None,
                    use_when_uncertain: bool = False, clarifying_question: str = None,
                    active: bool = True, image_url: str = None,
                    sort_order: int = 0, default_materials: list = None) -> bool:
        """Add a new package for a specific company"""
        import json
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            services_json = json.dumps(services or [])
            materials_json = json.dumps(default_materials) if default_materials else '[]'
            cursor.execute("""
                INSERT INTO packages (id, company_id, name, description, services,
                                     price_override, price_max_override, duration_override,
                                     use_when_uncertain,
                                     clarifying_question, active, image_url, sort_order, default_materials)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (package_id, company_id, name, description, services_json,
                  price_override, price_max_override, duration_override,
                  use_when_uncertain,
                  clarifying_question, 1 if active else 0, image_url, sort_order, materials_json))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Error adding package: {e}")
            return False
        finally:
            self.return_connection(conn)

    def update_package(self, package_id: str, company_id: int = None, **kwargs) -> bool:
        """Update package information for a specific company"""
        import json
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            allowed_fields = ['name', 'description', 'services', 'price_override',
                             'price_max_override', 'duration_override', 'use_when_uncertain',
                             'clarifying_question',
                             'active', 'image_url', 'sort_order', 'default_materials']
            
            fields = []
            values = []
            for key, value in kwargs.items():
                if key in allowed_fields:
                    if key == 'active' and isinstance(value, bool):
                        value = 1 if value else 0
                    if key == 'services' and isinstance(value, list):
                        value = json.dumps(value)
                    if key == 'default_materials' and isinstance(value, list):
                        value = json.dumps(value)
                    fields.append(f"{key} = %s")
                    values.append(value)
            
            if fields:
                values.append(datetime.now())
                values.append(package_id)
                if company_id:
                    values.append(company_id)
                    query = f"UPDATE packages SET {', '.join(fields)}, updated_at = %s WHERE id = %s AND company_id = %s"
                else:
                    query = f"UPDATE packages SET {', '.join(fields)}, updated_at = %s WHERE id = %s"
                cursor.execute(query, values)
                conn.commit()
                success = cursor.rowcount > 0
            else:
                success = False
            
            return success
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Error updating package: {e}")
            return False
        finally:
            self.return_connection(conn)

    def delete_package(self, package_id: str, company_id: int = None) -> dict:
        """Delete a package for a specific company. Returns info about affected bookings."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Get the package name to find affected bookings
            if company_id:
                cursor.execute("SELECT name FROM packages WHERE id = %s AND company_id = %s", (package_id, company_id))
            else:
                cursor.execute("SELECT name FROM packages WHERE id = %s", (package_id,))
            
            package = cursor.fetchone()
            package_name = package['name'] if package else None
            
            # Count bookings that reference this package
            jobs_count = 0
            if package_name and company_id:
                cursor.execute("""
                    SELECT COUNT(*) as count FROM bookings 
                    WHERE service_type = %s AND company_id = %s
                """, (package_name, company_id))
                result = cursor.fetchone()
                jobs_count = result['count'] if result else 0
            
            # Delete the package
            if company_id:
                cursor.execute("DELETE FROM packages WHERE id = %s AND company_id = %s", (package_id, company_id))
            else:
                cursor.execute("DELETE FROM packages WHERE id = %s", (package_id,))
            
            package_deleted = cursor.rowcount > 0
            conn.commit()
            
            return {
                "success": package_deleted,
                "jobs_affected": jobs_count
            }
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Error deleting package: {e}")
            return {
                "success": False,
                "error": str(e),
                "jobs_affected": 0
            }
        finally:
            self.return_connection(conn)

    # ==========================================
    # Worker Account Methods (Worker Portal)
    # ==========================================

    def create_worker_account(self, worker_id: int, company_id: int, email: str,
                              invite_token: str, invite_expires_at) -> Optional[int]:
        """Create a worker account for portal access"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO worker_accounts (worker_id, company_id, email, invite_token, invite_expires_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (worker_id, company_id, email, invite_token, invite_expires_at))
            result = cursor.fetchone()
            conn.commit()
            return result['id'] if result else None
        except Exception as e:
            conn.rollback()
            print(f"Error creating worker account: {e}")
            return None
        finally:
            self.return_connection(conn)

    def get_worker_account_by_email(self, email: str) -> Optional[Dict]:
        """Get worker account by email"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM worker_accounts WHERE email = %s", (email,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            self.return_connection(conn)

    def get_worker_account_by_invite_token(self, token: str) -> Optional[Dict]:
        """Get worker account by invite token"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM worker_accounts WHERE invite_token = %s", (token,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            self.return_connection(conn)

    def get_worker_account_by_worker_id(self, worker_id: int) -> Optional[Dict]:
        """Get worker account by worker_id"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM worker_accounts WHERE worker_id = %s", (worker_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            self.return_connection(conn)

    def set_worker_account_password(self, account_id: int, password_hash: str) -> bool:
        """Set password for a worker account (first-time setup)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE worker_accounts 
                SET password_hash = %s, password_set = TRUE, 
                    invite_token = NULL, invite_expires_at = NULL,
                    updated_at = NOW()
                WHERE id = %s
            """, (password_hash, account_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"Error setting worker account password: {e}")
            return False
        finally:
            self.return_connection(conn)

    def update_worker_account_last_login(self, account_id: int):
        """Update last login timestamp for worker account"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE worker_accounts SET last_login = NOW() WHERE id = %s",
                (account_id,)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error updating worker last login: {e}")
        finally:
            self.return_connection(conn)

    def get_worker_account_by_reset_token(self, token: str) -> Optional[Dict]:
        """Get worker account by password reset token"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT * FROM worker_accounts WHERE reset_token = %s", (token,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            cursor.close()
            self.return_connection(conn)

    def update_worker_account_reset_token(self, account_id: int, reset_token, reset_token_expires) -> bool:
        """Set or clear the password reset token for a worker account"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE worker_accounts SET reset_token = %s, reset_token_expires = %s WHERE id = %s",
                (reset_token, reset_token_expires, account_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"Error updating worker reset token: {e}")
            return False
        finally:
            self.return_connection(conn)

    def reset_worker_account_password(self, account_id: int, password_hash: str) -> bool:
        """Reset password for a worker account (forgot password flow)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE worker_accounts
                SET password_hash = %s, password_set = TRUE,
                    reset_token = NULL, reset_token_expires = NULL,
                    updated_at = NOW()
                WHERE id = %s
            """, (password_hash, account_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"Error resetting worker password: {e}")
            return False
        finally:
            self.return_connection(conn)

    def delete_worker_account(self, worker_id: int) -> bool:
        """Delete worker account when worker is deleted"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM worker_accounts WHERE worker_id = %s", (worker_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"Error deleting worker account: {e}")
            return False
        finally:
            self.return_connection(conn)


    # ==========================================
    # Worker Time Off Methods
    # ==========================================

    def create_time_off_request(self, worker_id: int, company_id: int,
                                start_date: str, end_date: str,
                                reason: str = None, leave_type: str = 'vacation') -> Optional[int]:
        """Create a time-off request"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO worker_time_off (worker_id, company_id, start_date, end_date, reason, type)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (worker_id, company_id, start_date, end_date, reason, leave_type))
            result = cursor.fetchone()
            conn.commit()
            return result['id'] if result else None
        except Exception as e:
            conn.rollback()
            print(f"Error creating time-off request: {e}")
            return None
        finally:
            self.return_connection(conn)

    def get_worker_time_off(self, worker_id: int) -> List[Dict]:
        """Get all time-off requests for a worker"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT * FROM worker_time_off 
                WHERE worker_id = %s 
                ORDER BY start_date DESC
            """, (worker_id,))
            rows = [dict(row) for row in cursor.fetchall()]
            # Normalize date fields to ISO strings for JSON serialization
            for row in rows:
                for key in ('start_date', 'end_date'):
                    if key in row and hasattr(row[key], 'isoformat'):
                        row[key] = row[key].isoformat()
                for key in ('created_at', 'updated_at', 'reviewed_at'):
                    if key in row and row[key] and hasattr(row[key], 'isoformat'):
                        row[key] = row[key].isoformat()
            return rows
        finally:
            self.return_connection(conn)

    def get_company_time_off_requests(self, company_id: int, status: str = None) -> List[Dict]:
        """Get all time-off requests for a company (owner view)"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            query = """
                SELECT t.*, w.name as worker_name
                FROM worker_time_off t
                JOIN workers w ON t.worker_id = w.id
                WHERE t.company_id = %s
            """
            params = [company_id]
            if status:
                query += " AND t.status = %s"
                params.append(status)
            query += " ORDER BY t.created_at DESC"
            cursor.execute(query, tuple(params))
            rows = [dict(row) for row in cursor.fetchall()]
            # Normalize date fields to ISO strings for JSON serialization
            for row in rows:
                for key in ('start_date', 'end_date'):
                    if key in row and hasattr(row[key], 'isoformat'):
                        row[key] = row[key].isoformat()
                for key in ('created_at', 'updated_at', 'reviewed_at'):
                    if key in row and row[key] and hasattr(row[key], 'isoformat'):
                        row[key] = row[key].isoformat()
            return rows
        finally:
            self.return_connection(conn)

    def update_time_off_status(self, request_id: int, company_id: int,
                               status: str, reviewer_note: str = None) -> bool:
        """Approve or deny a time-off request (owner only)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE worker_time_off 
                SET status = %s, reviewer_note = %s, reviewed_at = NOW(), updated_at = NOW()
                WHERE id = %s AND company_id = %s
            """, (status, reviewer_note, request_id, company_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"Error updating time-off status: {e}")
            return False
        finally:
            self.return_connection(conn)

    def delete_time_off_request(self, request_id: int, worker_id: int) -> bool:
        """Delete a pending time-off request (worker can only delete their own pending requests)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                DELETE FROM worker_time_off 
                WHERE id = %s AND worker_id = %s AND status = 'pending'
            """, (request_id, worker_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"Error deleting time-off request: {e}")
            return False
        finally:
            self.return_connection(conn)


    def get_workers_on_leave(self, company_id: int, start_date, end_date) -> list:
        """Get approved time-off records overlapping the given date range.
        Returns list of dicts with worker_id, start_date, end_date.
        Returns empty list if table doesn't exist yet."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT worker_id, start_date, end_date FROM worker_time_off
                WHERE company_id = %s AND status = 'approved'
                AND start_date <= %s AND end_date >= %s
            """, (company_id, end_date, start_date))
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            # Table may not exist yet
            conn.rollback()
            return []
        finally:
            self.return_connection(conn)

    # ==========================================
    # Notification Methods
    # ==========================================

    def create_notification(self, company_id: int, recipient_type: str,
                           recipient_id: int, notif_type: str, message: str,
                           metadata: dict = None) -> Optional[int]:
        """Create a notification. recipient_type is 'owner' or 'worker'."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO notifications (company_id, recipient_type, recipient_id, type, message, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (company_id, recipient_type, recipient_id, notif_type, message,
                  __import__('json').dumps(metadata or {})))
            result = cursor.fetchone()
            conn.commit()
            return result['id'] if result else None
        except Exception as e:
            conn.rollback()
            print(f"Error creating notification: {e}")
            return None
        finally:
            self.return_connection(conn)

    def get_owner_notifications(self, company_id: int, limit: int = 30) -> List[Dict]:
        """Get notifications for the business owner (last 48 hours)."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT * FROM notifications
                WHERE company_id = %s AND recipient_type = 'owner'
                AND created_at > NOW() - INTERVAL '48 hours'
                ORDER BY created_at DESC
                LIMIT %s
            """, (company_id, limit))
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            conn.rollback()
            return []
        finally:
            self.return_connection(conn)

    def get_worker_notifications(self, worker_id: int, company_id: int, limit: int = 30) -> List[Dict]:
        """Get notifications for a specific worker (last 48 hours)."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT * FROM notifications
                WHERE company_id = %s AND recipient_type = 'worker' AND recipient_id = %s
                AND created_at > NOW() - INTERVAL '48 hours'
                ORDER BY created_at DESC
                LIMIT %s
            """, (company_id, worker_id, limit))
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            conn.rollback()
            return []
        finally:
            self.return_connection(conn)

    # ── Messaging ──────────────────────────────────────────────────────

    def send_message(self, company_id: int, worker_id: int, sender_type: str, content: str) -> Optional[Dict]:
        """Send a message between owner and worker. sender_type is 'owner' or 'worker'."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO messages (company_id, worker_id, sender_type, content)
                VALUES (%s, %s, %s, %s)
                RETURNING *
            """, (company_id, worker_id, sender_type, content))
            result = cursor.fetchone()
            conn.commit()
            return dict(result) if result else None
        except Exception as e:
            conn.rollback()
            print(f"Error sending message: {e}")
            return None
        finally:
            self.return_connection(conn)

    def get_conversation(self, company_id: int, worker_id: int, limit: int = 50, before_id: int = None) -> List[Dict]:
        """Get messages between owner and a specific worker."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if before_id:
                cursor.execute("""
                    SELECT * FROM messages
                    WHERE company_id = %s AND worker_id = %s AND id < %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (company_id, worker_id, before_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM messages
                    WHERE company_id = %s AND worker_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (company_id, worker_id, limit))
            rows = cursor.fetchall()
            return [dict(r) for r in reversed(rows)]  # Return in chronological order
        except Exception as e:
            conn.rollback()
            print(f"Error getting conversation: {e}")
            return []
        finally:
            self.return_connection(conn)

    def mark_messages_read(self, company_id: int, worker_id: int, reader_type: str) -> int:
        """Mark messages as read. reader_type='owner' marks worker messages as read, and vice versa."""
        sender_type = 'worker' if reader_type == 'owner' else 'owner'
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE messages SET read = TRUE
                WHERE company_id = %s AND worker_id = %s AND sender_type = %s AND read = FALSE
            """, (company_id, worker_id, sender_type))
            count = cursor.rowcount
            conn.commit()
            return count
        except Exception as e:
            conn.rollback()
            print(f"Error marking messages read: {e}")
            return 0
        finally:
            self.return_connection(conn)

    def get_unread_message_counts(self, company_id: int) -> Dict[int, int]:
        """Get unread message counts per worker for the owner."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT worker_id, COUNT(*) as unread
                FROM messages
                WHERE company_id = %s AND sender_type = 'worker' AND read = FALSE
                GROUP BY worker_id
            """, (company_id,))
            return {row['worker_id']: row['unread'] for row in cursor.fetchall()}
        except Exception:
            conn.rollback()
            return {}
        finally:
            self.return_connection(conn)

    def get_worker_unread_count(self, company_id: int, worker_id: int) -> int:
        """Get unread message count for a specific worker."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM messages
                WHERE company_id = %s AND worker_id = %s AND sender_type = 'owner' AND read = FALSE
            """, (company_id, worker_id))
            return cursor.fetchone()[0]
        except Exception:
            conn.rollback()
            return 0
        finally:
            self.return_connection(conn)

    def get_owner_conversations_summary(self, company_id: int) -> List[Dict]:
        """Get a summary of all conversations for the owner with last message and unread count."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT DISTINCT ON (m.worker_id)
                    m.worker_id,
                    w.name as worker_name,
                    w.image_url as worker_image,
                    m.content as last_message,
                    m.sender_type as last_sender,
                    m.created_at as last_message_at,
                    (SELECT COUNT(*) FROM messages m2 
                     WHERE m2.company_id = m.company_id AND m2.worker_id = m.worker_id 
                     AND m2.sender_type = 'worker' AND m2.read = FALSE) as unread_count
                FROM messages m
                JOIN workers w ON w.id = m.worker_id
                WHERE m.company_id = %s
                ORDER BY m.worker_id, m.created_at DESC
            """, (company_id,))
            rows = [dict(r) for r in cursor.fetchall()]
            # Sort by last message time descending
            rows.sort(key=lambda x: x.get('last_message_at') or datetime.min, reverse=True)
            return rows
        except Exception as e:
            conn.rollback()
            print(f"Error getting conversations summary: {e}")
            return []
        finally:
            self.return_connection(conn)

    # ============================================
    # Call Logs
    # ============================================

    def create_call_log(self, company_id: int, phone_number: str = None,
                        caller_name: str = None, address: str = None,
                        eircode: str = None, duration_seconds: int = None,
                        call_outcome: str = 'no_action', ai_summary: str = None,
                        summary: str = None, call_sid: str = None,
                        is_lost_job: bool = False, lost_job_reason: str = None) -> Optional[int]:
        """Create a call log entry for every call regardless of outcome."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO call_logs 
                (company_id, phone_number, caller_name, address, eircode,
                 duration_seconds, call_outcome, ai_summary, summary, call_sid,
                 is_lost_job, lost_job_reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (company_id, phone_number, caller_name, address, eircode,
                  duration_seconds, call_outcome, ai_summary, summary, call_sid,
                  is_lost_job, lost_job_reason))
            result = cursor.fetchone()
            conn.commit()
            return result[0] if result else None
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Failed to create call log: {e}")
            return None
        finally:
            self.return_connection(conn)

    def update_call_log(self, call_log_id: int, recording_url: str = None) -> bool:
        """Update a call log entry (e.g., to attach a recording URL after upload)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            updates = []
            params = []
            if recording_url is not None:
                updates.append("recording_url = %s")
                params.append(recording_url)
            if not updates:
                return False
            params.append(call_log_id)
            cursor.execute(f"UPDATE call_logs SET {', '.join(updates)} WHERE id = %s", tuple(params))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Failed to update call log: {e}")
            return False
        finally:
            self.return_connection(conn)

    def get_call_logs(self, company_id: int, limit: int = 100, offset: int = 0,
                      outcome_filter: str = None, search: str = None,
                      lost_only: bool = False, outcomes: list = None,
                      include_lost: bool = False) -> List[Dict]:
        """Get call logs for a company with optional filtering."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            query = "SELECT * FROM call_logs WHERE company_id = %s"
            params = [company_id]

            if outcomes and include_lost:
                # OR: outcome in list OR is_lost_job
                placeholders = ','.join(['%s'] * len(outcomes))
                query += f" AND (call_outcome IN ({placeholders}) OR is_lost_job = TRUE)"
                params.extend(outcomes)
            elif outcomes:
                placeholders = ','.join(['%s'] * len(outcomes))
                query += f" AND call_outcome IN ({placeholders})"
                params.extend(outcomes)
            elif outcome_filter and outcome_filter != 'all':
                query += " AND call_outcome = %s"
                params.append(outcome_filter)

            if lost_only:
                query += " AND is_lost_job = TRUE"

            if search:
                query += " AND (caller_name ILIKE %s OR phone_number ILIKE %s OR address ILIKE %s)"
                term = f"%{search}%"
                params.extend([term, term, term])

            query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cursor.execute(query, tuple(params))
            return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Failed to get call logs: {e}")
            return []
        finally:
            self.return_connection(conn)

    def get_call_log_count(self, company_id: int, outcome_filter: str = None,
                           search: str = None, lost_only: bool = False,
                           outcomes: list = None, include_lost: bool = False) -> int:
        """Get total count of call logs for pagination."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            query = "SELECT COUNT(*) FROM call_logs WHERE company_id = %s"
            params = [company_id]

            if outcomes and include_lost:
                placeholders = ','.join(['%s'] * len(outcomes))
                query += f" AND (call_outcome IN ({placeholders}) OR is_lost_job = TRUE)"
                params.extend(outcomes)
            elif outcomes:
                placeholders = ','.join(['%s'] * len(outcomes))
                query += f" AND call_outcome IN ({placeholders})"
                params.extend(outcomes)
            elif outcome_filter and outcome_filter != 'all':
                query += " AND call_outcome = %s"
                params.append(outcome_filter)

            if lost_only:
                query += " AND is_lost_job = TRUE"

            if search:
                query += " AND (caller_name ILIKE %s OR phone_number ILIKE %s OR address ILIKE %s)"
                term = f"%{search}%"
                params.extend([term, term, term])

            cursor.execute(query, tuple(params))
            return cursor.fetchone()[0]
        except Exception as e:
            conn.rollback()
            return 0
        finally:
            self.return_connection(conn)
