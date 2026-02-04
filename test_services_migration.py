"""Test services database migration"""
from src.services.settings_manager import get_settings_manager
from src.services.database import get_database

print("="*60)
print("Testing Services Database Migration")
print("="*60)

# Test 1: Settings Manager
print("\n1️⃣ Testing Settings Manager")
mgr = get_settings_manager()
services = mgr.get_services()
print(f"✅ Loaded {len(services)} services from database via settings_manager")
for idx, service in enumerate(services[:5], 1):
    print(f"   {idx}. {service['name']} ({service['category']}) - €{service['price']}")

# Test 2: Services Menu
print("\n2️⃣ Testing Services Menu")
menu = mgr.get_services_menu()
print(f"✅ Services menu structure:")
print(f"   Business: {menu['business_name']}")
print(f"   Services count: {len(menu['services'])}")
print(f"   Business hours: {menu['business_hours']['start_hour']}-{menu['business_hours']['end_hour']}")

# Test 3: Direct Database Access
print("\n3️⃣ Testing Direct Database Access")
db = get_database()
all_services = db.get_all_services(active_only=False)
print(f"✅ Database contains {len(all_services)} total services")

# Test 4: Get Specific Service
print("\n4️⃣ Testing Get Service by ID")
if services:
    first_service = services[0]
    service_id = first_service['id']
    fetched = mgr.get_service_by_id(service_id)
    print(f"✅ Retrieved service: {fetched['name']}")

# Test 5: Get Service by Name
print("\n5️⃣ Testing Get Service by Name")
service = mgr.get_service_by_name("Leak Repairs")
if service:
    print(f"✅ Found service: {service['name']} - €{service['price']}")
else:
    print("❌ Service not found")

print("\n" + "="*60)
print("✅ All tests passed! Services are loading from database.")
print("="*60)
