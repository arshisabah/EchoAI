# app/services/meeting_room_manager.py
"""
Multi-user meeting room management system.
Handles real-time collaboration, broadcasting, and participant management.
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ParticipantRole(str, Enum):
    """Participant roles in a meeting."""
    HOST = "host"
    MODERATOR = "moderator"
    PARTICIPANT = "participant"
    OBSERVER = "observer"


class MeetingStatus(str, Enum):
    """Meeting status."""
    WAITING = "waiting"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


@dataclass
class Participant:
    user_id: str
    username: str
    role: ParticipantRole
    joined_at: datetime
    websocket: Any
    is_speaking: bool = False
    is_muted: bool = False
    total_speaking_time: float = 0.0
    emotion_state: str = "neutral"
    last_activity: datetime = None
    is_video_on: bool = False
    is_audio_on: bool = True

    def to_dict(self):
        """SAFE serialization (no recursion, do not deepcopy websocket)."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role.value,
            "joined_at": self.joined_at.isoformat(),
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "is_speaking": self.is_speaking,
            "is_muted": self.is_muted,
            "is_video_on": self.is_video_on,
            "is_audio_on": self.is_audio_on,
            "total_speaking_time": self.total_speaking_time,
            "emotion_state": self.emotion_state,
        }


@dataclass
class MeetingRoom:
    """Represents a meeting room."""
    room_id: str
    room_name: str
    created_at: datetime
    created_by: str
    status: MeetingStatus
    participants: Dict[str, Participant]
    max_participants: int = 50
    password: Optional[str] = None
    is_recording: bool = False
    metadata: Dict[str, Any] = None
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'room_id': self.room_id,
            'room_name': self.room_name,
            'created_at': self.created_at.isoformat(),
            'created_by': self.created_by,
            'status': self.status.value,
            'participant_count': len(self.participants),
            'max_participants': self.max_participants,
            'is_recording': self.is_recording,
            'has_password': self.password is not None and self.password != "",
            'participants': [p.to_dict() for p in self.participants.values()],
            'metadata': self.metadata or {}
        }


