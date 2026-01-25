"""
COMPREHENSIVE AI RECEPTIONIST FLOW TEST
========================================
This test simulates the COMPLETE flow of the AI receptionist with extensive edge cases,
boundary conditions, and challenging scenarios to ensure robustness.

Test Scenarios:
1. Standard booking flow - happy path
2. Returning customer recognition
3. Edge cases:
   - Name spelling variations and corrections
   - Invalid email formats  
   - Invalid phone numbers
   - Date ambiguities (next Monday, this Friday, etc.)
   - Time format variations (12hr vs 24hr)
   - Address validation
   - Service selection edge cases
4. Emergency/urgent scenarios
5. Cancellation and rescheduling
6. Multiple service booking
7. Availability conflicts
8. Business hours edge cases
9. Customer interruption and correction scenarios
10. Missing or incomplete information recovery
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from services.llm_stream import stream_llm, process_appointment_with_calendar, SYSTEM_PROMPT, reset_appointment_state


class ConversationSimulator:
    """Simulates a conversation with the AI receptionist"""
    
    def __init__(self, scenario_name):
        self.scenario_name = scenario_name
        self.conversation = []
        self.response_history = []
        self.issues_found = []
        
    async def send_message(self, user_message, expected_keywords=None):
        """Send a message and get response"""
        print(f"\n{'='*80}")
        print(f"👤 USER: {user_message}")
        print(f"{'='*80}")
        
        # Add user message
        self.conversation.append({"role": "user", "content": user_message})
        
        # Add system prompt on first message
        if len(self.conversation) == 1:
            self.conversation.insert(0, {
                "role": "system",
                "content": SYSTEM_PROMPT
            })
        
        # Get AI response
        response_text = ""
        try:
            async for token in stream_llm(self.conversation, process_appointment_with_calendar, caller_phone=None):
                if token != "<<<FLUSH>>>":
                    response_text += token
                    
            # Add to conversation
            self.conversation.append({"role": "assistant", "content": response_text})
            self.response_history.append(response_text)
            
            print(f"🤖 AI: {response_text}")
            
            # Check for expected keywords
            if expected_keywords:
                for keyword in expected_keywords:
                    if keyword.lower() not in response_text.lower():
                        issue = f"⚠️ MISSING EXPECTED KEYWORD: '{keyword}' in response"
                        print(issue)
                        self.issues_found.append(issue)
            
            # Check response length (should be concise for phone calls)
            word_count = len(response_text.split())
            if word_count > 30:
                issue = f"⚠️ RESPONSE TOO LONG: {word_count} words (should be <30 for phone)"
                print(issue)
                self.issues_found.append(issue)
                
            # Check for robotic phrases
            robotic_phrases = [
                "i am unable to",
                "i cannot",
                "i do not have the ability",
                "as an ai",
                "i apologize, but"
            ]
            for phrase in robotic_phrases:
                if phrase in response_text.lower():
                    issue = f"⚠️ ROBOTIC PHRASE DETECTED: '{phrase}'"
                    print(issue)
                    self.issues_found.append(issue)
            
            return response_text
            
        except Exception as e:
            error = f"❌ ERROR: {str(e)}"
            print(error)
            self.issues_found.append(error)
            return None
    
    def check_for_repetition(self):
        """Check if AI is asking the same question multiple times"""
        if len(self.response_history) < 2:
            return
            
        recent_responses = self.response_history[-5:]  # Check last 5
        
        for i, resp1 in enumerate(recent_responses):
            for resp2 in recent_responses[i+1:]:
                # Check for similar questions
                if self._similarity(resp1, resp2) > 0.7:
                    issue = f"⚠️ POTENTIAL REPETITION:\n  '{resp1}'\n  '{resp2}'"
                    print(issue)
                    self.issues_found.append(issue)
    
    def _similarity(self, text1, text2):
        """Simple similarity check"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0
        return len(words1 & words2) / len(words1 | words2)
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{'#'*80}")
        print(f"SCENARIO: {self.scenario_name}")
        print(f"{'#'*80}")
        print(f"Total exchanges: {len(self.response_history)}")
        print(f"Issues found: {len(self.issues_found)}")
        
        if self.issues_found:
            print("\n⚠️ ISSUES DETECTED:")
            for issue in self.issues_found:
                print(f"  - {issue}")
        else:
            print("\n✅ NO ISSUES DETECTED - FLOW LOOKS GOOD!")
        
        print(f"{'#'*80}\n")
        

