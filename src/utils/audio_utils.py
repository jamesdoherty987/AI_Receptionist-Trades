"""
Audio utility functions for processing mulaw audio
"""

MU_LAW_DECODE_TABLE = [0] * 256


def build_mulaw():
    """Build mulaw decoding lookup table"""
    for i in range(256):
        mu = (~i) & 0xFF
        sign = mu & 0x80
        exponent = (mu >> 4) & 0x07
        mantissa = mu & 0x0F
        sample = ((mantissa << 3) + 0x84) << exponent
        sample -= 0x84
        if sign:
            sample = -sample
        MU_LAW_DECODE_TABLE[i] = max(-32768, min(32767, sample))


build_mulaw()


def ulaw_energy(frame: bytes) -> float:
    """
    Calculate energy level from mulaw audio frame
    
    Args:
        frame: Raw mulaw audio bytes
        
    Returns:
        RMS energy value
    """
    if not frame:
        return 0.0
    total = 0
    for b in frame:
        s = MU_LAW_DECODE_TABLE[b]
        total += s * s
    return (total / len(frame)) ** 0.5

def mulaw_to_wav(mulaw_data: bytes, sample_rate: int = 8000) -> bytes:
    """
    Convert raw mulaw audio bytes to WAV format for browser playback.

    Args:
        mulaw_data: Raw mulaw-encoded audio bytes
        sample_rate: Sample rate (default 8kHz for Twilio)

    Returns:
        Complete WAV file as bytes (PCM 16-bit mono)
    """
    import struct

    if not mulaw_data:
        raise ValueError("mulaw_data cannot be empty")

    num_samples = len(mulaw_data)

    # Decode mulaw to 16-bit PCM
    pcm_samples = bytearray(num_samples * 2)
    for i in range(num_samples):
        sample = MU_LAW_DECODE_TABLE[mulaw_data[i]]
        struct.pack_into('<h', pcm_samples, i * 2, sample)

    # Build WAV header (44 bytes)
    data_size = len(pcm_samples)
    file_size = 36 + data_size

    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', file_size, b'WAVE',
        b'fmt ', 16,           # fmt chunk size
        1,                     # PCM format
        1,                     # mono
        sample_rate,           # sample rate
        sample_rate * 2,       # byte rate (16-bit mono)
        2,                     # block align
        16,                    # bits per sample
        b'data', data_size     # data chunk
    )

    return bytes(header) + bytes(pcm_samples)


