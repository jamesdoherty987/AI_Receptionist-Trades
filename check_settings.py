from src.services.settings_manager import get_settings_manager

mgr = get_settings_manager()
settings = mgr.get_business_settings()

print("Current Business Settings:")
print(f"  Days Open: {settings.get('days_open')}")
print(f"  Start Hour: {settings.get('opening_hours_start')}")
print(f"  End Hour: {settings.get('opening_hours_end')}")
print(f"  Appointment Duration: {settings.get('appointment_duration')} minutes")