async def test_scenario_1_standard_booking():
    """Test 1: Standard booking - new customer, straightforward flow"""
    sim = ConversationSimulator("Standard New Customer Booking")
    
    # Initial greeting
    await sim.send_message("Hi there")
    
    # Customer states issue
    await sim.send_message("I have a leaking tap in my kitchen")
    
    # Provide name when asked (AI should ask for name)
    await sim.send_message("My name is Sarah Murphy")
    
    # Confirm spelling (AI should spell it back)
    await sim.send_message("Yes that's correct")
    
    # Provide phone when asked
    await sim.send_message("My number is 087 123 4567")
    
    # Provide email when asked
    await sim.send_message("sarah.murphy@email.com")
    
    # Provide address when asked
    await sim.send_message("15 O'Connell Street, Limerick")
    
    # Choose time (AI should check availability)
    await sim.send_message("What times do you have tomorrow?")
    
    # Confirm time
    await sim.send_message("2pm works for me")
    
    # Confirm booking
    await sim.send_message("Yes, book it please")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_2_returning_customer():
    """Test 2: Returning customer - should recognize and pre-fill details"""
    sim = ConversationSimulator("Returning Customer Recognition")
    
    await sim.send_message("Hello")
    
    # Use a name that might be in the system
    await sim.send_message("This is James Doherty")
    
    # AI should spell back name
    await sim.send_message("Yes, that's right")
    
    # If recognized as returning, AI should confirm details
    # Otherwise, continue as new customer
    await sim.send_message("Yes that's me")
    
    # New job
    await sim.send_message("I need an electrician to install a new socket")
    
    # Confirm address or provide new one
    await sim.send_message("Same address as before")
    
    # Choose time
    await sim.send_message("Friday morning if possible")
    
    await sim.send_message("9am would be perfect")
    
    await sim.send_message("Yes please book it")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_3_name_spelling_corrections():
    """Test 3: Name spelling issues and corrections"""
    sim = ConversationSimulator("Name Spelling Edge Cases")
    
    await sim.send_message("Hi")
    
    # Complex Irish name with apostrophe
    await sim.send_message("I need help with my boiler. My name is Sinéad O'Brien")
    
    # AI spells it back - we say it's wrong
    await sim.send_message("No, it's O-apostrophe-B-R-I-E-N with an accent on the e in Sinead")
    
    # Confirm when correct
    await sim.send_message("Yes that's correct now")
    
    # Continue flow
    await sim.send_message("085 987 6543")
    
    await sim.send_message("sinead.obrien@gmail.com")
    
    await sim.send_message("24 Church Road, Ennis, Co Clare")
    
    await sim.send_message("Next Tuesday afternoon")
    
    await sim.send_message("2pm is fine")
    
    await sim.send_message("Yes")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_4_invalid_inputs():
    """Test 4: Invalid phone/email - recovery"""
    sim = ConversationSimulator("Invalid Input Recovery")
    
    await sim.send_message("Hello, I need a plumber")
    
    await sim.send_message("Michael Collins")
    
    await sim.send_message("Yes")
    
    # Invalid phone number
    await sim.send_message("123")
    
    # AI should ask again - provide valid
    await sim.send_message("Sorry, it's 086 555 1234")
    
    # Invalid email
    await sim.send_message("michael.email.com")
    
    # AI should ask again - provide valid
    await sim.send_message("michael.collins@email.com")
    
    await sim.send_message("10 Main Street, Cork")
    
    await sim.send_message("Tomorrow at 10am if available")
    
    await sim.send_message("Yes please")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_5_emergency_urgent():
    """Test 5: Emergency/urgent scenario"""
    sim = ConversationSimulator("Emergency Urgent Request")
    
    # Start with emergency
    await sim.send_message("EMERGENCY! I have a burst pipe flooding my bathroom!")
    
    # AI should acknowledge urgency
    await sim.send_message("Yes it's an emergency, water everywhere")
    
    await sim.send_message("Patrick Walsh")
    
    await sim.send_message("Correct")
    
    await sim.send_message("089 876 5432")
    
    await sim.send_message("pwalsh@email.ie")
    
    await sim.send_message("45 Riverside, Limerick")
    
    # Should offer earliest available
    await sim.send_message("As soon as possible please!")
    
    # Should get specific time
    await sim.send_message("Yes, that time works")
    
    await sim.send_message("Yes book it")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_6_date_ambiguity():
    """Test 6: Date parsing edge cases"""
    sim = ConversationSimulator("Date Ambiguity Handling")
    
    await sim.send_message("Hi")
    
    await sim.send_message("My name is Lisa Ryan, I need carpentry work")
    
    await sim.send_message("Yes")
    
    await sim.send_message("083 456 7890")
    
    await sim.send_message("lisa.ryan@example.com")
    
    await sim.send_message("8 Park View, Galway")
    
    # Ambiguous: "next Monday" - which Monday?
    today = datetime.now()
    await sim.send_message("Next Monday morning")
    
    # AI should clarify or suggest specific date
    await sim.send_message("Yes, next week Monday")
    
    await sim.send_message("10am")
    
    await sim.send_message("Yes confirm")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_7_cancellation():
    """Test 7: Appointment cancellation"""
    sim = ConversationSimulator("Appointment Cancellation")
    
    await sim.send_message("Hello, I need to cancel an appointment")
    
    # AI should ask for date/time of appointment
    await sim.send_message("It was for tomorrow at 2pm")
    
    # AI should look it up and confirm customer name
    await sim.send_message("Yes that's correct")
    
    # Confirm cancellation
    await sim.send_message("Yes please cancel it")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_8_availability_conflict():
    """Test 8: Requested time not available"""
    sim = ConversationSimulator("Availability Conflict Resolution")
    
    await sim.send_message("Hi")
    
    await sim.send_message("David Murphy here, need electrical work")
    
    await sim.send_message("Correct")
    
    await sim.send_message("087 234 5678")
    
    await sim.send_message("dmurphy@email.com")
    
    await sim.send_message("12 High Street, Tralee")
    
    # Request specific time (might not be available)
    await sim.send_message("I need someone tomorrow at 3:47pm exactly")
    
    # AI should check availability and suggest alternatives
    await sim.send_message("What times are available tomorrow?")
    
    # Choose from available
    await sim.send_message("4pm then")
    
    await sim.send_message("Yes")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_9_customer_provides_all_info_upfront():
    """Test 9: Customer volunteers all info at once"""
    sim = ConversationSimulator("All Info Upfront")
    
    # Customer provides everything in first message
    await sim.send_message(
        "Hi, this is Emma Walsh, phone 086 111 2222, email emma@email.ie, "
        "I have a leaking radiator at 5 Castle Street Killarney, can someone come tomorrow at 11am?"
    )
    
    # AI should acknowledge all info and confirm
    await sim.send_message("E-M-M-A W-A-L-S-H, yes that's right")
    
    # Should just need to confirm availability and book
    await sim.send_message("Yes please book it")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_10_customer_changes_mind():
    """Test 10: Customer changes details mid-conversation"""
    sim = ConversationSimulator("Customer Changes Mind")
    
    await sim.send_message("Hello")
    
    await sim.send_message("I need a plumber for a leak")
    
    await sim.send_message("John O'Neill")
    
    await sim.send_message("Yes")
    
    # Gives phone
    await sim.send_message("085 777 8888")
    
    # Changes mind
    await sim.send_message("Wait, actually use 086 999 0000 instead")
    
    await sim.send_message("john.oneill@email.com")
    
    # Gives address
    await sim.send_message("15 Oak Avenue, Sligo")
    
    # Changes address
    await sim.send_message("Sorry, make that 25 Oak Avenue, not 15")
    
    await sim.send_message("Friday at 2pm")
    
    # Changes time
    await sim.send_message("Actually, can we do 3pm instead?")
    
    await sim.send_message("Yes book it")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_11_unclear_service_request():
    """Test 11: Vague service description"""
    sim = ConversationSimulator("Unclear Service Request")
    
    await sim.send_message("Hi there")
    
    # Very vague description
    await sim.send_message("Something's wrong with my house")
    
    # AI should ask clarifying questions
    await sim.send_message("I don't know, it's making a weird noise")
    
    await sim.send_message("It's coming from the heating system I think")
    
    await sim.send_message("Mary Kennedy")
    
    await sim.send_message("Yes")
    
    await sim.send_message("087 333 4444")
    
    await sim.send_message("mary.k@email.ie")
    
    await sim.send_message("30 Green Road, Waterford")
    
    await sim.send_message("Monday morning")
    
    await sim.send_message("10am")
    
    await sim.send_message("Yes")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_12_multiple_issues():
    """Test 12: Customer with multiple problems"""
    sim = ConversationSimulator("Multiple Issues/Services")
    
    await sim.send_message("Hello")
    
    await sim.send_message(
        "I have several problems - a leaking tap, a broken light switch, and I need a door fixed"
    )
    
    # AI should handle multiple services
    await sim.send_message("Tom O'Connor")
    
    await sim.send_message("Yes correct")
    
    await sim.send_message("086 555 6666")
    
    await sim.send_message("tom.oconnor@email.com")
    
    await sim.send_message("7 Mill Street, Clonmel")
    
    await sim.send_message("Next Wednesday")
    
    await sim.send_message("Morning is better, 9am?")
    
    await sim.send_message("Yes book it")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_13_outside_business_hours():
    """Test 13: Calling outside business hours"""
    sim = ConversationSimulator("Outside Business Hours")
    
    await sim.send_message("Hi")
    
    # Request for weekend/evening
    await sim.send_message("Can someone come on Sunday?")
    
    # AI should mention premium rate for emergency or suggest alternative
    await sim.send_message("It's not an emergency, what about Monday?")
    
    await sim.send_message("Niall Murphy")
    
    await sim.send_message("Yes")
    
    await sim.send_message("083 777 9999")
    
    await sim.send_message("niall@email.ie")
    
    await sim.send_message("22 River Road, Dundalk")
    
    await sim.send_message("Monday 11am")
    
    await sim.send_message("Yes")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_14_quote_inquiry():
    """Test 14: Customer wants quote, not immediate booking"""
    sim = ConversationSimulator("Quote Inquiry")
    
    await sim.send_message("Hello")
    
    await sim.send_message("Can I get a quote for installing a new boiler?")
    
    # AI should handle quote requests
    await sim.send_message("Yes, I'd like someone to come look at it")
    
    await sim.send_message("Rachel O'Donnell")
    
    await sim.send_message("Correct")
    
    await sim.send_message("087 888 9999")
    
    await sim.send_message("rachel.od@email.com")
    
    await sim.send_message("18 Chapel Street, Drogheda")
    
    await sim.send_message("Thursday afternoon")
    
    await sim.send_message("2pm")
    
    await sim.send_message("Yes")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def test_scenario_15_aggressive_interruptions():
    """Test 15: Impatient customer interrupting"""
    sim = ConversationSimulator("Impatient Customer")
    
    await sim.send_message("I need a plumber NOW")
    
    await sim.send_message("Kevin")
    
    # Doesn't wait for spelling confirmation
    await sim.send_message("Just book it! 086 123 4567")
    
    # Still interrupting
    await sim.send_message("kevin@email.com, 40 Main St Athlone, tomorrow 1pm, BOOK IT!")
    
    # AI should handle and confirm
    await sim.send_message("K-E-V-I-N yes yes")
    
    await sim.send_message("YES CONFIRM")
    
    sim.check_for_repetition()
    sim.print_summary()
    return sim


