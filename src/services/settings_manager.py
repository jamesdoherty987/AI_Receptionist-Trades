"""
Settings Manager for AI Receptionist  
Manages both business and developer settings using PostgreSQL
"""
import json
from datetime import datetime
from typing import Dict, Any, Optional, List


class SettingsManager:
    """Manage application settings"""
    
    def __init__(self):
        """Initialize settings manager using PostgreSQL"""
        self.init_settings_tables()
    
    def init_settings_tables(self):
        """Initialize settings tables"""
        # Settings tables are now part of main database schema
        # They are created in database.py or db_postgres_wrapper.py
        # This method exists for backwards compatibility
        from src.services.database import get_database
        db = get_database()
        
        # Just ensure database is initialized
        # The tables will be created automatically
        print("✅ Settings tables initialized")
    
    def get_business_settings(self) -> Dict[str, Any]:
        """Get current business settings"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            conn = db.get_connection()
            
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM business_settings ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            db.return_connection(conn)
            
            if not row:
                return {}
            
            settings = dict(row)
            
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
                    if isinstance(settings['days_open'], str):
                        settings['days_open'] = json.loads(settings['days_open'])
                except:
                    settings['days_open'] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            
            if settings.get('services'):
                try:
                    if isinstance(settings['services'], str):
                        settings['services'] = json.loads(settings['services'])
                except:
                    settings['services'] = []
            
            if settings.get('payment_methods'):
                try:
                    if isinstance(settings['payment_methods'], str):
                        settings['payment_methods'] = json.loads(settings['payment_methods'])
                except:
                    settings['payment_methods'] = ["cash", "card", "Apple Pay"]
            
            return settings
            
        except Exception as e:
            print(f"Error getting business settings: {e}")
            return {}
    
    def update_business_settings(self, settings: Dict[str, Any], user_id: Optional[int] = None) -> bool:
        """Update business settings"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            conn = db.get_connection()
            
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
                'logo_url', 'business_hours'
            ]
            
            # Build update query
            update_fields = []
            values = []
            for key, value in settings.items():
                if key not in ['id', 'created_at', 'updated_at'] and key in valid_columns:
                    update_fields.append(f"{key} = %s")
                    values.append(value)
            
            if not update_fields:
                db.return_connection(conn)
                return False
            
            values.append(datetime.now().isoformat())
            
            cursor = conn.cursor()
            update_query = f"""
                UPDATE business_settings 
                SET {', '.join(update_fields)}, updated_at = %s
                WHERE id = (SELECT MAX(id) FROM business_settings)
            """
            
            cursor.execute(update_query, values)
            conn.commit()
            
            db.return_connection(conn)
            
            return True
            
        except Exception as e:
            print(f"Error updating business settings: {e}")
            return False
    
    def get_developer_settings(self) -> Dict[str, Any]:
        """Get current developer settings"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            conn = db.get_connection()
            
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM developer_settings ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            db.return_connection(conn)
            
            return dict(row) if row else {}
                
        except Exception as e:
            print(f"Error getting developer settings: {e}")
            return {}
    
    def update_developer_settings(self, settings: Dict[str, Any], user_id: Optional[int] = None) -> bool:
        """Update developer settings"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # Build update query
            update_fields = []
            values = []
            for key, value in settings.items():
                if key not in ['id', 'created_at', 'updated_at']:
                    update_fields.append(f"{key} = %s")
                    values.append(value)
            
            if not update_fields:
                db.return_connection(conn)
                return False
            
            values.append(datetime.now().isoformat())
            
            update_query = f"""
                UPDATE developer_settings 
                SET {', '.join(update_fields)}, updated_at = %s
                WHERE id = (SELECT MAX(id) FROM developer_settings)
            """
            
            cursor.execute(update_query, values)
            conn.commit()
            
            db.return_connection(conn)
            
            return True
            
        except Exception as e:
            print(f"Error updating developer settings: {e}")
            return False
    
    def get_settings_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get settings change history"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            conn = db.get_connection()
            
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT sl.*, u.username, u.full_name
                FROM settings_log sl
                LEFT JOIN users u ON sl.user_id = u.id
                ORDER BY sl.changed_at DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
            db.return_connection(conn)
            return [dict(row) for row in rows]
                
        except Exception as e:
            print(f"Error getting settings history: {e}")
            return []
    
    # ======= Services/Menu Management =======
    
    def get_services_menu(self) -> Dict[str, Any]:
        """Get services menu from database"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            services = db.get_all_services(active_only=True)
            business_settings = self.get_business_settings()
            
            # Return format compatible with old JSON structure
            return {
                "business_name": business_settings.get('business_name', 'Your Business'),
                "business_hours": {
                    "start_hour": business_settings.get('opening_hours_start', 9),
                    "end_hour": business_settings.get('opening_hours_end', 17),
                    "days_open": business_settings.get('days_open', ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
                },
                "services": services,
                "pricing_notes": {}
            }
        except Exception as e:
            print(f"Error getting services from database: {e}")
            # Return default structure
            return {
                "business_name": "Your Business",
                "business_hours": {
                    "start_hour": 9,
                    "end_hour": 17,
                    "days_open": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                },
                "services": [],
                "pricing_notes": {}
            }
    
    def update_services_menu(self, menu_data: Dict[str, Any]) -> bool:
        """Update services menu in database (deprecated - use database methods directly)"""
        print("⚠️ update_services_menu is deprecated - use database.add_service() or database.update_service()")
        return False
    
    def add_service(self, service: Dict[str, Any]) -> bool:
        """Add a new service to the database"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            return db.add_service(
                service_id=service.get('id', f"service_{datetime.now().timestamp()}"),
                category=service.get('category', 'General'),
                name=service['name'],
                description=service.get('description'),
                duration_minutes=service.get('duration_minutes', 60),
                price=service.get('price', 0),
                emergency_price=service.get('emergency_price'),
                currency=service.get('currency', 'EUR'),
                active=service.get('active', True),
                image_url=service.get('image_url'),
                sort_order=service.get('sort_order', 0)
            )
        except Exception as e:
            print(f"Error adding service: {e}")
            return False
    
    def update_service(self, service_id: str, service_data: Dict[str, Any]) -> bool:
        """Update an existing service"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            return db.update_service(service_id, **service_data)
        except Exception as e:
            print(f"Error updating service: {e}")
            return False
    
    def delete_service(self, service_id: str) -> bool:
        """Delete a service from the database"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            return db.delete_service(service_id)
        except Exception as e:
            print(f"Error deleting service: {e}")
            return False
    
    def update_business_hours(self, hours_data: Dict[str, Any]) -> bool:
        """Update business hours in business settings"""
        return self.update_business_settings(hours_data)
    
    def is_ai_receptionist_enabled(self) -> bool:
        """Check if AI receptionist is enabled"""
        try:
            settings = self.get_developer_settings()
            return bool(settings.get('ai_receptionist_enabled', 1))
        except Exception as e:
            print(f"Error checking AI receptionist status: {e}")
            return True  # Default to enabled on error
    
    def set_ai_receptionist_enabled(self, enabled: bool) -> bool:
        """Enable or disable AI receptionist"""
        try:
            success = self.update_developer_settings({'ai_receptionist_enabled': 1 if enabled else 0})
            if success:
                print(f"✅ AI Receptionist {'enabled' if enabled else 'disabled'}")
            return success
        except Exception as e:
            print(f"Error updating AI receptionist status: {e}")
            return False
    
    def get_fallback_phone_number(self) -> Optional[str]:
        """Get business phone number for transfers and when AI is disabled"""
        try:
            settings = self.get_business_settings()
            phone = settings.get('phone')
            if phone:
                # Return phone as-is if it already has country code
                if phone.startswith('+'):
                    return phone
                # Otherwise add country code from settings, default to Ireland
                country_code = settings.get('country_code', '+353')
                return f"{country_code}{phone.lstrip('0')}"
            return None
        except Exception as e:
            print(f"Error getting business phone number: {e}")
            return None
    
    def set_fallback_phone_number(self, phone: str) -> bool:
        """Deprecated: Use business phone instead. This method is kept for backwards compatibility."""
        print(f"⚠️ set_fallback_phone_number is deprecated. Business phone is now used for transfers.")
        print(f"   Update the business phone in business settings instead.")
        return False
    
    def get_services(self) -> List[Dict[str, Any]]:
        """Get all services from database"""
        from src.services.database import get_database
        db = get_database()
        try:
            return db.get_all_services(active_only=True)
        except Exception as e:
            print(f"Error getting services: {e}")
            return []
    
    def get_service_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get service by name from database"""
        services = self.get_services()
        for service in services:
            if service.get('name', '').lower() == name.lower():
                return service
        return None
    
    def get_service_by_id(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get service by ID from database"""
        from src.services.database import get_database
        db = get_database()
        try:
            return db.get_service(service_id)
        except Exception as e:
            print(f"Error getting service: {e}")
            return None
    
    def get_business_hours(self) -> Dict[str, Any]:
        """Get business hours from business settings"""
        settings = self.get_business_settings()
        return {
            "start_hour": settings.get('opening_hours_start', 9),
            "end_hour": settings.get('opening_hours_end', 17),
            "days_open": settings.get('days_open', ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
        }


# Singleton instance
_settings_manager = None

def get_settings_manager() -> SettingsManager:
    """Get settings manager singleton"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
