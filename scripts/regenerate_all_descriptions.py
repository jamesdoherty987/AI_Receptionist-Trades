"""
Force regenerate all client descriptions using AI
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database import Database
from src.services.client_description_generator import update_client_description

def regenerate_descriptions():
    """Regenerate descriptions for all clients with bookings"""
    db = Database()
    
    print("\n" + "="*80)
    print("🤖 REGENERATING CLIENT DESCRIPTIONS WITH AI")
    print("="*80 + "\n")
    
    all_clients = db.get_all_clients()
    
    updated = 0
    skipped = 0
    
    for client in all_clients:
        client_id = client['id']
        name = client['name'].title()
        
        # Get bookings
        bookings = db.get_client_bookings(client_id)
        
        if not bookings or len(bookings) == 0:
            print(f"⏭️  {name} - No bookings, skipped")
            skipped += 1
            continue
        
        print(f"📝 {name} ({len(bookings)} appointments)... ", end="", flush=True)
        
        try:
            success = update_client_description(client_id)
            if success:
                # Get and display the new description
                updated_client = db.get_client(client_id)
                description = updated_client.get('description', '')
                if description:
                    print(f"✅")
                    print(f"   → {description[:100]}{'...' if len(description) > 100 else ''}")
                else:
                    print(f"⚠️  No description generated")
                updated += 1
            else:
                print(f"❌ Failed")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "="*80)
    print(f"✅ Updated: {updated} clients")
    print(f"⏭️  Skipped: {skipped} clients (no bookings)")
    print("="*80 + "\n")

if __name__ == "__main__":
    regenerate_descriptions()
