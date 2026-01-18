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
