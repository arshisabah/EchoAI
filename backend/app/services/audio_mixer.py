"""
Audio mixing service for combining multiple participant streams.
"""

import logging
from typing import List, Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)


class AudioMixer:
    """Mix audio from multiple participants."""
    
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
    
    def mix_streams(
        self, 
        audio_streams: List[np.ndarray],
        normalize: bool = True
    ) -> np.ndarray:
        """
        Mix multiple audio streams into one.
        
        Args:
            audio_streams: List of audio arrays to mix
            normalize: Whether to normalize the output
            
        Returns:
            Mixed audio as numpy array
        """
        if not audio_streams:
            return np.array([], dtype=np.float32)
        
        # Filter out empty streams
        valid_streams = [s for s in audio_streams if len(s) > 0]
        
        if not valid_streams:
            return np.array([], dtype=np.float32)
        
        # Find maximum length
        max_length = max(len(stream) for stream in valid_streams)
        
        # Initialize output buffer
        mixed = np.zeros(max_length, dtype=np.float32)
        
        # Add all streams
        for stream in valid_streams:
            # Pad shorter streams with zeros
            if len(stream) < max_length:
                padded = np.pad(stream, (0, max_length - len(stream)), mode='constant')
            else:
                padded = stream
            
            mixed += padded
        
        # Normalize to prevent clipping
        if normalize and len(valid_streams) > 0:
            # Use average mixing (divide by number of streams)
            mixed = mixed / len(valid_streams)
            
            # Additional normalization if still clipping
            max_val = np.max(np.abs(mixed))
            if max_val > 1.0:
                mixed = mixed / max_val
        
        return mixed
    
    def mix_with_weights(
        self,
        audio_streams: List[np.ndarray],
        weights: List[float]
    ) -> np.ndarray:
        """
        Mix audio streams with custom weights.
        
        Args:
            audio_streams: List of audio arrays
            weights: List of weights (one per stream)
            
        Returns:
            Weighted mixed audio
        """
        if not audio_streams or not weights:
            return np.array([], dtype=np.float32)
        
        if len(audio_streams) != len(weights):
            logger.warning("Stream and weight count mismatch, using equal weights")
            return self.mix_streams(audio_streams)
        
        # Filter valid streams
        valid_pairs = [(s, w) for s, w in zip(audio_streams, weights) if len(s) > 0]
        
        if not valid_pairs:
            return np.array([], dtype=np.float32)
        
        valid_streams, valid_weights = zip(*valid_pairs)
        
        # Normalize weights
        weight_sum = sum(valid_weights)
        if weight_sum > 0:
            normalized_weights = [w / weight_sum for w in valid_weights]
        else:
            normalized_weights = [1.0 / len(valid_weights)] * len(valid_weights)
        
        # Find maximum length
        max_length = max(len(stream) for stream in valid_streams)
        
        # Initialize output
        mixed = np.zeros(max_length, dtype=np.float32)
        
        # Mix with weights
        for stream, weight in zip(valid_streams, normalized_weights):
            if len(stream) < max_length:
                padded = np.pad(stream, (0, max_length - len(stream)), mode='constant')
            else:
                padded = stream
            
            mixed += padded * weight
        
        # Prevent clipping
        max_val = np.max(np.abs(mixed))
        if max_val > 1.0:
            mixed = mixed / max_val
        
        return mixed


# Singleton instance
_audio_mixer: Optional[AudioMixer] = None


def get_audio_mixer() -> AudioMixer:
    """Get singleton audio mixer instance."""
    global _audio_mixer
    if _audio_mixer is None:
        _audio_mixer = AudioMixer()
    return _audio_mixer
