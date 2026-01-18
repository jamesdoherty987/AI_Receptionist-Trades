"""
Setup script: Add notes to all past appointments and mark them as complete
"""
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database import Database
from src.services.client_description_generator import update_client_description

# Sample notes for different service types
TREATMENT_NOTES = {
    "back": [
        "Patient reported significant improvement in lower back mobility",
        "Recommended daily stretching routine",
        "Applied heat therapy and manual adjustment"
    ],
    "neck": [
        "Reduced stiffness observed during examination",
        "Prescribed neck exercises for home practice",
        "Patient showing good progress"
    ],
    "shoulder": [
        "Range of motion improving steadily",
        "Continuing strengthening exercises",
        "Patient responding well to treatment"
    ],
    "knee": [
        "Swelling has decreased significantly",
        "Walking without discomfort",
        "Recommended gradual return to activity"
    ],
    "general": [
        "Patient reported feeling better overall",
        "Treatment plan progressing as expected",
        "Follow-up scheduled as needed"
    ],
    "injury": [
        "Healing progressing well",
        "Pain levels reduced",
        "Patient following recommended care plan"
    ],
    "pain": [
        "Pain management techniques discussed",
        "Patient reports improvement",
        "Continuing current treatment approach"
    ]
}

def add_notes_to_appointment(db, booking_id, service_type):
    """Add realistic notes to an appointment"""
    # Determine note category based on service type
    service_lower = service_type.lower()
    
    if "back" in service_lower:
        notes = TREATMENT_NOTES["back"]
    elif "neck" in service_lower:
        notes = TREATMENT_NOTES["neck"]
    elif "shoulder" in service_lower:
        notes = TREATMENT_NOTES["shoulder"]
    elif "knee" in service_lower:
        notes = TREATMENT_NOTES["knee"]
    elif "injury" in service_lower or "sprain" in service_lower:
        notes = TREATMENT_NOTES["injury"]
    elif "pain" in service_lower:
        notes = TREATMENT_NOTES["pain"]
    else:
        notes = TREATMENT_NOTES["general"]
    
    # Add 1-3 notes per appointment
    import random
    num_notes = random.randint(1, 3)
    selected_notes = random.sample(notes, min(num_notes, len(notes)))
    
    for note_text in selected_notes:
        db.add_appointment_note(booking_id, note_text, created_by="Dr. Smith")

def setup_past_appointments():
    """Add notes to past appointments and mark them complete"""
    db = Database()
    
    print("\n" + "="*80)
    print("🏥 SETTING UP PAST APPOINTMENTS")
    print("="*80 + "\n")
    
    # Get all bookings
    all_bookings = db.get_all_bookings()
    
    # Filter to past appointments (before today)
    now = datetime.now()
    past_bookings = []
    
    for booking in all_bookings:
        try:
            appt_time = datetime.strptime(booking['appointment_time'], "%Y-%m-%d %H:%M:%S")
            if appt_time < now:
                past_bookings.append(booking)
        except:
            continue
    
    print(f"Found {len(past_bookings)} past appointments\n")
    
    if not past_bookings:
        print("✅ No past appointments to process")
        return
    
    processed_count = 0
    clients_updated = set()
    
    for booking in past_bookings:
        booking_id = booking['id']
        client_id = booking['client_id']
        client_name = booking['client_name']
        appt_time = booking['appointment_time']
        service = booking['service_type']
        status = booking['status']
        
        # Get existing notes
        existing_notes = db.get_appointment_notes(booking_id)
        
        print(f"📅 {appt_time} - {client_name}")
        print(f"   Service: {service}")
        print(f"   Status: {status}")
        
        # Add notes if none exist
        if len(existing_notes) == 0:
            add_notes_to_appointment(db, booking_id, service)
            new_notes = db.get_appointment_notes(booking_id)
            print(f"   ✅ Added {len(new_notes)} note(s)")
        else:
            print(f"   ✓ Already has {len(existing_notes)} note(s)")
        
        # Mark as complete if not already
        if status != 'completed':
            db.update_booking(booking_id, status='completed')
            print(f"   ✅ Marked as COMPLETED")
            clients_updated.add(client_id)
        else:
            print(f"   ✓ Already completed")
        
        processed_count += 1
        print()
    
    print("="*80)
    print(f"✅ Processed {processed_count} past appointments")
    print(f"📝 Updated status for {len(clients_updated)} clients")
    print("="*80 + "\n")
    
    # Now update descriptions for all affected clients
    if clients_updated:
        print("🤖 Updating client descriptions with AI...\n")
        
        for client_id in clients_updated:
            client = db.get_client(client_id)
            if client:
                print(f"Updating {client['name'].title()}...", end=" ")
                try:
                    success = update_client_description(client_id)
                    if success:
                        print("✅")
                    else:
                        print("⚠️ (no bookings)")
                except Exception as e:
                    print(f"❌ {e}")
        
        print(f"\n✅ Updated descriptions for {len(clients_updated)} clients")
    
    print("\n" + "="*80)
    print("✅ SETUP COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    setup_past_appointments()
