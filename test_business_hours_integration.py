#!/usr/bin/env python3
"""
Test business hours integration - verify database settings are used everywhere
"""
from src.utils.config import Config
from src.services.settings_manager import get_settings_manager

print("=" * 60)
print("🧪 Testing Business Hours Integration")
print("=" * 60)

# Test 1: Get database settings
print("\n1️⃣ Testing database settings:")
mgr = get_settings_manager()
db_settings = mgr.get_business_settings()
print(f"   Database hours: {db_settings.get('opening_hours_start')} - {db_settings.get('opening_hours_end')}")
print(f"   Database days: {db_settings.get('days_open')}")

# Test 2: Get dynamic config
print("\n2️⃣ Testing Config.get_business_hours():")
hours = Config.get_business_hours()
print(f"   Dynamic hours: {hours['start']} - {hours['end']}")
print(f"   Dynamic days: {hours['days_open']}")

# Test 3: Get business days indices
print("\n3️⃣ Testing Config.get_business_days_indices():")
indices = Config.get_business_days_indices()
print(f"   Weekday indices: {indices}")
print(f"   (0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun)")

# Test 4: Verify match
print("\n4️⃣ Verification:")
if (hours['start'] == db_settings.get('opening_hours_start') and 
    hours['end'] == db_settings.get('opening_hours_end')):
    print("   ✅ Config matches database!")
else:
    print("   ❌ MISMATCH between config and database!")

# Test 5: Load services menu (should NOT have business hours)
print("\n5️⃣ Testing services_menu.json:")
import json
from pathlib import Path
services_path = Path(__file__).parent / 'config' / 'services_menu.json'
with open(services_path) as f:
    menu = json.load(f)
    if 'business_hours' in menu:
        print("   ⚠️  business_hours still in services_menu.json (should be removed)")
    else:
        print("   ✅ business_hours removed from services_menu.json")
    print(f"   Services count: {len(menu.get('services', []))}")

print("\n" + "=" * 60)
print("✅ Test complete! Business hours should be in database only.")
print("=" * 60)