class MeetingRoomManager:
    """
    Manages multiple meeting rooms with real-time broadcasting.
    Handles participant connections, message routing, and room lifecycle.
    """
    
    def __init__(self):
        self.rooms: Dict[str, MeetingRoom] = {}
        self._lock = asyncio.Lock()
        self.broadcast_queue: asyncio.Queue = asyncio.Queue()
        self._broadcast_task = None
        logger.info("MeetingRoomManager initialized")
    
    async def start_broadcasting(self):
        """Start the background broadcast task."""
        if self._broadcast_task is None:
            self._broadcast_task = asyncio.create_task(self._broadcast_worker())
            logger.info("Broadcast worker started")
    
    async def stop_broadcasting(self):
        """Stop the background broadcast task."""
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
            self._broadcast_task = None
            logger.info("Broadcast worker stopped")
    
    async def _broadcast_worker(self):
        """Background worker for broadcasting messages."""
        while True:
            try:
                # Get message from queue
                room_id, message, exclude_user_id = await self.broadcast_queue.get()
                
                # Broadcast to all participants in room
                await self._send_to_room(room_id, message, exclude_user_id)
                
                self.broadcast_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Broadcast worker error: {e}")
    
    async def create_room(
        self,
        room_id: str,
        room_name: str,
        created_by: str,
        password: Optional[str] = None,
        max_participants: int = 50
    ) -> MeetingRoom:
        """Create a new meeting room."""
        async with self._lock:
            if room_id in self.rooms:
                raise ValueError(f"Room {room_id} already exists")
            
            room = MeetingRoom(
                room_id=room_id,
                room_name=room_name,
                created_at=datetime.utcnow(),
                created_by=created_by,
                status=MeetingStatus.WAITING,
                participants={},
                max_participants=max_participants,
                password=password,
                metadata={}
            )
            
            self.rooms[room_id] = room
            logger.info(f"Created room: {room_id} by {created_by}")
            
            return room
    
    async def join_room(
        self,
        room_id: str,
        user_id: str,
        username: str,
        websocket: Any,
        password: Optional[str] = None,
        role: ParticipantRole = ParticipantRole.PARTICIPANT
    ) -> Participant:
        """Add a participant to a room."""
        async with self._lock:
            room = self.rooms.get(room_id)
            
            if not room:
                raise ValueError(f"Room {room_id} not found")

            # Normalize room-stored password
            clean_stored = None if room.password in (None, "", " ", "null", "undefined") else room.password

            # Normalize received password
            clean_received = None if password in (None, "", " ", "null", "undefined") else password

            logger.warning(f"🔐 Password check → stored={clean_stored!r}, received={clean_received!r}")

            # Validate only if room HAS a password
            if clean_stored is not None:
                if clean_received != clean_stored:
                    raise ValueError("Invalid room password")

            
            # Check capacity
            if len(room.participants) >= room.max_participants:
                raise ValueError("Room is full")
            
            # Close existing connection if user already in room
            if user_id in room.participants:
                old = room.participants[user_id]
                try:
                    await old.websocket.close()
                    logger.info(f"Closed old connection for user {username} ({user_id}) in room {room_id}")
                except Exception as e:
                    logger.warning(f"Failed to close old websocket for {user_id}: {e}")
                room.participants.pop(user_id)
            
            # Create participant
            participant = Participant(
                user_id=user_id,
                username=username,
                role=role,
                joined_at=datetime.utcnow(),
                websocket=websocket,
                last_activity=datetime.utcnow()
            )
        
            
            logger.info(f"User {username} ({user_id}) joined room {room_id}")
            
            # Broadcast join event to all participants
            
            room.participants[user_id] = participant
            # Start room if this is the first participant
            if len(room.participants) == 0 and room.status == MeetingStatus.WAITING:
                room.status = MeetingStatus.ACTIVE
            
            room.participants[user_id] = participant

            # Then broadcast join event with updated counts
            await self.broadcast_to_room(room_id, {
                "type": "participant_joined",
                "user_id": user_id,
                "username": username,
                "role": role.value,
                "participant_count": len(room.participants),
                "timestamp": datetime.utcnow().isoformat(),
                "participants": [p.to_dict() for p in room.participants.values()]
            }, exclude_user_id=user_id)
                        
            return participant
    
    async def leave_room(self, room_id: str, user_id: str):
        """Remove a participant from a room."""
        async with self._lock:
            room = self.rooms.get(room_id)
            
            if not room:
                return
            
            participant = room.participants.pop(user_id, None)
            
            if participant:
                participant.last_activity = datetime.utcnow()


            if participant:
                logger.info(f"User {participant.username} left room {room_id}")
                
                # ✅ Close the participant's WebSocket connection
                try:
                    await participant.websocket.close()
                    logger.info(f"Closed WebSocket for {participant.username} ({user_id})")
                except Exception as e:
                    logger.warning(f"Error closing WebSocket for {user_id}: {e}")

                # ✅ Broadcast updated leave event
                await self.broadcast_to_room(room_id, {
                    "type": "participant_left",
                    "user_id": user_id,
                    "username": participant.username,
                    "timestamp": datetime.utcnow().isoformat(),
                    "participant_count": len(room.participants),
                    "participants": [p.to_dict() for p in room.participants.values()],
                    "room_status": room.status.value
                })
                
                # ✅ End room if empty
            if len(room.participants) == 0:
                room.status = MeetingStatus.ENDED
                logger.info(f"Room {room_id} ended (empty)")
                
                # Notify frontend that room ended
                await self.broadcast_to_room(room_id, {
                    "type": "room_ended",
                    "room_id": room_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
    
    async def broadcast_to_room(
        self,
        room_id: str,
        message: Dict[str, Any],
        exclude_user_id: Optional[str] = None
    ):
        """
        Broadcast a message to all participants in a room.
        
        Args:
            room_id: Room to broadcast to
            message: Message to broadcast
            exclude_user_id: Optional user ID to exclude from broadcast
        """
        # Add to broadcast queue for async processing
        await self.broadcast_queue.put((room_id, message, exclude_user_id))
    
    async def _send_to_room(
        self,
        room_id: str,
        message: Dict[str, Any],
        exclude_user_id: Optional[str] = None
    ):
        """Internal method to send message to room participants."""
        room = self.rooms.get(room_id)
        
        if not room:
            return
        
        # Send to all participants except excluded user
        dead_connections = []
        
        for user_id, participant in room.participants.items():
            if user_id == exclude_user_id:
                continue
            
            try:
                await participant.websocket.send_json(message)
                participant.last_activity = datetime.utcnow() 
            except Exception as e:
                logger.warning(f"Failed to send to {user_id}: {e}")
                dead_connections.append(user_id)
        
        # Clean up dead connections
        for user_id in dead_connections:
            await self.leave_room(room_id, user_id)
        # 🔹 Auto-remove empty rooms to save memory
        if not room.participants:
            self.rooms.pop(room_id, None)
            logger.info(f"🧹 Cleaned up empty room {room_id}")
    async def broadcast_transcript(
        self,
        room_id: str,
        user_id: str,
        username: str,
        text: str,
        emotion: str,
        confidence: float,
        emotion_guidance: Dict[str, Any]
    ):
        """
        Broadcast a transcript entry to all participants.
        
        Args:
            room_id: Room ID
            user_id: Speaking user ID
            username: Speaking username
            text: Transcribed text
            emotion: Detected emotion
            confidence: Confidence score
            emotion_guidance: Guidance for responding to this emotion
        """
        message = {
            "type": "live_transcript",
            "user_id": user_id,
            "username": username,
            "text": text,
            "emotion": emotion,
            "confidence": confidence,
            "emotion_guidance": emotion_guidance,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_room(room_id, message)
        
        # Update participant state
        room = self.rooms.get(room_id)
        if room and user_id in room.participants:
            participant = room.participants[user_id]
            participant.emotion_state = emotion
            participant.is_speaking = True
            participant.last_activity = datetime.utcnow()
            # 🔹 Roughly estimate speaking duration (assuming 2.5 words/sec)
            participant.total_speaking_time += len(text.split()) / 2.5
        # 🔹 Notify all clients who the active speaker is
        await self.broadcast_to_room(room_id, {
            "type": "active_speaker",
            "user_id": user_id,
            "username": username,
            "timestamp": datetime.utcnow().isoformat()
        })
    async def update_participant_state(
            self,
            room_id: str,
            user_id: str,
            is_speaking: bool = None,
            is_muted: bool = None,
            emotion_state: str = None,
            is_video_on: bool = None,      # 🔹 New
            is_audio_on: bool = None       # 🔹 New
    ):
        """Update participant state and broadcast to room."""
        room = self.rooms.get(room_id)
        if not room or user_id not in room.participants:
            return

        participant = room.participants[user_id]

        if is_speaking is not None:
            participant.is_speaking = is_speaking
        if is_muted is not None:
            participant.is_muted = is_muted
        if emotion_state is not None:
            participant.emotion_state = emotion_state
        if is_video_on is not None:
            participant.is_video_on = is_video_on
        if is_audio_on is not None:
            participant.is_audio_on = is_audio_on

        participant.last_activity = datetime.utcnow()

        # ✅ Broadcast state update
        await self.broadcast_to_room(room_id, {
            "type": "participant_state_update",
            "user_id": user_id,
            "username": participant.username,
            "is_speaking": participant.is_speaking,
            "is_muted": participant.is_muted,
            "emotion_state": participant.emotion_state,
            "is_video_on": participant.is_video_on,   # 🔹 New
            "is_audio_on": participant.is_audio_on,   # 🔹 New
            "timestamp": datetime.utcnow().isoformat()
        })

    
    async def get_room_info(self, room_id: str) -> Optional[Dict[str, Any]]:
        """Get room information."""
        room = self.rooms.get(room_id)
        return room.to_dict() if room else None
    
    async def list_rooms(self) -> List[Dict[str, Any]]:
        """List all active rooms."""
        return [room.to_dict() for room in self.rooms.values()]
    
    async def get_room_participants(self, room_id: str) -> List[Dict[str, Any]]:
        """Get all participants in a room."""
        room = self.rooms.get(room_id)
        
        if not room:
            return []
        
        return [p.to_dict() for p in room.participants.values()]
    
    async def end_room(self, room_id: str, ended_by: str):
        """End a meeting room."""
        room = self.rooms.get(room_id)
        
        if not room:
            return
        
        room.status = MeetingStatus.ENDED
        
        # Notify all participants
        await self.broadcast_to_room(room_id, {
            "type": "room_ended",
            "ended_by": ended_by,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Close all connections
        for participant in room.participants.values():
            try:
                await participant.websocket.close()
            except:
                pass
        
        logger.info(f"Room {room_id} ended by {ended_by}")


# Singleton
_meeting_room_manager: Optional[MeetingRoomManager] = None


def get_meeting_room_manager() -> MeetingRoomManager:
    """Get singleton meeting room manager."""
    global _meeting_room_manager
    if _meeting_room_manager is None:
        _meeting_room_manager = MeetingRoomManager()
    return _meeting_room_manager