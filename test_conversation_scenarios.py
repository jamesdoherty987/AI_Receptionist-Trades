"""
Real-world conversation scenarios demonstrating the AI receptionist
properly collecting name, phone, email, address, and issue for all cases.
"""

def print_conversation(title, scenario):
    """Print a formatted conversation scenario"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)
    print(scenario)
    print("="*80)

def scenario_new_customer_emergency():
    """New customer with emergency - all fields collected"""
    return """
👤 SCENARIO 1: NEW CUSTOMER - EMERGENCY

Customer: "My pipe burst! Water everywhere!"

AI: "That's an emergency. We can get someone there ASAP. Can I get your name please?"

Customer: "Sarah Murphy"

AI: "Thanks Sarah. Just to confirm, is that spelled S-A-R-A-H M-U-R-P-H-Y?"

Customer: "Yes"

AI (calls lookup_customer): [SYSTEM: No match found - new customer]

AI: "Welcome to Swift Trade Services, Sarah! What's your phone number?"

Customer: "085-1234567"

AI: "That's 0-8-5-1-2-3-4-5-6-7, correct?"

Customer: "Yes"

AI: "And your email address?"

Customer: "sarah.murphy@gmail.com"

AI: "So that's s-a-r-a-h dot m-u-r-p-h-y at g-m-a-i-l dot com?"

Customer: "Correct"

AI: "What's the full address?"

Customer: "23 Oak Drive, Limerick"

AI: "Let me check..." [calls check_availability]

AI: "I can have someone there at 11 AM today. Does that work?"

Customer: "Perfect"

AI: "Brilliant! So that's Sarah Murphy, today at 11 AM for emergency burst pipe 
    at 23 Oak Drive, Limerick. Contact: 0851234567, sarah.murphy@gmail.com. All correct?"

Customer: "Yes"

AI: [calls book_job with ALL fields]:
    - customer_name: "Sarah Murphy"
    - phone: "0851234567"
    - email: "sarah.murphy@gmail.com"
    - job_address: "23 Oak Drive, Limerick"
    - job_description: "Emergency burst pipe"
    - appointment_datetime: "today at 11 AM"
    - urgency_level: "emergency"

✅ DATABASE SAVES:
    - Client: Sarah Murphy, phone 0851234567, email sarah.murphy@gmail.com
    - Booking: Address "23 Oak Drive, Limerick", urgency "emergency"

AI: "You're all set! They'll be there at 11 AM."
"""

def scenario_returning_customer_same_address():
    """Returning customer - confirming existing address"""
    return """
👤 SCENARIO 2: RETURNING CUSTOMER - SAME ADDRESS

Customer: "Hi, I'm John O'Brien"

AI: "Thanks John. Is that J-O-H-N O-apostrophe-B-R-I-E-N?"

Customer: "Yes"

AI (calls lookup_customer): [SYSTEM: Found! Phone: 087-9876543, Email: john@email.com,
                                     Last Address: 15 Park Road, Limerick]

AI: "Great to hear from you again, John! I have your number as 087-9876543. Still correct?"

Customer: "Yes"

AI: "Perfect. And your email is john@email.com, still good?"

Customer: "Yes"

AI: "How can I help you today?"

Customer: "I need some new lights installed in the kitchen"

AI: "No problem. Is that for the same address we have on file, 15 Park Road, or different?"

Customer: "Yes, same address"

AI: "Grand. When would suit you for us to come out?"

Customer: "How's next Tuesday?"

AI: "Let me check..." [calls check_availability]

AI: "Tuesday I have morning slots at 9 or 11, or afternoon at 2. What works?"

Customer: "11am is perfect"

AI: [calls book_job with ALL fields]:
    - customer_name: "John O'Brien"
    - phone: "087-9876543"
    - email: "john@email.com"
    - job_address: "15 Park Road, Limerick"  ← CONFIRMED from last job
    - job_description: "Kitchen lighting installation"
    - appointment_datetime: "Tuesday at 11am"
    - urgency_level: "scheduled"

✅ DATABASE SAVES:
    - Booking: Address "15 Park Road, Limerick" properly saved

AI: "Brilliant. So that's John O'Brien, Tuesday at 11am for kitchen lighting 
    installation at 15 Park Road. All correct?"

Customer: "Yes"

AI: "Lovely, you're all set!"
"""

def scenario_returning_customer_different_address():
    """Returning customer - different address this time"""
    return """
👤 SCENARIO 3: RETURNING CUSTOMER - DIFFERENT ADDRESS

Customer: "Hi, Tom Walsh here"

AI: "Hi Tom. Is that T-O-M W-A-L-S-H?"

