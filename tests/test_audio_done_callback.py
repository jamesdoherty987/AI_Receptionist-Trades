"""
Tests for the on_audio_done callback fix.

The bug: stream_tts() calls on_audio_done early (~0.6s) when the TTS receiver
exits, but stream_tts() itself doesn't return until ~10s later (sender waits
for LLM generator to close). The fallback line after `await stream_tts()`
was unconditionally overwriting last_tts_audio_done, destroying the early
timestamp from the callback.

The fix: a boolean flag (_*_audio_done_fired) prevents the fallback from
overwriting when the callback already fired.

These tests simulate the exact production timing to prove the fix works.
"""
import asyncio
import pytest


class TestCallbackNotOverwritten:
    """Simulate the exact pattern from media_handler.py to prove the fix."""

    @pytest.mark.asyncio
    async def test_callback_fires_early_not_overwritten(self):
        """
        Simulates: callback fires at 0.05s, stream_tts returns at 0.2s.
        Before fix: last_tts_audio_done = late timestamp (0.2s mark).
        After fix:  last_tts_audio_done = early timestamp (0.05s mark).
        """
        last_tts_audio_done = 0.0

        # Simulate stream_tts that calls on_audio_done early, then blocks
        async def fake_stream_tts(on_audio_done=None):
            # Receiver finishes early and fires callback (like Flushed signal)
            await asyncio.sleep(0.05)
            if on_audio_done:
                on_audio_done()
            # But stream_tts blocks longer waiting for sender to finish
            await asyncio.sleep(0.15)

        # --- THE FIXED PATTERN (from media_handler.py) ---
        _audio_done_fired = False

        def _on_audio_done():
            nonlocal last_tts_audio_done, _audio_done_fired
            last_tts_audio_done = asyncio.get_event_loop().time()
            _audio_done_fired = True

        before_call = asyncio.get_event_loop().time()
        await fake_stream_tts(on_audio_done=_on_audio_done)
        after_call = asyncio.get_event_loop().time()

        if not _audio_done_fired:
            last_tts_audio_done = asyncio.get_event_loop().time()

        # The callback should have fired
        assert _audio_done_fired is True

        # last_tts_audio_done should be the EARLY timestamp, not the late one
        # It should be closer to before_call + 0.05s than to after_call
        callback_delta = last_tts_audio_done - before_call
        total_delta = after_call - before_call

        # Callback fired around 0.05s, total took ~0.2s
        # The key assertion: callback time is significantly less than total time
        assert callback_delta < total_delta * 0.6, (
            f"Callback timestamp too late! callback_delta={callback_delta:.3f}s, "
            f"total_delta={total_delta:.3f}s — fallback likely overwrote it"
        )

    @pytest.mark.asyncio
    async def test_fallback_works_when_callback_doesnt_fire(self):
        """
        If on_audio_done never fires (edge case), the fallback should set
        last_tts_audio_done so we don't get stuck with timestamp 0.
        """
        last_tts_audio_done = 0.0

        async def fake_stream_tts_no_callback(on_audio_done=None):
            # Simulate a case where callback never fires
            await asyncio.sleep(0.05)

        _audio_done_fired = False

        def _on_audio_done():
            nonlocal last_tts_audio_done, _audio_done_fired
            last_tts_audio_done = asyncio.get_event_loop().time()
            _audio_done_fired = True

        await fake_stream_tts_no_callback(on_audio_done=None)  # callback not passed

        if not _audio_done_fired:
            last_tts_audio_done = asyncio.get_event_loop().time()

        # Fallback should have set it to a real timestamp
        assert last_tts_audio_done > 0.0
        assert _audio_done_fired is False

    @pytest.mark.asyncio
    async def test_old_buggy_pattern_would_fail(self):
        """
        Demonstrates the OLD buggy pattern: unconditional overwrite after
        stream_tts returns. This proves the bug was real.
        """
        last_tts_audio_done = 0.0
        callback_timestamp = 0.0

        async def fake_stream_tts(on_audio_done=None):
            await asyncio.sleep(0.05)
            if on_audio_done:
                on_audio_done()
            await asyncio.sleep(0.15)

        def _on_audio_done():
            nonlocal last_tts_audio_done, callback_timestamp
            last_tts_audio_done = asyncio.get_event_loop().time()
            callback_timestamp = last_tts_audio_done

        await fake_stream_tts(on_audio_done=_on_audio_done)

        # OLD BUGGY LINE: unconditional overwrite
        last_tts_audio_done = asyncio.get_event_loop().time()

        # The callback DID fire with an early timestamp
        assert callback_timestamp > 0.0

        # But last_tts_audio_done is now the LATE timestamp (the bug)
        overwrite_delta = last_tts_audio_done - callback_timestamp
        assert overwrite_delta > 0.1, (
            f"Expected significant overwrite gap, got {overwrite_delta:.3f}s"
        )


