from src.services.database import Database

db = Database()
bookings = db.get_all_bookings()[:5]

print("Checking first 5 bookings:")
print("="*60)
for b in bookings:
    print(f"ID: {b['id']}")
    print(f"  Client Name: {b['client_name']}")
    print(f"  Charge: {b.get('charge', 'N/A')}")
    print(f"  Payment Status: {b.get('payment_status', 'N/A')}")
    print()