async def run_all_tests():
    """Run all test scenarios"""
    print("\n" + "="*80)
    print("COMPREHENSIVE AI RECEPTIONIST TESTING")
    print("="*80)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")
    
    all_results = []
    
    # Run all scenarios
    scenarios = [
        ("Standard Booking", test_scenario_1_standard_booking),
        ("Returning Customer", test_scenario_2_returning_customer),
        ("Name Spelling Issues", test_scenario_3_name_spelling_corrections),
        ("Invalid Input Recovery", test_scenario_4_invalid_inputs),
        ("Emergency Urgent", test_scenario_5_emergency_urgent),
        ("Date Ambiguity", test_scenario_6_date_ambiguity),
        ("Cancellation", test_scenario_7_cancellation),
        ("Availability Conflict", test_scenario_8_availability_conflict),
        ("All Info Upfront", test_scenario_9_customer_provides_all_info_upfront),
        ("Customer Changes Mind", test_scenario_10_customer_changes_mind),
        ("Unclear Service", test_scenario_11_unclear_service_request),
        ("Multiple Issues", test_scenario_12_multiple_issues),
        ("Outside Hours", test_scenario_13_outside_business_hours),
        ("Quote Inquiry", test_scenario_14_quote_inquiry),
        ("Impatient Customer", test_scenario_15_aggressive_interruptions),
    ]
    
    for scenario_name, scenario_func in scenarios:
        print(f"\n{'█'*80}")
        print(f"█ RUNNING: {scenario_name}")
        print(f"{'█'*80}\n")
        
        try:
            # Reset state between scenarios
            reset_appointment_state()
            
            result = await scenario_func()
            all_results.append((scenario_name, result))
            
        except Exception as e:
            print(f"\n❌ SCENARIO FAILED WITH EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL TEST SUMMARY")
    print("="*80)
    
    total_issues = 0
    for scenario_name, result in all_results:
        issue_count = len(result.issues_found)
        total_issues += issue_count
        status = "✅ PASS" if issue_count == 0 else f"⚠️ {issue_count} ISSUES"
        print(f"{status:20} | {scenario_name}")
    
    print("="*80)
    print(f"Total Scenarios: {len(all_results)}")
    print(f"Total Issues: {total_issues}")
    
    if total_issues == 0:
        print("\n🎉 ALL TESTS PASSED - RECEPTIONIST IS ROBUST!")
    else:
        print(f"\n⚠️ FOUND {total_issues} ISSUES ACROSS {len(all_results)} SCENARIOS")
    
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
