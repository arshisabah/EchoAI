# app/services/continuous_transcript_manager.py
"""
Continuous Transcript Manager for EchoAI
Manages continuous transcription bars with smart bar creation rules:
- Appends to same bar while speaker continues
- Creates new bar on: speaker change, 15s silence, or 30s duration
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
import pytz

logger = logging.getLogger(__name__)


def get_ist_now() -> datetime:
    """Get timezone-aware IST datetime (India Standard Time)"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)


@dataclass
class TranscriptBar:
    """Represents a single transcript bar (continuous speech segment)"""
    id: str
    session_id: str
    speaker: str
    text: str
    started_at: datetime
    updated_at: datetime
    confidence: float
    word_count: int = 0
    status: str = "active"  # active, processing_emotion, finalized
    emotion: Optional[str] = "neutral"  # ✅ Default to neutral instead of None
    emotion_confidence: Optional[float] = 0.0  # ✅ Default to 0.0 instead of None
    emotion_scores: Optional[Dict[str, float]] = None
    emotion_guidance: Optional[dict] = None  # ✅ Changed from str to dict
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        """Convert to dictionary for WebSocket transmission"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "speaker_id": self.speaker,  # ✅ Frontend expects speaker_id
            "speaker_name": self.metadata.get("speaker_name", "Unknown"),  # ✅ Add speaker_name
            "text": self.text,
            "timestamp": self.started_at.isoformat() if self.started_at.tzinfo else self.started_at.replace(tzinfo=pytz.timezone('Asia/Kolkata')).isoformat(),  # ✅ Ensure IST timezone
            "updated_at": self.updated_at.isoformat() if self.updated_at.tzinfo else self.updated_at.replace(tzinfo=pytz.timezone('Asia/Kolkata')).isoformat(),
            "confidence": self.confidence,
            "word_count": self.word_count,
            "status": self.status,
            "emotion": self.emotion or "neutral",  # ✅ Always provide emotion (default neutral)
            "emotion_confidence": self.emotion_confidence or 0.0,  # ✅ Always provide confidence
            "emotion_scores": self.emotion_scores or {},  # ✅ Always provide scores
            "emotion_guidance": self.emotion_guidance or {},  # ✅ Always provide guidance (empty dict if not ready)
            "metadata": self.metadata,
            "duration": self.duration_seconds()  # ✅ Add duration for frontend
        }
    
    def duration_seconds(self) -> float:
        """Calculate duration of this transcript bar"""
        return (self.updated_at - self.started_at).total_seconds()


class ContinuousTranscriptManager:
    """
    Manages continuous transcript bars with Google Meet-like behavior.
    Handles appending, bar finalization, and triggers async emotion processing.
    """
    
    # Thresholds
    SILENCE_THRESHOLD_SECONDS = 15  # New bar after 15s silence
    MAX_DURATION_SECONDS = 30       # New bar after 30s continuous speech
    
    def __init__(self):
        # Active bars per session (one bar per session at a time)
        self.active_bars: Dict[str, TranscriptBar] = {}
        
        # All transcript bars (history)
        self.all_bars: Dict[str, list] = {}  # session_id -> list of bars
        
        # Last activity timestamp per session
        self.last_activity: Dict[str, datetime] = {}
        
        # Emotion processing queue (bars waiting for emotion analysis)
        self.emotion_queue: asyncio.Queue = asyncio.Queue()
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        
        logger.info("✅ ContinuousTranscriptManager initialized")
    
    async def process_transcription(
        self,
        session_id: str,
        speaker: str,
        text: str,
        confidence: float,
        timestamp: Optional[datetime] = None,
        speaker_name: str = "Unknown"
    ) -> Dict[str, Any]:
        """
        Process incoming transcription and determine whether to append or create new bar.
        
        Returns:
            dict with 'action' (append/create) and 'bar' (TranscriptBar object)
        """
        if timestamp is None:
            timestamp = get_ist_now()
        
        async with self._lock:
            # Initialize session if needed
            if session_id not in self.all_bars:
                self.all_bars[session_id] = []
            
            # Get current active bar for this session
            current_bar = self.active_bars.get(session_id)
            
            # Determine if we need a new bar
            need_new_bar = self._should_create_new_bar(
                session_id, speaker, current_bar, timestamp
            )
            
            if need_new_bar:
                # Store reference to bar being finalized (for audio caching)
                finalized_bar = current_bar
                
                # Finalize current bar if exists (this will queue it for emotion processing)
                if current_bar:
                    await self._finalize_bar(current_bar)
                
                # Create new bar
                new_bar = TranscriptBar(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    speaker=speaker,
                    text=text,
                    started_at=timestamp,
                    updated_at=timestamp,
                    confidence=confidence,
                    word_count=len(text.split()),
                    status="active",
                    metadata={"speaker_name": speaker_name}
                )
                
                self.active_bars[session_id] = new_bar
                self.all_bars[session_id].append(new_bar)
                self.last_activity[session_id] = timestamp
                
                logger.info(f"📝 Created new transcript bar: session={session_id}, speaker={speaker}, bar_id={new_bar.id}")
                
                # ❌ DON'T queue new bar for emotion - only finalized bars get emotion processing
                # The previous bar was already queued in _finalize_bar() above
                
                return {
                    "action": "create",
                    "bar": new_bar,
                    "finalized_bar": finalized_bar,  # Return finalized bar for audio caching
                    "reason": self._get_new_bar_reason(current_bar, speaker, timestamp)
                }
            else:
                # REPLACE text (not append) since Faster-Whisper sends CUMULATIVE text
                # Example: If bar has "Hello" and Whisper sends "Hello my", we replace to get "Hello my"
                # NOT append which would give "Hello Hello my"
                current_bar.text = text  # REPLACE, don't append
                current_bar.updated_at = timestamp
                current_bar.word_count = len(current_bar.text.split())
                # Update confidence (weighted average)
                current_bar.confidence = (current_bar.confidence + confidence) / 2
                self.last_activity[session_id] = timestamp
                
                logger.debug(f"➕ Updated bar: session={session_id}, bar_id={current_bar.id}, new_length={len(current_bar.text)}")
                
                # Don't queue on every append - only on create and finalize to prevent duplicates
                
                return {
                    "action": "append",
                    "bar": current_bar
                }
    
    def _should_create_new_bar(
        self,
        session_id: str,
        speaker: str,
        current_bar: Optional[TranscriptBar],
        timestamp: datetime
    ) -> bool:
        """
        Determine if a new transcript bar should be created.
        
        New bar conditions:
        1. No current bar exists
        2. Speaker changed (interruption)
        3. Silence > 15 seconds
        4. Duration > 30 seconds
        """
        # No current bar - create new one
        if not current_bar:
            logger.debug(f"🆕 New bar needed: No current bar for session {session_id}")
            return True
        
        # Speaker change (interruption)
        if current_bar.speaker != speaker:
            logger.info(f"👥 New bar needed: Speaker change {current_bar.speaker} -> {speaker}")
            return True
        
        # Silence threshold (15 seconds)
        last_activity = self.last_activity.get(session_id)
        if last_activity:
            silence_duration = (timestamp - last_activity).total_seconds()
            if silence_duration > self.SILENCE_THRESHOLD_SECONDS:
                logger.info(f"🔇 New bar needed: Silence threshold exceeded ({silence_duration:.1f}s)")
                return True
        
        # Duration threshold (30 seconds)
        bar_duration = current_bar.duration_seconds()
        if bar_duration > self.MAX_DURATION_SECONDS:
            logger.info(f"⏱️ New bar needed: Duration threshold exceeded ({bar_duration:.1f}s)")
            return True
        
        # Continue with current bar
        return False
    
    def _get_new_bar_reason(
        self,
        previous_bar: Optional[TranscriptBar],
        new_speaker: str,
        timestamp: datetime
    ) -> str:
        """Get human-readable reason for creating new bar"""
        if not previous_bar:
            return "first_bar"
        
        if previous_bar.speaker != new_speaker:
            return "speaker_change"
        
        last_activity = self.last_activity.get(previous_bar.session_id)
        if last_activity:
            silence = (timestamp - last_activity).total_seconds()
            if silence > self.SILENCE_THRESHOLD_SECONDS:
                return "silence_threshold"
        
        if previous_bar.duration_seconds() > self.MAX_DURATION_SECONDS:
            return "duration_threshold"
        
        return "unknown"
    
    async def _finalize_bar(self, bar: TranscriptBar):
        """
        Finalize a transcript bar and queue it for emotion analysis.
        This does NOT block - emotion processing happens asynchronously.
        """
        bar.status = "processing_emotion"
        bar.updated_at = get_ist_now()
        
        logger.info(f"🔒 Finalized bar: session={bar.session_id}, bar_id={bar.id}, duration={bar.duration_seconds():.1f}s")
        
        # Queue for async emotion processing
        await self.emotion_queue.put(bar)
    
    async def get_session_bars(self, session_id: str) -> list:
        """Get all transcript bars for a session"""
        return self.all_bars.get(session_id, [])
    
    async def get_active_bar(self, session_id: str) -> Optional[TranscriptBar]:
        """Get currently active bar for a session"""
        return self.active_bars.get(session_id)
    
    async def force_finalize_session(self, session_id: str):
        """Force finalize any active bar for a session (e.g., when meeting ends)"""
        async with self._lock:
            if session_id in self.active_bars:
                bar = self.active_bars[session_id]
                await self._finalize_bar(bar)
                del self.active_bars[session_id]
                logger.info(f"🏁 Force finalized session: {session_id}")


# Singleton instance
_continuous_transcript_manager = None


def get_continuous_transcript_manager() -> ContinuousTranscriptManager:
    """Get or create singleton instance"""
    global _continuous_transcript_manager
    if _continuous_transcript_manager is None:
        _continuous_transcript_manager = ContinuousTranscriptManager()
    return _continuous_transcript_manager
