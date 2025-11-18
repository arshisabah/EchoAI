"""
Audio recording module for meeting rooms.
Records and stores audio from all participants during meetings.
"""

import io
import logging
import wave
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Records audio from multiple participants in a meeting."""
    
    def __init__(self, room_id: str, sample_rate: int = 16000):
        self.room_id = room_id
        self.sample_rate = sample_rate
        self.is_recording = False
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
        # Store audio chunks per participant
        self.participant_chunks: Dict[str, List[np.ndarray]] = defaultdict(list)
        
        # Mixed audio buffer
        self.mixed_audio: Optional[np.ndarray] = None
        
        logger.info(f"AudioRecorder initialized for room {room_id}")
    
    def start_recording(self):
        """Start recording audio."""
        if self.is_recording:
            logger.warning(f"Recording already started for room {self.room_id}")
            return
        
        self.is_recording = True
        self.start_time = datetime.utcnow()
        logger.info(f"Started recording for room {self.room_id}")
    
    def stop_recording(self):
        """Stop recording audio."""
        if not self.is_recording:
            logger.warning(f"Recording not started for room {self.room_id}")
            return
        
        self.is_recording = False
        self.end_time = datetime.utcnow()
        
        # Mix all participant audio
        self._mix_audio()
        
        logger.info(f"Stopped recording for room {self.room_id}")
    
    def add_audio_chunk(self, participant_id: str, audio_data: np.ndarray):
        """
        Add an audio chunk from a participant.
        
        Args:
            participant_id: Unique identifier for the participant
            audio_data: Audio data as numpy array
        """
        if not self.is_recording:
            return
        
        # Ensure audio is mono
        if audio_data.ndim > 1:
            audio_data = np.mean(audio_data, axis=1)
        
        # Normalize to [-1, 1]
        if len(audio_data) > 0:
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                audio_data = audio_data / max_val
        
        self.participant_chunks[participant_id].append(audio_data)
    
    def _mix_audio(self):
        """Mix audio from all participants into a single track."""
        if not self.participant_chunks:
            logger.warning(f"No audio chunks to mix for room {self.room_id}")
            self.mixed_audio = np.array([], dtype=np.float32)
            return
        
        # Find the maximum length
        max_length = 0
        for participant_id, chunks in self.participant_chunks.items():
            if chunks:
                total_length = sum(len(chunk) for chunk in chunks)
                max_length = max(max_length, total_length)
        
        if max_length == 0:
            self.mixed_audio = np.array([], dtype=np.float32)
            return
        
        # Initialize mixed audio buffer
        mixed = np.zeros(max_length, dtype=np.float32)
        
        # Mix all participant audio
        for participant_id, chunks in self.participant_chunks.items():
            # Concatenate chunks for this participant
            participant_audio = np.concatenate(chunks) if chunks else np.array([])
            
            if len(participant_audio) > 0:
                # Add to mixed audio (simple addition, can be improved with better mixing)
                mix_length = min(len(participant_audio), len(mixed))
                mixed[:mix_length] += participant_audio[:mix_length]
        
        # Normalize mixed audio to prevent clipping
        max_val = np.max(np.abs(mixed))
        if max_val > 1.0:
            mixed = mixed / max_val
        
        self.mixed_audio = mixed
        logger.info(f"Mixed audio for room {self.room_id}: {len(mixed)} samples, "
                   f"{len(self.participant_chunks)} participants")
    
    def get_wav_bytes(self) -> bytes:
        """
        Get the mixed audio as WAV bytes.
        
        Returns:
            WAV file as bytes
        """
        if self.mixed_audio is None:
            self._mix_audio()
        
        if self.mixed_audio is None or len(self.mixed_audio) == 0:
            # Return empty WAV file
            logger.warning(f"No audio to export for room {self.room_id}")
            return self._create_empty_wav()
        
        # Convert to 16-bit PCM
        audio_int16 = (self.mixed_audio * 32767).astype(np.int16)
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        
        wav_buffer.seek(0)
        return wav_buffer.read()
    
    def _create_empty_wav(self) -> bytes:
        """Create an empty WAV file."""
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            # Write 1 second of silence
            silence = np.zeros(self.sample_rate, dtype=np.int16)
            wav_file.writeframes(silence.tobytes())
        
        wav_buffer.seek(0)
        return wav_buffer.read()
    
    def get_duration_seconds(self) -> float:
        """Get the duration of the recording in seconds."""
        if self.mixed_audio is None:
            return 0.0
        
        return len(self.mixed_audio) / self.sample_rate
    
    def get_metadata(self) -> Dict:
        """Get recording metadata."""
        return {
            "room_id": self.room_id,
            "sample_rate": self.sample_rate,
            "duration_seconds": self.get_duration_seconds(),
            "participant_count": len(self.participant_chunks),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "is_recording": self.is_recording
        }


# Global storage for meeting recordings
_meeting_recordings: Dict[str, AudioRecorder] = {}


def get_or_create_recorder(room_id: str, sample_rate: int = 16000) -> AudioRecorder:
    """Get or create an audio recorder for a room."""
    if room_id not in _meeting_recordings:
        _meeting_recordings[room_id] = AudioRecorder(room_id, sample_rate)
    return _meeting_recordings[room_id]


def get_recorder(room_id: str) -> Optional[AudioRecorder]:
    """Get an existing audio recorder for a room."""
    return _meeting_recordings.get(room_id)


def delete_recorder(room_id: str):
    """Delete an audio recorder for a room."""
    if room_id in _meeting_recordings:
        del _meeting_recordings[room_id]
        logger.info(f"Deleted recorder for room {room_id}")
