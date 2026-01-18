"""
Test that the system never generates "let me check" or similar phrases
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_prompt_has_prohibition():
    """Verify the main prompt explicitly prohibits checking phrases"""
    prompt_path = Path(__file__).parent.parent / 'prompts' / 'receptionist_prompt.txt'
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_content = f.read()
    
    # Check for prohibition section
    assert 'ABSOLUTE PROHIBITIONS' in prompt_content, "Missing ABSOLUTE PROHIBITIONS section"
    assert '❌' in prompt_content, "Missing visual prohibition markers"
    assert 'Let me check' in prompt_content, "Missing 'Let me check' in prohibitions"
    assert 'One moment' in prompt_content, "Missing 'One moment' in prohibitions"
    
    # Ensure no examples contain these phrases
    lines = prompt_content.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith('Agent:') and 'Let me check' in line:
            print(f"❌ FOUND 'Let me check' in example at line {i+1}: {line}")
            assert False, f"Found prohibited phrase in Agent example: {line}"
    
    print("✅ Prompt file has proper prohibitions and no bad examples")


def test_system_messages_have_explicit_warnings():
    """Verify system messages in llm_stream.py have explicit warnings"""
    llm_stream_path = Path(__file__).parent.parent / 'src' / 'services' / 'llm_stream.py'
    
    with open(llm_stream_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for aggressive warnings in system messages
    assert '🚨 ABSOLUTE PROHIBITION' in content, "Missing strong prohibition language"
    assert 'DO NOT say "let me check"' in content, "Missing explicit prohibition"
    assert 'the check is ALREADY DONE' in content, "Missing explanation that check is complete"
    assert 'DATABASE LOOKUP ALREADY COMPLETE' in content, "Missing clear status indicator"
    
    print("✅ System messages have explicit prohibitions")


def test_no_default_times():
    """Verify date parser never defaults to a time"""
    from src.utils.date_parser import parse_datetime
    
    # Test cases that should return None (no default time)
    test_cases = [
        "",  # Empty string
        "tomorrow",  # Relative day without time
        "january 5th",  # Date without time
        "next friday",  # Day without time
        "jan 5",  # Abbreviated month, no time
    ]
    
    print("\n" + "="*60)
    print("Testing NO DEFAULT TIMES behavior:")
    print("="*60)
    
    for test_input in test_cases:
        result = parse_datetime(test_input)
        print(f"\nInput: '{test_input}'")
        if result is None:
            print(f"✅ Correctly returned None (will ask for time)")
        else:
            print(f"❌ FAILED: Returned {result} instead of None")
            assert False, f"parse_datetime should return None for '{test_input}', got {result}"
    
    print("\n✅ All date-only inputs correctly return None")


if __name__ == "__main__":
    print("="*70)
    print("TESTING: NO CHECKING PHRASES & NO DEFAULT TIMES")
    print("="*70)
    
    test_prompt_has_prohibition()
    test_system_messages_have_explicit_warnings()
    test_no_default_times()
    
    print("\n" + "="*70)
    print("ALL TESTS PASSED! ✅")
    print("="*70)
    print("\nKey fixes verified:")
    print("✅ Prompt explicitly prohibits 'let me check' phrases")
    print("✅ System messages have aggressive warnings")
    print("✅ No default times - always asks user")
    print("✅ Date parser returns None for date-only input")
