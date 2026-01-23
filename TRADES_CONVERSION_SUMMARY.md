# Trades Company Conversion - Changes Made

## Overview
Converted AI Receptionist from clinic/physiotherapy focus to trades/maintenance company focus.

## Key Changes

### 1. Business Information (`config/business_info.json`)
**BEFORE:** Munster Physio - Physiotherapy Clinic
**AFTER:** Swift Trade Services - Multi-Trade Services Company

Changes:
- Business name: "Swift Trade Services"
- Business type: Multi-trade services (plumbing, electrical, heating, carpentry, etc.)
- Hours: 8 AM - 6 PM, Monday-Saturday (was 9 AM - 5 PM, Monday-Friday)
- Emergency availability: 24/7 emergency callouts
- Services: Plumbing, electrical, heating, carpentry, painting, property maintenance
- Pricing: Callout fee (€60) + hourly rate (€50/hr), emergency rate (€120)
- Service area: Mobile service - covers Limerick and surrounding counties
- Job types: Emergency, Same-Day, Scheduled, Quote/Estimate
- Property types: Residential and Commercial

### 2. AI Prompts - Trades Focus

#### Core Collection Requirements
**REMOVED:**
- Date of Birth (DOB) - not needed for trades business

**ADDED/ENHANCED:**
- ✅ Name (spell back for confirmation)
- ✅ Phone number (MANDATORY - read back digit by digit)
- ✅ Email address (MANDATORY - spell back for confirmation)
- ✅ Job address (full address including Eircode if available)
- ✅ Job description (detailed issue description)
- ✅ Urgency level (Emergency/Same-Day/Scheduled/Quote)
- ✅ Property type (Residential or Commercial)

####Urgency Classification System
1. **🚨 EMERGENCY** - Burst pipes, electrical hazards, flooding, gas smell
   - Response: Within 2 hours
   - Rate: €120 (outside normal hours)
   
2. **⚡ SAME-DAY** - Leaking tap, blocked drain, broken appliance
   - Response: Try to fit in today
   - Rate: Standard callout + hourly
   
3. **📅 SCHEDULED** - Installations, routine maintenance
   - Response: Book convenient time
   - Rate: Standard callout + hourly
   
4. **💰 QUOTE** - Just needs pricing/estimate
   - Response: Free quote appointment
   - Rate: No charge for quote

#### Validation Changes
**Phone Validation:**
- Read back digit by digit: "That's 0-8-5-1-2-3-4-5-6-7?"
- Irish mobile: 085/086/087/089 + 7 digits
- Irish landline: area code + 7 digits
- MANDATORY - cannot proceed without it

**Email Validation:**
- Spell back entire email: "So j-o-h-n at g-m-a-i-l dot com?"
- Confirm domain (.com vs .ie, gmail vs hotmail)
- MANDATORY - cannot proceed without it

**Address Collection:**
- Always get full address: "What's the full address for the job?"
- Ask for town/city if only street given
- Ask for Eircode if available (optional but helpful)
- For returning customers: confirm if same address or different location

**Job Description:**
- Get specific details about the issue
- Ask follow-up questions:
  * "Is it leaking constantly or only when you turn it on?"
  * "When did you first notice this?"
  * "Have you tried anything already?"
- More detail = better prepared tradesperson

#### Conversation Style
- Irish casual language: "Grand", "Lovely", "No problem", "Brilliant"
- Brief responses (12-15 words max for phone calls)
- One question at a time
- Natural and conversational
- Solution-focused and helpful

### 3. Code Changes Required

#### `src/services/llm_stream.py`
Need to remove/update:
- `date_of_birth` field from `_appointment_state`
- `dob_confirmed` field
- `check_caller_in_database()` - remove DOB parameter logic
- All DOB pattern detection code
- All DOB validation logic
- System messages mentioning DOB

Update client lookup to use:
- Name + Phone combination
- Name + Email combination
- Name only (with confirmation)

#### `src/services/database.py`
**KEEP** `date_of_birth` column for backwards compatibility (existing data)
**UPDATE** client lookup methods:
- `find_or_create_client()` - remove DOB priority, use phone/email
- `get_client_by_name_and_dob()` - deprecate or make optional

#### Prompt File Replacements
- ✅ `prompts/receptionist_prompt.txt` - COMPLETED
- ✅ `prompts/receptionist_prompt_fast.txt` - COMPLETED
- ✅ `config/business_info.json` - COMPLETED

### 4. Features Added for Trades

1. **Urgency Assessment** - Automatic classification based on keywords and context
2. **Address Validation** - Mandatory collection with Eircode support
3. **Job Description Gathering** - Detailed issue collection with follow-up questions
4. **Property Type Tracking** - Residential vs Commercial
5. **Emergency Callout Handling** - Premium rate acknowledgment
6. **Free Quote Appointments** - No-obligation estimate bookings
7. **Materials Flexibility** - Can supply or work with customer materials
8. **Multi-Job Booking** - Handle multiple different trades at once

### 5. Remaining Work

#### Code Updates Needed:
1. Update `llm_stream.py` to remove DOB logic completely
2. Update database client matching to prioritize phone/email over DOB
3. Update appointment booking flow to collect address
4. Add urgency field to appointments
5. Update confirmation messages for trades terminology

#### Testing Needed:
1. Test new customer flow (phone + email + address collection)
2. Test returning customer flow (confirm contact info + address)
3. Test emergency booking flow
4. Test quote appointment flow
5. Test address validation
6. Test job description gathering

### 6. Terminology Changes

| Old (Clinic) | New (Trades) |
|--------------|---------------|
| Patient | Customer |
| Appointment | Job/Booking |
| Practitioner | Tradesperson/Technician |
| Clinic | Business |
| Visit | Callout |
| Treatment | Work/Service |
| Medical | Trade/Maintenance |

### 7. Backwards Compatibility

- Database schema retains DOB field (won't break existing data)
- Existing appointments remain unchanged
- Old customer records remain valid
- New bookings simply won't collect DOB

## Summary

This conversion transforms the AI receptionist from a healthcare-focused booking system to a comprehensive trades company dispatch system, maintaining robust validation while adapting to the specific needs of service/maintenance businesses.

**Core Philosophy:**
- Fast and efficient
- Robust validation (phone, email, address)
- Not hardcoded - flexible and adaptable
- Context-aware and intelligent
- Professional yet friendly
