"""Delete base64 images from database"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.database import get_database

def delete_base64_images():
    """Delete all base64 images from database"""
    print("=" * 70)
    print("DELETING BASE64 IMAGES FROM DATABASE")
    print("=" * 70)
    
    db = get_database()
    deleted_count = 0
    
    # Delete from services
    print("\n1️⃣ Checking Services...")
    services = db.get_all_services(active_only=False)
    
    for service in services:
        if service.get('image_url') and service['image_url'].startswith('data:image/'):
            service_id = service['id']
            service_name = service['name']
            print(f"   Deleting image from: {service_name}")
            db.update_service(service_id, image_url='')
            deleted_count += 1
    
    # Delete from workers
    print("\n2️⃣ Checking Workers...")
    workers = db.get_all_workers()
    
    for worker in workers:
        if worker.get('image_url') and worker['image_url'].startswith('data:image/'):
            worker_id = worker['id']
            worker_name = worker['name']
            print(f"   Deleting image from: {worker_name}")
            db.update_worker(worker_id, image_url='')
            deleted_count += 1
    
    # Delete from companies
    print("\n3️⃣ Checking Companies...")
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, company_name, logo_url FROM companies WHERE logo_url LIKE 'data:image/%'")
        companies = cursor.fetchall()
        
        for company in companies:
            company_id, name, logo_url = company
            print(f"   Deleting logo from: {name}")
            cursor.execute("UPDATE companies SET logo_url = '' WHERE id = ?", (company_id,))
            deleted_count += 1
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"   ⚠️ Error checking companies: {e}")
    
    print("\n" + "=" * 70)
    print(f"✅ DELETED {deleted_count} BASE64 IMAGES FROM DATABASE")
    print("=" * 70)

if __name__ == "__main__":
    delete_base64_images()