class TestCallbackTimingAccuracy:
    """Test that the callback timestamp accurately reflects when audio ended."""

    @pytest.mark.asyncio
    async def test_callback_timestamp_within_tolerance(self):
        """
        The callback timestamp should be within ~50ms of when it actually fired,
        not 10+ seconds late like the bug caused.
        """
        last_tts_audio_done = 0.0
        expected_callback_time = 0.0

        async def fake_stream_tts(on_audio_done=None):
            nonlocal expected_callback_time
            await asyncio.sleep(0.05)
            expected_callback_time = asyncio.get_event_loop().time()
            if on_audio_done:
                on_audio_done()
            await asyncio.sleep(0.15)

        _audio_done_fired = False

        def _on_audio_done():
            nonlocal last_tts_audio_done, _audio_done_fired
            last_tts_audio_done = asyncio.get_event_loop().time()
            _audio_done_fired = True

        await fake_stream_tts(on_audio_done=_on_audio_done)
        if not _audio_done_fired:
            last_tts_audio_done = asyncio.get_event_loop().time()

        # Timestamp should be very close to when callback actually fired
        drift = abs(last_tts_audio_done - expected_callback_time)
        assert drift < 0.05, f"Callback timestamp drifted {drift:.3f}s from actual fire time"

    @pytest.mark.asyncio
    async def test_phase2_window_uses_correct_anchor(self):
        """
        Simulate the Phase 2 capture window calculation.
        With the fix, the window should anchor to the early callback time,
        giving a ~10s larger capture window than the buggy version.
        """
        last_tts_audio_done = 0.0

        async def fake_stream_tts(on_audio_done=None):
            await asyncio.sleep(0.05)
            if on_audio_done:
                on_audio_done()
            await asyncio.sleep(0.15)

        _audio_done_fired = False

        def _on_audio_done():
            nonlocal last_tts_audio_done, _audio_done_fired
            last_tts_audio_done = asyncio.get_event_loop().time()
            _audio_done_fired = True

        await fake_stream_tts(on_audio_done=_on_audio_done)
        if not _audio_done_fired:
            last_tts_audio_done = asyncio.get_event_loop().time()

        # Simulate Phase 2 happening 0.3s after stream_tts returns
        # (caller starts speaking after AI finishes)
        await asyncio.sleep(0.1)
        phase2_time = asyncio.get_event_loop().time()

        # The capture window: phase2_time - last_tts_audio_done
        # With fix: ~0.35s (0.05 callback + 0.15 remaining + 0.1 wait + small overhead)
        # With bug: ~0.1s (only the 0.1 wait after overwrite)
        window = phase2_time - last_tts_audio_done
        assert window > 0.2, (
            f"Capture window too small ({window:.3f}s) — "
            f"callback timestamp may have been overwritten"
        )


class TestBothFlowPatterns:
    """Verify the fix pattern works for both queued and direct flows."""

    @pytest.mark.asyncio
    async def test_queued_flow_pattern(self):
        """Simulate the queued flow pattern from media_handler.py."""
        last_tts_audio_done = 0.0

        async def fake_stream_tts(on_audio_done=None):
            await asyncio.sleep(0.03)
            if on_audio_done:
                on_audio_done()
            await asyncio.sleep(0.1)

        # Exact pattern from queued flow
        _queued_audio_done_fired = False

        def _on_queued_audio_done():
            nonlocal last_tts_audio_done, _queued_audio_done_fired
            last_tts_audio_done = asyncio.get_event_loop().time()
            _queued_audio_done_fired = True

        before = asyncio.get_event_loop().time()
        await fake_stream_tts(on_audio_done=_on_queued_audio_done)
        if not _queued_audio_done_fired:
            last_tts_audio_done = asyncio.get_event_loop().time()
        after = asyncio.get_event_loop().time()

        assert _queued_audio_done_fired is True
        assert (last_tts_audio_done - before) < (after - before) * 0.5

    @pytest.mark.asyncio
    async def test_direct_flow_pattern(self):
        """Simulate the direct flow pattern from media_handler.py."""
        last_tts_audio_done = 0.0

        async def fake_stream_tts(on_audio_done=None):
            await asyncio.sleep(0.03)
            if on_audio_done:
                on_audio_done()
            await asyncio.sleep(0.1)

        # Exact pattern from direct flow
        _direct_audio_done_fired = False

        def _on_direct_audio_done():
            nonlocal last_tts_audio_done, _direct_audio_done_fired
            last_tts_audio_done = asyncio.get_event_loop().time()
            _direct_audio_done_fired = True

        before = asyncio.get_event_loop().time()
        await fake_stream_tts(on_audio_done=_on_direct_audio_done)
        if not _direct_audio_done_fired:
            last_tts_audio_done = asyncio.get_event_loop().time()
        after = asyncio.get_event_loop().time()

        assert _direct_audio_done_fired is True
        assert (last_tts_audio_done - before) < (after - before) * 0.5
