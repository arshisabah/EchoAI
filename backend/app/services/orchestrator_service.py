# app/services/orchestrator_service.py
"""
FIXED VERSION – Correct response format for meeting router
✅ Returns multi_speaker_chunk (not "multi")
✅ Proper speaker identification
✅ Safe buffering with limits
"""

import asyncio
import io
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

import numpy as np
import soundfile as sf
import librosa

from app.services.transcription_service import get_transcription_service
from app.services.emotion_analysis import analyze_text_and_audio_combined
from app.services.summary_service import get_summary_service
from app.services.speaker_identification_service import get_speaker_service
from app.services.audio_utils import bytes_to_numpy

logger = logging.getLogger(__name__)


# ==========================================================
# SESSION DATA CLASS
# ==========================================================
class SessionData:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.transcript_entries = []
        self.speakers = []
        self.is_active = True


# ==========================================================
# ORCHESTRATOR SERVICE
# ==========================================================
class OrchestratorService:

    def __init__(self):
        self.transcription_service = get_transcription_service()
        self.summary_service = get_summary_service()
        self.speaker_service = get_speaker_service()

        self.active_sessions: Dict[str, SessionData] = {}
        self.audio_buffers: Dict[str, List[np.ndarray]] = {}

        logger.info("✅ OrchestratorService initialized")

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._cleanup_inactive_sessions())
        except RuntimeError:
            pass  # running outside event loop (startup okay)

    # ==========================================================
    # START SESSION
    # ==========================================================
    async def start_session(self, session_id: str):
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = SessionData(session_id)
            logger.info(f"🟢 Created new session: {session_id}")
        return {
            "session_id": session_id,
            "status": "active",
            "created_at": self.active_sessions[session_id].created_at.isoformat()
        }

    # ==========================================================
    # PROCESS AUDIO CHUNK - FIXED
    # ==========================================================
    async def process_audio_chunk(self, audio_bytes: bytes, session_id: str, participant_id=None):
        try:
            # Ensure session exists
            session = self.active_sessions.setdefault(session_id, SessionData(session_id))
            session.last_activity = datetime.utcnow()

            # ---------- STEP 1: Decode audio safely ----------
            sample_rate = 16000
            audio_array = None

            # Try PCM
            try:
                pcm = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                if len(pcm) > 0:
                    audio_array = pcm
            except:
                pass

            # Try soundfile
            if audio_array is None:
                try:
                    io_stream = io.BytesIO(audio_bytes)
                    sf_audio, sf_sr = sf.read(io_stream, dtype="float32", always_2d=False)
                    if sf_audio.ndim > 1:
                        sf_audio = np.mean(sf_audio, axis=1)
                    audio_array = sf_audio
                    sample_rate = sf_sr
                except:
                    pass

            # Fallback decode
            if audio_array is None:
                audio_array = bytes_to_numpy(audio_bytes, sample_rate=16000)
                sample_rate = 16000

            # Empty or invalid audio
            if audio_array is None or len(audio_array) == 0:
                return None

            # Skip silence
            if np.abs(audio_array).mean() < 0.004:
                return None

            # Normalize
            audio_array = audio_array / (np.max(np.abs(audio_array)) + 1e-6)

            # ---------- STEP 2: BUFFER ----------
            buf = self.audio_buffers.setdefault(session_id, [])
            buf.append(audio_array)

            # HARD LIMIT: max 5s buffer
            MAX_SAMPLES = 16000 * 5
            total_len = sum(len(x) for x in buf)
            if total_len > MAX_SAMPLES:
                self.audio_buffers[session_id] = buf[-3:]

            # Combine chunks
            try:
                combined = np.concatenate(self.audio_buffers[session_id])
            except:
                self.audio_buffers[session_id] = []
                return None

            duration_sec = len(combined) / 16000

            if duration_sec < 4.0:
                return {"type": "listening", "buffered_duration": duration_sec}

            # Clear buffer after processing
            self.audio_buffers[session_id] = []
            audio_array = combined

            # Whisper empty reshape prevention
            if len(audio_array) < 300:
                logger.warning("⚠️ Chunk too small, skipping.")
                return None

            # ---------- STEP 3: TRANSCRIBE ----------
            asr_results = await self.transcription_service.transcribe_chunk(
                audio_array, session_id, 16000
            )

            processed = []
            for r in asr_results:
                text = (r.text or "").strip()
                if not text:
                    continue

                # ✅ FIX: Use participant_id if provided, otherwise identify speaker
                if participant_id:
                    speaker = participant_id
                else:
                    speaker = await self.speaker_service.identify_speaker(
                        audio_array, session_id, 16000
                    )

                # Emotion (safe)
                try:
                    emotion = await analyze_text_and_audio_combined(
                        text=text, audio_array=audio_array,
                        sample_rate=16000, text_weight=0.6, audio_weight=0.4
                    )
                except:
                    emotion = {"emotion": "neutral", "confidence": 0, "scores": {}}

                entry = {
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "participant_id": participant_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "text": text,
                    "speaker": speaker,
                    "confidence": r.confidence,
                    "word_count": len(text.split()),
                    "processing_time_ms": r.processing_time_ms,
                    "words": r.words,
                    "emotion": emotion["emotion"],
                    "emotion_confidence": emotion.get("confidence", 0),
                    "emotion_scores": emotion.get("scores", {}),
                }

                session.transcript_entries.append(entry)
                if speaker not in session.speakers:
                    session.speakers.append(speaker)

                processed.append(entry)

            # ✅ FIX: Return correct format expected by meeting.py
            if len(processed) == 1:
                return processed[0]
            elif len(processed) > 1:
                return {"type": "multi_speaker_chunk", "entries": processed}
            else:
                return None

        except Exception as e:
            logger.exception(f"❌ process_audio_chunk failed: {e}")
            return None

    # ==========================================================
    # GET SESSION TRANSCRIPT
    # ==========================================================
    async def get_session_transcript(self, session_id: str):
        session = self.active_sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        return {
            "session_id": session_id,
            "entries": session.transcript_entries,
            "speaker_count": len(session.speakers),
            "speakers": session.speakers,
            "total_entries": len(session.transcript_entries),
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
        }

    # ==========================================================
    # CLEAN INACTIVE SESSIONS
    # ==========================================================
    async def _cleanup_inactive_sessions(self):
        while True:
            await asyncio.sleep(300)
            now = datetime.utcnow()

            stale = [
                sid for sid, s in self.active_sessions.items()
                if (now - s.last_activity).total_seconds() > 1800
            ]

            for sid in stale:
                del self.active_sessions[sid]
                self.audio_buffers.pop(sid, None)
                logger.info(f"🧹 Cleaned inactive session {sid}")


# ==========================================================
# SINGLETON
# ==========================================================
_orchestrator = None


def get_orchestrator_service():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OrchestratorService()
    return _orchestrator