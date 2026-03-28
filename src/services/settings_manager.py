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
        print("[SUCCESS] Settings tables initialized")
    
    def get_business_settings(self, company_id: int = None) -> Dict[str, Any]:
        """Get current business settings for a specific company"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            conn = db.get_connection()
            
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if company_id:
                cursor.execute("SELECT * FROM business_settings WHERE company_id = %s ORDER BY id DESC LIMIT 1", (company_id,))
            else:
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
    
    def update_business_settings(self, settings: Dict[str, Any], company_id: int = None, user_id: Optional[int] = None) -> bool:
        """Update business settings for a specific company"""
        from src.services.database import get_database
        db = get_database()
        import traceback
        import sys
        try:
            sys.stdout.write(f"[SETTINGS_MANAGER] update_business_settings called with: {settings}\n")
            conn = db.get_connection()
            old_settings = self.get_business_settings(company_id=company_id)
            sys.stdout.write(f"[SETTINGS_MANAGER] old_settings: {old_settings}\n")
            field_mapping = {
                'business_phone': 'phone',
                'business_email': 'email',
                'business_address': 'address',
            }
            mapped_settings = {}
            for key, value in settings.items():
                mapped_key = field_mapping.get(key, key)
                mapped_settings[mapped_key] = value
            settings = mapped_settings
            if 'days_open' in settings and isinstance(settings['days_open'], list):
                settings['days_open'] = json.dumps(settings['days_open'])
            if 'services' in settings and isinstance(settings['services'], list):
                settings['services'] = json.dumps(settings['services'])
            if 'payment_methods' in settings and isinstance(settings['payment_methods'], list):
                settings['payment_methods'] = json.dumps(settings['payment_methods'])
            valid_columns = [
                'business_name', 'business_type', 'phone', 'email', 'website',
                'address', 'city', 'country', 'timezone', 'currency', 'default_charge',
                'appointment_duration', 'opening_hours_start', 'opening_hours_end',
                'days_open', 'max_booking_days_ahead', 'allow_weekend_booking',
                'services', 'payment_methods', 'cancellation_policy',
                'reminder_hours_before', 'auto_confirm_bookings', 'fallback_phone_number',
                'logo_url', 'business_hours',
                'bank_iban', 'bank_bic', 'bank_name', 'bank_account_holder',
                'revolut_phone', 'buffer_time_minutes', 'default_duration_minutes'
            ]
            update_fields = []
            values = []
            for key, value in settings.items():
                if key not in ['id', 'created_at', 'updated_at', 'company_id'] and key in valid_columns:
                    update_fields.append(f"{key} = %s")
                    values.append(value)
            sys.stdout.write(f"[SETTINGS_MANAGER] update_fields: {update_fields}\n")
            sys.stdout.write(f"[SETTINGS_MANAGER] values: {values}\n")
            if not update_fields:
                db.return_connection(conn)
                sys.stdout.write("[SETTINGS_MANAGER] No update fields found.\n")
                return False
            values.append(datetime.now().isoformat())
            cursor = conn.cursor()
            
            if company_id:
                # Check if settings exist for this company
                cursor.execute("SELECT id FROM business_settings WHERE company_id = %s", (company_id,))
                existing = cursor.fetchone()
                
                if existing:
                    values.append(company_id)
                    update_query = f"""
                        UPDATE business_settings 
                        SET {', '.join(update_fields)}, updated_at = %s
                        WHERE company_id = %s
                    """
                else:
                    # Insert new settings for this company
                    insert_fields = [f.split(' = ')[0] for f in update_fields]
                    insert_fields.append('updated_at')
                    insert_fields.append('company_id')
                    values.append(company_id)
                    placeholders = ', '.join(['%s'] * len(values))
                    update_query = f"""
                        INSERT INTO business_settings ({', '.join(insert_fields)})
                        VALUES ({placeholders})
                    """
            else:
                update_query = f"""
                    UPDATE business_settings 
                    SET {', '.join(update_fields)}, updated_at = %s
                    WHERE id = (SELECT MAX(id) FROM business_settings)
                """
            sys.stdout.write(f"[SETTINGS_MANAGER] update_query: {update_query}\n")
            try:
                cursor.execute(update_query, values)
                conn.commit()
                sys.stdout.write("[SETTINGS_MANAGER] Update committed successfully.\n")
            except Exception as sql_e:
                conn.rollback()
                sys.stdout.write(f"[SETTINGS_MANAGER] SQL error: {sql_e}\n")
                traceback.print_exc()
                db.return_connection(conn)
                return False
            db.return_connection(conn)
            return True
        except Exception as e:
            sys.stdout.write(f"[SETTINGS_MANAGER] Exception: {e}\n")
            traceback.print_exc()
            return False
    
    def get_developer_settings(self, company_id: int = None) -> Dict[str, Any]:
        """Get current developer settings for a specific company"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            conn = db.get_connection()
            
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if company_id:
                cursor.execute("SELECT * FROM developer_settings WHERE company_id = %s ORDER BY id DESC LIMIT 1", (company_id,))
            else:
                cursor.execute("SELECT * FROM developer_settings ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            db.return_connection(conn)
            
            return dict(row) if row else {}
                
        except Exception as e:
            print(f"Error getting developer settings: {e}")
            return {}
    
    def update_developer_settings(self, settings: Dict[str, Any], company_id: int = None, user_id: Optional[int] = None) -> bool:
        """Update developer settings for a specific company"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # Build update query
            update_fields = []
            values = []
            for key, value in settings.items():
                if key not in ['id', 'created_at', 'updated_at', 'company_id']:
                    update_fields.append(f"{key} = %s")
                    values.append(value)
            
            if not update_fields:
                db.return_connection(conn)
                return False
            
            values.append(datetime.now().isoformat())
            
            if company_id:
                # Check if settings exist for this company
                cursor.execute("SELECT id FROM developer_settings WHERE company_id = %s", (company_id,))
                existing = cursor.fetchone()
                
                if existing:
                    values.append(company_id)
                    update_query = f"""
                        UPDATE developer_settings 
                        SET {', '.join(update_fields)}, updated_at = %s
                        WHERE company_id = %s
                    """
                else:
                    # Insert new settings for this company
                    insert_fields = [f.split(' = ')[0] for f in update_fields]
                    insert_fields.append('updated_at')
                    insert_fields.append('company_id')
                    values.append(company_id)
                    placeholders = ', '.join(['%s'] * len(values))
                    update_query = f"""
                        INSERT INTO developer_settings ({', '.join(insert_fields)})
                        VALUES ({placeholders})
                    """
            else:
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
    
    def get_services_menu(self, company_id: int = None) -> Dict[str, Any]:
        """Get services menu from database for a specific company"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            services = db.get_all_services(active_only=True, company_id=company_id)
            business_settings = self.get_business_settings(company_id=company_id)
            
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
    
    def update_services_menu(self, menu_data: Dict[str, Any], company_id: int = None) -> bool:
        """Update services menu in database (deprecated - use database methods directly)"""
        print("[WARNING] update_services_menu is deprecated - use database.add_service() or database.update_service()")
        return False
    
    def add_service(self, service: Dict[str, Any], company_id: int = None) -> bool:
        """Add a new service to the database for a specific company"""
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
                price_max=service.get('price_max'),
                emergency_price=service.get('emergency_price'),
                currency=service.get('currency', 'EUR'),
                active=service.get('active', True),
                image_url=service.get('image_url'),
                sort_order=service.get('sort_order', 0),
                workers_required=service.get('workers_required', 1),
                worker_restrictions=service.get('worker_restrictions'),
                requires_callout=service.get('requires_callout', False),
                company_id=company_id
            )
        except Exception as e:
            print(f"Error adding service: {e}")
            return False
    
    def update_service(self, service_id: str, service_data: Dict[str, Any], company_id: int = None) -> bool:
        """Update an existing service for a specific company"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            # Remove company_id from service_data if present to avoid duplicate keyword argument
            clean_data = {k: v for k, v in service_data.items() if k != 'company_id'}
            return db.update_service(service_id, company_id=company_id, **clean_data)
        except Exception as e:
            print(f"Error updating service: {e}")
            return False
    
    def delete_service(self, service_id: str, company_id: int = None) -> dict:
        """Delete a service from the database for a specific company"""
        from src.services.database import get_database
        db = get_database()
        
        try:
            return db.delete_service(service_id, company_id=company_id)
        except Exception as e:
            print(f"Error deleting service: {e}")
            return {"success": False, "error": str(e), "jobs_affected": 0}
    
    def update_business_hours(self, hours_data: Dict[str, Any], company_id: int = None) -> bool:
        """Update business hours in business settings for a specific company"""
        return self.update_business_settings(hours_data, company_id=company_id)
    
    def is_ai_receptionist_enabled(self, company_id: int = None) -> bool:
        """Check if AI receptionist is enabled for a specific company"""
        try:
            settings = self.get_developer_settings(company_id=company_id)
            return bool(settings.get('ai_receptionist_enabled', 1))
        except Exception as e:
            print(f"Error checking AI receptionist status: {e}")
            return True  # Default to enabled on error
    
    def set_ai_receptionist_enabled(self, enabled: bool, company_id: int = None) -> bool:
        """Enable or disable AI receptionist for a specific company"""
        try:
            success = self.update_developer_settings({'ai_receptionist_enabled': 1 if enabled else 0}, company_id=company_id)
            if success:
                print(f"[SUCCESS] AI Receptionist {'enabled' if enabled else 'disabled'}")
            return success
        except Exception as e:
            print(f"Error updating AI receptionist status: {e}")
            return False
    
    def get_fallback_phone_number(self, company_id: int = None) -> Optional[str]:
        """Get business phone number for transfers and when AI is disabled.
        Reads from companies table (source of truth) with fallback to business_settings."""
        try:
            phone = None
            
            # Primary: check companies table (settings page saves here)
            if company_id:
                from src.services.database import get_database
                db = get_database()
                company = db.get_company(company_id)
                if company:
                    phone = company.get('phone')
            
            # Fallback: check business_settings table (legacy)
            if not phone:
                settings = self.get_business_settings(company_id=company_id)
                phone = settings.get('phone')
            
            if phone:
                phone = phone.strip()
                # Return phone as-is if it already has country code
                if phone.startswith('+'):
                    return phone
                # Otherwise add country code, default to Ireland
                return f"+353{phone.lstrip('0')}"
            return None
        except Exception as e:
            print(f"Error getting business phone number: {e}")
            return None
    
    def set_fallback_phone_number(self, phone: str, company_id: int = None) -> bool:
        """Deprecated: Use business phone instead. This method is kept for backwards compatibility."""
        print(f"[WARNING] set_fallback_phone_number is deprecated. Business phone is now used for transfers.")
        print(f"   Update the business phone in business settings instead.")
        return False
    
    def get_services(self, company_id: int = None) -> List[Dict[str, Any]]:
        """Get all services from database for a specific company"""
        from src.services.database import get_database
        db = get_database()
        try:
            return db.get_all_services(active_only=True, company_id=company_id)
        except Exception as e:
            print(f"Error getting services: {e}")
            return []
    
    def get_service_by_name(self, name: str, company_id: int = None) -> Optional[Dict[str, Any]]:
        """Get service by name from database for a specific company"""
        services = self.get_services(company_id=company_id)
        for service in services:
            if service.get('name', '').lower() == name.lower():
                return service
        return None
    
    def get_service_by_id(self, service_id: str, company_id: int = None) -> Optional[Dict[str, Any]]:
        """Get service by ID from database for a specific company"""
        from src.services.database import get_database
        db = get_database()
        try:
            return db.get_service(service_id, company_id=company_id)
        except Exception as e:
            print(f"Error getting service: {e}")
            return None
    
    def get_business_hours(self, company_id: int = None) -> Dict[str, Any]:
        """Get business hours from business settings for a specific company"""
        from src.utils.config import Config
        
        # First try to get from company's business_hours string
        if company_id:
            try:
                from src.services.database import get_database
                db = get_database()
                company = db.get_company(company_id)
                if company and company.get('business_hours'):
                    parsed = Config.parse_business_hours_string(company['business_hours'])
                    return {
                        "start_hour": parsed['start'],
                        "end_hour": parsed['end'],
                        "days_open": parsed['days_open']
                    }
            except Exception as e:
                print(f"[WARNING] Could not parse company business hours: {e}")
        
        # Fallback to business_settings table
        settings = self.get_business_settings(company_id=company_id)
        
        # Check if there's a business_hours string in settings
        if settings.get('business_hours'):
            parsed = Config.parse_business_hours_string(settings['business_hours'])
            return {
                "start_hour": parsed['start'],
                "end_hour": parsed['end'],
                "days_open": parsed['days_open']
            }
        
        return {
            "start_hour": settings.get('opening_hours_start', 9),
            "end_hour": settings.get('opening_hours_end', 17),
            "days_open": settings.get('days_open', ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
        }
    
    def get_buffer_time_minutes(self, company_id: int = None) -> int:
        """Get buffer time in minutes between appointments for a specific company"""
        settings = self.get_business_settings(company_id=company_id)
        return settings.get('buffer_time_minutes', 15)
    
    def get_default_duration_minutes(self, company_id: int = None) -> int:
        """Get default appointment duration in minutes for a specific company (1 day default for trades)"""
        settings = self.get_business_settings(company_id=company_id)
        return settings.get('default_duration_minutes', 1440)
    
    def get_service_duration(self, service_name: str, company_id: int = None) -> int:
        """Get duration for a specific service by name, with fallback to default"""
        service = self.get_service_by_name(service_name, company_id=company_id)
        if service and service.get('duration_minutes'):
            return service['duration_minutes']
        return self.get_default_duration_minutes(company_id=company_id)
    
    def get_total_booking_duration(self, service_name: str = None, service_duration: int = None, company_id: int = None) -> int:
        """Get total duration for a booking (no buffer time)
        
        Args:
            service_name: Name of the service (optional, used to look up duration)
            service_duration: Explicit duration in minutes (optional, overrides service lookup)
            company_id: Company ID for multi-tenant isolation
            
        Returns:
            Total duration in minutes (service duration only, no buffer)
        """
        if service_duration is not None:
            duration = service_duration
        elif service_name:
            duration = self.get_service_duration(service_name, company_id=company_id)
        else:
            duration = self.get_default_duration_minutes(company_id=company_id)
        
        return duration
    
    # ======= Package Management =======
    
    def get_packages(self, company_id: int = None, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all packages for a company with resolved service details, duration, and price."""
        from src.services.database import get_database
        db = get_database()
        try:
            packages = db.get_all_packages(active_only=active_only, company_id=company_id)
            result = []
            for pkg in packages:
                resolved_services = self.resolve_package_services(pkg, company_id=company_id)
                pkg['services'] = resolved_services
                duration_info = self.calculate_package_duration(pkg, company_id=company_id)
                pkg['total_duration_minutes'] = duration_info['min_minutes']
                pkg['duration_label'] = duration_info['label']
                price_info = self.calculate_package_price(pkg, company_id=company_id)
                pkg['total_price'] = price_info['price']
                pkg['total_price_max'] = price_info['price_max']
                result.append(pkg)
            return result
        except Exception as e:
            print(f"Error getting packages: {e}")
            return []
    
    def get_package_by_id(self, package_id: str, company_id: int = None) -> Optional[Dict[str, Any]]:
        """Get a single package by ID with resolved service details."""
        from src.services.database import get_database
        db = get_database()
        try:
            pkg = db.get_package(package_id, company_id=company_id)
            if not pkg:
                return None
            resolved_services = self.resolve_package_services(pkg, company_id=company_id)
            pkg['services'] = resolved_services
            duration_info = self.calculate_package_duration(pkg, company_id=company_id)
            pkg['total_duration_minutes'] = duration_info['min_minutes']
            pkg['duration_label'] = duration_info['label']
            price_info = self.calculate_package_price(pkg, company_id=company_id)
            pkg['total_price'] = price_info['price']
            pkg['total_price_max'] = price_info['price_max']
            return pkg
        except Exception as e:
            print(f"Error getting package: {e}")
            return None
    
    def resolve_package_services(self, package: Dict[str, Any], company_id: int = None) -> List[Dict[str, Any]]:
        """Resolve JSONB service references to full service objects, ordered by sort_order.
        
        Skips inactive or missing services and logs warnings.
        If fewer than 2 active services remain, marks the package as inactive.
        """
        from src.services.database import get_database
        db = get_database()
        
        services_ref = package.get('services', [])
        if isinstance(services_ref, str):
            services_ref = json.loads(services_ref)
        
        # Sort by sort_order
        sorted_refs = sorted(services_ref, key=lambda s: s.get('sort_order', 0))
        
        resolved = []
        for ref in sorted_refs:
            service_id = ref.get('service_id')
            if not service_id:
                continue
            
            svc = db.get_service(service_id, company_id=company_id)
            if not svc:
                print(f"[WARNING] Package '{package.get('name')}' references missing service: {service_id}")
                continue
            
            # Skip inactive services
            if not svc.get('active', 1):
                print(f"[WARNING] Package '{package.get('name')}' references inactive service: {svc.get('name', service_id)}")
                continue
            
            resolved.append({
                'service_id': service_id,
                'name': svc.get('name', ''),
                'duration_minutes': svc.get('duration_minutes', 0),
                'price': svc.get('price', 0),
                'price_max': svc.get('price_max'),
                'sort_order': ref.get('sort_order', 0),
            })
        
        # If fewer than 2 active services remain, mark package as inactive
        if len(resolved) < 2 and package.get('active', 1):
            pkg_id = package.get('id')
            pkg_company = company_id or package.get('company_id')
            if pkg_id:
                print(f"[WARNING] Package '{package.get('name')}' has fewer than 2 active services ({len(resolved)}), marking inactive")
                try:
                    db.update_package(pkg_id, company_id=pkg_company, active=False)
                except Exception as e:
                    print(f"[ERROR] Failed to auto-deactivate package '{package.get('name')}': {e}")
        
        return resolved
    
    def calculate_package_duration(self, package: Dict[str, Any], company_id: int = None) -> Dict[str, Any]:
        """Calculate total duration from constituent services.
        
        Returns dict with min_minutes, max_minutes, and human-readable label.
        """
        from src.services.calendar_tools import format_duration_label
        
        services = package.get('services', [])
        if isinstance(services, str):
            services = json.loads(services)
        
        min_minutes = 0
        max_minutes = 0
        for svc in services:
            duration = svc.get('duration_minutes', 0)
            min_minutes += duration
            # Use price_max-style logic: if service has a max duration variant, use it
            max_dur = svc.get('duration_max_minutes', duration)
            max_minutes += max_dur
        
        # If max equals min, they're the same
        if max_minutes <= min_minutes:
            max_minutes = min_minutes
        
        label = format_duration_label(min_minutes) if min_minutes > 0 else "unknown"
        
        return {
            'min_minutes': min_minutes,
            'max_minutes': max_minutes,
            'label': label,
        }
    
    def calculate_package_price(self, package: Dict[str, Any], company_id: int = None) -> Dict[str, Any]:
        """Calculate total price, respecting price_override if set.
        
        Returns dict with price and price_max.
        """
        services = package.get('services', [])
        if isinstance(services, str):
            services = json.loads(services)
        
        price_override = package.get('price_override')
        price_max_override = package.get('price_max_override')
        
        if price_override is not None:
            price = price_override
        else:
            price = sum(svc.get('price', 0) for svc in services)
        
        if price_max_override is not None:
            price_max = price_max_override
        else:
            price_max = sum(
                (svc.get('price_max') or svc.get('price', 0))
                for svc in services
            )
        
        return {
            'price': price,
            'price_max': price_max,
        }
    
    def _validate_package_data(self, package_data: Dict[str, Any], company_id: int = None) -> Optional[str]:
        """Validate package data. Returns error message string or None if valid."""
        import json as _json

        # Name validation
        name = package_data.get('name', '')
        if not name or not name.strip():
            return "Package name is required"
        if len(name) > 200:
            return "Package name must be 200 characters or fewer"

        # Services validation
        services = package_data.get('services', [])
        if isinstance(services, str):
            services = _json.loads(services)

        if len(services) < 2:
            return "Package must contain at least 2 services"

        # Check for duplicate service_ids
        service_ids = [s.get('service_id') for s in services]
        if len(service_ids) != len(set(service_ids)):
            return "Package contains duplicate service references"

        # Clarifying question validation (before DB check — no DB needed)
        clarifying_question = package_data.get('clarifying_question')
        if clarifying_question is not None and len(clarifying_question) > 500:
            return "Clarifying question must be 500 characters or fewer"

        # Price override validation (before DB check — no DB needed)
        price_override = package_data.get('price_override')
        if price_override is not None and price_override < 0:
            return "Price override must be non-negative"

        price_max_override = package_data.get('price_max_override')
        if price_max_override is not None and price_max_override < 0:
            return "Price max override must be non-negative"

        # Validate all service_ids exist in the same company (requires DB)
        from src.services.database import get_database
        db = get_database()
        for sid in service_ids:
            svc = db.get_service(sid, company_id=company_id)
            if not svc:
                return f"Service '{sid}' not found in this company"

        return None
    
    def add_package(self, package_data: Dict[str, Any], company_id: int = None) -> Dict[str, Any]:
        """Add a new package with validation.
        
        Returns dict with 'success' bool and optionally 'error' string or 'package_id' string.
        """
        from src.services.database import get_database
        db = get_database()
        
        # Validate
        error = self._validate_package_data(package_data, company_id=company_id)
        if error:
            return {"success": False, "error": error}
        
        # Generate ID
        package_id = f"pkg_{datetime.now().timestamp()}"
        
        services = package_data.get('services', [])
        if isinstance(services, str):
            services = json.loads(services)
        
        try:
            success = db.add_package(
                package_id=package_id,
                company_id=company_id,
                name=package_data['name'].strip(),
                description=package_data.get('description'),
                services=services,
                price_override=package_data.get('price_override'),
                price_max_override=package_data.get('price_max_override'),
                use_when_uncertain=package_data.get('use_when_uncertain', False),
                clarifying_question=package_data.get('clarifying_question'),
                active=package_data.get('active', True),
                image_url=package_data.get('image_url'),
                sort_order=package_data.get('sort_order', 0),
            )
            if success:
                return {"success": True, "package_id": package_id}
            return {"success": False, "error": "Failed to insert package"}
        except Exception as e:
            print(f"Error adding package: {e}")
            return {"success": False, "error": str(e)}
    
    def update_package(self, package_id: str, package_data: Dict[str, Any], company_id: int = None) -> Dict[str, Any]:
        """Update an existing package with validation.
        
        Returns dict with 'success' bool and optionally 'error' string.
        """
        from src.services.database import get_database
        db = get_database()
        
        # Check package exists
        existing = db.get_package(package_id, company_id=company_id)
        if not existing:
            return {"success": False, "error": "Package not found"}
        
        # Merge existing data with updates for validation
        merged = {**existing}
        merged.update(package_data)
        
        # Parse services if needed for validation
        if 'services' in merged and isinstance(merged['services'], str):
            merged['services'] = json.loads(merged['services'])
        
        # Validate merged data
        error = self._validate_package_data(merged, company_id=company_id)
        if error:
            return {"success": False, "error": error}
        
        # Build kwargs for update
        update_kwargs = {}
        allowed = ['name', 'description', 'services', 'price_override', 'price_max_override',
                    'use_when_uncertain', 'clarifying_question', 'active', 'image_url', 'sort_order']
        for key in allowed:
            if key in package_data:
                update_kwargs[key] = package_data[key]
        
        try:
            success = db.update_package(package_id, company_id=company_id, **update_kwargs)
            if success:
                return {"success": True}
            return {"success": False, "error": "No rows updated"}
        except Exception as e:
            print(f"Error updating package: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_package(self, package_id: str, company_id: int = None) -> Dict[str, Any]:
        """Delete a package and return info about affected bookings."""
        from src.services.database import get_database
        db = get_database()
        
        try:
            return db.delete_package(package_id, company_id=company_id)
        except Exception as e:
            print(f"Error deleting package: {e}")
            return {"success": False, "error": str(e), "jobs_affected": 0}


# Singleton instance
_settings_manager = None

def get_settings_manager() -> SettingsManager:
    """Get settings manager singleton"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