Customer: "Yes"

AI (calls lookup_customer): [SYSTEM: Found! Phone: 089-7771234, Email: tom@email.com,
                                     Last Address: 8 High Street, Ennis]

AI: "Good to hear from you again, Tom! I have 089-7771234. Still good?"

Customer: "Yes"

AI: "And your email is tom@email.com, correct?"

Customer: "Yes"

AI: "Perfect. What can I help you with?"

Customer: "Kitchen tap dripping at my rental property"

AI: "No problem. Is this for the same address we have on file, 8 High Street, or different?"

Customer: "No, this is for a different place - my rental property"

AI: "No problem. What's the full address for this job?"

Customer: "42 Main Street, Limerick"

AI: "Got it. Let me see if we can fit you in..." [calls check_availability]

AI: "I can get someone there today at 4pm. Does that work?"

Customer: "Perfect"

AI: [calls book_job with ALL fields]:
    - customer_name: "Tom Walsh"
    - phone: "089-7771234"
    - email: "tom@email.com"
    - job_address: "42 Main Street, Limerick"  ← NEW ADDRESS collected
    - job_description: "Dripping kitchen tap"
    - appointment_datetime: "today at 4pm"
    - urgency_level: "same-day"

✅ DATABASE SAVES:
    - Booking: NEW address "42 Main Street, Limerick" properly saved
    - Next time customer books at 42 Main Street, system will remember it

AI: "Grand. That's Tom Walsh, today at 4pm for dripping tap at 42 Main Street, 
    Limerick. Phone 089-7771234, tom@email.com. Correct?"

Customer: "Yes"

AI: "Lovely, you're booked!"
"""

def scenario_returning_customer_missing_data():
    """Returning customer with missing email - must collect it"""
    return """
👤 SCENARIO 4: RETURNING CUSTOMER - MISSING EMAIL

Customer: "It's Mary here, I need a plumber"

AI: "Hi Mary. Can you spell your full name for me?"

Customer: "M-A-R-Y F-I-T-Z-G-E-R-A-L-D"

AI (calls lookup_customer): [SYSTEM: Found! Phone: 086-5554321, Email: NULL,
                                     Last Address: 42 Green Street, Limerick]

AI: "Great to hear from you again, Mary! I have your phone as 086-5554321. Still correct?"

Customer: "Yes"

AI: "Perfect. I don't have an email on file - what's your email address?"

Customer: "maryf@hotmail.com"

AI: "So m-a-r-y-f at h-o-t-m-a-i-l dot com?"

Customer: "Yes"

AI: "Thanks! What's the issue?"

Customer: "Sink is blocked"

AI: "No problem. Is this for 42 Green Street, or a different location?"

Customer: "Same address"

AI: "When works for you?"

Customer: "Friday afternoon?"

AI: [calls check_availability]

AI: "Friday I have 2 PM or 4 PM. Which is better?"

Customer: "2pm works"

AI: [calls book_job with ALL fields]:
    - customer_name: "Mary Fitzgerald"
    - phone: "086-5554321"
    - email: "maryf@hotmail.com"  ← NOW COLLECTED
    - job_address: "42 Green Street, Limerick"
    - job_description: "Blocked sink"
    - appointment_datetime: "Friday at 2pm"
    - urgency_level: "scheduled"

✅ DATABASE SAVES:
    - Client record UPDATED with email
    - Booking: Address and ALL contact info saved

AI: "Brilliant. So that's Mary Fitzgerald, Friday at 2pm for blocked sink at 
    42 Green Street. Phone 086-5554321, email maryf@hotmail.com. All correct?"

Customer: "Perfect"

AI: "Grand, you're booked!"
"""

def scenario_edge_case_no_address_on_file():
    """Returning customer but no address in system - must ask"""
    return """
👤 SCENARIO 5: EDGE CASE - RETURNING CUSTOMER, NO ADDRESS ON FILE

Customer: "James Doherty calling"

AI: "Thanks James, J-A-M-E-S D-O-H-E-R-T-Y?"

Customer: "Yes"

AI (calls lookup_customer): [SYSTEM: Found! Phone: 0852635954, Email: jk@gmail.com,
                                     Last Address: NULL]

AI: "Great to hear from you again, James! Is 0852635954 still the best number?"

Customer: "Yes it is"

AI: "Perfect! What can I help you with?"

Customer: "Sink is leaking"

AI: "No problem. I don't have an address on file - what's the full address for this job?"

Customer: "32 Silvergrove, Ballybeg, Ennis"

AI: "Got it. When works for you?"

Customer: "Friday afternoon?"

