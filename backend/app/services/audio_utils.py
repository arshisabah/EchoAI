# app/services/audio_utils.py
"""
Audio utility functions for processing audio data.
"""

import io
import wave
import struct
import logging
import numpy as np
from typing import Tuple

logger = logging.getLogger(__name__)


def bytes_to_numpy(audio_bytes: bytes, sample_rate: int = 16000) -> Tuple[np.ndarray, int]:
    """
    Convert audio bytes to numpy array.
    
    Supports:
    - WAV format
    - Raw PCM16
    - WebM (via soundfile)
    
    Args:
        audio_bytes: Raw audio data
        sample_rate: Target sample rate
        
    Returns:
        Tuple of (audio_array, sample_rate)
    """
    try:
        # Try as WAV first
        return _bytes_to_numpy_wav(audio_bytes, sample_rate)
    except Exception as e:
        logger.debug(f"Not WAV format: {e}")
        
    try:
        # Try with soundfile (handles more formats)
        return _bytes_to_numpy_soundfile(audio_bytes, sample_rate)
    except Exception as e:
        logger.debug(f"Soundfile failed: {e}")
        
    try:
        # Fallback to raw PCM16
        return _bytes_to_numpy_raw(audio_bytes, sample_rate)
    except Exception as e:
        logger.error(f"All audio conversion methods failed: {e}")
        return np.array([], dtype=np.float32), sample_rate


def _bytes_to_numpy_wav(audio_bytes: bytes, target_sr: int) -> Tuple[np.ndarray, int]:
    """Convert WAV bytes to numpy array."""
    audio_io = io.BytesIO(audio_bytes)
    
    with wave.open(audio_io, 'rb') as wav_file:
        sample_rate = wav_file.getframerate()
        n_channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        n_frames = wav_file.getnframes()
        
        # Read audio data
        audio_data = wav_file.readframes(n_frames)
        
        # Convert to numpy array
        if sample_width == 2:  # 16-bit
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
        elif sample_width == 4:  # 32-bit
            audio_array = np.frombuffer(audio_data, dtype=np.int32)
        else:
            raise ValueError(f"Unsupported sample width: {sample_width}")
        
        # Convert to float32 [-1.0, 1.0]
        audio_array = audio_array.astype(np.float32) / 32768.0
        
        # Handle stereo -> mono
        if n_channels > 1:
            audio_array = audio_array.reshape(-1, n_channels)
            audio_array = np.mean(audio_array, axis=1)
        
        # Resample if needed
        if sample_rate != target_sr:
            audio_array = resample_audio(audio_array, sample_rate, target_sr)
            sample_rate = target_sr
        
        return audio_array, sample_rate


def _bytes_to_numpy_soundfile(audio_bytes: bytes, target_sr: int) -> Tuple[np.ndarray, int]:
    """Convert audio bytes using soundfile library."""
    import soundfile as sf
    
    audio_io = io.BytesIO(audio_bytes)
    audio_array, sample_rate = sf.read(audio_io, dtype='float32')
    
    # Handle stereo
    if len(audio_array.shape) > 1:
        audio_array = np.mean(audio_array, axis=1)
    
    # Resample if needed
    if sample_rate != target_sr:
        audio_array = resample_audio(audio_array, sample_rate, target_sr)
        sample_rate = target_sr
    
    return audio_array, sample_rate


def _bytes_to_numpy_raw(audio_bytes: bytes, sample_rate: int) -> Tuple[np.ndarray, int]:
    """Convert raw PCM16 bytes to numpy array."""
    # Assume raw PCM16 (little-endian)
    n_samples = len(audio_bytes) // 2
    
    if n_samples == 0:
        return np.array([], dtype=np.float32), sample_rate
    
    # Unpack as signed 16-bit integers
    fmt = "<" + "h" * n_samples
    int16_data = struct.unpack(fmt, audio_bytes)
    
    # Convert to float32 [-1.0, 1.0]
    audio_array = np.array(int16_data, dtype=np.float32) / 32768.0
    
    return audio_array, sample_rate


