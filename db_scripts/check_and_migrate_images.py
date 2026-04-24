#!/usr/bin/env python3
"""
Check for base64-encoded images in database and optionally migrate them to R2
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from src.services.database import get_database
from src.services.storage_r2 import upload_company_file, is_r2_enabled
import base64
import io

def check_database_for_base64_images():
    """Check database for base64-encoded images"""
    load_dotenv()
    
    print("🔍 Checking database for base64-encoded images...")
    print("-" * 50)
    
    db = get_database()
    
    # Check companies table for logo_url
    try:
        conn = db.get_connection()
        
        # Handle both PostgreSQL and SQLite
        if hasattr(db, 'use_postgres') and db.use_postgres:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT id, company_name, logo_url FROM companies WHERE logo_url IS NOT NULL")
            companies = cursor.fetchall()
            db.return_connection(conn)
        else:
            conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
            cursor = conn.cursor()
            cursor.execute("SELECT id, company_name, logo_url FROM companies WHERE logo_url IS NOT NULL")
            companies = cursor.fetchall()
            conn.close()
        
        base64_count = 0
        url_count = 0
        companies_with_base64 = []
        
        for company in companies:
            if company['logo_url']:
                if company['logo_url'].startswith('data:image/'):
                    base64_count += 1
                    # Get size estimate
                    size_kb = len(company['logo_url']) / 1024
                    companies_with_base64.append({
                        'id': company['id'],
                        'name': company['company_name'],
                        'size_kb': size_kb
                    })
                elif company['logo_url'].startswith('http'):
                    url_count += 1
        
        print(f"\n📊 Summary:")
        print(f"   Total companies with logos: {len(companies)}")
        print(f"   ✅ Already using URLs: {url_count}")
        print(f"   ⚠️  Using base64 (in database): {base64_count}")
        
        if base64_count > 0:
            print(f"\n📋 Companies with base64 images:")
            total_size = 0
            for comp in companies_with_base64:
                print(f"   - Company ID {comp['id']}: {comp['name']}")
                print(f"     Size: {comp['size_kb']:.2f} KB")
                total_size += comp['size_kb']
            
            print(f"\n💾 Total database bloat from base64 images: {total_size:.2f} KB")
            
            if is_r2_enabled():
                print(f"\n✅ R2 is configured and ready")
                response = input(f"\n🔄 Do you want to migrate these {base64_count} image(s) to R2? (yes/no): ")
                
                if response.lower() in ['yes', 'y']:
                    migrate_images_to_r2(companies_with_base64, db)
                else:
                    print("   ⏭️  Migration skipped")
            else:
                print(f"\n⚠️  R2 is not configured. Images will remain as base64 in database.")
                print(f"   To migrate, configure R2 environment variables first.")
        else:
            print(f"\n🎉 No base64 images found! All images are using URLs or no images uploaded yet.")
        
        # Also check employees table for image_url
        if hasattr(db, 'use_postgres') and db.use_postgres:
            conn = db.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT id, name, image_url FROM employees WHERE image_url IS NOT NULL AND image_url LIKE 'data:image%'")
            employees = cursor.fetchall()
            db.return_connection(conn)
        else:
            conn = db.get_connection()
            conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, image_url FROM employees WHERE image_url IS NOT NULL AND image_url LIKE 'data:image%'")
            employees = cursor.fetchall()
            conn.close()
        
        if len(employees) > 0:
            print(f"\n👷 Employees with base64 images: {len(employees)}")
            print(f"   (Employee images are not currently migrated by this script)")
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()


def migrate_images_to_r2(companies_with_base64, db):
    """Migrate base64 images to R2"""
    print(f"\n🚀 Starting migration to R2...")
    print("-" * 50)
    
    success_count = 0
    failed_count = 0
    
    for company_data in companies_with_base64:
        company_id = company_data['id']
        company_name = company_data['name']
        
        print(f"\n📤 Migrating Company ID {company_id}: {company_name}")
        
        try:
            # Get full company record
            company = db.get_company(company_id)
            logo_base64 = company['logo_url']
            
            # Extract base64 data and content type
            header, encoded = logo_base64.split(',', 1)
            content_type = header.split(';')[0].split(':')[1]
            extension = content_type.split('/')[-1]
            
            # Decode base64
            image_data = base64.b64decode(encoded)
            
            # Generate filename
            from datetime import datetime
            import secrets
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"logo_migrated_{timestamp}_{secrets.token_hex(4)}.{extension}"
            
            # Upload to R2
            public_url = upload_company_file(
                company_id=company_id,
                file_data=io.BytesIO(image_data),
                filename=filename,
                file_type='logos',
                content_type=content_type
            )
            
            if public_url:
                # Update database with new URL
                db.update_company(company_id, logo_url=public_url)
                print(f"   ✅ Migrated successfully")
                print(f"   📎 New URL: {public_url}")
                print(f"   💾 Saved: {company_data['size_kb']:.2f} KB from database")
                success_count += 1
            else:
                print(f"   ❌ Upload failed - R2 not available")
                failed_count += 1
                
        except Exception as e:
            print(f"   ❌ Migration failed: {e}")
            failed_count += 1
    
    print(f"\n{'='*50}")
    print(f"🎉 Migration Complete!")
    print(f"   ✅ Successfully migrated: {success_count}")
    print(f"   ❌ Failed: {failed_count}")
    print(f"{'='*50}")


if __name__ == "__main__":
    check_database_for_base64_images()