AI: [calls check_availability]

AI: "Friday I have 2 PM, 3 PM, or 4 PM. Which suits?"

Customer: "3 PM is good"

AI: [calls book_job with ALL fields]:
    - customer_name: "James Doherty"
    - phone: "0852635954"
    - email: "jk@gmail.com"
    - job_address: "32 Silvergrove, Ballybeg, Ennis"  ← NOW COLLECTED
    - job_description: "Leaking sink"
    - appointment_datetime: "Friday at 3pm"
    - urgency_level: "scheduled"

✅ DATABASE SAVES:
    - Booking: Address NOW saved for future reference
    - Next time: System will ask "Is this for 32 Silvergrove, or different?"

AI: "Perfect! So James Doherty, Friday at 3 PM for leaking sink at 
    32 Silvergrove, Ballybeg, Ennis. Correct?"

Customer: "Yes"

AI: "Brilliant, you're all set!"
"""

def scenario_validation_failure():
    """AI tries to book without address - system rejects it"""
    return """
👤 SCENARIO 6: VALIDATION - MISSING ADDRESS BLOCKED

[Hypothetical bad scenario - system prevents this]

Customer: "Book me in for tomorrow at 2pm, my name is Bob Smith"

AI: [Attempts to call book_job]:
    - customer_name: "Bob Smith"
    - phone: "0851112222"
    - email: "bob@email.com"
    - job_address: MISSING ❌
    - job_description: "General maintenance"
    - appointment_datetime: "tomorrow at 2pm"
    - urgency_level: "scheduled"

SYSTEM: ❌ REJECTED!
    Error: "Job address is required. Please ask for the full address 
           where the work will be performed."

AI: "And what's the full address for the job?"

Customer: "123 Test Street, Cork"

AI: [NOW calls book_job with address]:
    - job_address: "123 Test Street, Cork" ✅

✅ DATABASE SAVES:
    - Booking with complete address information

This ensures:
- AI cannot bypass address collection
- Database always has complete information
- Tradesperson knows where to go
"""

def run_scenario_demonstrations():
    """Run all scenario demonstrations"""
    print("\n" + "█"*80)
    print("  REAL-WORLD CONVERSATION SCENARIOS")
    print("  Demonstrating Proper Address Collection")
    print("█"*80)
    
    scenarios = [
        ("NEW CUSTOMER - EMERGENCY", scenario_new_customer_emergency),
        ("RETURNING CUSTOMER - SAME ADDRESS", scenario_returning_customer_same_address),
        ("RETURNING CUSTOMER - DIFFERENT ADDRESS", scenario_returning_customer_different_address),
        ("RETURNING CUSTOMER - MISSING EMAIL", scenario_returning_customer_missing_data),
        ("RETURNING CUSTOMER - NO ADDRESS ON FILE", scenario_edge_case_no_address_on_file),
        ("VALIDATION - MISSING ADDRESS BLOCKED", scenario_validation_failure)
    ]
    
    for title, scenario_func in scenarios:
        print_conversation(title, scenario_func())
    
    print("\n" + "█"*80)
    print("  KEY TAKEAWAYS")
    print("█"*80)
    print("""
✅ ALWAYS COLLECTED (EVERY JOB):
    1. Name (spelled and confirmed)
    2. Phone (read back and confirmed)
    3. Email (spelled back and confirmed)
    4. Address (full address for THIS specific job)
    5. Job Description (detailed issue)
    6. Date & Time (specific time)
    7. Urgency Level (emergency/same-day/scheduled/quote)

📋 FOR NEW CUSTOMERS:
    - Collect all 4 contact items fresh (name, phone, email, address)
    - No assumptions - ask for everything

📋 FOR RETURNING CUSTOMERS:
    - Verify phone and email are still current
    - ASK about address: "Is this for [last address], or different?"
    - If same: Use last address
    - If different: Collect new address
    - If no address on file: "What's the full address for this job?"

🚨 SYSTEM VALIDATION:
    - book_job tool REQUIRES all fields
    - Rejects booking if phone, email, OR address is missing
    - AI cannot bypass this requirement
    - Database only saves complete bookings

💾 DATABASE STORAGE:
    - Address saved in bookings table (NOT just notes)
    - Visible on job cards and dashboard
    - Tradesperson knows exactly where to go
    - System remembers for future bookings

🎯 RESULT:
    - No more missing addresses
    - No more missing contact information
    - Every job has complete, accurate information
    - Tradesperson can find the location
    - Customer can be contacted
    """)
    print("█"*80)

if __name__ == "__main__":
    run_scenario_demonstrations()
