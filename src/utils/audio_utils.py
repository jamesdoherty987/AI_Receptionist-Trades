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

