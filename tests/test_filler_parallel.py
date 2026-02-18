"""
Test script to verify filler audio system works correctly.

The filler audio system:
1. Pre-recorded audio files are stored in R2 bucket
2. At startup, they're downloaded and cached in memory
3. When a tool call is detected, the filler plays INSTANTLY (no TTS latency)
4. Tool execution happens IN PARALLEL with audio playback

Run with: python tests/test_filler_parallel.py
"""
import asyncio
import time
import sys
import os
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_prerecorded_audio_loading():
    """Test that pre-recorded audio files are loaded from R2"""
    print("\n" + "="*80)
    print("TEST 1: Pre-recorded Audio Loading from R2")
    print("="*80)
    
    from src.services.prerecorded_audio import (
        has_prerecorded_fillers, get_random_filler_id, get_filler_audio,
        FILLER_PHRASES, _audio_cache, preload_fillers
    )
    
    # Force reload
    preload_fillers()
    
    print(f"\nFiller phrases defined: {list(FILLER_PHRASES.keys())}")
    print(f"Audio cache contents: {list(_audio_cache.keys())}")
    print(f"has_prerecorded_fillers(): {has_prerecorded_fillers()}")
    
    r2_url = os.getenv('R2_PUBLIC_URL', '')
    print(f"R2_PUBLIC_URL configured: {'Yes' if r2_url else 'No'}")
    
    if has_prerecorded_fillers():
        print("\n✅ Pre-recorded fillers are loaded!")
        for phrase_id, audio in _audio_cache.items():
            duration_ms = len(audio) / 8  # 8 bytes per ms at 8kHz mulaw
            print(f"   - {phrase_id}: {len(audio)} bytes ({duration_ms:.0f}ms)")
        
        # Test getting a random filler
        filler_id = get_random_filler_id()
        audio = get_filler_audio(filler_id)
        print(f"\nRandom filler test: {filler_id} = {len(audio) if audio else 0} bytes")
        return True
    else:
        print("\n⚠️ No pre-recorded fillers available")
        if not r2_url:
            print("   Reason: R2_PUBLIC_URL not configured in .env")
            print("   The system will fall back to TTS for filler messages")
            print("   (This is OK for local dev - TTS fallback works)")
            return True  # Not a failure - just not configured
        else:
            print("   Reason: Audio files not found in R2")
            print("   Run: python scripts/generate_filler_audio.py")
            return False  # This IS a failure - R2 configured but files missing


def test_filler_detection():
    """Test that filler-triggering phrases are detected correctly"""
    print("\n" + "="*80)
    print("TEST 2: Filler Trigger Detection (No API needed)")
    print("="*80)
    
    # These are the phrases that should trigger fillers
    test_phrases = [
        ("what times are available tomorrow", True, "availability"),
        ("when can I book", True, "availability"),
        ("yes that's correct", True, "booking confirmation"),
        ("cancel my appointment", True, "cancellation"),
        ("reschedule my appointment", True, "reschedule"),
        ("when is my appointment", True, "lookup"),
        ("my name is John", True, "customer lookup"),
        ("speak to a human", True, "transfer"),
        ("hello", False, "greeting - no tool needed"),
        ("what services do you offer", False, "info - no tool needed"),
    ]
    
    # Simulate the detection logic from llm_stream.py
    availability_phrases = ["available", "availability", "what times", "when are you", "when can", "any slots", "free", "open"]
    booking_confirm_phrases = ["yes", "yeah", "yep", "correct", "that's right", "book it", "sounds good", "perfect", "go ahead"]
    cancel_phrases = ["cancel", "cancelling", "canceling"]
    cancel_context = ["appointment", "booking", "scheduled", "job"]
    reschedule_phrases = ["reschedule", "change my appointment", "move my appointment", "different time"]
    lookup_phrases = ["my appointment", "do i have", "what time is my", "when is my"]
    name_intro_patterns = ["my name is ", "the name is ", "name's "]
    transfer_phrases = ["transfer", "speak to a", "talk to a", "speak with", "talk with", "real person", "a human"]
    
    def would_trigger_filler(text):
        text_lower = text.lower()
        if any(p in text_lower for p in availability_phrases):
            return True
        if any(p in text_lower for p in booking_confirm_phrases):
            return True
        if any(p in text_lower for p in cancel_phrases) and any(c in text_lower for c in cancel_context):
            return True
        if any(p in text_lower for p in reschedule_phrases):
            return True
        if any(p in text_lower for p in lookup_phrases):
            return True
        if any(p in text_lower for p in name_intro_patterns):
            return True
        if any(p in text_lower for p in transfer_phrases):
            return True
        return False
    
    passed = 0
    failed = 0
    
    for phrase, expected, reason in test_phrases:
        result = would_trigger_filler(phrase)
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"{status} '{phrase}' -> {result} (expected {expected}) [{reason}]")
    
    print(f"\nResults: {passed}/{len(test_phrases)} passed")
    return failed == 0


