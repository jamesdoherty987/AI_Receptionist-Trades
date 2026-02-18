# Filler Audio Debugging Guide

## Overview

The filler audio system provides instant audio feedback to callers while the AI processes their request. Instead of silence during tool execution (database queries, etc.), the caller hears "Let me check that for you" or similar phrases.

## How It Works

1. **Pre-recorded audio files** are stored in R2 bucket (Cloudflare)
2. **At server startup**, files are downloaded and cached in memory
3. **When a tool call is detected**, the filler plays INSTANTLY (no TTS latency)
4. **Tool execution happens IN PARALLEL** with audio playback

## What to Look For in Logs

When a call comes in and the user asks something that triggers a tool call (like "what times are available tomorrow"), you should see these log messages:

### 1. Pre-Check Detection (IMMEDIATE - before OpenAI)
```
🚀 PRE-CHECK: Availability check detected
🗣️ [PRE-CHECK] Speaking BEFORE OpenAI call at X.XXX: 'Let me check that for you.'
```

### 2. SPLIT_TTS Marker
```
🔀 SPLIT_TTS MARKER DETECTED (fast path): 'Let me check that for you.'
📊 Pre-recorded fillers available: True
📊 Filler ID: one_moment, Audio bytes: XXXX
```

### 3. Parallel Execution
```
⚡ [PARALLEL] Starting TRUE PARALLEL at X.XXX
⚡ [PARALLEL] Creating prefetch task...
⚡ [PARALLEL] Creating audio task...
[AUDIO] 🔊 Sending XXXX bytes (XXXms) of pre-recorded audio
[AUDIO] ✅ Sent XX chunks in X.XXXs
✓ [PARALLEL] Audio send complete in X.XXXs
```

### 4. Tool Execution (happens in parallel)
```
🔧 [TOOL_PHASE] Starting tool execution at X.XXX
🔧 [TOOL_EXEC] Executing: check_availability
🔧 [TOOL_EXEC] Tool check_availability completed in X.XXs
```

### 5. Prefetch Progress
```
⚡ [PREFETCH] Starting prefetch at X.XXX
⚡ [PREFETCH] Token #1 at X.XXXs: 'I have...'
⚡ [PREFETCH] Complete: XX tokens in X.XXXs
```

### 6. Continuation TTS
```
🔄 [CONTINUATION] Starting second TTS session at X.XXX
⚡ [CONTINUATION] Prefetch ready after X.XXXs: XX tokens available
```

## Expected Timing

For good user experience:
- SPLIT_TTS marker: within 0.1s of detecting tool need
- Pre-recorded audio starts: within 0.2s
- Tool execution: 0.5-2s (database dependent)
- Follow-up response: within 2-3s total

## Common Issues

### "No pre-recorded fillers available"
- **Cause**: R2_PUBLIC_URL not configured
- **Solution**: Set R2_PUBLIC_URL in .env, then run `python scripts/generate_filler_audio.py`

### Large gap between filler and content
- **Cause**: Slow tool execution or OpenAI API
- **Solution**: Check database performance, network latency

### Filler not playing at all
- **Cause**: Pre-check detection not triggering
- **Solution**: Check if user message contains expected keywords

## Testing

Run the test script (no API keys needed):
```bash
python tests/test_filler_parallel.py
```

This verifies:
1. Pre-recorded audio loading from R2
2. Filler trigger phrase detection
3. Parallel execution flow
4. Full mock stream flow
