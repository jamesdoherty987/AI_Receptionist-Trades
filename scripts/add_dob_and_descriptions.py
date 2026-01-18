"""
Add date of birth and AI-generated descriptions to existing clients
"""
import sys
import os
from datetime import datetime, timedelta
import random

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database import Database

# Sample dates of birth for test clients
SAMPLE_DOBS = [
    "1985-03-15",
    "1990-07-22",
    "1988-11-08",
    "1992-04-30",
    "1987-09-14",
    "1991-01-25",
    "1989-06-18",
    "1993-12-05",
    "1986-08-20",
    "1994-02-11",
    "1990-10-07",
    "1988-05-16",
    "1992-03-28",
    "1987-11-19",
    "1991-07-04"
]

# Sample injury types for descriptions
INJURY_TYPES = [
    "back injury", "neck pain", "shoulder injury", "knee pain",
    "ankle sprain", "wrist injury", "hip pain", "elbow pain",
    "leg injury", "foot injury", "finger injury", "toe injury",
    "arm injury", "muscle strain", "sports injury"
]

def generate_client_description(client, bookings):
    """Generate an AI-style description for a client based on their booking history"""
    
    if not bookings or len(bookings) == 0:
        return None
    
    # Get first and last visit dates
    first_visit = bookings[-1]['appointment_time'] if bookings else None
    last_visit = bookings[0]['appointment_time'] if bookings else None
    total_visits = len(bookings)
    
    if not first_visit or not last_visit:
        return None
    
    # Parse dates
    try:
        first_date = datetime.strptime(first_visit, "%Y-%m-%d %H:%M:%S")
        last_date = datetime.strptime(last_visit, "%Y-%m-%d %H:%M:%S")
    except:
        first_date = datetime.now() - timedelta(days=random.randint(200, 700))
        last_date = datetime.now() - timedelta(days=random.randint(1, 30))
    
    # Generate random initial injury and subsequent injuries
    initial_injury = random.choice(INJURY_TYPES)
    subsequent_injuries = random.sample([i for i in INJURY_TYPES if i != initial_injury], 
                                       min(3, len(INJURY_TYPES) - 1))
    
    # Create description
    name_parts = client['name'].split()
    first_name = name_parts[0].capitalize()
    
    # Determine if initial injury is resolved
    resolved_status = random.choice([
        "that is now resolved",
        "which has improved significantly",
        "that has been successfully treated"
    ])
    
    # Format dates for description
    first_visit_str = first_date.strftime("%d/%m/%y").lstrip("0").replace("/0", "/")
    last_visit_str = last_date.strftime("%d/%m/%y").lstrip("0").replace("/0", "/")
    
    description = (
        f"When {first_name} first came in on {first_visit_str}, they had a {initial_injury}, {resolved_status}. "
        f"Since then, they have been in {total_visits} times with {', '.join(subsequent_injuries[:-1])}"
    )
    
    if len(subsequent_injuries) > 1:
        description += f" and a {subsequent_injuries[-1]}."
    else:
        description += "."
    
    # Add last visit info if recent
    last_injury = random.choice(INJURY_TYPES)
    description += f" Their last visit on {last_visit_str}, their {last_injury.replace('injury', '').replace('pain', '').strip()} was hurting."
    
    return description

def add_dobs_and_descriptions():
    """Add dates of birth and descriptions to all existing clients"""
    db = Database()
    
    print("\n" + "="*80)
    print("📝 ADDING DATES OF BIRTH AND DESCRIPTIONS TO CLIENTS")
    print("="*80 + "\n")
    
    # Get all clients
    all_clients = db.get_all_clients()
    
    if not all_clients:
        print("❌ No clients found in database")
        return
    
    print(f"Found {len(all_clients)} clients\n")
    
    # Track updates
    updated_count = 0
    
    for i, client in enumerate(all_clients):
        client_id = client['id']
        name = client['name'].title()
        
        # Assign a DOB if not already set (only if it's actually None or a timestamp)
        dob = client.get('date_of_birth')
        if not dob or len(str(dob)) > 10:  # If None or looks like a timestamp
            dob = SAMPLE_DOBS[i % len(SAMPLE_DOBS)]
        
        # Get client's booking history
        bookings = db.get_client_bookings(client_id)
        
        # Generate description based on booking history
        description = generate_client_description(client, bookings)
        
        # Update client
        db.update_client(client_id, date_of_birth=dob, description=description)
        
        print(f"✅ Updated {name}")
        print(f"   DOB: {dob}")
        if description:
            print(f"   Description: {description[:80]}...")
        else:
            print(f"   Description: None (no bookings)")
        print()
        
        updated_count += 1
    
    print("="*80)
    print(f"✅ Successfully updated {updated_count} clients with DOB and descriptions")
    print("="*80 + "\n")

if __name__ == "__main__":
    add_dobs_and_descriptions()
