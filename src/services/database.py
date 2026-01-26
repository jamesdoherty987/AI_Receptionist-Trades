"""
Database models for AI Trades Receptionist
Stores client information, jobs, notes, and workers
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import json


from src.utils.config import config

class Database:
    """SQLite database for client, job, and worker management"""
    
    def __init__(self, db_path: str = "data/receptionist.db"):
        """Initialize database connection"""
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Clients table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                date_of_birth DATE,
                description TEXT,
                first_visit DATE,
                last_visit DATE,
                total_appointments INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, phone, email)
            )
        """)
        
        # Bookings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients (id)
            )
        """)
        
        # Appointment notes table (notes specific to each appointment)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointment_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER,
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                note TEXT NOT NULL,
                created_by TEXT DEFAULT 'system',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients (id)
            )
        """)
        
        # Call logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT,
                duration_seconds INTEGER,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Workers table (for tradespersons/staff)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                trade_specialty TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Worker assignments table (linking workers to jobs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS worker_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER NOT NULL,
                worker_id INTEGER NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (booking_id) REFERENCES bookings (id) ON DELETE CASCADE,
                FOREIGN KEY (worker_id) REFERENCES workers (id) ON DELETE CASCADE,
                UNIQUE(booking_id, worker_id)
            )
        """)
        
        # Add charge column to bookings if it doesn't exist
        cursor.execute("""
            PRAGMA table_info(bookings)
        """)
        columns = [column[1] for column in cursor.fetchall()]
        if 'charge' not in columns:
            cursor.execute("""
                ALTER TABLE bookings ADD COLUMN charge REAL DEFAULT {config.DEFAULT_APPOINTMENT_CHARGE}
            """)
            print("✅ Added charge column to bookings table")
        
        if 'payment_status' not in columns:
            cursor.execute("""
                ALTER TABLE bookings ADD COLUMN payment_status TEXT DEFAULT 'unpaid'
            """)
            print("✅ Added payment_status column to bookings table")
        
        if 'payment_method' not in columns:
            cursor.execute("""
                ALTER TABLE bookings ADD COLUMN payment_method TEXT
            """)
            print("✅ Added payment_method column to bookings table")
        
        # Add date_of_birth and description to clients if they don't exist
        cursor.execute("""
            PRAGMA table_info(clients)
        """)
        client_columns = [column[1] for column in cursor.fetchall()]
        if 'date_of_birth' not in client_columns:
            cursor.execute("""
                ALTER TABLE clients ADD COLUMN date_of_birth DATE
            """)
            print("✅ Added date_of_birth column to clients table")
        
        if 'description' not in client_columns:
            cursor.execute("""
                ALTER TABLE clients ADD COLUMN description TEXT
            """)
            print("✅ Added description column to clients table")
        
        # Add new fields to bookings table if they don't exist
        cursor.execute("""
            PRAGMA table_info(bookings)
        """)
        booking_columns = [column[1] for column in cursor.fetchall()]
        
        if 'urgency' not in booking_columns:
            cursor.execute("""
                ALTER TABLE bookings ADD COLUMN urgency TEXT DEFAULT 'scheduled'
            """)
            print("✅ Added urgency column to bookings table")
        
        if 'address' not in booking_columns:
            cursor.execute("""
                ALTER TABLE bookings ADD COLUMN address TEXT
            """)
            print("✅ Added address column to bookings table")
        
        if 'eircode' not in booking_columns:
            cursor.execute("""
                ALTER TABLE bookings ADD COLUMN eircode TEXT
            """)
            print("✅ Added eircode column to bookings table")
        
        if 'property_type' not in booking_columns:
            cursor.execute("""
                ALTER TABLE bookings ADD COLUMN property_type TEXT
            """)
            print("✅ Added property_type column to bookings table")
        
        conn.commit()
        conn.close()
        print("✅ Database initialized")
    
    # Client methods
    def add_client(self, name: str, phone: str = None, email: str = None, date_of_birth: str = None, description: str = None) -> int:
        """Add a new client. Requires either phone or email."""
        if not phone and not email:
            raise ValueError("Client must have either phone number or email address")
        
        # Normalize name to lowercase for case-insensitive matching
        name = name.lower().strip()
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO clients (name, phone, email, date_of_birth, description, first_visit)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, phone, email, date_of_birth, description, datetime.now()))
            
            client_id = cursor.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            # Client already exists
            conn.rollback()
            # Find existing client
            cursor.execute("""
                SELECT id FROM clients 
                WHERE name = ? AND (phone = ? OR email = ?)
            """, (name, phone, email))
            row = cursor.fetchone()
            client_id = row[0] if row else None
        finally:
            conn.close()
        
        return client_id
    
    def find_or_create_client(self, name: str, phone: str = None, email: str = None, date_of_birth: str = None) -> int:
        """
        Find existing client or create new one. 
        Priority: name + DOB (if DOB provided) > name + phone > name + email
        """
        if not phone and not email:
            raise ValueError("Client must have either phone number or email address")
        
        # Normalize name to lowercase for case-insensitive matching
        name = name.lower().strip()
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # First priority: Try to find by name + DOB if DOB is provided
        if date_of_birth:
            cursor.execute("""
                SELECT id FROM clients WHERE name = ? AND date_of_birth = ?
            """, (name, date_of_birth))
            row = cursor.fetchone()
            if row:
                conn.close()
                print(f"✅ Found existing client by name + DOB: {name} (ID: {row[0]})")
                return row[0]
            else:
                # DOB provided but no match found - this is a NEW person with same name
                # Create new client immediately without checking phone/email
                conn.close()
                print(f"✅ Creating NEW client (same name, different DOB): {name} (DOB: {date_of_birth})")
                return self.add_client(name, phone, email, date_of_birth)
        
        # No DOB provided - fall back to matching by name + contact info
        if phone:
            cursor.execute("""
                SELECT id FROM clients WHERE name = ? AND phone = ?
            """, (name, phone))
        elif email:
            cursor.execute("""
                SELECT id FROM clients WHERE name = ? AND email = ?
            """, (name, email))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row[0]
        else:
            # Create new client
            return self.add_client(name, phone, email, date_of_birth)
    
    def get_client(self, client_id: int) -> Optional[Dict]:
        """Get client by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0], 'name': row[1], 'phone': row[2], 'email': row[3],
                'first_visit': row[4], 'last_visit': row[5], 
                'total_appointments': row[6], 'created_at': row[7], 'updated_at': row[8],
                'date_of_birth': row[9], 'description': row[10]
            }
        return None
    
    def get_client_by_phone(self, phone: str) -> Optional[Dict]:
        """Get client by phone number"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM clients WHERE phone = ?", (phone,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0], 'name': row[1], 'phone': row[2], 'email': row[3],
                'first_visit': row[4], 'last_visit': row[5], 
                'total_appointments': row[6], 'created_at': row[7], 'updated_at': row[8],
                'date_of_birth': row[9], 'description': row[10]
            }
        return None
    
    def get_clients_by_name(self, name: str) -> List[Dict]:
        """Get all clients with a given name (case-insensitive)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Normalize name for case-insensitive search
        name = name.lower().strip()
        
        cursor.execute("SELECT * FROM clients WHERE name = ?", (name,))
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0], 'name': row[1], 'phone': row[2], 'email': row[3],
            'first_visit': row[4], 'last_visit': row[5], 
            'total_appointments': row[6], 'created_at': row[7], 'updated_at': row[8],
            'date_of_birth': row[9], 'description': row[10]
        } for row in rows]
    
    def get_client_by_name_and_dob(self, name: str, date_of_birth: str) -> Optional[Dict]:
        """Get client by name and date of birth"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Normalize name for case-insensitive search
        name = name.lower().strip()
        
        print(f"🔍 DB: Looking for client with name='{name}' and dob='{date_of_birth}'")
        cursor.execute("SELECT * FROM clients WHERE name = ? AND date_of_birth = ?", (name, date_of_birth))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            print(f"✅ DB: Found client ID={row[0]}, name={row[1]}, phone={row[2]}, dob={row[9]}")
            return {
                'id': row[0], 'name': row[1], 'phone': row[2], 'email': row[3],
                'first_visit': row[4], 'last_visit': row[5], 
                'total_appointments': row[6], 'created_at': row[7], 'updated_at': row[8],
                'date_of_birth': row[9], 'description': row[10]
            }
        print(f"❌ DB: No client found with name='{name}' and dob='{date_of_birth}'")
        return None
    
    def update_client_description(self, client_id: int, description: str):
        """Update client description (AI-generated summary)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE clients 
            SET description = ?, updated_at = ?
            WHERE id = ?
        """, (description, datetime.now(), client_id))
        
        conn.commit()
        conn.close()
    
    def update_client_dob(self, client_id: int, date_of_birth: str):
        """Update client date of birth"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE clients 
            SET date_of_birth = ?, updated_at = ?
            WHERE id = ?
        """, (date_of_birth, datetime.now(), client_id))
        
        conn.commit()
        conn.close()
        print(f"✅ Updated DOB for client {client_id}: {date_of_birth}")
    
    def get_all_clients(self) -> List[Dict]:
        """Get all clients"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM clients ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0], 'name': row[1], 'phone': row[2], 'email': row[3],
            'first_visit': row[4], 'last_visit': row[5], 
            'total_appointments': row[6], 'created_at': row[7], 'updated_at': row[8],
            'date_of_birth': row[9], 'description': row[10]
        } for row in rows]
    
    def update_client(self, client_id: int, **kwargs):
        """Update client information"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in ['name', 'phone', 'email', 'date_of_birth', 'description']:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if fields:
            values.append(datetime.now())
            values.append(client_id)
            query = f"UPDATE clients SET {', '.join(fields)}, updated_at = ? WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
        
        conn.close()
    
    # Booking methods
    def add_booking(self, client_id: int, calendar_event_id: str, 
                   appointment_time: datetime, service_type: str,
                   phone_number: str = None, email: str = None,
                   urgency: str = 'scheduled', address: str = None,
                   eircode: str = None, property_type: str = None,
                   charge: float = None) -> int:
        """Add a new booking"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # If phone/email not provided, get from client record
        if not phone_number and not email:
            client = self.get_client(client_id)
            if client:
                phone_number = client.get('phone')
                email = client.get('email')
        
        # If charge not provided, use default (database will use 50.0)
        if charge is not None:
            cursor.execute("""
                INSERT INTO bookings (client_id, calendar_event_id, appointment_time, 
                                    service_type, phone_number, email, urgency, address,
                                    eircode, property_type, charge)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (client_id, calendar_event_id, appointment_time, service_type, 
                  phone_number, email, urgency, address, eircode, property_type, charge))
        else:
            cursor.execute("""
                INSERT INTO bookings (client_id, calendar_event_id, appointment_time, 
                                    service_type, phone_number, email, urgency, address,
                                    eircode, property_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (client_id, calendar_event_id, appointment_time, service_type, 
                  phone_number, email, urgency, address, eircode, property_type))
        
        booking_id = cursor.lastrowid
        
        # Update client stats
        cursor.execute("""
            UPDATE clients 
            SET total_appointments = total_appointments + 1,
                last_visit = ?,
                updated_at = ?
            WHERE id = ?
        """, (appointment_time, datetime.now(), client_id))
        
        conn.commit()
        conn.close()
        return booking_id
    
    def get_client_bookings(self, client_id: int) -> List[Dict]:
        """Get all bookings for a client with their notes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM bookings 
            WHERE client_id = ? 
            ORDER BY appointment_time DESC
        """, (client_id,))
        
        rows = cursor.fetchall()
        
        bookings = []
        for row in rows:
            booking = {
                'id': row[0], 'client_id': row[1], 'calendar_event_id': row[2],
                'appointment_time': row[3], 'service_type': row[4], 'status': row[5],
                'phone_number': row[6], 'email': row[7], 'created_at': row[8],
                'charge': row[9] if len(row) > 9 else None,
                'payment_status': row[10] if len(row) > 10 else None,
                'payment_method': row[11] if len(row) > 11 else None,
                'urgency': row[12] if len(row) > 12 else None,
                'address': row[13] if len(row) > 13 else None,
                'eircode': row[14] if len(row) > 14 else None,
                'property_type': row[15] if len(row) > 15 else None
            }
            # Get notes for this booking
            booking['notes'] = self.get_appointment_notes(booking['id'])
            bookings.append(booking)
        
        conn.close()
        return bookings
    
    def get_all_bookings(self) -> List[Dict]:
        """Get all bookings"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT b.*, c.name as client_name 
            FROM bookings b
            LEFT JOIN clients c ON b.client_id = c.id
            ORDER BY b.appointment_time DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0], 'client_id': row[1], 'calendar_event_id': row[2],
            'appointment_time': row[3], 'service_type': row[4], 'status': row[5],
            'phone_number': row[6], 'email': row[7], 'created_at': row[8],
            'charge': row[9], 'payment_status': row[10], 'payment_method': row[11],
            'urgency': row[12], 'address': row[13], 'eircode': row[14], 
            'property_type': row[15], 'client_name': row[16]
        } for row in rows]
    
    def update_booking(self, booking_id: int, **kwargs) -> bool:
        """Update booking information"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in ['calendar_event_id', 'appointment_time', 'service_type', 
                      'status', 'phone_number', 'email', 'charge', 'payment_status', 
                      'payment_method', 'urgency', 'address', 'eircode', 'property_type']:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if fields:
            values.append(booking_id)
            query = f"UPDATE bookings SET {', '.join(fields)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
            success = cursor.rowcount > 0
        else:
            success = False
        
        conn.close()
        return success
    
    def delete_booking(self, booking_id: int) -> bool:
        """Delete a booking completely from the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Delete associated appointment notes first (foreign key constraint)
            cursor.execute("DELETE FROM appointment_notes WHERE booking_id = ?", (booking_id,))
            # Delete the booking
            cursor.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                print(f"✅ Deleted booking from database (ID: {booking_id})")
        except Exception as e:
            print(f"❌ Failed to delete booking: {e}")
            conn.rollback()
            success = False
        finally:
            conn.close()
        
        return success
    
    def get_financial_stats(self) -> Dict:
        """Get financial statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Total revenue
        cursor.execute("SELECT SUM(charge) FROM bookings WHERE status != 'cancelled'")
        total_revenue = cursor.fetchone()[0] or 0
        
        # Revenue by status
        cursor.execute("""
            SELECT payment_status, SUM(charge), COUNT(*) 
            FROM bookings 
            WHERE status != 'cancelled'
            GROUP BY payment_status
        """)
        payment_breakdown = cursor.fetchall()
        
        # Revenue by month
        cursor.execute("""
            SELECT strftime('%Y-%m', appointment_time) as month, 
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
        
        conn.close()
        
        # Convert payment_breakdown array to dictionary for easier access
        breakdown_dict = {'paid': 0, 'unpaid': 0}
        for row in payment_breakdown:
            status = row[0] or 'unpaid'
            amount = float(row[1] or 0)
            if status in breakdown_dict:
                breakdown_dict[status] = amount
        
        return {
            'total_revenue': float(total_revenue),
            'payment_breakdown': breakdown_dict,
            'monthly_revenue': [
                {'month': row[0], 'revenue': float(row[1] or 0), 'appointments': row[2]}
                for row in monthly_revenue
            ],
            'payment_methods': {
                row[0]: float(row[1] or 0)
                for row in payment_methods
            }
        }
    
    # Notes methods (client-level notes)
    def add_note(self, client_id: int, note: str, created_by: str = "system") -> int:
        """Add a note to a client"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO notes (client_id, note, created_by)
            VALUES (?, ?, ?)
        """, (client_id, note, created_by))
        
        note_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return note_id
    
    def get_client_notes(self, client_id: int) -> List[Dict]:
        """Get all notes for a client"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM notes 
            WHERE client_id = ? 
            ORDER BY created_at DESC
        """, (client_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0], 'client_id': row[1], 'note': row[2],
            'created_by': row[3], 'created_at': row[4]
        } for row in rows]
    
    # Appointment notes methods (appointment-specific notes)
    def add_appointment_note(self, booking_id: int, note: str, created_by: str = "system") -> int:
        """Add a note to a specific appointment"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO appointment_notes (booking_id, note, created_by)
            VALUES (?, ?, ?)
        """, (booking_id, note, created_by))
        
        note_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return note_id
    
    def get_appointment_notes(self, booking_id: int) -> List[Dict]:
        """Get all notes for a specific appointment"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM appointment_notes 
            WHERE booking_id = ? 
            ORDER BY created_at DESC
        """, (booking_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0], 'booking_id': row[1], 'note': row[2],
            'created_by': row[3], 'created_at': row[4], 'updated_at': row[5]
        } for row in rows]
    
    def update_appointment_note(self, note_id: int, note: str) -> bool:
        """Update an appointment note"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE appointment_notes 
            SET note = ?, updated_at = ?
            WHERE id = ?
        """, (note, datetime.now(), note_id))
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0
    
    def delete_appointment_note(self, note_id: int) -> bool:
        """Delete an appointment note"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM appointment_notes WHERE id = ?", (note_id,))
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0
    
    # Call log methods
    def add_call_log(self, phone_number: str, duration_seconds: int = 0, summary: str = ""):
        """Log a call"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO call_logs (phone_number, duration_seconds, summary)
            VALUES (?, ?, ?)
        """, (phone_number, duration_seconds, summary))
        
        conn.commit()
        conn.close()
    
    # Worker methods
    def add_worker(self, name: str, phone: str = None, email: str = None, trade_specialty: str = None) -> int:
        """Add a new worker/tradesperson"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO workers (name, phone, email, trade_specialty)
            VALUES (?, ?, ?, ?)
        """, (name, phone, email, trade_specialty))
        
        worker_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return worker_id
    
    def get_all_workers(self) -> List[Dict]:
        """Get all workers"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM workers ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0], 'name': row[1], 'phone': row[2], 'email': row[3],
            'trade_specialty': row[4], 'status': row[5], 
            'created_at': row[6], 'updated_at': row[7]
        } for row in rows]
    
    def get_worker(self, worker_id: int) -> Optional[Dict]:
        """Get worker by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0], 'name': row[1], 'phone': row[2], 'email': row[3],
                'trade_specialty': row[4], 'status': row[5],
                'created_at': row[6], 'updated_at': row[7]
            }
        return None
    
    def update_worker(self, worker_id: int, **kwargs):
        """Update worker information"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in ['name', 'phone', 'email', 'trade_specialty', 'status']:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if fields:
            values.append(datetime.now())
            values.append(worker_id)
            query = f"UPDATE workers SET {', '.join(fields)}, updated_at = ? WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
        
        conn.close()
    
    def delete_worker(self, worker_id: int) -> bool:
        """Delete a worker"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return rows_affected > 0
    
    # Worker Assignment methods
    def assign_worker_to_job(self, booking_id: int, worker_id: int) -> Dict:
        """Assign a worker to a job with conflict detection"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # First, get the job details to check timing
        cursor.execute("""
            SELECT b.appointment_time, b.service_type, c.name as client_name 
            FROM bookings b
            LEFT JOIN clients c ON b.client_id = c.id
            WHERE b.id = ?
        """, (booking_id,))
        job = cursor.fetchone()
        
        if not job:
            conn.close()
            return {"success": False, "error": "Job not found"}
        
        job_time = datetime.fromisoformat(job[0].replace('Z', '+00:00')) if isinstance(job[0], str) else job[0]
        
        # Check if worker is already assigned to another job at the same time
        # We'll consider a conflict if jobs overlap within a 2-hour window
        cursor.execute("""
            SELECT b.id, b.appointment_time, c.name as client_name, b.service_type
            FROM worker_assignments wa
            JOIN bookings b ON wa.booking_id = b.id
            LEFT JOIN clients c ON b.client_id = c.id
            WHERE wa.worker_id = ?
            AND b.status != 'cancelled'
            AND b.status != 'completed'
            AND b.id != ?
        """, (worker_id, booking_id,))
        
        existing_assignments = cursor.fetchall()
        
        # Check for time conflicts (within 2 hours)
        for assignment in existing_assignments:
            existing_time = datetime.fromisoformat(assignment[1].replace('Z', '+00:00')) if isinstance(assignment[1], str) else assignment[1]
            time_diff = abs((job_time - existing_time).total_seconds() / 3600)  # hours
            
            if time_diff < 2:  # Conflict if within 2 hours
                conn.close()
                return {
                    "success": False,
                    "error": "Worker is already assigned to another job at this time",
                    "conflict": {
                        "job_id": assignment[0],
                        "time": assignment[1],
                        "client": assignment[2],
                        "service": assignment[3]
                    }
                }
        
        # No conflicts, proceed with assignment
        try:
            cursor.execute("""
                INSERT INTO worker_assignments (booking_id, worker_id)
                VALUES (?, ?)
            """, (booking_id, worker_id))
            
            assignment_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "assignment_id": assignment_id,
                "message": "Worker assigned successfully"
            }
        except sqlite3.IntegrityError:
            conn.close()
            return {
                "success": False,
                "error": "Worker is already assigned to this job"
            }
    
    def remove_worker_from_job(self, booking_id: int, worker_id: int) -> bool:
        """Remove a worker assignment from a job"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM worker_assignments
            WHERE booking_id = ? AND worker_id = ?
        """, (booking_id, worker_id))
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return rows_affected > 0
    
    def get_job_workers(self, booking_id: int) -> List[Dict]:
        """Get all workers assigned to a specific job"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT w.id, w.name, w.phone, w.email, w.trade_specialty, wa.assigned_at
            FROM worker_assignments wa
            JOIN workers w ON wa.worker_id = w.id
            WHERE wa.booking_id = ?
        """, (booking_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0],
            'name': row[1],
            'phone': row[2],
            'email': row[3],
            'trade_specialty': row[4],
            'assigned_at': row[5]
        } for row in rows]
    
    def get_worker_jobs(self, worker_id: int, include_completed: bool = False) -> List[Dict]:
        """Get all jobs assigned to a specific worker"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT b.id, b.appointment_time, c.name as client_name, b.service_type, 
                   b.status, b.address, b.phone_number, wa.assigned_at
            FROM worker_assignments wa
            JOIN bookings b ON wa.booking_id = b.id
            LEFT JOIN clients c ON b.client_id = c.id
            WHERE wa.worker_id = ?
        """
        
        if not include_completed:
            query += " AND b.status != 'completed' AND b.status != 'cancelled'"
        
        query += " ORDER BY b.appointment_time ASC"
        
        cursor.execute(query, (worker_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0],
            'appointment_time': row[1],
            'client_name': row[2],
            'service_type': row[3],
            'status': row[4],
            'address': row[5],
            'phone_number': row[6],
            'assigned_at': row[7]
        } for row in rows]
    
    def get_worker_schedule(self, worker_id: int, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Get worker's schedule within a date range"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT b.id, b.appointment_time, c.name as client_name, b.service_type, 
                   b.status, b.address
            FROM worker_assignments wa
            JOIN bookings b ON wa.booking_id = b.id
            LEFT JOIN clients c ON b.client_id = c.id
            WHERE wa.worker_id = ?
            AND b.status != 'cancelled'
        """
        
        params = [worker_id]
        
        if start_date:
            query += " AND b.appointment_time >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND b.appointment_time <= ?"
            params.append(end_date)
        
        query += " ORDER BY b.appointment_time ASC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': row[0],
            'appointment_time': row[1],
            'client_name': row[2],
            'service_type': row[3],
            'status': row[4],
            'address': row[5]
        } for row in rows]


# Global database instance
_db = None

def get_database() -> Database:
    """Get or create global database instance"""
    global _db
    if _db is None:
        _db = Database()
    return _db
