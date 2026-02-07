"""Check for recent image uploads in database and R2"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.database import get_database

# Try to import R2, but don't fail if not available
try:
    from src.services.storage_r2 import get_r2_storage, is_r2_enabled
    R2_AVAILABLE = True
except ImportError:
    R2_AVAILABLE = False

def check_recent_images():
    """Check for images in database and R2"""
    print("=" * 70)
    print("CHECKING FOR IMAGE UPLOADS")
    print("=" * 70)
    
    # Check R2 Configuration
    print("\n📦 R2 Storage Status:")
    print("-" * 70)
    if R2_AVAILABLE:
        if is_r2_enabled():
            print("✅ R2 Storage is ENABLED")
            r2 = get_r2_storage()
            if r2:
                print(f"   Account ID: {r2.account_id}")
                print(f"   Bucket: {r2.bucket_name}")
                print(f"   Public URL: {r2.public_url}")
        else:
            print("❌ R2 Storage is NOT CONFIGURED")
            print("   Images will be stored as base64 in database")
    else:
        print("⚠️ R2 module not available (missing boto3)")
        print("   Images will be stored as base64 in database")
    
    # Check database
    print("\n📊 Database Entries:")
    print("-" * 70)
    db = get_database()
    
    # Check services with images
    print("\n1️⃣ Services with Images:")
    services = db.get_all_services(active_only=False)
    services_with_images = [s for s in services if s.get('image_url')]
    
    if services_with_images:
        for service in services_with_images:
            print(f"\n   Service: {service['name']}")
            image_url = service.get('image_url', '')
            if image_url.startswith('data:image/'):
                print(f"   Storage: BASE64 in database")
                print(f"   Size: ~{len(image_url)} characters")
            elif image_url.startswith('http'):
                print(f"   Storage: R2 (External URL)")
                print(f"   URL: {image_url}")
            else:
                print(f"   Storage: Unknown")
                print(f"   Value: {image_url[:100]}...")
    else:
        print("   No services with images found")
    
    # Check company logos
    print("\n2️⃣ Company Logos:")
    try:
        # Get current company (assumes single company for now)
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, company_name, logo_url FROM companies WHERE logo_url IS NOT NULL AND logo_url != ''")
        companies = cursor.fetchall()
        conn.close()
        
        if companies:
            for company in companies:
                company_id, name, logo_url = company
                print(f"\n   Company: {name} (ID: {company_id})")
                if logo_url.startswith('data:image/'):
                    print(f"   Storage: BASE64 in database")
                    print(f"   Size: ~{len(logo_url)} characters")
                elif logo_url.startswith('http'):
                    print(f"   Storage: R2 (External URL)")
                    print(f"   URL: {logo_url}")
                else:
                    print(f"   Storage: Unknown")
                    print(f"   Value: {logo_url[:100]}...")
        else:
            print("   No companies with logos found")
    except Exception as e:
        print(f"   ⚠️ Error checking companies: {e}")
    
    # Check workers with images
    print("\n3️⃣ Workers with Images:")
    try:
        workers = db.get_all_workers()
        workers_with_images = [w for w in workers if w.get('image_url')]
        
        if workers_with_images:
            for worker in workers_with_images:
                print(f"\n   Worker: {worker['name']}")
                image_url = worker.get('image_url', '')
                if image_url.startswith('data:image/'):
                    print(f"   Storage: BASE64 in database")
                    print(f"   Size: ~{len(image_url)} characters")
                elif image_url.startswith('http'):
                    print(f"   Storage: R2 (External URL)")
                    print(f"   URL: {image_url}")
                else:
                    print(f"   Storage: Unknown")
                    print(f"   Value: {image_url[:100]}...")
        else:
            print("   No workers with images found")
    except Exception as e:
        print(f"   ⚠️ Error checking workers: {e}")
    
    print("\n" + "=" * 70)
    print("CHECK COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    check_recent_images()