def trim_silence_mulaw(packets: list, energy_threshold: float = 100.0,
                       pad_packets: int = 10, sample_rate: int = 8000) -> bytes:
    """
    Trim leading and trailing silence from a list of mulaw audio packets.
    
    Uses an adaptive noise-floor approach for the leading edge:
    - Estimates the noise floor from the quietest 25% of packets
    - Sets the effective threshold at max(energy_threshold, noise_floor * 3)
    - This reliably cuts through line noise / ambient hum that sits just
      below the fixed threshold on phone calls (typically RMS 10-30)
    
    Then uses a sliding-window to detect speech onset/offset:
    - Scans with a window of WINDOW_SIZE packets
    - Speech starts when MIN_ACTIVE packets in the window exceed the threshold
    - This catches the beginning of speech even if the first syllable is soft
    
    Args:
        packets: List of raw mulaw byte packets (e.g., from a deque)
        energy_threshold: RMS energy below this is considered silence (default 100)
        pad_packets: Number of silent packets to keep before/after speech (~20ms each)
        sample_rate: Sample rate for duration calculation (default 8kHz)
    
    Returns:
        Concatenated mulaw bytes containing only the speech portion.
        Returns all packets joined if no speech boundary is found.
    """
    if not packets:
        return b''
    
    n = len(packets)
    energies = [ulaw_energy(p) for p in packets]
    
    # Adaptive noise floor: sort energies, take the 25th percentile as the
    # noise floor estimate. Real speech is typically 5-10x louder than line noise.
    # Use max(caller's threshold, noise_floor * 2.5) so we reliably cut through
    # whatever ambient level this particular call has.
    # Cap at 2x the fixed threshold so we never get too aggressive on noisy calls
    # (e.g. mobile with noise_floor=25 → adaptive=62, not 75).
    sorted_energies = sorted(energies)
    noise_floor_idx = min(max(0, n // 4 - 1), n - 1)  # Clamp to valid index
    noise_floor = sorted_energies[noise_floor_idx] if sorted_energies else 0
    adaptive_threshold = min(
        max(energy_threshold, noise_floor * 2.5),
        energy_threshold * 2.0  # Never more than 2x the caller's threshold
    )
    
    # Sliding window parameters: look for 3+ active packets in a window of 5
    # Each packet is ~20ms, so window = 100ms, need 60ms of energy = speech onset
    WINDOW_SIZE = 5
    MIN_ACTIVE = 3
    
    # Find speech start: first window where enough packets are above threshold
    first_voice = -1
    for i in range(n - WINDOW_SIZE + 1):
        window = energies[i:i + WINDOW_SIZE]
        active = sum(1 for e in window if e >= adaptive_threshold)
        if active >= MIN_ACTIVE:
            # Speech detected — but the actual start might be a few packets
            # before this window. Walk backwards to find the first packet in
            # this cluster that's above threshold (or a lower "onset" threshold).
            onset_threshold = adaptive_threshold * 0.5  # Catch soft starts
            first_voice = i
            for j in range(i, max(-1, i - pad_packets), -1):
                if energies[j] >= onset_threshold:
                    first_voice = j
                else:
                    break
            break
    
    if first_voice < 0:
        # No speech detected at all — return everything (let caller decide)
        return b''.join(packets)
    
    # Find speech end: last window where enough packets are above threshold
    # Use the original (lower) threshold for the trailing edge — we'd rather
    # keep a bit of trailing silence than clip the end of an eircode.
    last_voice = first_voice
    for i in range(n - WINDOW_SIZE, first_voice - 1, -1):
        window = energies[i:i + WINDOW_SIZE]
        active = sum(1 for e in window if e >= energy_threshold)
        if active >= MIN_ACTIVE:
            # Walk forward to find the last active packet in this cluster
            onset_threshold = energy_threshold * 0.5
            last_voice = i + WINDOW_SIZE - 1
            for j in range(i + WINDOW_SIZE - 1, min(n, i + WINDOW_SIZE + pad_packets)):
                if j < n and energies[j] >= onset_threshold:
                    last_voice = j
                else:
                    break
            break
    
    # Leading padding: 10 packets (~200ms) — enough to catch soft speech onset
    # without letting seconds of dead air through. Still conservative.
    # Trailing padding: full pad_packets to avoid clipping final syllable.
    lead_pad = min(pad_packets, 10)
    start = max(0, first_voice - lead_pad)
    end = min(n, last_voice + pad_packets + 1)
    
    trimmed = b''.join(packets[start:end])
    total_bytes = sum(len(p) for p in packets)
    trimmed_duration = len(trimmed) / sample_rate
    original_duration = total_bytes / sample_rate
    
    # Log energy distribution for debugging
    above_threshold = sum(1 for e in energies if e >= adaptive_threshold)
    max_energy = max(energies) if energies else 0
    min_energy = min(energies) if energies else 0
    avg_energy = sum(energies) / len(energies) if energies else 0
    
    print(f"🎙️ [ADDR_AUDIO] Trimmed: {original_duration:.1f}s → {trimmed_duration:.1f}s "
          f"(packets {start}-{end-1} of {n})")
    print(f"🎙️ [ADDR_AUDIO] Threshold: fixed={energy_threshold}, noise_floor={noise_floor:.0f}, "
          f"adaptive={adaptive_threshold:.0f}")
    print(f"🎙️ [ADDR_AUDIO] Energy: min={min_energy:.0f}, max={max_energy:.0f}, avg={avg_energy:.0f}, "
          f"above_threshold={above_threshold}/{n}, first_voice={first_voice}, last_voice={last_voice}")
    
    return trimmed

