# backend/app/services/audio_preprocessing.py
"""
Advanced audio preprocessing for improved transcription accuracy.
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)

try:
    import scipy.signal as signal
    SCIPY_AVAILABLE = True
except ImportError:
    logger.warning("scipy not available - some preprocessing features disabled")
    SCIPY_AVAILABLE = False


def preprocess_audio_for_transcription(
    audio_array: np.ndarray, 
    sample_rate: int = 16000
) -> np.ndarray:
    """
    Preprocess audio to improve transcription accuracy.
    
    Args:
        audio_array: Input audio array
        sample_rate: Sample rate in Hz
        
    Returns:
        Preprocessed audio array
    """
    if len(audio_array) == 0:
        return audio_array
    
    # 1. Remove DC offset (removes constant noise)
    audio_array = audio_array - np.mean(audio_array)
    
    # 2. Apply high-pass filter to remove low-frequency noise (< 80Hz)
    if SCIPY_AVAILABLE:
        try:
            sos = signal.butter(4, 80, 'hp', fs=sample_rate, output='sos')
            audio_array = signal.sosfilt(sos, audio_array)
        except Exception as e:
            logger.debug(f"High-pass filter failed: {e}")
    
    # 3. Gentle normalization with soft clipping
    max_val = np.max(np.abs(audio_array))
    if max_val > 0.01:
        audio_array = audio_array / max_val * 0.85  # Leave 15% headroom
    
    # 4. Apply soft limiting to prevent clipping artifacts
    audio_array = np.tanh(audio_array * 1.2) / 1.2
    
    return audio_array.astype(np.float32)