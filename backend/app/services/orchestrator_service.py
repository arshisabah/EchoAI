# app/services/orchestrator_service.py
"""
Fixed Orchestrator Service for real-time transcription and emotion analysis.
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import numpy as np

from app.services.transcription_service import get_transcription_service, process_audio_chunk
from app.services.emotion_analysis import get_emotion_service
from app.services.summary_service import get_summary_service
from app.services.speaker_identification_service import get_speaker_service
from app.services.audio_utils import bytes_to_numpy

logger = logging.getLogger(__name__)


class SessionData:
    """Container for session-level data and statistics."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.utcnow()
        self.transcript_entries: List[Dict[str, Any]] = []
        self.speakers: List[str] = []
        self.total_duration = 0.0
        self.is_active = True
        self.last_activity = datetime.utcnow()


class OrchestratorService:
    """
    Main orchestrator service for real-time AI processing.
    Coordinates transcription, emotion analysis, and speaker identification.
    """

    def __init__(self):
        self.transcription_service = get_transcription_service()
        self.emotion_service = get_emotion_service()
        self.summary_service = get_summary_service()
        self.speaker_service = get_speaker_service()
        
        # Session management
        self.active_sessions: Dict[str, SessionData] = {}
        
        logger.info("OrchestratorService initialized")

    async def start_session(self, session_id: str):
        """Start or restore a session."""
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = SessionData(session_id)
            logger.info(f"✅ Created new session: {session_id}")
        else:
            logger.info(f"Session {session_id} already exists.")
        
        return {
            "session_id": session_id,
            "status": "active",
            "created_at": self.active_sessions[session_id].created_at.isoformat()
        }

    async def process_audio_chunk(
        self,
        audio_bytes: bytes,
        session_id: str,
        participant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single audio chunk through the complete AI pipeline.
        Returns processed results with transcription and emotion analysis.
        """
        try:
            # Ensure session exists
            if session_id not in self.active_sessions:
                self.active_sessions[session_id] = SessionData(session_id)

            session = self.active_sessions[session_id]
            session.last_activity = datetime.utcnow()

            # Convert audio bytes to numpy array
            audio_array, sample_rate = bytes_to_numpy(audio_bytes, sample_rate=16000)
            
            if len(audio_array) == 0:
                logger.warning(f"Empty audio chunk for session {session_id}")
                return None

            # 1. TRANSCRIPTION - Get speech-to-text
            transcription_results = await process_audio_chunk(audio_array, session_id)
            
            if not transcription_results:
                logger.debug(f"No transcription results for session {session_id}")
                return None

            # Process each transcription result
            processed_entries = []
            
            for trans_entry in transcription_results:
                text = trans_entry.get("text", "").strip()
                if not text:
                    continue

                # 2. SPEAKER IDENTIFICATION
                speaker = await self.speaker_service.identify_speaker(
                    audio_array, session_id, sample_rate
                )
                
                # 3. EMOTION ANALYSIS - Analyze emotion from text
                emotion_result = await self.emotion_service.analyze_text(text)

                # 4. Update speaker statistics
                await self.speaker_service.update_speaker_statistics(
                    speaker,
                    speaking_duration=len(audio_array) / sample_rate,
                    word_count=len(text.split())
                )

                # 5. Build comprehensive entry
                entry = {
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "participant_id": participant_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    
                    # Transcription data
                    "text": text,
                    "speaker": speaker,
                    "confidence": trans_entry.get("confidence", 0.0),
                    "word_count": len(text.split()),
                    "processing_time_ms": trans_entry.get("processing_time_ms", 0.0),
                    "words": trans_entry.get("words", []),
                    
                    # Emotion analysis results
                    "emotion": emotion_result.get("emotion", "neutral"),
                    "emotion_confidence": emotion_result.get("confidence", 0.0),
                    "emotion_scores": emotion_result.get("scores", {}),
                    
                    # Audio characteristics
                    "audio_duration_ms": len(audio_array) / sample_rate * 1000,
                    "sample_rate": sample_rate
                }

                processed_entries.append(entry)
                
                # Add to session transcript
                session.transcript_entries.append(entry)
                if speaker not in session.speakers:
                    session.speakers.append(speaker)

            # Return the result
            if len(processed_entries) == 1:
                return processed_entries[0]
            elif len(processed_entries) > 1:
                # Multiple speakers detected - return combined result
                return {
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "participant_id": participant_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "type": "multi_speaker_chunk",
                    "entries": processed_entries,
                    "speaker_count": len(set(e["speaker"] for e in processed_entries)),
                    "total_words": sum(e["word_count"] for e in processed_entries)
                }
            else:
                return None

        except Exception as e:
            logger.exception(f"Orchestrator failed to process chunk for session {session_id}: {e}")
            return None

    async def generate_realtime_summary(self, session_id: str, last_n_entries: int = 10) -> Dict[str, Any]:
        """Generate a real-time summary of recent conversation."""
        try:
            session = self.active_sessions.get(session_id)
            if not session or not session.transcript_entries:
                return {
                    "summary": "No recent activity to summarize.",
                    "entry_count": 0,
                    "speakers": []
                }

            # Get recent entries
            recent_entries = session.transcript_entries[-last_n_entries:]
            recent_texts = [entry["text"] for entry in recent_entries if entry.get("text")]

            if not recent_texts:
                return {
                    "summary": "No text content to summarize.",
                    "entry_count": 0,
                    "speakers": []
                }

            # Generate summary
            summary_result = await self.summary_service.generate_structured_summary(
                recent_texts, session_id, mode="realtime"
            )

            # Add context
            speakers_in_summary = list(set(entry["speaker"] for entry in recent_entries))
            
            return {
                **summary_result,
                "speakers": speakers_in_summary,
                "entry_count": len(recent_entries),
                "time_range": {
                    "start": recent_entries[0]["timestamp"] if recent_entries else None,
                    "end": recent_entries[-1]["timestamp"] if recent_entries else None
                }
            }

        except Exception as e:
            logger.error(f"Real-time summary generation failed for session {session_id}: {e}")
            return {
                "summary": "Summary generation failed.",
                "entry_count": 0,
                "speakers": [],
                "error": str(e)
            }

    async def generate_session_insights(self, session_id: str) -> Dict[str, Any]:
        """Generate comprehensive insights for an entire session."""
        try:
            session = self.active_sessions.get(session_id)
            if not session:
                return {"error": f"Session {session_id} not found"}

            # Generate different types of analysis
            tasks = [
                self.summary_service.generate_meeting_insights(session.transcript_entries),
                self.emotion_service.analyze_session_emotions(session.transcript_entries),
                self.speaker_service.analyze_speaker_patterns(session_id)
            ]

            meeting_insights, emotion_insights, speaker_insights = await asyncio.gather(*tasks)

            # Combine all insights
            comprehensive_insights = {
                "session_id": session_id,
                "generated_at": datetime.utcnow().isoformat(),
                "session_duration_minutes": (
                    datetime.utcnow() - session.created_at
                ).total_seconds() / 60,
                
                # Meeting summary and insights
                "meeting_summary": meeting_insights.get("summary", ""),
                "action_items": meeting_insights.get("action_items", []),
                "key_topics": meeting_insights.get("key_topics", ""),
                "total_words": meeting_insights.get("total_words", 0),
                
                # Emotion analysis
                "overall_emotion": emotion_insights.get("overall_emotion", "neutral"),
                "emotion_distribution": emotion_insights.get("emotion_distribution", {}),
                "emotion_timeline": emotion_insights.get("emotion_timeline", []),
                
                # Speaker analytics
                "speaker_statistics": speaker_insights,
                "total_participants": len(session.speakers),
                "participant_list": session.speakers,
                
                # Session metadata
                "total_transcript_entries": len(session.transcript_entries),
                "session_start_time": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat()
            }

            return comprehensive_insights

        except Exception as e:
            logger.error(f"Session insights generation failed for {session_id}: {e}")
            return {
                "session_id": session_id,
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat()
            }

    async def get_session_transcript(
        self, 
        session_id: str, 
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """Get the complete transcript for a session."""
        try:
            session = self.active_sessions.get(session_id)
            if not session:
                return {"error": f"Session {session_id} not found"}

            transcript_data = {
                "session_id": session_id,
                "transcript": session.transcript_entries,
                "total_entries": len(session.transcript_entries),
                "speakers": session.speakers,
                "session_start": session.created_at.isoformat(),
                "last_update": session.last_activity.isoformat()
            }

            if include_metadata:
                # Add session statistics
                total_words = sum(entry.get("word_count", 0) for entry in session.transcript_entries)
                speaker_word_counts = {}
                
                for entry in session.transcript_entries:
                    speaker = entry.get("speaker", "Unknown")
                    words = entry.get("word_count", 0)
                    speaker_word_counts[speaker] = speaker_word_counts.get(speaker, 0) + words

                transcript_data["metadata"] = {
                    "total_words": total_words,
                    "speaker_word_counts": speaker_word_counts,
                    "session_duration_minutes": (
                        session.last_activity - session.created_at
                    ).total_seconds() / 60,
                    "average_words_per_entry": total_words / len(session.transcript_entries) if session.transcript_entries else 0
                }

            return transcript_data

        except Exception as e:
            logger.error(f"Failed to get transcript for session {session_id}: {e}")
            return {"error": str(e)}

    async def close_session(self, session_id: str) -> Dict[str, Any]:
        """Close a session and generate final summary."""
        try:
            session = self.active_sessions.get(session_id)
            if not session:
                return {"error": f"Session {session_id} not found"}

            # Generate final comprehensive summary
            final_insights = await self.generate_session_insights(session_id)
            
            # Generate final summary
            all_texts = [entry["text"] for entry in session.transcript_entries if entry.get("text")]
            final_summary = await self.summary_service.generate_structured_summary(
                all_texts, session_id, mode="final"
            )

            # Mark session as closed
            session.is_active = False
            
            session_data = {
                "session_id": session_id,
                "status": "closed",
                "final_summary": final_summary,
                "insights": final_insights,
                "closed_at": datetime.utcnow().isoformat(),
                "total_entries": len(session.transcript_entries),
                "duration_minutes": (
                    datetime.utcnow() - session.created_at
                ).total_seconds() / 60
            }

            logger.info(f"Session {session_id} closed successfully")
            return session_data

        except Exception as e:
            logger.error(f"Failed to close session {session_id}: {e}")
            return {"error": str(e)}

    def list_active_sessions(self) -> List[Dict[str, Any]]:
        """Get list of all active sessions."""
        active_sessions = []
        
        for session_id, session in self.active_sessions.items():
            if session.is_active:
                active_sessions.append({
                    "session_id": session_id,
                    "created_at": session.created_at.isoformat(),
                    "last_activity": session.last_activity.isoformat(),
                    "participant_count": len(session.speakers),
                    "transcript_entries": len(session.transcript_entries),
                    "duration_minutes": (
                        datetime.utcnow() - session.created_at
                    ).total_seconds() / 60
                })
        
        return active_sessions


# Singleton accessor
_orchestrator_service: Optional[OrchestratorService] = None


def get_orchestrator_service() -> OrchestratorService:
    """Get the singleton orchestrator service instance."""
    global _orchestrator_service
    if _orchestrator_service is None:
        _orchestrator_service = OrchestratorService()
    return _orchestrator_service