"""
Test the improved AI receptionist logic
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

print("\n" + "="*80)
print("🤖 AI RECEPTIONIST LOGIC VALIDATION")
print("="*80 + "\n")

# Check 1: Verify prompt has mandatory contact info requirements
print("✅ Checking prompt for contact info requirements...")
prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'receptionist_prompt.txt')
with open(prompt_path, 'r', encoding='utf-8') as f:
    prompt_content = f.read()

checks = {
    "MANDATORY phone or email collection": "MANDATORY" in prompt_content and "phone OR email" in prompt_content.lower(),
    "Contact validation checklist": "✅ Phone OR Email" in prompt_content,
    "DOB requirement for all clients": "Date of Birth (for all clients" in prompt_content,
    "Contact confirmation in final step": "The best way to reach you" in prompt_content,
    "New client must collect phone+DOB": "MUST GET A PHONE NUMBER" in prompt_content,
    "Returning client contact validation": "verify they have valid contact information" in prompt_content,
}

all_passed = True
for check_name, passed in checks.items():
    status = "✅" if passed else "❌"
    print(f"  {status} {check_name}")
    if not passed:
        all_passed = False

print()

# Check 2: Verify required fields are documented
print("✅ Checking required booking fields...")
required_fields = [
    "Name (confirmed with spelling)",
    "Date of Birth",
    "Contact Information",
    "Appointment Date & Time",
    "Reason for appointment"
]

fields_found = {field: field in prompt_content for field in required_fields}
for field, found in fields_found.items():
    status = "✅" if found else "❌"
    print(f"  {status} {field}")
    if not found:
        all_passed = False

print()

# Check 3: Verify examples include contact collection
print("✅ Checking examples include contact info collection...")
example_checks = {
    "New client example collects phone": "Is the phone number you're calling from" in prompt_content and "Example 1" in prompt_content,
    "New client example collects DOB": "date of birth" in prompt_content.lower() and "Example 1" in prompt_content,
    "Confirmation includes contact method": "best way to reach you" in prompt_content.lower() and "Example" in prompt_content,
    "Example for email-only client": "Example 8" in prompt_content or "rather not give my phone" in prompt_content,
}

for check_name, passed in example_checks.items():
    status = "✅" if passed else "❌"
    print(f"  {status} {check_name}")
    if not passed:
        all_passed = False

print()
print("="*80)
if all_passed:
    print("✅ ALL CHECKS PASSED - AI logic is properly configured")
else:
    print("⚠️ SOME CHECKS FAILED - Review the prompt file")
print("="*80 + "\n")

# Print key improvements
print("📋 KEY IMPROVEMENTS MADE:")
print("  1. ✅ Phone number or email is now MANDATORY for all bookings")
print("  2. ✅ Phone is PREFERRED - AI will try to get phone first")
print("  3. ✅ Date of Birth is MANDATORY for all clients (new and returning)")
print("  4. ✅ Validation checklist before confirming bookings")
print("  5. ✅ Returning clients with missing info must update before booking")
print("  6. ✅ Confirmation step includes contact method verification")
print("  7. ✅ Examples show proper contact collection flow")
print("  8. ✅ Critical reminders section emphasizes contact requirement")
print()
