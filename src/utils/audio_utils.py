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
    
    Uses per-packet energy detection to find where speech starts and ends,
    then returns only the speech portion with a small padding on each side.
    
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
    
    # Find first packet above threshold (speech start)
    first_voice = -1
    for i in range(n):
        if ulaw_energy(packets[i]) >= energy_threshold:
            first_voice = i
            break
    
    if first_voice < 0:
        # No speech detected at all — return everything (let caller decide)
        return b''.join(packets)
    
    # Find last packet above threshold (speech end)
    last_voice = first_voice
    for i in range(n - 1, first_voice - 1, -1):
        if ulaw_energy(packets[i]) >= energy_threshold:
            last_voice = i
            break
    
    # Add padding
    start = max(0, first_voice - pad_packets)
    end = min(n, last_voice + pad_packets + 1)
    
    trimmed = b''.join(packets[start:end])
    total_bytes = sum(len(p) for p in packets)
    trimmed_duration = len(trimmed) / sample_rate
    original_duration = total_bytes / sample_rate
    
    # Log energy distribution for debugging
    energies = [ulaw_energy(p) for p in packets]
    above_threshold = sum(1 for e in energies if e >= energy_threshold)
    max_energy = max(energies) if energies else 0
    min_energy = min(energies) if energies else 0
    avg_energy = sum(energies) / len(energies) if energies else 0
    
    print(f"🎙️ [ADDR_AUDIO] Trimmed: {original_duration:.1f}s → {trimmed_duration:.1f}s "
          f"(packets {start}-{end-1} of {n}, threshold={energy_threshold})")
    print(f"🎙️ [ADDR_AUDIO] Energy: min={min_energy:.0f}, max={max_energy:.0f}, avg={avg_energy:.0f}, "
          f"above_threshold={above_threshold}/{n}, first_voice={first_voice}, last_voice={last_voice}")
    
    return trimmed

