"""
Database cleanup script - removes clients without contact info
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database import Database

def cleanup_database():
    """Remove clients and bookings that don't have proper contact info"""
    db = Database()
    
    print("\n" + "="*80)
    print("🧹 DATABASE CLEANUP - Removing Invalid Records")
    print("="*80 + "\n")
    
    # Get all clients
    all_clients = db.get_all_clients()
    print(f"📊 Total clients in database: {len(all_clients)}\n")
    
    invalid_clients = []
    valid_clients = []
    
    # Check each client
    for client in all_clients:
        has_phone = client.get('phone') and client['phone'].strip()
        has_email = client.get('email') and client['email'].strip()
        
        if not has_phone and not has_email:
            invalid_clients.append(client)
            print(f"❌ Invalid: {client['name']} (ID: {client['id']}) - No phone or email")
        else:
            valid_clients.append(client)
    
    if not invalid_clients:
        print("✅ No invalid clients found! Database is clean.\n")
        return
    
    print(f"\n📋 Found {len(invalid_clients)} invalid clients")
    print(f"✅ {len(valid_clients)} valid clients will be kept\n")
    
    # Confirm deletion
    print("⚠️  WARNING: This will permanently delete these clients and their bookings!")
    response = input("Do you want to proceed? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("\n❌ Cleanup cancelled by user\n")
        return
    
    # Delete invalid clients
    conn = db.get_connection()
    cursor = conn.cursor()
    
    deleted_count = 0
    bookings_deleted = 0
    
    for client in invalid_clients:
        client_id = client['id']
        
        # First, delete all bookings for this client
        cursor.execute("SELECT COUNT(*) FROM bookings WHERE client_id = ?", (client_id,))
        booking_count = cursor.fetchone()[0]
        
        cursor.execute("DELETE FROM bookings WHERE client_id = ?", (client_id,))
        bookings_deleted += booking_count
        
        # Delete appointment notes
        cursor.execute("DELETE FROM appointment_notes WHERE booking_id IN (SELECT id FROM bookings WHERE client_id = ?)", (client_id,))
        
        # Delete client notes
        cursor.execute("DELETE FROM notes WHERE client_id = ?", (client_id,))
        
        # Delete the client
        cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        deleted_count += 1
        
        print(f"🗑️  Deleted: {client['name']} (ID: {client_id}) and {booking_count} booking(s)")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Cleanup complete!")
    print(f"   - Deleted {deleted_count} invalid clients")
    print(f"   - Deleted {bookings_deleted} associated bookings")
    print(f"   - Kept {len(valid_clients)} valid clients\n")
    print("="*80 + "\n")

if __name__ == "__main__":
    cleanup_database()
