# backend/services/audio_utils.py
"""
Audio utility functions for EchoAI.

Responsibilities:
- Convert raw PCM or WAV audio bytes to numpy arrays
- Ensure sample rate is correct (default 16kHz)
- Normalize to float32 in range [-1.0, 1.0]
"""

import io
import wave
import numpy as np
import soundfile as sf
from typing import Tuple


def bytes_to_numpy(audio_bytes: bytes, sample_rate: int = 16000) -> Tuple[np.ndarray, int]:
    """
    Convert raw audio bytes (PCM16 or WAV) to numpy float32 array for WhisperX.

    Returns:
        audio_array: np.ndarray (float32, shape=(n_samples,))
        sr: int (sample_rate)
    """
    try:
        # Try reading as WAV using soundfile
        audio_io = io.BytesIO(audio_bytes)
        data, sr = sf.read(audio_io, dtype="float32")
        # Ensure mono
        if len(data.shape) > 1:
            data = np.mean(data, axis=1)
        # Resample if needed
        if sr != sample_rate:
            import librosa
            data = librosa.resample(data, orig_sr=sr, target_sr=sample_rate)
            sr = sample_rate
        return data, sr
    except Exception:
        # Fallback: raw PCM16 bytes
        # Convert bytes -> int16 -> float32
        import struct
        import math

        n_samples = len(audio_bytes) // 2
        fmt = "<" + "h" * n_samples
        int16_data = struct.unpack(fmt, audio_bytes)
        data = np.array(int16_data, dtype=np.float32) / 32768.0  # normalize
        return data, sample_rate
