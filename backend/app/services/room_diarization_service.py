"""
Room-level diarization service for multi-participant meetings.
Manages mixed audio streams and speaker identification using Faster-Whisper + speaker identification.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from collections import defaultdict

import numpy as np

from app.services.audio_mixer import get_audio_mixer
from app.services.faster_whisper_transcription import get_faster_whisper_service
from app.services.speaker_identification_service import get_speaker_service

logger = logging.getLogger(__name__)

# Constants
MAX_BUFFER_CHUNKS = 3  # Maximum audio chunks to buffer per participant (~300ms)
INT16_MAX = 32767  # Maximum value for 16-bit signed integer audio
SAMPLE_RATE = 16000  # Audio sample rate


class RoomDiarizationService:
    """
    Manages room-level audio mixing and diarization.
    
    Features:
    - Collects audio from all participants in a room
    - Mixes audio streams in real-time
    - Uses Faster-Whisper for transcription (local, free)
    - Uses speaker identification service for diarization
    - Maps identified speakers to participant usernames
    """
    
    def __init__(self):
        # Use Faster-Whisper instead of Deepgram
        self.whisper_service = get_faster_whisper_service()
        self.speaker_service = get_speaker_service()
        self.audio_mixer = get_audio_mixer()
        
        # Room-level buffers: room_id -> {participant_id -> [audio_chunks]}
        self.room_buffers: Dict[str, Dict[str, List[np.ndarray]]] = defaultdict(lambda: defaultdict(list))
        
        # Room-level streaming sessions
        self.room_streams: Dict[str, str] = {}  # room_id -> stream_id
        
        # Speaker mapping: room_id -> {identified_speaker -> participant_id}
        self.speaker_mapping: Dict[str, Dict[str, str]] = defaultdict(dict)
        
        # Participant info: room_id -> {participant_id -> username}
        self.participant_info: Dict[str, Dict[str, str]] = defaultdict(dict)
        
        # Room callbacks: room_id -> callback function
        self.room_callbacks: Dict[str, Callable] = {}
        
        logger.info("✅ RoomDiarizationService initialized (Faster-Whisper + Speaker ID)")
    
    async def start_room_diarization(
        self,
        room_id: str,
        on_transcript: Callable,
        language: str = "en"
    ) -> bool:
        """
        Start diarization for a room with mixed audio stream using Faster-Whisper + speaker ID.
        
        Args:
            room_id: Room identifier
            on_transcript: Callback for transcript results
            language: Language code
            
        Returns:
            bool: True if started successfully
        """
        if not self.whisper_service:
            logger.error("❌ Faster-Whisper service not available")
            return False
        
        if room_id in self.room_streams:
            logger.warning(f"⚠️ Diarization already started for room {room_id}")
            return True
        
        try:
            stream_id = f"room_{room_id}"
            
            # Wrap callback to add speaker identification
            async def wrapped_callback(result: dict):
                try:
                    text = result.get("text", "").strip()
                    if not text:
                        return
                    
                    # Get audio for speaker identification if available
                    audio_array = result.get("audio_array")
                    if audio_array is not None and len(audio_array) > 0:
                        # Identify speaker using audio fingerprinting
                        speaker_id = await self.speaker_service.identify_speaker(
                            audio_array, stream_id, SAMPLE_RATE
                        )
                        
                        # Try to map to participant
                        participant_id = self.resolve_speaker(room_id, speaker_id)
                        if participant_id:
                            result["speaker"] = speaker_id
                            result["participant_id"] = participant_id
                            result["username"] = self.get_participant_name(room_id, participant_id)
                        else:
                            # Unknown speaker - use identified speaker ID
                            result["speaker"] = speaker_id
                            result["participant_id"] = speaker_id
                            result["username"] = speaker_id
                    
                    # Call original callback with enriched result
                    await on_transcript(result)
                    
                except Exception as e:
                    logger.error(f"❌ Error in room diarization callback: {e}", exc_info=True)
            
            # Start Faster-Whisper stream with callback
            success = await self.whisper_service.start_stream(
                session_id=stream_id,
                on_transcript=wrapped_callback,
                language=language
            )
            
            if success:
                self.room_streams[room_id] = stream_id
                self.room_callbacks[room_id] = on_transcript
                logger.info(f"✅ Started room diarization for {room_id} with Faster-Whisper")
                return True
            else:
                logger.error(f"❌ Failed to start room diarization for {room_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error starting room diarization for {room_id}: {e}", exc_info=True)
            return False
    
    async def stop_room_diarization(self, room_id: str) -> bool:
        """
        Stop diarization for a room.
        
        Args:
            room_id: Room identifier
            
        Returns:
            bool: True if stopped successfully
        """
        if not self.whisper_service:
            return False
        
        if room_id not in self.room_streams:
            logger.debug(f"No diarization active for room {room_id}")
            return True
        
        try:
            stream_id = self.room_streams[room_id]
            await self.whisper_service.stop_stream(stream_id)
            
            # Clean up
            if room_id in self.room_streams:
                del self.room_streams[room_id]
            if room_id in self.room_callbacks:
                del self.room_callbacks[room_id]
            if room_id in self.room_buffers:
                del self.room_buffers[room_id]
            if room_id in self.speaker_mapping:
                del self.speaker_mapping[room_id]
            if room_id in self.participant_info:
                del self.participant_info[room_id]
            
            logger.info(f"✅ Stopped room diarization for {room_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping room diarization for {room_id}: {e}")
            return False
    
    def register_participant(self, room_id: str, participant_id: str, username: str):
        """
        Register a participant in a room for speaker mapping.
        
        Args:
            room_id: Room identifier
            participant_id: Participant identifier
            username: Participant username
        """
        self.participant_info[room_id][participant_id] = username
        logger.debug(f"Registered participant {username} ({participant_id}) in room {room_id}")
    
    def unregister_participant(self, room_id: str, participant_id: str):
        """
        Unregister a participant from a room.
        
        Args:
            room_id: Room identifier
            participant_id: Participant identifier
        """
        if room_id in self.participant_info and participant_id in self.participant_info[room_id]:
            del self.participant_info[room_id][participant_id]
            logger.debug(f"Unregistered participant {participant_id} from room {room_id}")
    
    async def add_audio_chunk(
        self,
        room_id: str,
        participant_id: str,
        audio_chunk: np.ndarray
    ):
        """
        Add audio chunk from a participant and mix with other streams for room-level processing.
        
        Args:
            room_id: Room identifier
            participant_id: Participant identifier
            audio_chunk: Audio data as numpy array
        """
        if not self.whisper_service or room_id not in self.room_streams:
            # Diarization not active for this room
            return
        
        try:
            # Add chunk to buffer
            self.room_buffers[room_id][participant_id].append(audio_chunk)
            
            # Keep only last MAX_BUFFER_CHUNKS per participant
            for pid in self.room_buffers[room_id]:
                if len(self.room_buffers[room_id][pid]) > MAX_BUFFER_CHUNKS:
                    self.room_buffers[room_id][pid].pop(0)
            
            # Mix audio from all participants
            all_chunks = []
            for pid, chunks in self.room_buffers[room_id].items():
                if chunks:
                    # Concatenate chunks from this participant
                    participant_audio = np.concatenate(chunks)
                    all_chunks.append(participant_audio)
            
            if not all_chunks:
                return
            
            # Mix all participant streams
            mixed_audio = self.audio_mixer.mix_streams(all_chunks, normalize=True)
            
            if len(mixed_audio) == 0:
                return
            
            # Convert to PCM int16 bytes for Faster-Whisper
            audio_int16 = (mixed_audio * INT16_MAX).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            # Send to Faster-Whisper stream
            stream_id = self.room_streams[room_id]
            await self.whisper_service.send_audio(stream_id, audio_bytes)
            
        except Exception as e:
            logger.error(f"❌ Error adding audio chunk for room {room_id}: {e}", exc_info=True)
    
    def map_speaker(self, room_id: str, speaker_id: str, participant_id: str):
        """
        Map an identified speaker ID to a participant.
        
        Args:
            room_id: Room identifier
            speaker_id: Identified speaker ID (e.g., "Speaker 1")
            participant_id: Participant identifier
        """
        self.speaker_mapping[room_id][speaker_id] = participant_id
        logger.debug(f"Mapped speaker '{speaker_id}' to participant '{participant_id}' in room {room_id}")
    
    def get_participant_name(self, room_id: str, participant_id: str) -> str:
        """
        Get participant username from ID.
        
        Args:
            room_id: Room identifier
            participant_id: Participant identifier
            
        Returns:
            str: Participant username or ID if not found
        """
        return self.participant_info[room_id].get(participant_id, participant_id)
    
    def resolve_speaker(self, room_id: str, speaker_id: Optional[str]) -> Optional[str]:
        """
        Resolve identified speaker ID to participant ID.
        
        Args:
            room_id: Room identifier
            speaker_id: Identified speaker ID (e.g., "Speaker 1")
            
        Returns:
            Optional[str]: Participant ID or None
        """
        if speaker_id is None:
            return None
        
        return self.speaker_mapping[room_id].get(speaker_id)


# Singleton instance
_room_diarization_service: Optional[RoomDiarizationService] = None


def get_room_diarization_service() -> RoomDiarizationService:
    """
    Get or create the room diarization service instance.
    Uses Faster-Whisper (local) + speaker identification (no API key needed).
    
    Returns:
        RoomDiarizationService instance
    """
    global _room_diarization_service
    
    if _room_diarization_service is None:
        try:
            _room_diarization_service = RoomDiarizationService()
            logger.info("✅ Room diarization service initialized (Faster-Whisper + Speaker ID)")
        except Exception as e:
            logger.error(f"❌ Failed to initialize room diarization service: {e}", exc_info=True)
            raise
    
    return _room_diarization_service
