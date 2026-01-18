"""
Clean up clients with 0 appointments
Clients should only exist if they have at least one booking
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database import Database

def cleanup_orphan_clients():
    """Remove clients who have no bookings"""
    db = Database()
    
    print("\n" + "="*80)
    print("🧹 CLEANING UP CLIENTS WITH 0 APPOINTMENTS")
    print("="*80 + "\n")
    
    # Get all clients
    all_clients = db.get_all_clients()
    print(f"Total clients in database: {len(all_clients)}\n")
    
    orphan_clients = []
    
    # Check each client
    for client in all_clients:
        total_appointments = client.get('total_appointments', 0)
        
        if total_appointments == 0:
            # Double-check by getting bookings
            bookings = db.get_client_bookings(client['id'])
            if len(bookings) == 0:
                orphan_clients.append(client)
                print(f"❌ Found orphan client: {client['name'].title()} (ID: {client['id']})")
    
    if not orphan_clients:
        print("✅ No orphan clients found! All clients have appointments.\n")
        return
    
    print(f"\n📊 Found {len(orphan_clients)} clients with 0 appointments")
    print("\nShould we delete these clients? (y/n): ", end='')
    
    response = input().strip().lower()
    
    if response == 'y':
        conn = db.get_connection()
        cursor = conn.cursor()
        
        for client in orphan_clients:
            cursor.execute("DELETE FROM clients WHERE id = ?", (client['id'],))
            print(f"🗑️  Deleted: {client['name'].title()} (ID: {client['id']})")
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ Deleted {len(orphan_clients)} orphan clients")
    else:
        print("\n❌ Cleanup cancelled")
    
    print("="*80 + "\n")

if __name__ == "__main__":
    cleanup_orphan_clients()
