"""
Import Services from JSON to Database
Migrates services from config/services_menu.json to database
Make sure DATABASE_URL is set in your .env file for production
Usage: python db_scripts/import_services_to_db.py
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.database import get_database


def import_services_from_json():
    """Import services from JSON file to database"""
    
    # Path to JSON file (config folder is in project root)
    project_root = Path(__file__).parent.parent
    json_path = project_root / 'config' / 'services_menu.json'
    
    if not json_path.exists():
        print(f"❌ Services JSON file not found: {json_path}")
        return False
    
    print(f"📂 Reading services from: {json_path}")
    
    # Load JSON data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    services = data.get('services', [])
    print(f"📋 Found {len(services)} services in JSON file")
    
    if not services:
        print("⚠️  No services to import")
        return True
    
    # Get database
    db = get_database()
    
    # Import each service
    imported = 0
    skipped = 0
    errors = 0
    
    for idx, service in enumerate(services, 1):
        service_id = service.get('id')
        service_name = service.get('name', f'Service {idx}')
        
        print(f"\n[{idx}/{len(services)}] Processing: {service_name}")
        
        # Check if service already exists
        existing = db.get_service(service_id) if service_id else None
        if existing:
            print(f"  ⏭️  Already exists, skipping")
            skipped += 1
            continue
        
        try:
            # Add service to database
            success = db.add_service(
                service_id=service_id or f"service_{int(datetime.now().timestamp() * 1000)}_{idx}",
                category=service.get('category', 'General'),
                name=service_name,
                description=service.get('description', ''),
                duration_minutes=service.get('duration_minutes', 60),
                price=float(service.get('price', 0)),
                emergency_price=float(service.get('emergency_price')) if service.get('emergency_price') else None,
                currency=service.get('currency', 'EUR'),
                active=True,
                image_url=service.get('image_url', ''),
                sort_order=idx
            )
            
            if success:
                print(f"  ✅ Imported successfully")
                imported += 1
            else:
                print(f"  ❌ Failed to import")
                errors += 1
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            errors += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 Import Summary:")
    print(f"   ✅ Imported: {imported}")
    print(f"   ⏭️  Skipped (already exists): {skipped}")
    print(f"   ❌ Errors: {errors}")
    print(f"   📋 Total: {len(services)}")
    print(f"{'='*60}")
    
    return errors == 0


def verify_import():
    """Verify services were imported correctly"""
    db = get_database()
    services = db.get_all_services(active_only=False)
    
    print(f"\n🔍 Verification:")
    print(f"   Database now contains {len(services)} services")
    
    if services:
        print(f"\n📋 Services in database:")
        for idx, service in enumerate(services, 1):
            print(f"   {idx}. {service.get('name')} ({service.get('category')}) - €{service.get('price')}")
    
    return True


if __name__ == "__main__":
    print("="*60)
    print("🔄 Services Migration: JSON → Database")
    print("="*60)
    
    # Check if DATABASE_URL is set (for production)
    if os.getenv('DATABASE_URL') or os.getenv('SUPABASE_DB_URL'):
        print("\n⚠️  Production database detected!")
        print("   This will import services to your PostgreSQL database.")
        response = input("   Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Migration cancelled")
            sys.exit(0)
    
    # Run import
    success = import_services_from_json()
    
    if success:
        # Verify import
        verify_import()
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration completed with errors")
        sys.exit(1)
