"""
Create duplicate James Doherty clients to test DOB verification
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database import Database

def create_duplicate_james():
    """Create multiple James Doherty clients with different DOBs"""
    db = Database()
    
    print("\n" + "="*80)
    print("👥 CREATING DUPLICATE JAMES DOHERTY CLIENTS")
    print("="*80 + "\n")
    
    james_clients = [
        {
            "name": "James Doherty",
            "phone": "0852635954",
            "email": "james.doherty1@email.com",
            "date_of_birth": "1990-01-12",
            "description": "When James first came in on 1/12/23, he had a back injury, that is now resolved. Since then he has been in 22 times with a finger injury, toe injury and a leg injury. His last visit on 10/12/25 his arm was hurting."
        },
        {
            "name": "James Doherty",
            "phone": "0871234567",
            "email": "james.doherty2@email.com",
            "date_of_birth": "1985-03-15",
            "description": "When James first came in on 15/3/24, he had a shoulder injury, which has improved significantly. Since then he has been in 8 times with a neck pain and knee pain. His last visit on 5/12/25 his wrist was hurting."
        },
        {
            "name": "James Doherty",
            "phone": "0869876543",
            "email": "james.doherty3@email.com",
            "date_of_birth": "1995-07-20",
            "description": "When James first came in on 20/7/24, he had a ankle sprain, that has been successfully treated. Since then he has been in 5 times with a hip pain. His last visit on 18/12/25 his elbow was hurting."
        }
    ]
    
    for james in james_clients:
        try:
            client_id = db.add_client(
                name=james["name"],
                phone=james["phone"],
                email=james["email"],
                date_of_birth=james["date_of_birth"],
                description=james["description"]
            )
            print(f"✅ Created James Doherty")
            print(f"   DOB: {james['date_of_birth']}")
            print(f"   Phone: {james['phone']}")
            print(f"   Email: {james['email']}")
            print(f"   Description: {james['description'][:80]}...")
            print()
        except Exception as e:
            print(f"❌ Error creating James Doherty: {e}\n")
    
    print("="*80)
    print("✅ DUPLICATE CLIENTS CREATED")
    print("="*80 + "\n")
    
    # Verify
    print("📋 Verifying - searching for 'James Doherty':\n")
    james_list = db.get_clients_by_name("james doherty")
    print(f"Found {len(james_list)} clients named James Doherty:\n")
    
    for i, client in enumerate(james_list, 1):
        print(f"{i}. DOB: {client['date_of_birth']}, Phone: {client['phone']}")
    
    print()

if __name__ == "__main__":
    create_duplicate_james()
