"""
Settings Manager for AI Receptionist
Manages both business and developer settings
"""
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List


class SettingsManager:
    """Manage application settings"""
    
    def __init__(self, db_path: str = "data/receptionist.db"):
        """Initialize settings manager"""
        self.db_path = db_path
        self.services_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            'config', 'services_menu.json'
        )
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_settings_tables()
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def init_settings_tables(self):
        """Initialize settings tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Business settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT,
                business_type TEXT,
                phone TEXT,
                email TEXT,
                website TEXT,
                address TEXT,
                city TEXT,
                country TEXT,
                timezone TEXT DEFAULT 'Europe/Dublin',
                currency TEXT DEFAULT 'EUR',
                default_charge REAL DEFAULT 50.0,
                appointment_duration INTEGER DEFAULT 60,
                opening_hours_start INTEGER DEFAULT 9,
                opening_hours_end INTEGER DEFAULT 17,
                days_open TEXT DEFAULT '["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]',
                max_booking_days_ahead INTEGER DEFAULT 30,
                allow_weekend_booking INTEGER DEFAULT 0,
                services TEXT,
                payment_methods TEXT DEFAULT '["cash", "card", "Apple Pay"]',
                cancellation_policy TEXT,
                reminder_hours_before INTEGER DEFAULT 24,
                auto_confirm_bookings INTEGER DEFAULT 1,
                fallback_phone_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Developer settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS developer_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                openai_model TEXT DEFAULT 'gpt-4o-mini',
                openai_temperature REAL DEFAULT 0.7,
                openai_max_tokens INTEGER DEFAULT 150,
                deepgram_model TEXT DEFAULT 'nova-2',
                tts_provider TEXT DEFAULT 'deepgram',
                elevenlabs_voice_id TEXT,
                webhook_url TEXT,
                webhook_secret TEXT,
                log_level TEXT DEFAULT 'INFO',
                enable_call_recording INTEGER DEFAULT 0,
                enable_analytics INTEGER DEFAULT 1,
                max_concurrent_calls INTEGER DEFAULT 10,
                session_timeout_minutes INTEGER DEFAULT 30,
                enable_maintenance_mode INTEGER DEFAULT 0,
                maintenance_message TEXT,
                rate_limit_per_minute INTEGER DEFAULT 60,
                enable_debug_mode INTEGER DEFAULT 0,
                ai_receptionist_enabled INTEGER DEFAULT 1,
                fallback_phone_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add new columns if table already exists (migration)
        try:
            # Migrate business_settings table
            cursor.execute("PRAGMA table_info(business_settings)")
            business_columns = [row[1] for row in cursor.fetchall()]
            
            if 'fallback_phone_number' not in business_columns:
                cursor.execute("""
                    ALTER TABLE business_settings 
                    ADD COLUMN fallback_phone_number TEXT
                """)
                print("✅ Added fallback_phone_number column to business_settings")
            
            if 'logo_url' not in business_columns:
                cursor.execute("""
                    ALTER TABLE business_settings 
                    ADD COLUMN logo_url TEXT
                """)
                print("✅ Added logo_url column to business_settings")
            
            # Migrate developer_settings table
            cursor.execute("PRAGMA table_info(developer_settings)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'ai_receptionist_enabled' not in columns:
                cursor.execute("""
                    ALTER TABLE developer_settings 
                    ADD COLUMN ai_receptionist_enabled INTEGER DEFAULT 1
                """)
                print("✅ Added ai_receptionist_enabled column")
            
            if 'fallback_phone_number' not in columns:
                cursor.execute("""
                    ALTER TABLE developer_settings 
                    ADD COLUMN fallback_phone_number TEXT
                """)
                print("✅ Added fallback_phone_number column")
        except Exception as e:
            # Columns might already exist, that's ok
            pass
        
        # User accounts table for access control
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                full_name TEXT,
                email TEXT,
                is_active INTEGER DEFAULT 1,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Settings change log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                setting_type TEXT,
                setting_key TEXT,
                old_value TEXT,
                new_value TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Initialize default settings if not exist
        cursor.execute("SELECT COUNT(*) FROM business_settings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO business_settings (
                    business_name, business_type, phone, email,
                    timezone, currency, default_charge
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                "JP Enterprise Trades",
                "Physiotherapy Clinic",
                "+353 XX XXX XXXX",
                "info@munsterphysio.ie",
                "Europe/Dublin",
                "EUR",
                50.0
            ))
        
        cursor.execute("SELECT COUNT(*) FROM developer_settings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO developer_settings (
                    openai_model, tts_provider, log_level
                ) VALUES (?, ?, ?)
            """, ("gpt-4o-mini", "deepgram", "INFO"))
        
        conn.commit()
        conn.close()
        print("✅ Settings tables initialized")
    
    def get_business_settings(self) -> Dict[str, Any]:
        """Get current business settings"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get actual column names from database
        cursor.execute("PRAGMA table_info(business_settings)")
        db_columns = [col[1] for col in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM business_settings ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {}
        
        settings = dict(zip(db_columns, row))
        
        # Map database column names to frontend field names
        if 'phone' in settings:
            settings['business_phone'] = settings.get('phone')
        if 'email' in settings:
            settings['business_email'] = settings.get('email')
        if 'address' in settings:
            settings['business_address'] = settings.get('address')
        
        # Parse JSON fields
        if settings.get('days_open'):
            try:
                settings['days_open'] = json.loads(settings['days_open'])
            except:
                settings['days_open'] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        
        if settings.get('services'):
            try:
                settings['services'] = json.loads(settings['services'])
            except:
                settings['services'] = []
        
        if settings.get('payment_methods'):
            try:
                settings['payment_methods'] = json.loads(settings['payment_methods'])
            except:
                settings['payment_methods'] = ["cash", "card", "Apple Pay"]
        
        return settings
    
    def update_business_settings(self, settings: Dict[str, Any], user_id: Optional[int] = None) -> bool:
        """Update business settings"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get old settings for logging
        old_settings = self.get_business_settings()
        
        # Map frontend field names to database column names
        field_mapping = {
            'business_phone': 'phone',
            'business_email': 'email',
            'business_address': 'address',
        }
        
        # Create a new dict with mapped field names
        mapped_settings = {}
        for key, value in settings.items():
            mapped_key = field_mapping.get(key, key)
            mapped_settings[mapped_key] = value
        
        settings = mapped_settings
        
        # Convert lists to JSON strings
        if 'days_open' in settings and isinstance(settings['days_open'], list):
            settings['days_open'] = json.dumps(settings['days_open'])
        if 'services' in settings and isinstance(settings['services'], list):
            settings['services'] = json.dumps(settings['services'])
        if 'payment_methods' in settings and isinstance(settings['payment_methods'], list):
            settings['payment_methods'] = json.dumps(settings['payment_methods'])
        
        # Valid database columns
        valid_columns = [
            'business_name', 'business_type', 'phone', 'email', 'website',
            'address', 'city', 'country', 'timezone', 'currency', 'default_charge',
            'appointment_duration', 'opening_hours_start', 'opening_hours_end',
            'days_open', 'max_booking_days_ahead', 'allow_weekend_booking',
            'services', 'payment_methods', 'cancellation_policy',
            'reminder_hours_before', 'auto_confirm_bookings', 'fallback_phone_number',
            'logo_url'
        ]
        
        # Build update query
        update_fields = []
        values = []
        for key, value in settings.items():
            if key not in ['id', 'created_at', 'updated_at'] and key in valid_columns:
                update_fields.append(f"{key} = ?")
                values.append(value)
        
        if not update_fields:
            conn.close()
            return False
        
        values.append(datetime.now().isoformat())
        update_query = f"""
            UPDATE business_settings 
            SET {', '.join(update_fields)}, updated_at = ?
            WHERE id = (SELECT MAX(id) FROM business_settings)
        """
        
        cursor.execute(update_query, values)
        
        # Log changes
        for key, new_value in settings.items():
            if key in old_settings and old_settings[key] != new_value:
                cursor.execute("""
                    INSERT INTO settings_log 
                    (user_id, setting_type, setting_key, old_value, new_value)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, 'business', key, str(old_settings[key]), str(new_value)))
        
        conn.commit()
        conn.close()
        return True
    
    def get_developer_settings(self) -> Dict[str, Any]:
        """Get current developer settings"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM developer_settings ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {}
        
        columns = [
            'id', 'openai_model', 'openai_temperature', 'openai_max_tokens',
            'deepgram_model', 'tts_provider', 'elevenlabs_voice_id',
            'webhook_url', 'webhook_secret', 'log_level', 'enable_call_recording',
            'enable_analytics', 'max_concurrent_calls', 'session_timeout_minutes',
            'enable_maintenance_mode', 'maintenance_message', 'rate_limit_per_minute',
            'enable_debug_mode', 'created_at', 'updated_at'
        ]
        
        return dict(zip(columns, row))
    
    def update_developer_settings(self, settings: Dict[str, Any], user_id: Optional[int] = None) -> bool:
        """Update developer settings"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get old settings for logging
        old_settings = self.get_developer_settings()
        
        # Build update query
        update_fields = []
        values = []
        for key, value in settings.items():
            if key not in ['id', 'created_at', 'updated_at']:
                update_fields.append(f"{key} = ?")
                values.append(value)
        
        if not update_fields:
            conn.close()
            return False
        
        values.append(datetime.now().isoformat())
        update_query = f"""
            UPDATE developer_settings 
            SET {', '.join(update_fields)}, updated_at = ?
            WHERE id = (SELECT MAX(id) FROM developer_settings)
        """
        
        cursor.execute(update_query, values)
        
        # Log changes
        for key, new_value in settings.items():
            if key in old_settings and old_settings[key] != new_value:
                cursor.execute("""
                    INSERT INTO settings_log 
                    (user_id, setting_type, setting_key, old_value, new_value)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, 'developer', key, str(old_settings[key]), str(new_value)))
        
        conn.commit()
        conn.close()
        return True
    
    def get_settings_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get settings change history"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT sl.*, u.username, u.full_name
            FROM settings_log sl
            LEFT JOIN users u ON sl.user_id = u.id
            ORDER BY sl.changed_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        columns = [
            'id', 'user_id', 'setting_type', 'setting_key', 'old_value',
            'new_value', 'changed_at', 'username', 'full_name'
        ]
        
        return [dict(zip(columns, row)) for row in rows]
    
    # ======= Services/Menu Management =======
    
    def get_services_menu(self) -> Dict[str, Any]:
        """Get services menu from JSON file"""
        try:
            with open(self.services_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            # Return default structure
            return {
                "business_name": "JP Enterprise Trades",
                "business_hours": {
                    "start_hour": 9,
                    "end_hour": 17,
                    "days_open": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                },
                "services": [],
                "pricing_notes": {}
            }
    
    def update_services_menu(self, menu_data: Dict[str, Any]) -> bool:
        """Update services menu JSON file"""
        try:
            menu_data['last_updated'] = datetime.now().isoformat()
            with open(self.services_path, 'w', encoding='utf-8') as f:
                json.dump(menu_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error updating services menu: {e}")
            return False
    
    def add_service(self, service: Dict[str, Any]) -> bool:
        """Add a new service to the menu"""
        menu = self.get_services_menu()
        if 'services' not in menu:
            menu['services'] = []
        menu['services'].append(service)
        return self.update_services_menu(menu)
    
    def update_service(self, service_id: str, service_data: Dict[str, Any]) -> bool:
        """Update an existing service"""
        menu = self.get_services_menu()
        for i, service in enumerate(menu.get('services', [])):
            if service.get('id') == service_id:
                menu['services'][i] = {**service, **service_data}
                return self.update_services_menu(menu)
        return False
    
    def delete_service(self, service_id: str) -> bool:
        """Delete a service from the menu"""
        menu = self.get_services_menu()
        original_count = len(menu.get('services', []))
        menu['services'] = [s for s in menu.get('services', []) if s.get('id') != service_id]
        if len(menu['services']) < original_count:
            return self.update_services_menu(menu)
        return False
    
    def update_business_hours(self, hours_data: Dict[str, Any]) -> bool:
        """Update business hours in services menu"""
        menu = self.get_services_menu()
        if 'business_hours' not in menu:
            menu['business_hours'] = {}
        menu['business_hours'].update(hours_data)
        return self.update_services_menu(menu)
    
    def is_ai_receptionist_enabled(self) -> bool:
        """Check if AI receptionist is enabled"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT ai_receptionist_enabled FROM developer_settings LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            return bool(result[0]) if result else True  # Default to enabled
        except Exception as e:
            print(f"Error checking AI receptionist status: {e}")
            return True  # Default to enabled on error
    
    def set_ai_receptionist_enabled(self, enabled: bool) -> bool:
        """Enable or disable AI receptionist"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Ensure at least one row exists
            cursor.execute("SELECT COUNT(*) FROM developer_settings")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO developer_settings (
                        openai_model, tts_provider, log_level, ai_receptionist_enabled
                    ) VALUES (?, ?, ?, ?)
                """, ("gpt-4o-mini", "deepgram", "INFO", 1 if enabled else 0))
            else:
                cursor.execute("""
                    UPDATE developer_settings 
                    SET ai_receptionist_enabled = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = (SELECT MIN(id) FROM developer_settings)
                """, (1 if enabled else 0,))
            
            conn.commit()
            conn.close()
            print(f"✅ AI Receptionist {'enabled' if enabled else 'disabled'}")
            return True
        except Exception as e:
            print(f"Error updating AI receptionist status: {e}")
            return False
    
    def get_fallback_phone_number(self) -> Optional[str]:
        """Get fallback phone number for when AI is disabled"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT fallback_phone_number FROM developer_settings LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            return result[0] if result and result[0] else None
        except Exception as e:
            print(f"Error getting fallback phone number: {e}")
            return None
    
    def set_fallback_phone_number(self, phone: str) -> bool:
        """Set fallback phone number for when AI is disabled"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Ensure at least one row exists
            cursor.execute("SELECT COUNT(*) FROM developer_settings")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO developer_settings (
                        openai_model, tts_provider, log_level, fallback_phone_number
                    ) VALUES (?, ?, ?, ?)
                """, ("gpt-4o-mini", "deepgram", "INFO", phone))
            else:
                cursor.execute("""
                    UPDATE developer_settings 
                    SET fallback_phone_number = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = (SELECT MIN(id) FROM developer_settings)
                """, (phone,))
            
            conn.commit()
            conn.close()
            print(f"✅ Fallback phone number set to: {phone}")
            return True
        except Exception as e:
            print(f"Error setting fallback phone number: {e}")
            return False


# Singleton instance
_settings_manager = None

def get_settings_manager() -> SettingsManager:
    """Get settings manager singleton"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
