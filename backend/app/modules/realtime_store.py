# app/modules/realtime_store.py
"""
Centralized real-time data store for transcripts and session management.
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
    emotions: Optional[Dict[str, float]] = None
    bias_tags: Optional[List[str]] = None
    summary_chunk: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None
    
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
    """Centralized store for managing real-time transcript data."""
    
    def __init__(self):
        self._transcripts: Dict[str, List[TranscriptEntry]] = {}
        self._sessions: Dict[str, SessionInfo] = {}
        self._connections: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        self._metadata: Dict[str, Dict] = {}
        
    async def create_session(self, meeting_id: str, metadata: Optional[Dict] = None) -> SessionInfo:
        """Create a new session."""
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
            self._metadata[meeting_id] = metadata or {}
            
            logger.info(f"Created new session: {meeting_id}")
            return session
    
    async def get_session(self, meeting_id: str) -> Optional[SessionInfo]:
        """Get session info."""
        return self._sessions.get(meeting_id)
    
    async def add_transcript_entry(
        self, 
        meeting_id: str, 
        speaker: str, 
        text: str, 
        confidence: float = 1.0
    ) -> TranscriptEntry:
        """Add a transcript entry."""
        async with self._lock:
            if meeting_id not in self._sessions:
                await self.create_session(meeting_id)
            
            entry = TranscriptEntry(
                id=f"{meeting_id}_{len(self._transcripts[meeting_id])}",
                speaker=speaker,
                text=text,
                timestamp=datetime.now(),
                confidence=confidence
            )
            
            self._transcripts[meeting_id].append(entry)
            
            session = self._sessions[meeting_id]
            session.participants.add(speaker)
            session.total_entries += 1
            
            await self._broadcast_to_connections(meeting_id, entry.to_dict())
            
            return entry
    
    async def get_transcripts(self, meeting_id: str) -> List[TranscriptEntry]:
        """Get all transcript entries."""
        return self._transcripts.get(meeting_id, [])
    
    def get_session_transcript(self, session_id: str) -> List[TranscriptEntry]:
        """Get session transcript (sync version)."""
        return self._transcripts.get(session_id, [])
    
    def get_session_metadata(self, session_id: str) -> Optional[Dict]:
        """Get session metadata."""
        return self._metadata.get(session_id)
    
    def get_analytics(self, meeting_id: str) -> dict:
        """Get analytics for a meeting."""
        transcripts = self._transcripts.get(meeting_id, [])
        session = self._sessions.get(meeting_id)
        
        if not transcripts or not session:
            return {}
        
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
            "average_confidence": sum(e.confidence for e in transcripts) / len(transcripts),
            "duration_minutes": (datetime.now() - session.created_at).total_seconds() / 60,
            "speakers": list(session.participants)
        }
    
    def list_sessions(self) -> List[str]:
        """List all session IDs."""
        return list(self._sessions.keys())
    
    def get_full_text(self, session_id: str, include_speakers: bool = True) -> str:
        """Get full transcript text."""
        transcripts = self._transcripts.get(session_id, [])
        if include_speakers:
            return "\n".join([f"{e.speaker}: {e.text}" for e in transcripts])
        return "\n".join([e.text for e in transcripts])
    
    async def _broadcast_to_connections(self, meeting_id: str, data: dict):
        """Broadcast data to connected clients."""
        if meeting_id not in self._connections:
            return
            
        dead_connections = set()
        
        for queue in self._connections[meeting_id].copy():
            try:
                await asyncio.wait_for(queue.put(data), timeout=1.0)
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"Failed to send to connection: {e}")
                dead_connections.add(queue)
        
        for queue in dead_connections:
            self._connections[meeting_id].discard(queue)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            del self._transcripts[session_id]
            if session_id in self._connections:
                del self._connections[session_id]
            if session_id in self._metadata:
                del self._metadata[session_id]
            return True
        return False


# Global singleton instance
_realtime_store: Optional[RealtimeStore] = None


def get_transcript_store() -> RealtimeStore:
    """Get the global transcript store instance."""
    global _realtime_store
    if _realtime_store is None:
        _realtime_store = RealtimeStore()
    return _realtime_store


# Alias for backward compatibility
def realtime_store() -> RealtimeStore:
    """Alias for get_transcript_store."""
    return get_transcript_store()


# Convenience function
def create_session(session_id: str, metadata: Optional[Dict] = None) -> bool:
    """Create a new session (sync wrapper)."""
    store = get_transcript_store()
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(store.create_session(session_id, metadata))
        return True
    except RuntimeError:
        # No event loop running, create new one
        asyncio.run(store.create_session(session_id, metadata))
        return True