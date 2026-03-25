"""
Audio conversion utilities for µ-law and PCM16 formats.

Voice Live API uses PCM16 at 24kHz
Genesys AudioConnector uses g711_ulaw at 8kHz
"""
import numpy as np
from typing import Union

# µ-law decode table (8-bit µ-law to 16-bit PCM)
ULAW_DECODE_TABLE = np.array([
    -32124, -31100, -30076, -29052, -28028, -27004, -25980, -24956,
    -23932, -22908, -21884, -20860, -19836, -18812, -17788, -16764,
    -15996, -15484, -14972, -14460, -13948, -13436, -12924, -12412,
    -11900, -11388, -10876, -10364, -9852, -9340, -8828, -8316,
    -7932, -7676, -7420, -7164, -6908, -6652, -6396, -6140,
    -5884, -5628, -5372, -5116, -4860, -4604, -4348, -4092,
    -3900, -3772, -3644, -3516, -3388, -3260, -3132, -3004,
    -2876, -2748, -2620, -2492, -2364, -2236, -2108, -1980,
    -1884, -1820, -1756, -1692, -1628, -1564, -1500, -1436,
    -1372, -1308, -1244, -1180, -1116, -1052, -988, -924,
    -876, -844, -812, -780, -748, -716, -684, -652,
    -620, -588, -556, -524, -492, -460, -428, -396,
    -372, -356, -340, -324, -308, -292, -276, -260,
    -244, -228, -212, -196, -180, -164, -148, -132,
    -120, -112, -104, -96, -88, -80, -72, -64,
    -56, -48, -40, -32, -24, -16, -8, 0,
    32124, 31100, 30076, 29052, 28028, 27004, 25980, 24956,
    23932, 22908, 21884, 20860, 19836, 18812, 17788, 16764,
    15996, 15484, 14972, 14460, 13948, 13436, 12924, 12412,
    11900, 11388, 10876, 10364, 9852, 9340, 8828, 8316,
    7932, 7676, 7420, 7164, 6908, 6652, 6396, 6140,
    5884, 5628, 5372, 5116, 4860, 4604, 4348, 4092,
    3900, 3772, 3644, 3516, 3388, 3260, 3132, 3004,
    2876, 2748, 2620, 2492, 2364, 2236, 2108, 1980,
    1884, 1820, 1756, 1692, 1628, 1564, 1500, 1436,
    1372, 1308, 1244, 1180, 1116, 1052, 988, 924,
    876, 844, 812, 780, 748, 716, 684, 652,
    620, 588, 556, 524, 492, 460, 428, 396,
    372, 356, 340, 324, 308, 292, 276, 260,
    244, 228, 212, 196, 180, 164, 148, 132,
    120, 112, 104, 96, 88, 80, 72, 64,
    56, 48, 40, 32, 24, 16, 8, 0
], dtype=np.int16)

# µ-law encode table for segment lookup
ULAW_ENCODE_TABLE = np.array([
    0, 0, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7
], dtype=np.uint8)


def cubic_interpolate(y0: float, y1: float, y2: float, y3: float, t: float) -> int:
    """Cubic interpolation helper for smoother upsampling."""
    a0 = y3 - y2 - y0 + y1
    a1 = y0 - y1 - a0
    a2 = y2 - y0
    a3 = y1
    return int(round(a0 * t * t * t + a1 * t * t + a2 * t + a3))


def ulaw_to_pcm16_24khz(ulaw_data: bytes) -> bytes:
    """
    Convert µ-law (8kHz) to PCM16 and upsample to 24kHz.
    Uses cubic interpolation for smoother, higher quality audio.
    
    Args:
        ulaw_data: Input µ-law audio bytes at 8kHz
        
    Returns:
        PCM16 audio bytes at 24kHz
    """
    # Decode µ-law to PCM16 at 8kHz
    ulaw_array = np.frombuffer(ulaw_data, dtype=np.uint8)
    pcm_8khz = ULAW_DECODE_TABLE[ulaw_array].astype(np.int16)
    
    # Upsample from 8kHz to 24kHz (3x) using cubic interpolation
    pcm_24khz = np.zeros(len(pcm_8khz) * 3, dtype=np.int16)
    
    for i in range(len(pcm_8khz)):
        # Get 4 samples for cubic interpolation (with boundary handling)
        y0 = pcm_8khz[i - 1] if i > 0 else pcm_8khz[i]
        y1 = pcm_8khz[i]
        y2 = pcm_8khz[i + 1] if i < len(pcm_8khz) - 1 else pcm_8khz[i]
        y3 = pcm_8khz[i + 2] if i < len(pcm_8khz) - 2 else y2
        
        # Original sample
        pcm_24khz[i * 3] = y1
        # Cubic interpolation at 1/3 and 2/3 positions
        pcm_24khz[i * 3 + 1] = cubic_interpolate(y0, y1, y2, y3, 1/3)
        pcm_24khz[i * 3 + 2] = cubic_interpolate(y0, y1, y2, y3, 2/3)
    
    return pcm_24khz.tobytes()


def linear_to_ulaw(sample: int) -> int:
    """Convert a single PCM16 sample to µ-law."""
    BIAS = 0x84
    CLIP = 32635
    
    # Determine sign and make sample positive
    if sample < 0:
        sign = 0x80
        sample = -sample
    else:
        sign = 0
    
    # Clip to max value
    if sample > CLIP:
        sample = CLIP
    
    sample = sample + BIAS
    
    # Ensure we don't go out of bounds for the lookup table
    lookup_idx = (sample >> 7) & 0xFF
    if lookup_idx >= len(ULAW_ENCODE_TABLE):
        lookup_idx = len(ULAW_ENCODE_TABLE) - 1
    
    exponent = int(ULAW_ENCODE_TABLE[lookup_idx])
    mantissa = (sample >> (exponent + 3)) & 0x0F
    
    return (~(sign | (exponent << 4) | mantissa)) & 0xFF


def pcm16_24khz_to_ulaw(pcm_24khz_base64: str) -> bytes:
    """
    Convert PCM16 at 24kHz to µ-law at 8kHz (downsample 3x).
    Uses averaging filter before downsampling to reduce aliasing artifacts.
    
    Args:
        pcm_24khz_base64: Base64 encoded PCM16 audio at 24kHz
        
    Returns:
        µ-law audio bytes at 8kHz
    """
    import base64
    
    pcm_buffer = base64.b64decode(pcm_24khz_base64)
    pcm_24khz = np.frombuffer(pcm_buffer, dtype=np.int16)
    
    # Downsample from 24kHz to 8kHz using averaging filter (anti-aliasing)
    ulaw_length = len(pcm_24khz) // 3
    ulaw_data = np.zeros(ulaw_length, dtype=np.uint8)
    
    for i in range(ulaw_length):
        idx = i * 3
        # Average 3 samples for anti-aliasing before downsampling
        sample0 = pcm_24khz[idx] if idx < len(pcm_24khz) else 0
        sample1 = pcm_24khz[idx + 1] if idx + 1 < len(pcm_24khz) else 0
        sample2 = pcm_24khz[idx + 2] if idx + 2 < len(pcm_24khz) else 0
        avg_sample = int(round((int(sample0) + int(sample1) + int(sample2)) / 3))
        ulaw_data[i] = linear_to_ulaw(avg_sample)
    
    return ulaw_data.tobytes()
