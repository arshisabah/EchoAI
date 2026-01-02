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
from app.modules.realtime_store import get_transcript_store
from app.utils.timezone import get_ist_timestamp
from app.services.continuous_transcript_manager import get_continuous_transcript_manager
from app.services.async_emotion_processor import get_async_emotion_processor

logger = logging.getLogger(__name__)


# ==========================================================
# AUTO-TRIMMING AUDIO BUFFER
# ==========================================================
class AutoTrimmingAudioList(list):
    """List that automatically trims to max samples when modified."""
    MAX_SAMPLES = 16000 * 3  # 3 seconds at 16kHz
    
    def append(self, item):
        super().append(item)
        self._trim()
    
    def _trim(self):
        """Trim buffer by sample count (FIFO - remove oldest chunks)."""
        total_len = sum(len(x) for x in self)
        while total_len > self.MAX_SAMPLES and len(self) > 1:
            self.pop(0)  # Remove oldest chunk
            total_len = sum(len(x) for x in self)


class AudioBufferDict(dict):
    """Dict that returns AutoTrimmingAudioList for audio buffers."""
    
    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = AutoTrimmingAudioList()
        return self[key]


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
        from app.core.config import settings
        
        self.transcription_service = get_transcription_service()
        self.summary_service = get_summary_service()
        self.speaker_service = get_speaker_service()
        self.transcript_store = get_transcript_store()
        self.transcript_manager = get_continuous_transcript_manager()
        self.emotion_processor = get_async_emotion_processor()

        self.active_sessions: Dict[str, SessionData] = {}
        self.audio_buffers: AudioBufferDict = AudioBufferDict()
        
        # Enable continuous transcription mode (Google Meet-like)
        self.use_continuous_transcription = True
        
        # Initialize streaming transcription (using Faster-Whisper - local, unlimited, free)
        self.use_streaming = True  # Always use streaming with local model
        self.assemblyai_service = None
        self.whisper_service = None
        
        try:
            from app.services.faster_whisper_transcription import get_faster_whisper_service
            self.whisper_service = get_faster_whisper_service()
            logger.info("✅ Faster-Whisper streaming transcription enabled (local, unlimited, free)")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Faster-Whisper: {e}", exc_info=True)
            self.use_streaming = False

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
            
            # Start emotion processor if not running
            if not self.emotion_processor.running:
                await self.emotion_processor.start()
            
            # Note: Faster-Whisper stream callback is registered by meeting.py, not here
            # This allows meeting.py to handle broadcasts directly
            
            logger.info(f"🟢 Created new session: {session_id} (streaming: {self.use_streaming}, continuous: {self.use_continuous_transcription})")
        return {
            "session_id": session_id,
            "status": "active",
            "created_at": self.active_sessions[session_id].created_at.isoformat()
        }

    # ==========================================================
    # PROCESS WITH CONTINUOUS TRANSCRIPTION (NEW)
    # ==========================================================
    async def process_transcription_continuous(
        self, 
        session_id: str,
        speaker: str,
        text: str,
        confidence: float,
        audio_array: Optional[np.ndarray] = None,
        speaker_name: str = "Unknown"
    ) -> Dict[str, Any]:
        """
        Process transcription using continuous transcript bar management.
        Returns action (append/create) and bar data for WebSocket response.
        """
        try:
            # Process through continuous transcript manager
            result = await self.transcript_manager.process_transcription(
                session_id=session_id,
                speaker=speaker,
                text=text,
                confidence=confidence,
                timestamp=datetime.utcnow(),
                speaker_name=speaker_name
            )
            
            bar = result["bar"]
            action = result["action"]
            
            # Cache audio for emotion processing (if available)
            if audio_array is not None and len(audio_array) > 0:
                self.emotion_processor.cache_audio_for_bar(bar.id, audio_array)
            
            # Build response for WebSocket
            response = {
                "type": "transcript_bar",
                "action": action,  # "append" or "create"
                "bar": bar.to_dict()
            }
            
            if action == "create" and "reason" in result:
                response["reason"] = result["reason"]
            
            logger.info(
                f"📊 Continuous transcription: action={action}, "
                f"session={session_id}, speaker={speaker}, "
                f"bar_id={bar.id}, text_length={len(text)}"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Error in continuous transcription: {e}", exc_info=True)
            return {
                "type": "transcript_bar",
                "action": "create",
                "bar": {
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "speaker": speaker,
                    "text": text,
                    "started_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                    "confidence": confidence,
                    "status": "active",
                    "word_count": len(text.split())
                }
            }

    # ==========================================================
    # HANDLE FASTER-WHISPER TRANSCRIPT CALLBACK
    # ==========================================================
    async def _handle_whisper_transcript(self, session_id: str, transcript_data: Dict[str, Any]):
        """Handle transcript callback from Faster-Whisper."""
        try:
            logger.info(f"📝 Faster-Whisper transcript received for {session_id}: {transcript_data.get('text', '')[:50]}")
            # Process transcript data if needed
            # This is called by Faster-Whisper service when transcript is ready
        except Exception as e:
            logger.error(f"❌ Error handling Faster-Whisper transcript: {e}", exc_info=True)

    # ==========================================================
    # PROCESS AUDIO CHUNK - FIXED
    # ==========================================================
    async def process_audio_chunk(self, audio_bytes: bytes, session_id: str, participant_id=None):
        """
        Process audio chunk using either streaming (Faster-Whisper) or legacy (buffered) mode.
        """
        # Route to appropriate processing mode
        logger.info(f"🔀 Routing audio - use_streaming: {self.use_streaming}, whisper_service: {self.whisper_service is not None}")
        if self.use_streaming and self.whisper_service:
            logger.info(f"🎯 Using STREAMING mode for {session_id}")
            return await self._process_audio_streaming(audio_bytes, session_id, participant_id)
        else:
            logger.info(f"🎯 Using LEGACY mode for {session_id}")
            return await self._process_audio_legacy(audio_bytes, session_id, participant_id)
    
    # ==========================================================
    # STREAMING MODE (DEEPGRAM)
    # ==========================================================
    async def _process_audio_streaming(self, audio_bytes: bytes, session_id: str, participant_id=None):
        """
        Process audio using Faster-Whisper streaming - immediate processing without buffering.
        """
        try:
            logger.info(f"🎵 [STREAMING] Processing audio - session: {session_id}, bytes: {len(audio_bytes)}")
            
            # Ensure session exists
            if session_id not in self.active_sessions:
                logger.warning(f"⚠️ Session {session_id} not found, creating it")
                await self.start_session(session_id)
            
            session = self.active_sessions[session_id]
            session.last_activity = datetime.utcnow()
            
            # Send audio to Faster-Whisper
            try:
                # Check if Faster-Whisper service is available
                if not self.whisper_service:
                    logger.error(f"❌ Faster-Whisper service not initialized")
                    return None
                
                logger.info(f"📤 Sending {len(audio_bytes)} bytes to Faster-Whisper for {session_id}")
                success = await self.whisper_service.send_audio(session_id, audio_bytes)
                
                if success:
                    logger.info(f"✅ Audio sent successfully to Faster-Whisper")
                else:
                    logger.warning(f"⚠️ Faster-Whisper send_audio returned False for {session_id}")
                    
            except Exception as e:
                logger.error(f"❌ Error sending audio to Faster-Whisper: {e}", exc_info=True)
                return None
            
            if not success:
                logger.warning(f"⚠️ Failed to send audio to Faster-Whisper for {session_id}")
                return None
            
            # Return immediately - transcripts will come via callback
            return {"type": "streaming", "status": "processing"}
            
        except Exception as e:
            logger.error(f"❌ Streaming audio processing error for {session_id}: {e}", exc_info=True)
            return None
    
    # ==========================================================
    # LEGACY MODE (BUFFERED WHISPER)
    # ==========================================================
    async def _process_audio_legacy(self, audio_bytes: bytes, session_id: str, participant_id=None):
        """
        Legacy buffered mode using Whisper transcription.
        """
        try:
            logger.info(f"🎵 [LEGACY] Processing audio chunk - session: {session_id}, participant: {participant_id}, bytes: {len(audio_bytes)}")
            
            # Ensure session exists
            if session_id not in self.active_sessions:
                logger.warning(f"⚠️ [LEGACY] Session {session_id} not found, creating it")
                await self.start_session(session_id)
            
            session = self.active_sessions[session_id]
            session.last_activity = datetime.utcnow()

            # ---------- STEP 1: Decode audio safely ----------
            sample_rate = 16000
            audio_array = None

            # Try PCM
            try:
                pcm = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                if len(pcm) > 0:
                    audio_array = pcm
                    logger.debug(f"✅ Decoded as PCM: {len(pcm)} samples")
            except Exception as e:
                logger.debug(f"❌ PCM decode failed: {e}")

            # Try soundfile
            if audio_array is None:
                try:
                    io_stream = io.BytesIO(audio_bytes)
                    sf_audio, sf_sr = sf.read(io_stream, dtype="float32", always_2d=False)
                    if sf_audio.ndim > 1:
                        sf_audio = np.mean(sf_audio, axis=1)
                    audio_array = sf_audio
                    sample_rate = sf_sr
                    logger.debug(f"✅ Decoded with soundfile: {len(sf_audio)} samples at {sf_sr}Hz")
                except Exception as e:
                    logger.debug(f"❌ Soundfile decode failed: {e}")

            # Fallback decode
            if audio_array is None:
                try:
                    audio_array, sample_rate = bytes_to_numpy(audio_bytes, sample_rate=16000)
                    logger.debug(f"✅ Decoded with fallback: {len(audio_array)} samples")
                except Exception as e:
                    logger.error(f"❌ All audio decode methods failed: {e}")

            # Empty or invalid audio
            if audio_array is None or len(audio_array) == 0:
                logger.warning(f"⚠️ Empty or invalid audio array for session {session_id}")
                return None

            # Skip silence
            mean_amplitude = np.abs(audio_array).mean()
            if mean_amplitude < 0.006:
                logger.debug(f"🔇 Skipping silence for session {session_id} (mean amplitude: {mean_amplitude:.6f})")
                return None
            
            logger.debug(f"🔊 Audio has voice activity (mean amplitude: {mean_amplitude:.6f})")

            # Better normalization - preserve dynamics
            max_amplitude = np.max(np.abs(audio_array))
            if max_amplitude > 0.1:  # Only normalize if needed
                audio_array = audio_array / max_amplitude * 0.9  # Leave 10% headroom
            # Apply advanced preprocessing for better accuracy
            try:
                from app.services.audio_preprocessing import preprocess_audio_for_transcription
                audio_array = preprocess_audio_for_transcription(audio_array, sample_rate=16000)
                logger.debug(f"✅ Applied audio preprocessing for session {session_id}")
            except Exception as preprocess_err:
                logger.warning(f"⚠️ Audio preprocessing skipped: {preprocess_err}")
            # ---------- STEP 2: BUFFER ----------
            # Buffer automatically trims to 3 seconds via AutoTrimmingAudioList
            buf = self.audio_buffers.setdefault(session_id, [])
            buf.append(audio_array)  # Auto-trims if needed

            # Combine chunks
            try:
                combined = np.concatenate(self.audio_buffers[session_id])
            except:
                self.audio_buffers[session_id] = []
                return None

            duration_sec = len(combined) / 16000
            
            # ✅ ADD DEBUG LOGGING
            logger.info(f"📊 Buffer stats for {session_id}: duration={duration_sec:.2f}s, samples={len(combined)}")


            # Wait for at least 0.8 seconds OR detect silence boundary (0.5s silence at end)
            # Reduced from 1.5s to 0.8s for better real-time responsiveness
            if duration_sec < 0.8:
                logger.debug(f"⏳ Buffering audio for session {session_id}: {duration_sec:.2f}s / 0.8s minimum")
                return {"type": "listening", "buffered_duration": duration_sec}
            
            # ✅ FIX: Force transcription after 2.0s OR when silence is detected
            if duration_sec < 2.0:
                tail_samples = min(int(16000 * 0.5), len(combined))  # Check last 0.5 seconds
                tail = combined[-tail_samples:]
                tail_energy = np.sqrt(np.mean(tail ** 2))
                logger.info(f"🔊 Tail energy: {tail_energy:.6f} (threshold: 0.008) - Duration: {duration_sec:.2f}s")
                
                if tail_energy >= 0.008:  # Still speaking - reduced from 0.012 for better sensitivity
                    logger.debug(f"🗣️ Still speaking - buffering more audio for session {session_id}")
                    return {"type": "listening", "buffered_duration": duration_sec}
                else:
                    logger.info(f"🔇 Silence detected at {duration_sec:.2f}s - proceeding to transcription")
            else:
                # Force transcription after 2.0 seconds regardless of silence
                logger.info(f"⏰ Buffer timeout at {duration_sec:.2f}s - forcing transcription")

            # Clear buffer after processing
            self.audio_buffers[session_id] = []
            audio_array = combined

            logger.info(f"🎯 TRANSCRIPTION TRIGGERED - Duration: {duration_sec:.2f}s, Samples: {len(audio_array)}")

            # Whisper empty reshape prevention
            if len(audio_array) < 300:
                logger.warning(f"⚠️ Chunk too small for session {session_id} ({len(audio_array)} samples), skipping.")
                return None

            # ---------- STEP 3: TRANSCRIBE ----------
            logger.info(f"🎙️ Starting transcription for session {session_id} - {duration_sec:.2f}s audio ({len(audio_array)} samples)")
            asr_results = await self.transcription_service.transcribe_chunk(
                audio_array, session_id, 16000
            )
            logger.info(f"📝 Transcription complete for session {session_id} - {len(asr_results)} result(s)")

            processed = []
            for r in asr_results:
                text = (r.text or "").strip()
                if not text:
                    logger.debug(f"⚠️ Empty transcription result for session {session_id}, skipping")
                    continue

                logger.info(f"💬 Transcribed text for session {session_id}: '{text[:100]}...' (confidence: {r.confidence:.2f})")

                # ✅ FIX: Use participant_id if provided, otherwise identify speaker
                if participant_id:
                    speaker = participant_id
                    logger.debug(f"👤 Using provided participant_id as speaker: {speaker}")
                else:
                    speaker = await self.speaker_service.identify_speaker(
                        audio_array, session_id, 16000
                    )
                    logger.debug(f"👤 Identified speaker: {speaker}")

                # Emotion (safe)
                try:
                    logger.debug(f"🎭 Analyzing emotion for session {session_id}")
                    emotion = await analyze_text_and_audio_combined(
                        text=text, audio_array=audio_array,
                        sample_rate=16000, text_weight=0.6, audio_weight=0.4
                    )
                    logger.debug(f"🎭 Emotion detected: {emotion.get('emotion', 'neutral')} (confidence: {emotion.get('confidence', 0):.2f})")
                except Exception as emotion_err:
                    logger.warning(f"⚠️ Emotion analysis failed for session {session_id}: {emotion_err}")
                    emotion = {"emotion": "neutral", "confidence": 0, "scores": {}}

                entry = {
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "participant_id": participant_id,
                    "timestamp": get_ist_timestamp(),
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

                # ✅ FIX: Sync to transcript store for downloads
                try:
                    store_entry = await self.transcript_store.add_transcript_entry(
                        meeting_id=session_id,
                        speaker=speaker,
                        text=text,
                        confidence=r.confidence
                    )
                    # Add emotion data to store entry
                    if store_entry:
                        store_entry.emotions = {
                            "emotion": emotion["emotion"],
                            "confidence": emotion.get("confidence", 0),
                            "scores": emotion.get("scores", {})
                        }
                except Exception as store_err:
                    logger.warning(f"Failed to sync to transcript store: {store_err}")

                processed.append(entry)

            # ✅ FIX: Return correct format expected by meeting.py
            if len(processed) == 1:
                logger.info(f"✅ RETURNING SINGLE ENTRY:")
                logger.info(f"   - speaker: {processed[0].get('speaker')}")
                logger.info(f"   - text: {processed[0].get('text', '')[:100]}...")
                logger.info(f"   - emotion: {processed[0].get('emotion')}")
                logger.info(f"   - has text field: {'text' in processed[0]}")
                logger.info(f"   - all keys: {list(processed[0].keys())}")
                return processed[0]
            elif len(processed) > 1:
                logger.info(f"✅ RETURNING MULTI-SPEAKER with {len(processed)} entries")
                return {"type": "multi_speaker_chunk", "entries": processed}
            else:
                logger.warning(f"⚠️ No valid entries processed for session {session_id} - RETURNING NONE")
                logger.warning(f"   - asr_results count: {len(asr_results)}")
                logger.warning(f"   - processed count: {len(processed)}")
                return None

        except Exception as e:
            logger.exception(f"❌ process_audio_chunk failed for session {session_id}: {e}")
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
    # SESSION MANAGEMENT METHODS
    # ==========================================================
    def get_session_list(self) -> List[Dict[str, Any]]:
        """Get list of all active sessions."""
        sessions = []
        for session_id, session in self.active_sessions.items():
            sessions.append({
                "session_id": session_id,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "is_active": session.is_active,
                "speaker_count": len(session.speakers),
                "entry_count": len(session.transcript_entries)
            })
        return sessions

    def get_session_details(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a session."""
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        return {
            "session_id": session_id,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "is_active": session.is_active,
            "speakers": session.speakers,
            "speaker_count": len(session.speakers),
            "transcript_entries": session.transcript_entries,
            "total_entries": len(session.transcript_entries)
        }

    def get_emotion_timeline(self, session_id: str) -> List[Dict[str, Any]]:
        """Get emotion timeline for a session."""
        session = self.active_sessions.get(session_id)
        if not session:
            return []
        
        timeline = []
        for entry in session.transcript_entries:
            if entry.get("emotion"):
                timeline.append({
                    "timestamp": entry.get("timestamp"),
                    "emotion": entry.get("emotion"),
                    "confidence": entry.get("emotion_confidence", 0),
                    "speaker": entry.get("speaker"),
                    "text_preview": entry.get("text", "")[:50]
                })
        
        return timeline

    # ==========================================================
    # CLOSE SESSION
    # ==========================================================
    async def close_session(self, session_id: str):
        """Close a session and cleanup resources."""
        try:
            if session_id in self.active_sessions:
                session = self.active_sessions[session_id]
                session.is_active = False
                session.last_activity = datetime.utcnow()
                logger.info(f"🔒 Closed session: {session_id}")
            
            # Finalize any active transcript bars
            if self.use_continuous_transcription:
                await self.transcript_manager.force_finalize_session(session_id)
            
            # Clear audio buffer
            if session_id in self.audio_buffers:
                del self.audio_buffers[session_id]
        except Exception as e:
            logger.error(f"Error closing session {session_id}: {e}")

    # ==========================================================
    # GENERATE REALTIME SUMMARY
    # ==========================================================
    async def generate_realtime_summary(self, session_id: str) -> Dict[str, Any]:
        """Generate a real-time summary for a session."""
        try:
            session = self.active_sessions.get(session_id)
            if not session:
                return {"error": "Session not found"}
            
            # Get transcript texts
            transcript_texts = [entry.get("text", "") for entry in session.transcript_entries]
            
            if not transcript_texts:
                return {
                    "session_id": session_id,
                    "summary": "No transcript available yet",
                    "entry_count": 0
                }
            
            # Generate summary using summary service
            summary_result = await self.summary_service.generate_structured_summary(
                transcript_texts,
                session_id,
                mode="realtime"
            )
            
            return {
                "session_id": session_id,
                "summary": summary_result,
                "entry_count": len(session.transcript_entries),
                "speaker_count": len(session.speakers),
                "generated_at": get_ist_timestamp()
            }
        except Exception as e:
            logger.error(f"Error generating realtime summary for {session_id}: {e}")
            return {
                "session_id": session_id,
                "error": str(e),
                "summary": "Error generating summary"
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