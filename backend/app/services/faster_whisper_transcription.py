"""
Faster-Whisper based real-time transcription service
Completely free, runs locally, no API costs
"""
import asyncio
import logging
from typing import Optional, Callable
from collections import deque
import numpy as np
import threading

logger = logging.getLogger(__name__)


class FasterWhisperService:
    """Real-time transcription using Faster-Whisper (local, free)"""
    
    def __init__(self):
        self.model = None
        self.active_sessions = {}
        self.audio_buffers = {}
        self.processing_tasks = {}
        self.model_lock = threading.Lock()
        
    def initialize_model(self):
        """Lazy load the model on first use"""
        if self.model is not None:
            return
            
        try:
            from faster_whisper import WhisperModel
            
            # Use base model for optimal speed/accuracy balance
            logger.info("🔧 Loading Faster-Whisper model (base - optimized balance)...")
            self.model = WhisperModel(
                "base",  # base=optimal balance for multi-user scenarios
                device="cpu",
                compute_type="int8",  # Optimized for CPU speed
                num_workers=1  # Single worker for lowest latency
            )
            logger.info("✅ Faster-Whisper model loaded successfully (base - optimized mode)")
            
        except Exception as e:
            logger.error(f"❌ Failed to load Faster-Whisper model: {e}")
            raise
    
    async def start_stream(
        self,
        session_id: str,
        on_transcript: Callable,
        language: str = "en",
        **kwargs
    ) -> bool:
        """Start transcription stream for a session"""
        try:
            # Initialize model on first use
            if self.model is None:
                self.initialize_model()
            
            # Create audio buffer for this session
            self.audio_buffers[session_id] = deque(maxlen=500)  # Keep last 500 chunks (~250 seconds)
            self.active_sessions[session_id] = {
                "callback": on_transcript,
                "language": language,
                "running": True,
                "accumulated_audio": bytearray(),
                "last_text": ""
            }
            
            # Start processing task
            self.processing_tasks[session_id] = asyncio.create_task(
                self._process_audio_stream(session_id)
            )
            
            logger.info(f"✅ Started Faster-Whisper stream for {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start Faster-Whisper stream: {e}")
            return False
    
    async def send_audio(self, session_id: str, audio_bytes: bytes) -> bool:
        """Add audio to processing buffer"""
        try:
            if session_id not in self.active_sessions:
                logger.warning(f"⚠️ Session {session_id} not active")
                return False
            
            # Add to buffer
            self.audio_buffers[session_id].append(audio_bytes)
            
            # Also accumulate for continuous processing
            self.active_sessions[session_id]["accumulated_audio"].extend(audio_bytes)
            
            # Update last audio time and reset silence flag (user is speaking again)
            self.active_sessions[session_id]["last_audio_time"] = asyncio.get_event_loop().time()
            self.active_sessions[session_id]["silence_flag_set"] = False
            
            logger.info(f"🎵 Added {len(audio_bytes)} bytes, buffer now: {len(self.active_sessions[session_id]['accumulated_audio'])} bytes")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding audio to buffer: {e}")
            return False
    
    async def _process_audio_stream(self, session_id: str):
        """Continuously process audio buffer"""
        try:
            session = self.active_sessions[session_id]
            process_interval = 0.3  # Process every 300ms
            min_audio_length = 64000  # 2 seconds minimum (increased from 0.5s)
            silence_threshold = 10.0  # 10 seconds of silence
            duration_threshold = 30.0  # 30 seconds continuous speaking
            
            session["last_audio_time"] = asyncio.get_event_loop().time()
            session["bar_start_time"] = asyncio.get_event_loop().time()
            session["last_transcript_text"] = ""
            session["accumulated_text"] = ""  # Accumulate text for current bar
            session["current_speaker"] = session_id
            session["create_new_bar"] = False
            session["silence_flag_set"] = False
            session["duration_flag_set"] = False
            
            logger.info(f"🎙️ Starting audio processing loop for {session_id}")
            
            while session["running"]:
                await asyncio.sleep(process_interval)
                
                current_time = asyncio.get_event_loop().time()
                time_since_audio = current_time - session.get("last_audio_time", current_time)
                bar_duration = current_time - session.get("bar_start_time", current_time)
                
                # Check if we should create a new bar on NEXT transcript
                # 1. After 3 seconds of silence
                if time_since_audio > silence_threshold and not session.get("silence_flag_set", False):
                    session["create_new_bar"] = True
                    session["silence_flag_set"] = True
                    logger.info(f"🔇 {silence_threshold}s silence detected - will create new bar on next speech")
                
                # 2. After 30 seconds of continuous speaking
                if bar_duration > duration_threshold and not session.get("duration_flag_set", False):
                    session["create_new_bar"] = True
                    session["duration_flag_set"] = True
                    logger.info(f"⏱️ 30s duration reached - will create new bar on next speech")
                
                # Get accumulated audio
                audio_data = bytes(session["accumulated_audio"])
                
                if len(audio_data) < min_audio_length:
                    logger.info(f"⏳ Buffer too small: {len(audio_data)}/{min_audio_length} bytes - waiting...")
                    continue
                
                logger.info(f"🎤 Processing {len(audio_data)} bytes of audio")
                
                # Convert to numpy array
                audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Check audio level
                audio_level = np.abs(audio_array).max()
                audio_rms = np.sqrt(np.mean(audio_array**2))
                logger.info(f"🔊 Audio level - max: {audio_level:.4f}, rms: {audio_rms:.4f}")
                
                # Skip if audio is too quiet (likely silence)
                if audio_rms < 0.001:
                    logger.warning(f"⚠️ Audio too quiet (RMS: {audio_rms:.4f}), skipping transcription")
                    session["accumulated_audio"] = bytearray()
                    continue
                
                # Transcribe
                try:
                    logger.info(f"🔄 Calling model.transcribe() for {len(audio_array)} samples")
                    segments, info = self.model.transcribe(
                        audio_array,
                        language="en",  # Force English language
                        task="transcribe",  # Transcribe (don't translate)
                        beam_size=1,
                        best_of=1,
                        temperature=[0.0, 0.2, 0.4, 0.6],  # Try multiple temperatures for better detection
                        vad_filter=False,  # Disable VAD - was filtering all speech as noise
                        word_timestamps=False,
                        no_speech_threshold=0.3  # Lower threshold = more sensitive to speech
                    )
                    
                    # Convert generator to list to check if empty
                    segments_list = list(segments)
                    logger.info(f"📊 Model returned {len(segments_list)} segments")
                    
                    # Build full text from all segments
                    full_text = ""
                    for segment in segments_list:
                        text = segment.text.strip()
                        if text:
                            full_text += text + " "
                    
                    full_text = full_text.strip()
                    
                    if full_text and full_text != session["last_transcript_text"]:
                        # Check if we should create new bar
                        create_new_bar = session.get("create_new_bar", False)
                        
                        # Accumulate text for current bar
                        if create_new_bar:
                            # Reset accumulated text when starting new bar
                            session["accumulated_text"] = full_text
                        else:
                            # Append to accumulated text
                            if session["accumulated_text"]:
                                session["accumulated_text"] += " " + full_text
                            else:
                                session["accumulated_text"] = full_text
                        
                        # Send CUMULATIVE text (not just the new chunk)
                        text_to_send = session["accumulated_text"]
                        
                        logger.info(f"📝 Transcript chunk: '{full_text[:30]}...' → Cumulative: '{text_to_send[:50]}...' (is_final={create_new_bar})")
                        
                        # Send transcript
                        result = {
                            "text": text_to_send,
                            "is_final": create_new_bar,
                            "confidence": 1.0,
                            "speech_final": create_new_bar,
                            "create_new_bar": create_new_bar
                        }
                        
                        logger.info(f"📤 Calling callback (is_final={create_new_bar})")
                        await session["callback"](result)
                        logger.info(f"✅ Callback completed")
                        
                        # Update tracking
                        session["last_transcript_text"] = full_text
                        session["accumulated_audio"] = bytearray()
                        
                        # Reset flags if new bar was created
                        if create_new_bar:
                            session["bar_start_time"] = asyncio.get_event_loop().time()
                            session["create_new_bar"] = False
                            session["silence_flag_set"] = False
                            session["duration_flag_set"] = False
                            session["last_transcript_text"] = ""
                            session["accumulated_text"] = ""  # Reset accumulation
                            logger.info(f"🆕 New bar created")
                    else:
                        if not full_text:
                            logger.info(f"⚠️ No speech detected in audio buffer, clearing buffer")
                            # Clear buffer to avoid accumulating silence forever
                            session["accumulated_audio"] = bytearray()
                        else:
                            logger.debug(f"⏭️ Duplicate transcript, skipping")
                
                except Exception as e:
                    logger.error(f"❌ Transcription error: {e}", exc_info=True)
                
        except Exception as e:
            logger.error(f"❌ Error in audio processing loop: {e}", exc_info=True)
    
    async def stop_stream(self, session_id: str):
        """Stop transcription stream"""
        try:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["running"] = False
                
                # Cancel processing task
                if session_id in self.processing_tasks:
                    self.processing_tasks[session_id].cancel()
                    del self.processing_tasks[session_id]
                
                # Cleanup
                del self.active_sessions[session_id]
                if session_id in self.audio_buffers:
                    del self.audio_buffers[session_id]
                
                logger.info(f"✅ Stopped Faster-Whisper stream for {session_id}")
                
        except Exception as e:
            logger.error(f"❌ Error stopping stream: {e}")


# Singleton instance
_whisper_service = None

def get_faster_whisper_service() -> FasterWhisperService:
    """Get or create Faster-Whisper service singleton"""
    global _whisper_service
    if _whisper_service is None:
        _whisper_service = FasterWhisperService()
    return _whisper_service
