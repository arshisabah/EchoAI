# app/modules/realtime_store.py
"""
Centralized real-time data store for transcripts and session management.
This replaces individual TRANSCRIPTS dictionaries in each router.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class SessionStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"

@dataclass
class TranscriptEntry:
    id: str
    speaker: str
    text: str
    timestamp: datetime
    confidence: float = 1.0
    # New fields
    emotions: Optional[Dict[str, float]] = None   # e.g., {"happy": 0.8, "angry": 0.1}
    bias_tags: Optional[List[str]] = None         # e.g., ["gender_bias", "dominance"]
    summary_chunk: Optional[str] = None           # e.g., "Decision about budget"
    metadata: Optional[Dict[str, str]] = None     # Flexible catch-all
    
    def to_dict(self):
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class SessionInfo:
    meeting_id: str
    status: SessionStatus
    created_at: datetime
    participants: Set[str]
    total_entries: int = 0
    
    def to_dict(self):
        return {
            'meeting_id': self.meeting_id,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'participants': list(self.participants),
            'total_entries': self.total_entries
        }

class RealtimeStore:
    """
    Centralized store for managing real-time transcript data and WebSocket connections.
    Thread-safe and async-ready.
    """
    
    def __init__(self):
        # Core data storage
        self._transcripts: Dict[str, List[TranscriptEntry]] = {}
        self._sessions: Dict[str, SessionInfo] = {}
        
        # WebSocket connection management
        self._connections: Dict[str, Set[asyncio.Queue]] = {}
        
        # Thread safety
        self._lock = asyncio.Lock()
        
    async def create_session(self, meeting_id: str) -> SessionInfo:
        """Create a new session for a meeting."""
        async with self._lock:
            if meeting_id in self._sessions:
                logger.warning(f"Session {meeting_id} already exists")
                return self._sessions[meeting_id]
                
            session = SessionInfo(
                meeting_id=meeting_id,
                status=SessionStatus.ACTIVE,
                created_at=datetime.now(),
                participants=set()
            )
            
            self._sessions[meeting_id] = session
            self._transcripts[meeting_id] = []
            self._connections[meeting_id] = set()
            
            logger.info(f"Created new session: {meeting_id}")
            return session
    
    async def get_session(self, meeting_id: str) -> Optional[SessionInfo]:
        """Get session info by meeting ID."""
        return self._sessions.get(meeting_id)
    
    async def add_transcript_entry(
        self, 
        meeting_id: str, 
        speaker: str, 
        text: str, 
        confidence: float = 1.0
    ) -> TranscriptEntry:
        """Add a new transcript entry and broadcast to connected clients."""
        async with self._lock:
            # Ensure session exists
            if meeting_id not in self._sessions:
                await self.create_session(meeting_id)
            
            # Create transcript entry
            entry = TranscriptEntry(
                id=f"{meeting_id}_{len(self._transcripts[meeting_id])}",
                speaker=speaker,
                text=text,
                timestamp=datetime.now(),
                confidence=confidence
            )
            
            # Store entry
            self._transcripts[meeting_id].append(entry)
            
            # Update session info
            session = self._sessions[meeting_id]
            session.participants.add(speaker)
            session.total_entries += 1
            
            # Broadcast to connected clients
            await self._broadcast_to_connections(meeting_id, entry.to_dict())
            
            logger.debug(f"Added transcript entry for {meeting_id}: {speaker}")
            return entry
    
    async def get_transcripts(self, meeting_id: str) -> List[TranscriptEntry]:
        """Get all transcript entries for a meeting."""
        return self._transcripts.get(meeting_id, [])
    
    async def get_recent_transcripts(self, meeting_id: str, limit: int = 50) -> List[TranscriptEntry]:
        """Get recent transcript entries for a meeting."""
        transcripts = self._transcripts.get(meeting_id, [])
        return transcripts[-limit:] if transcripts else []
    
    async def add_connection(self, meeting_id: str, queue: asyncio.Queue):
        """Add a WebSocket connection queue for a meeting."""
        async with self._lock:
            if meeting_id not in self._connections:
                self._connections[meeting_id] = set()
            self._connections[meeting_id].add(queue)
            logger.info(f"Added connection for meeting {meeting_id}. Total: {len(self._connections[meeting_id])}")
    
    async def remove_connection(self, meeting_id: str, queue: asyncio.Queue):
        """Remove a WebSocket connection queue."""
        async with self._lock:
            if meeting_id in self._connections:
                self._connections[meeting_id].discard(queue)
                if not self._connections[meeting_id]:
                    # Clean up empty connection sets
                    del self._connections[meeting_id]
                logger.info(f"Removed connection for meeting {meeting_id}")
    
    async def _broadcast_to_connections(self, meeting_id: str, data: dict):
        """Broadcast data to all connected WebSocket clients for a meeting."""
        if meeting_id not in self._connections:
            return
            
        dead_connections = set()
        
        for queue in self._connections[meeting_id].copy():
            try:
                await asyncio.wait_for(queue.put(data), timeout=1.0)
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"Failed to send to connection: {e}")
                dead_connections.add(queue)
        
        # Clean up dead connections
        for queue in dead_connections:
            self._connections[meeting_id].discard(queue)
    
    async def end_session(self, meeting_id: str):
        """End a session and clean up resources."""
        async with self._lock:
            if meeting_id in self._sessions:
                self._sessions[meeting_id].status = SessionStatus.ENDED
                
                # Notify all connections that session ended
                await self._broadcast_to_connections(meeting_id, {
                    "type": "session_ended",
                    "meeting_id": meeting_id,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Clean up connections
                if meeting_id in self._connections:
                    del self._connections[meeting_id]
                    
                logger.info(f"Ended session: {meeting_id}")
    
    async def get_analytics_data(self, meeting_id: str) -> dict:
        """Get analytics data for a meeting."""
        transcripts = await self.get_transcripts(meeting_id)
        session = await self.get_session(meeting_id)
        
        if not transcripts or not session:
            return {}
        
        # Calculate analytics
        total_words = sum(len(entry.text.split()) for entry in transcripts)
        speaker_stats = {}
        
        for entry in transcripts:
            if entry.speaker not in speaker_stats:
                speaker_stats[entry.speaker] = {"words": 0, "entries": 0}
            speaker_stats[entry.speaker]["words"] += len(entry.text.split())
            speaker_stats[entry.speaker]["entries"] += 1
        
        return {
            "meeting_id": meeting_id,
            "session_info": session.to_dict(),
            "total_transcripts": len(transcripts),
            "total_words": total_words,
            "speaker_statistics": speaker_stats,
            "average_confidence": sum(entry.confidence for entry in transcripts) / len(transcripts),
            "duration_minutes": (datetime.now() - session.created_at).total_seconds() / 60
        }

# Global instance - singleton pattern
realtime_store = RealtimeStore()

# Convenience functions for backward compatibility
async def get_transcripts(meeting_id: str) -> List[dict]:
    """Get all transcripts for a meeting as dictionaries."""
    entries = await realtime_store.get_transcripts(meeting_id)
    return [entry.to_dict() for entry in entries]

async def add_transcript(meeting_id: str, speaker: str, text: str, confidence: float = 1.0):
    """Add a transcript entry."""
    return await realtime_store.add_transcript_entry(meeting_id, speaker, text, confidence)