def resample_audio(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """
    Resample audio to target sample rate.
    
    Args:
        audio: Audio array
        orig_sr: Original sample rate
        target_sr: Target sample rate
        
    Returns:
        Resampled audio array
    """
    if orig_sr == target_sr:
        return audio
    
    try:
        import librosa
        return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)
    except ImportError:
        logger.warning("librosa not available, using simple resampling")
        return simple_resample(audio, orig_sr, target_sr)


def simple_resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Simple linear interpolation resampling."""
    duration = len(audio) / orig_sr
    target_length = int(duration * target_sr)
    
    if target_length == 0:
        return np.array([], dtype=np.float32)
    
    # Linear interpolation
    x_old = np.linspace(0, len(audio) - 1, len(audio))
    x_new = np.linspace(0, len(audio) - 1, target_length)
    
    audio_resampled = np.interp(x_new, x_old, audio)
    
    return audio_resampled.astype(np.float32)


def normalize_audio(audio: np.ndarray, target_db: float = -20.0) -> np.ndarray:
    """
    Normalize audio to target dB level.
    
    Args:
        audio: Audio array
        target_db: Target dB level
        
    Returns:
        Normalized audio
    """
    if len(audio) == 0:
        return audio
    
    # Calculate RMS
    rms = np.sqrt(np.mean(audio ** 2))
    
    if rms == 0:
        return audio
    
    # Convert target dB to linear scale
    target_linear = 10 ** (target_db / 20.0)
    
    # Normalize
    normalized = audio * (target_linear / rms)
    
    # Clip to [-1.0, 1.0]
    normalized = np.clip(normalized, -1.0, 1.0)
    
    return normalized


def split_audio_chunks(
    audio: np.ndarray, 
    sample_rate: int, 
    chunk_duration_ms: int = 1000
) -> list:
    """
    Split audio into chunks.
    
    Args:
        audio: Audio array
        sample_rate: Sample rate
        chunk_duration_ms: Chunk duration in milliseconds
        
    Returns:
        List of audio chunks
    """
    chunk_size = int(sample_rate * chunk_duration_ms / 1000)
    
    chunks = []
    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i + chunk_size]
        if len(chunk) > 0:
            chunks.append(chunk)
    
    return chunks


def detect_silence(
    audio: np.ndarray, 
    sample_rate: int,
    silence_threshold: float = 0.01,
    min_silence_duration_ms: int = 500
) -> list:
    """
    Detect silent regions in audio.
    
    Args:
        audio: Audio array
        sample_rate: Sample rate
        silence_threshold: Amplitude threshold for silence
        min_silence_duration_ms: Minimum silence duration in ms
        
    Returns:
        List of (start, end) tuples for silent regions
    """
    # Calculate energy in short windows
    window_size = int(sample_rate * 0.02)  # 20ms windows
    hop_size = window_size // 2
    
    energy = []
    for i in range(0, len(audio) - window_size, hop_size):
        window = audio[i:i + window_size]
        energy.append(np.sqrt(np.mean(window ** 2)))
    
    # Find silent regions
    is_silent = np.array(energy) < silence_threshold
    
    # Merge nearby silent regions
    min_silence_frames = int(min_silence_duration_ms / 1000 * sample_rate / hop_size)
    
    silent_regions = []
    start = None
    
    for i, silent in enumerate(is_silent):
        if silent and start is None:
            start = i * hop_size
        elif not silent and start is not None:
            end = i * hop_size
            if (end - start) >= min_silence_frames * hop_size:
                silent_regions.append((start / sample_rate, end / sample_rate))
            start = None
    
    return silent_regions


def remove_silence(
    audio: np.ndarray,
    sample_rate: int,
    silence_threshold: float = 0.01
) -> np.ndarray:
    """Remove silent portions from audio."""
    silent_regions = detect_silence(audio, sample_rate, silence_threshold)
    
    if not silent_regions:
        return audio
    
    # Keep non-silent portions
    non_silent_audio = []
    last_end = 0
    
    for start, end in silent_regions:
        start_sample = int(start * sample_rate)
        non_silent_audio.append(audio[last_end:start_sample])
        last_end = int(end * sample_rate)
    
    # Add remaining audio
    non_silent_audio.append(audio[last_end:])
    
    # Concatenate
    result = np.concatenate(non_silent_audio)
    
    return result