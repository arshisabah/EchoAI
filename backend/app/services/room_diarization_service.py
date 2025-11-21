"""
Room-level diarization service for multi-participant meetings.
Manages mixed audio streams and speaker identification.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict

import numpy as np

from app.services.audio_mixer import get_audio_mixer
from app.services.deepgram_transcription import get_deepgram_service

logger = logging.getLogger(__name__)


class RoomDiarizationService:
    """
    Manages room-level audio mixing and diarization.
    
    Features:
    - Collects audio from all participants in a room
    - Mixes audio streams in real-time
    - Sends mixed stream to Deepgram with diarization enabled
    - Maps Deepgram speaker labels to participant usernames
    """
    
    def __init__(self, deepgram_api_key: Optional[str] = None):
        self.deepgram_service = None
        if deepgram_api_key:
            self.deepgram_service = get_deepgram_service(deepgram_api_key)
        
        self.audio_mixer = get_audio_mixer()
        
        # Room-level buffers: room_id -> {participant_id -> [audio_chunks]}
        self.room_buffers: Dict[str, Dict[str, List[np.ndarray]]] = defaultdict(lambda: defaultdict(list))
        
        # Room-level Deepgram connections
        self.room_connections: Dict[str, bool] = {}
        
        # Speaker mapping: room_id -> {deepgram_speaker_id -> participant_id}
        self.speaker_mapping: Dict[str, Dict[int, str]] = defaultdict(dict)
        
        # Participant info: room_id -> {participant_id -> username}
        self.participant_info: Dict[str, Dict[str, str]] = defaultdict(dict)
        
        logger.info("✅ RoomDiarizationService initialized")
    
    async def start_room_diarization(
        self,
        room_id: str,
        on_transcript: callable,
        language: str = "en",
        model: str = "nova-2"
    ) -> bool:
        """
        Start diarization for a room with mixed audio stream.
        
        Args:
            room_id: Room identifier
            on_transcript: Callback for transcript results
            language: Language code
            model: Deepgram model
            
        Returns:
            bool: True if started successfully
        """
        if not self.deepgram_service:
            logger.error("❌ Deepgram service not available")
            return False
        
        if room_id in self.room_connections:
            logger.warning(f"⚠️ Diarization already started for room {room_id}")
            return True
        
        try:
            # Start Deepgram stream with diarization enabled
            success = await self.deepgram_service.start_stream(
                session_id=f"room_{room_id}",
                on_transcript=on_transcript,
                language=language,
                model=model,
                smart_format=True,
                interim_results=True,
                diarize=True  # Enable diarization
            )
            
            if success:
                self.room_connections[room_id] = True
                logger.info(f"✅ Started room diarization for {room_id}")
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
        if not self.deepgram_service:
            return False
        
        if room_id not in self.room_connections:
            logger.debug(f"No diarization active for room {room_id}")
            return True
        
        try:
            await self.deepgram_service.stop_stream(f"room_{room_id}")
            
            # Clean up
            if room_id in self.room_connections:
                del self.room_connections[room_id]
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
        Add audio chunk from a participant and mix with other streams.
        
        Args:
            room_id: Room identifier
            participant_id: Participant identifier
            audio_chunk: Audio data as numpy array
        """
        if not self.deepgram_service or room_id not in self.room_connections:
            # Diarization not active for this room
            return
        
        try:
            # Add chunk to buffer
            self.room_buffers[room_id][participant_id].append(audio_chunk)
            
            # Keep only last 3 chunks per participant (about 300ms)
            for pid in self.room_buffers[room_id]:
                if len(self.room_buffers[room_id][pid]) > 3:
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
            
            # Convert to PCM int16 bytes
            audio_int16 = (mixed_audio * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            # Send to Deepgram
            await self.deepgram_service.send_audio(f"room_{room_id}", audio_bytes)
            
        except Exception as e:
            logger.error(f"❌ Error adding audio chunk for room {room_id}: {e}", exc_info=True)
    
    def map_speaker(self, room_id: str, deepgram_speaker: int, participant_id: str):
        """
        Map a Deepgram speaker ID to a participant.
        
        Args:
            room_id: Room identifier
            deepgram_speaker: Deepgram speaker ID
            participant_id: Participant identifier
        """
        self.speaker_mapping[room_id][deepgram_speaker] = participant_id
        logger.debug(f"Mapped speaker {deepgram_speaker} to {participant_id} in room {room_id}")
    
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
    
    def resolve_speaker(self, room_id: str, deepgram_speaker: Optional[int]) -> Optional[str]:
        """
        Resolve Deepgram speaker ID to participant ID.
        
        Args:
            room_id: Room identifier
            deepgram_speaker: Deepgram speaker ID
            
        Returns:
            Optional[str]: Participant ID or None
        """
        if deepgram_speaker is None:
            return None
        
        return self.speaker_mapping[room_id].get(deepgram_speaker)


# Singleton instance
_room_diarization_service: Optional[RoomDiarizationService] = None


def get_room_diarization_service(api_key: Optional[str] = None) -> Optional[RoomDiarizationService]:
    """
    Get or create the room diarization service instance.
    
    Args:
        api_key: Deepgram API key (required on first call)
        
    Returns:
        RoomDiarizationService instance or None if not available
    """
    global _room_diarization_service
    
    if _room_diarization_service is None:
        if not api_key:
            logger.warning("⚠️ Deepgram API key required to initialize room diarization service")
            return None
        try:
            _room_diarization_service = RoomDiarizationService(api_key)
        except Exception as e:
            logger.error(f"❌ Failed to initialize room diarization service: {e}")
            return None
    
    return _room_diarization_service
