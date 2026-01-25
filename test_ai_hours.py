#!/usr/bin/env python3
"""Quick test of AI functions"""
from datetime import datetime
from src.services.llm_stream import is_business_day, get_business_hours_from_menu

dt = datetime(2026, 1, 27)  # Monday
print(f"Is Monday business day? {is_business_day(dt)}")

hours = get_business_hours_from_menu()
print(f"Business hours: {hours['start']}-{hours['end']}")

# Test Sunday
dt_sunday = datetime(2026, 1, 25)
print(f"Is Sunday business day? {is_business_day(dt_sunday)}")
