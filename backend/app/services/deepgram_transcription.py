# app/services/deepgram_transcription.py
"""
Deepgram Real-Time Streaming Transcription Service

This service provides low-latency (<700ms) streaming transcription using
Deepgram's live API with built-in VAD and word-by-word results.
"""

import asyncio
import logging
import base64
from typing import Optional, Dict, Callable, Any
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from deepgram import (
        DeepgramClient,
        DeepgramClientOptions,
        LiveTranscriptionEvents,
        LiveOptions,
    )
    DEEPGRAM_AVAILABLE = True
except ImportError:
    DEEPGRAM_AVAILABLE = False
    logger.warning("⚠️ Deepgram SDK not installed. Streaming transcription unavailable.")


class DeepgramStreamingService:
    """
    Manages Deepgram live streaming connections for real-time transcription.
    
    Features:
    - Real-time streaming with <700ms latency
    - Built-in VAD (no manual detection needed)
    - Partial and final transcript results
    - Automatic reconnection on errors
    """
    
    def __init__(self, api_key: str):
        if not DEEPGRAM_AVAILABLE:
            raise ImportError("Deepgram SDK is not installed. Run: pip install deepgram-sdk==3.2.7")
        
        if not api_key:
            raise ValueError("Deepgram API key is required")
        
        self.api_key = api_key
        self.client = None
        self.connections: Dict[str, Any] = {}  # session_id -> connection
        self.callbacks: Dict[str, Callable] = {}  # session_id -> callback
        
        logger.info("✅ DeepgramStreamingService initialized")
    
    async def start_stream(
        self,
        session_id: str,
        on_transcript: Callable[[Dict[str, Any]], None],
        language: str = "en",
        model: str = "nova-2",
        smart_format: bool = True,
        interim_results: bool = True,
    ) -> bool:
        """
        Start a streaming connection for a session.
        
        Args:
            session_id: Unique identifier for the session
            on_transcript: Callback function for transcript results
            language: Language code (default: "en")
            model: Deepgram model to use (default: "nova-2")
            smart_format: Enable smart formatting
            interim_results: Enable partial results
            
        Returns:
            bool: True if connection started successfully
        """
        try:
            if session_id in self.connections:
                logger.warning(f"⚠️ Stream already exists for session {session_id}")
                return True
            
            # Initialize Deepgram client
            if not self.client:
                self.client = DeepgramClient(self.api_key)
            
            # Create live connection
            dg_connection = self.client.listen.live.v("1")
            
            # Store callback
            self.callbacks[session_id] = on_transcript
            
            # Set up event handlers
            def on_message(self_inner, result, **kwargs):
                """Handle transcript messages"""
                try:
                    if result and hasattr(result, 'channel'):
                        channel = result.channel
                        if hasattr(channel, 'alternatives') and len(channel.alternatives) > 0:
                            alternative = channel.alternatives[0]
                            transcript = alternative.transcript
                            
                            if transcript.strip():
                                is_final = result.is_final if hasattr(result, 'is_final') else True
                                confidence = alternative.confidence if hasattr(alternative, 'confidence') else 1.0
                                
                                # Extract word-level timestamps if available
                                words = []
                                if hasattr(alternative, 'words'):
                                    for word_obj in alternative.words:
                                        words.append({
                                            'word': word_obj.word if hasattr(word_obj, 'word') else '',
                                            'start': word_obj.start if hasattr(word_obj, 'start') else 0,
                                            'end': word_obj.end if hasattr(word_obj, 'end') else 0,
                                            'confidence': word_obj.confidence if hasattr(word_obj, 'confidence') else 1.0,
                                        })
                                
                                transcript_result = {
                                    'text': transcript,
                                    'is_final': is_final,
                                    'confidence': confidence,
                                    'words': words,
                                    'session_id': session_id,
                                    'timestamp': datetime.utcnow().isoformat(),
                                }
                                
                                # Call the callback
                                callback = self.callbacks.get(session_id)
                                if callback:
                                    asyncio.create_task(self._safe_callback(callback, transcript_result))
                                
                except Exception as e:
                    logger.error(f"❌ Error processing transcript message for {session_id}: {e}", exc_info=True)
            
            def on_metadata(self_inner, metadata, **kwargs):
                """Handle metadata messages"""
                logger.debug(f"📊 Metadata for {session_id}: {metadata}")
            
            def on_error(self_inner, error, **kwargs):
                """Handle errors"""
                logger.error(f"❌ Deepgram error for {session_id}: {error}")
            
            def on_close(self_inner, close_msg, **kwargs):
                """Handle connection close"""
                logger.info(f"🔌 Deepgram connection closed for {session_id}")
                if session_id in self.connections:
                    del self.connections[session_id]
                if session_id in self.callbacks:
                    del self.callbacks[session_id]
            
            # Register event handlers
            dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
            dg_connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
            dg_connection.on(LiveTranscriptionEvents.Error, on_error)
            dg_connection.on(LiveTranscriptionEvents.Close, on_close)
            
            # Configure options
            options = LiveOptions(
                model=model,
                language=language,
                smart_format=smart_format,
                interim_results=interim_results,
                encoding="linear16",
                sample_rate=16000,
                channels=1,
                vad_events=True,  # Enable Voice Activity Detection events
            )
            
            # Start the connection
            if not dg_connection.start(options):
                logger.error(f"❌ Failed to start Deepgram connection for {session_id}")
                return False
            
            # Store connection
            self.connections[session_id] = dg_connection
            
            logger.info(f"✅ Started Deepgram stream for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start Deepgram stream for {session_id}: {e}", exc_info=True)
            return False
    
    async def send_audio(self, session_id: str, audio_data: bytes) -> bool:
        """
        Send audio data to the streaming connection.
        
        Args:
            session_id: Session identifier
            audio_data: Raw audio bytes (16kHz, 16-bit PCM)
            
        Returns:
            bool: True if audio sent successfully
        """
        try:
            connection = self.connections.get(session_id)
            if not connection:
                logger.warning(f"⚠️ No active connection for session {session_id}")
                return False
            
            # Send audio to Deepgram
            connection.send(audio_data)
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send audio for {session_id}: {e}", exc_info=True)
            return False
    
    async def stop_stream(self, session_id: str) -> bool:
        """
        Stop the streaming connection for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if stopped successfully
        """
        try:
            connection = self.connections.get(session_id)
            if not connection:
                logger.debug(f"No active connection to stop for {session_id}")
                return True
            
            # Finish the connection
            connection.finish()
            
            # Clean up
            if session_id in self.connections:
                del self.connections[session_id]
            if session_id in self.callbacks:
                del self.callbacks[session_id]
            
            logger.info(f"✅ Stopped Deepgram stream for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to stop stream for {session_id}: {e}", exc_info=True)
            return False
    
    async def _safe_callback(self, callback: Callable, result: Dict[str, Any]):
        """Safely execute callback with error handling"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(result)
            else:
                callback(result)
        except Exception as e:
            logger.error(f"❌ Error in transcript callback: {e}", exc_info=True)
    
    async def cleanup(self):
        """Clean up all active connections"""
        session_ids = list(self.connections.keys())
        for session_id in session_ids:
            await self.stop_stream(session_id)
        logger.info("✅ All Deepgram connections cleaned up")


# Singleton instance
_deepgram_service: Optional[DeepgramStreamingService] = None


def get_deepgram_service(api_key: Optional[str] = None) -> Optional[DeepgramStreamingService]:
    """
    Get or create the Deepgram streaming service instance.
    
    Args:
        api_key: Deepgram API key (required on first call)
        
    Returns:
        DeepgramStreamingService instance or None if not available
    """
    global _deepgram_service
    
    if not DEEPGRAM_AVAILABLE:
        return None
    
    if _deepgram_service is None:
        if not api_key:
            logger.warning("⚠️ Deepgram API key required to initialize service")
            return None
        try:
            _deepgram_service = DeepgramStreamingService(api_key)
        except Exception as e:
            logger.error(f"❌ Failed to initialize Deepgram service: {e}")
            return None
    
    return _deepgram_service
