import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import pytz
from app.core.config import settings

logger = logging.getLogger(__name__)

class TranscriptMerger:
    """
    Google Meet-style transcript merging:
    - Merges consecutive transcripts from same speaker
    - Creates new entry only when speaker changes
    - Handles incremental updates without word repetition
    - Manages IST timestamps
    - Delays emotion analysis until speaker turn ends
    """
    
    def __init__(self):
        self.active_transcripts: Dict[str, Dict] = {}  # room_id -> active transcript data
        self.last_update_time: Dict[str, datetime] = {}  # room_id -> last update time
        self.timezone = pytz.timezone(settings.TIMEZONE)
        self.speaker_turn_timeout = settings.SPEAKER_TURN_TIMEOUT_SECONDS
        
    def get_ist_timestamp(self) -> str:
        """Get current timestamp in IST"""
        utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)
        ist_time = utc_now.astimezone(self.timezone)
        return ist_time.isoformat()
    
    def should_create_new_entry(self, room_id: str, speaker: str) -> bool:
        """
        Determine if we should create a new transcript entry or merge with existing.
        New entry if:
        1. No active transcript for this room
        2. Speaker changed
        3. Timeout exceeded (speaker paused too long)
        """
        if room_id not in self.active_transcripts:
            return True
        
        active = self.active_transcripts[room_id]
        
        # Different speaker = new entry
        if active.get("speaker") != speaker:
            logger.info(f"👥 Speaker change detected: {active.get('speaker')} -> {speaker}")
            return True
        
        # Check timeout
        if room_id in self.last_update_time:
            time_since_last = (datetime.utcnow() - self.last_update_time[room_id]).total_seconds()
            if time_since_last > self.speaker_turn_timeout:
                logger.info(f"⏰ Speaker turn timeout ({time_since_last:.1f}s) - creating new entry")
                return True
        
        return False
    
    def merge_or_create(
        self,
        room_id: str,
        speaker: str,
        username: str,
        text: str,
        is_final: bool = False,
        confidence: float = 0.0,
        user_id: str = None
    ) -> Dict:
        """
        Merge text with existing transcript or create new entry.
        Returns: {
            "action": "create" | "update",
            "entry_id": str,
            "text": str,
            "previous_text": str (for detecting new words only),
            "should_analyze_emotion": bool
        }
        """
        should_create = self.should_create_new_entry(room_id, speaker)
        
        if should_create:
            # Finalize previous transcript if exists (trigger emotion analysis)
            previous_entry = self.active_transcripts.get(room_id)
            if previous_entry:
                logger.info(f"🔚 Finalizing previous transcript for speaker {previous_entry.get('speaker')}")
                previous_entry["finalized"] = True
                previous_entry["should_analyze_emotion"] = True
            
            # Create new entry
            import uuid
            entry_id = str(uuid.uuid4())
            entry = {
                "id": entry_id,
                "room_id": room_id,
                "speaker": speaker,
                "username": username,
                "user_id": user_id or speaker,
                "text": text,
                "previous_text": "",
                "confidence": confidence,
                "timestamp": self.get_ist_timestamp(),
                "start_time": datetime.utcnow(),
                "last_update": datetime.utcnow(),
                "finalized": is_final,
                "should_analyze_emotion": is_final,
                "word_count": len(text.split())
            }
            
            self.active_transcripts[room_id] = entry
            self.last_update_time[room_id] = datetime.utcnow()
            
            logger.info(f"📝 Created new transcript entry for {username} in {room_id}")
            
            return {
                "action": "create",
                "entry": entry,
                "previous_entry": previous_entry  # Return previous to analyze its emotion
            }
        
        else:
            # Update existing entry
            active = self.active_transcripts[room_id]
            previous_text = active["text"]
            
            # Append new text (Deepgram handles deduplication)
            active["text"] = text  # Deepgram sends full text with incremental updates
            active["previous_text"] = previous_text
            active["last_update"] = datetime.utcnow()
            active["confidence"] = max(active["confidence"], confidence)
            active["word_count"] = len(text.split())
            active["finalized"] = is_final
            active["should_analyze_emotion"] = is_final
            
            self.last_update_time[room_id] = datetime.utcnow()
            
            # Extract only new words for display
            new_words = self._extract_new_words(previous_text, text)
            
            logger.info(f"📝 Updated transcript for {username}: +{len(new_words.split())} words")
            
            return {
                "action": "update",
                "entry": active,
                "new_words": new_words,
                "previous_entry": None
            }
    
    def _extract_new_words(self, previous_text: str, current_text: str) -> str:
        """
        Extract only the new words added to the transcript.
        Deepgram sends full text each time, so we need to find the diff.
        """
        if not previous_text:
            return current_text
        
        # Simple approach: if current starts with previous, return the difference
        if current_text.startswith(previous_text):
            new_part = current_text[len(previous_text):].strip()
            return new_part
        
        # Fallback: return full current text if no clear match
        return current_text
    
    def finalize_active_transcript(self, room_id: str) -> Optional[Dict]:
        """
        Finalize the active transcript for a room.
        Returns the finalized entry for emotion analysis.
        """
        if room_id in self.active_transcripts:
            entry = self.active_transcripts[room_id]
            entry["finalized"] = True
            entry["should_analyze_emotion"] = True
            logger.info(f"🔚 Finalized transcript for room {room_id}")
            return entry
        return None
    
    def clear_room(self, room_id: str):
        """Clear active transcript for a room"""
        if room_id in self.active_transcripts:
            del self.active_transcripts[room_id]
        if room_id in self.last_update_time:
            del self.last_update_time[room_id]
        logger.info(f"🧹 Cleared transcript state for room {room_id}")

# Global instance
_transcript_merger = None

def get_transcript_merger() -> TranscriptMerger:
    global _transcript_merger
    if _transcript_merger is None:
        _transcript_merger = TranscriptMerger()
    return _transcript_merger