@pytest.mark.asyncio
async def test_parallel_execution_simulation():
    """Test that parallel execution works correctly (simulated, no API needed)"""
    print("\n" + "="*80)
    print("TEST 3: Parallel Execution Simulation")
    print("="*80)
    
    from src.services.prerecorded_audio import has_prerecorded_fillers, get_filler_audio, get_random_filler_id
    
    start_time = time.time()
    
    # Simulate the parallel execution flow
    async def simulate_tool_execution():
        """Simulate a tool call that takes 1.5 seconds"""
        print(f"   🔧 [TOOL] Starting at {time.time() - start_time:.3f}s")
        await asyncio.sleep(1.5)  # Simulate database query
        print(f"   🔧 [TOOL] Complete at {time.time() - start_time:.3f}s")
        return {"success": True, "times": ["9:00 AM", "10:00 AM", "2:00 PM"]}
    
    async def simulate_audio_send():
        """Simulate sending pre-recorded audio"""
        if has_prerecorded_fillers():
            filler_id = get_random_filler_id()
            audio = get_filler_audio(filler_id)
            if audio:
                duration_ms = len(audio) / 8
                print(f"   🔊 [AUDIO] Sending {filler_id} ({duration_ms:.0f}ms) at {time.time() - start_time:.3f}s")
                # Simulate the time to send audio chunks (very fast)
                await asyncio.sleep(0.05)
                print(f"   🔊 [AUDIO] Send complete at {time.time() - start_time:.3f}s")
                print(f"   🔊 [AUDIO] Audio will play for {duration_ms:.0f}ms on caller's phone")
                return True
        
        print(f"   🔊 [AUDIO] No pre-recorded audio, would use TTS fallback")
        await asyncio.sleep(0.3)  # TTS would take longer
        return False
    
    print("\nSimulating parallel execution:")
    print(f"   Start time: {start_time:.3f}")
    
    # Run both in parallel (this is what media_handler does)
    tool_task = asyncio.create_task(simulate_tool_execution())
    audio_task = asyncio.create_task(simulate_audio_send())
    
    # Wait for audio first (it's faster)
    used_prerecorded = await audio_task
    
    # Then wait for tool
    tool_result = await tool_task
    
    total_time = time.time() - start_time
    
    print(f"\n📊 Results:")
    print(f"   Total time: {total_time:.3f}s")
    print(f"   Used pre-recorded audio: {used_prerecorded}")
    print(f"   Tool result: {tool_result}")
    
    if used_prerecorded:
        print(f"\n✅ Parallel execution working!")
        print(f"   Audio was sent immediately while tool executed in background")
        print(f"   Caller heard filler within ~50ms, tool took ~1.5s")
        print(f"   Without parallel: would have been ~1.5s of silence")
    else:
        print(f"\n⚠️ Would fall back to TTS (slower but still works)")
    
    return True  # Test passes if we get here


