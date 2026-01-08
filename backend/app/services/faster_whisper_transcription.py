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
        """Lazy load the model on first use with GPU support"""
        if self.model is not None:
            return
            
        try:
            import torch
            from faster_whisper import WhisperModel
            
            # Detect best available device
            # AMD GPUs: Use CUDA (ROCm provides CUDA compatibility)
            # NVIDIA GPUs: Use CUDA
            # CPU: Fallback
            device = "cpu"
            compute_type = "int8"  # Default for CPU
            
            if torch.cuda.is_available():
                device = "cuda"
                compute_type = "float16"  # Use FP16 on GPU for speed
                logger.info(f"🎮 GPU detected: {torch.cuda.get_device_name(0)} - using CUDA acceleration")
            else:
                logger.info("💻 No GPU detected - using CPU with int8 quantization")
            
            # Use base model for better accuracy
            logger.info(f"🔧 Loading Faster-Whisper 'base' model on {device}...")
            self.model = WhisperModel(
                "base",  # Base model for balanced speed/accuracy
                device=device,
                compute_type=compute_type,
                num_workers=4 if device == "cuda" else 1,  # More workers on GPU
                download_root=None,
                local_files_only=False
            )
            logger.info(f"✅ Faster-Whisper 'base' model loaded successfully on {device}")
            
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
            
            # Reduced logging for performance
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding audio to buffer: {e}")
            return False
    
    async def _process_audio_stream(self, session_id: str):
        """Continuously process audio buffer"""
        try:
            session = self.active_sessions[session_id]
            process_interval = 0.05  # Process every 50ms (balanced)
            min_audio_length = 8192  # 0.25 seconds minimum (better quality)
            silence_threshold = 15.0  # 15 seconds of silence (as required)
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
            
            # Main processing loop - check running flag on each iteration
            while session.get("running", False):
                await asyncio.sleep(process_interval)
                
                # Double-check session still exists and is running
                if session_id not in self.active_sessions:
                    logger.info(f"Session {session_id} no longer exists, stopping processing loop")
                    break
                    
                session = self.active_sessions.get(session_id)
                if not session or not session.get("running", False):
                    logger.info(f"Session {session_id} stopped, exiting processing loop")
                    break
                
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
                    # Reduced logging for performance
                    continue
                
                # Convert to numpy array
                audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Check audio level
                audio_rms = np.sqrt(np.mean(audio_array**2))
                
                # Log audio level when it changes significantly
                logger.info(f"🎤 Audio RMS: {audio_rms:.6f}, Buffer: {len(audio_data)} bytes")
                
                # Skip if audio is too quiet (likely silence) - raised threshold for better quality
                if audio_rms < 0.001:
                    session["accumulated_audio"] = bytearray()
                    continue
                
                # Transcribe
                try:
                    segments, info = self.model.transcribe(
                        audio_array,
                        language="en",
                        task="transcribe",
                        beam_size=5,  # Better accuracy with base model
                        best_of=5,  # Sample multiple candidates
                        temperature=0.0,  # Deterministic
                        vad_filter=False,  # DISABLE VAD - it's filtering out real speech
                        word_timestamps=False,  # No word timestamps for speed
                        no_speech_threshold=0.25,  # Lower threshold to detect more speech
                        compression_ratio_threshold=2.4,
                        log_prob_threshold=-1.0,
                        condition_on_previous_text=False,  # DISABLE - prevents hallucination repetition
                        initial_prompt=None
                    )
                    
                    # Convert generator to list
                    segments_list = list(segments)
                    
                    # Log transcription results AND Whisper's analysis
                    logger.info(f"🎯 Transcribed {len(segments_list)} segments, audio_rms={audio_rms:.6f}")
                    logger.info(f"   📊 Whisper info: language={info.language}, language_probability={info.language_probability:.3f}")
                    
                    # Build full text from all segments
                    full_text = ""
                    for segment in segments_list:
                        text = segment.text.strip()
                        
                        # CRITICAL: Reject segments where Whisper itself thinks it's not speech
                        if segment.no_speech_prob > 0.5:
                            logger.warning(f"   ⚠️ REJECTED: '{text}' (no_speech_prob={segment.no_speech_prob:.3f} too high)")
                            continue
                        
                        if text:
                            full_text += text + " "
                            # Log segment with probability scores
                            logger.info(f"   📝 Segment: '{text}' (prob={segment.avg_logprob:.3f}, no_speech_prob={segment.no_speech_prob:.3f})")
                    
                    full_text = full_text.strip()
                    
                    if full_text and full_text != session["last_transcript_text"]:
                        # Check if we need to start a new bar (duration/silence threshold reached)
                        should_finalize = session.get("create_new_bar", False)
                        
                        # ✅ FIX: If bar should be finalized, DON'T send cumulative text to new bar
                        # The finalized bar already has the complete text
                        if should_finalize:
                            logger.info(f"🔒 Bar finalization detected - skipping duplicate text broadcast")
                            # Reset everything for clean new bar
                            session["accumulated_text"] = ""
                            session["accumulated_audio"] = bytearray()
                            session["last_transcript_text"] = ""
                            session["bar_start_time"] = asyncio.get_event_loop().time()
                            session["create_new_bar"] = False
                            session["silence_flag_set"] = False
                            session["duration_flag_set"] = False
                            # Don't send this text - it's already in the finalized bar
                            continue
                        
                        # Accumulate text for current bar
                        if session["accumulated_text"]:
                            session["accumulated_text"] += " " + full_text
                        else:
                            session["accumulated_text"] = full_text
                        
                        # Send CUMULATIVE text (entire accumulated transcript for this bar)
                        text_to_send = session["accumulated_text"]
                        
                        # Send transcript
                        result = {
                            "text": text_to_send,
                            "is_final": should_finalize,
                            "confidence": 1.0,
                            "speech_final": should_finalize,
                        }
                        
                        await session["callback"](result)
                        
                        # Update tracking
                        session["last_transcript_text"] = full_text
                        session["accumulated_audio"] = bytearray()
                        
                        # Reset flags and timers if bar was finalized
                        if should_finalize:
                            session["bar_start_time"] = asyncio.get_event_loop().time()
                            session["create_new_bar"] = False
                            session["silence_flag_set"] = False
                            session["duration_flag_set"] = False
                            session["last_transcript_text"] = ""
                    else:
                        if not full_text:
                            # Clear buffer to avoid accumulating silence
                            session["accumulated_audio"] = bytearray()
                
                except Exception as e:
                    logger.error(f"❌ Transcription error: {e}", exc_info=True)
                
        except Exception as e:
            logger.error(f"❌ Error in audio processing loop: {e}", exc_info=True)
    
    async def stop_stream(self, session_id: str):
        """Stop transcription stream"""
        try:
            if session_id in self.active_sessions:
                # Set running flag to False first
                self.active_sessions[session_id]["running"] = False
                logger.info(f"🛑 Stopping stream for {session_id}")
                
                # Give processing loop a moment to exit gracefully
                await asyncio.sleep(0.2)
                
                # Cancel processing task
                if session_id in self.processing_tasks:
                    task = self.processing_tasks[session_id]
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    del self.processing_tasks[session_id]
                
                # Cleanup sessions and buffers
                if session_id in self.active_sessions:
                    del self.active_sessions[session_id]
                if session_id in self.audio_buffers:
                    del self.audio_buffers[session_id]
                
                logger.info(f"✅ Stopped Faster-Whisper stream for {session_id}")
                
        except Exception as e:
            logger.error(f"❌ Error stopping stream: {e}", exc_info=True)


# Singleton instance
_whisper_service = None

def get_faster_whisper_service() -> FasterWhisperService:
    """Get or create Faster-Whisper service singleton"""
    global _whisper_service
    if _whisper_service is None:
        _whisper_service = FasterWhisperService()
    return _whisper_service