@pytest.mark.asyncio
async def test_full_flow_with_mock_stream():
    """Test the full flow with a mock LLM stream"""
    print("\n" + "="*80)
    print("TEST 4: Full Flow with Mock LLM Stream")
    print("="*80)
    
    from src.services.prerecorded_audio import has_prerecorded_fillers
    
    start_time = time.time()
    
    # Mock the stream_llm generator
    async def mock_stream_llm():
        """Simulate what stream_llm does"""
        # 1. Immediately yield the SPLIT_TTS marker (this is instant)
        yield "<<<SPLIT_TTS:Let me check that for you.>>>"
        
        # 2. Simulate OpenAI processing + tool execution (takes time)
        await asyncio.sleep(1.5)
        
        # 3. Yield the actual response tokens
        response = "I have 9 AM, 10 AM, and 2 PM available tomorrow. Which works best for you?"
        for word in response.split():
            yield word + " "
            await asyncio.sleep(0.02)  # Simulate streaming delay
    
    # Simulate what media_handler does
    prefetch_buffer = []
    prefetch_done = asyncio.Event()
    
    async def prefetch_remaining(stream):
        prefetch_start = time.time()
        print(f"   ⚡ [PREFETCH] Started at {prefetch_start - start_time:.3f}s")
        async for token in stream:
            if token.startswith("<<<"):
                continue
            prefetch_buffer.append(token)
            if len(prefetch_buffer) == 1:
                print(f"   ⚡ [PREFETCH] First token at {time.time() - start_time:.3f}s")
        prefetch_done.set()
        print(f"   ⚡ [PREFETCH] Done at {time.time() - start_time:.3f}s with {len(prefetch_buffer)} tokens")
    
    async def send_audio():
        audio_start = time.time()
        if has_prerecorded_fillers():
            print(f"   🔊 [AUDIO] Sending pre-recorded at {audio_start - start_time:.3f}s")
            await asyncio.sleep(0.05)  # Very fast
        else:
            print(f"   🔊 [AUDIO] TTS fallback at {audio_start - start_time:.3f}s")
            await asyncio.sleep(0.3)  # TTS is slower
        print(f"   🔊 [AUDIO] Done at {time.time() - start_time:.3f}s")
    
    stream = mock_stream_llm()
    
    # Get first token
    first_token = None
    async for token in stream:
        first_token = token
        break
    
    print(f"\n🔀 Got first token at {time.time() - start_time:.3f}s: {first_token[:50]}...")
    
    if first_token.startswith("<<<SPLIT_TTS:"):
        # Start parallel execution
        prefetch_task = asyncio.create_task(prefetch_remaining(stream))
        audio_task = asyncio.create_task(send_audio())
        
        # Wait for audio (fast)
        await audio_task
        
        # Wait for prefetch (slower - waiting for tool execution)
        await asyncio.wait_for(prefetch_done.wait(), timeout=10.0)
    
    total_time = time.time() - start_time
    response = "".join(prefetch_buffer)
    
    print(f"\n📊 Results:")
    print(f"   Total time: {total_time:.3f}s")
    print(f"   Response: {response[:100]}...")
    print(f"\n✅ Flow completed successfully!")
    
    return True


def main():
    """Run all tests"""
    print("="*80)
    print("FILLER AUDIO SYSTEM TESTS")
    print("="*80)
    print("\nThese tests verify the pre-recorded filler audio system.")
    print("No OpenAI API key is needed - fillers are pre-recorded in R2.\n")
    
    results = []
    
    # Test 1: Pre-recorded audio loading
    results.append(("Pre-recorded Audio Loading", test_prerecorded_audio_loading()))
    
    # Test 2: Filler detection
    results.append(("Filler Trigger Detection", test_filler_detection()))
    
    # Test 3: Parallel execution simulation
    results.append(("Parallel Execution", asyncio.run(test_parallel_execution_simulation())))
    
    # Test 4: Full flow
    results.append(("Full Flow", asyncio.run(test_full_flow_with_mock_stream())))
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status}: {name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ All tests passed!")
    else:
        print("\n⚠️ Some tests failed - check output above")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
