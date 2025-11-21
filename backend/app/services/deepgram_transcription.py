# app/services/deepgram_transcription.py
"""
Deepgram Real-Time Streaming Transcription Service

This service provides low-latency (<700ms) streaming transcription using
Deepgram's live API with built-in VAD and word-by-word results.
"""

import asyncio
import logging
from typing import Optional, Dict, Callable, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

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
        self.loops: Dict[str, Any] = {}  # session_id -> event loop
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.keepalive_tasks: Dict[str, Any] = {}  # session_id -> keepalive task
        self.connection_ready: Dict[str, asyncio.Event] = {}  # session_id -> ready event
        
        logger.info("✅ DeepgramStreamingService initialized")
    
    async def start_stream(
        self,
        session_id: str,
        on_transcript: Callable[[Dict[str, Any]], None],
        language: str = "en",
        model: str = "nova-2",
        smart_format: bool = True,
        interim_results: bool = True,
        diarize: bool = True,
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
            
            # Store the event loop for this session
            try:
                self.loops[session_id] = asyncio.get_running_loop()
            except RuntimeError:
                self.loops[session_id] = asyncio.get_event_loop()
            
            # Create ready event for this session
            self.connection_ready[session_id] = asyncio.Event()
            
            # Initialize Deepgram client
            if not self.client:
                self.client = DeepgramClient(self.api_key)
            
            # Create live connection
            dg_connection = self.client.listen.live.v("1")
            
            # Store callback
            self.callbacks[session_id] = on_transcript

            def on_open(self_inner,open_msg ,  **kwargs):
                """Handle connection open"""
                logger.info(f"🔌 Deepgram connection opened for {session_id}: {open_msg}")
                logger.info(f" open msg: {open_msg}")
                # Mark connection as ready
                ready_event = self.connection_ready.get(session_id)
                if ready_event:
                    ready_event.set()
                    logger.info(f"✅ Connection marked as ready for {session_id}")
            
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

                                #extract speakker label from deepgram
                                speaker = None
                                if hasattr(channel, 'speaker'):
                                    speaker = channel.speaker
                                
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
                                    'speaker': speaker,
                                    'session_id': session_id,
                                    'timestamp': datetime.utcnow().isoformat(),
                                }
                                
                                # Log the transcript
                                logger.info(f"📝 {'✅ Final' if is_final else '⏳ Partial'} transcript: '{transcript}'")
                                
                                # Call the callback safely using the stored event loop
                                callback = self.callbacks.get(session_id)
                                loop = self.loops.get(session_id)
                                
                                if callback and loop:
                                    try:
                                        # Schedule callback in the stored event loop
                                        asyncio.run_coroutine_threadsafe(
                                            self._safe_callback(callback, transcript_result),
                                            loop
                                        )
                                    except Exception as e:
                                        logger.error(f"❌ Error scheduling callback: {e}")
                            
                except Exception as e:
                    logger.error(f"❌ Error processing transcript message for {session_id}: {e}", exc_info=True)
            
            def on_metadata(self_inner, metadata, **kwargs):
                """Handle metadata messages"""
                logger.debug(f"📊 Metadata for {session_id}: {metadata}")
            
            def on_error(self_inner, error, **kwargs):
                """Handle errors"""
                logger.error(f"❌ Deepgram error for {session_id}: {error}")
                
                # Check if it's a timeout error
                error_str = str(error) if error else ""
                if "timeout" in error_str.lower() or "1011" in error_str:
                    logger.warning(f"⚠️ Deepgram timeout detected for {session_id}, attempting reconnect...")
                    # Schedule reconnection
                    try:
                        loop = self.loops.get(session_id)
                        callback = self.callbacks.get(session_id)
                        if loop and callback:
                            # Reconnect in 1 second
                            asyncio.run_coroutine_threadsafe(
                                self._reconnect_stream(session_id, callback),
                                loop
                            )
                    except Exception as e:
                        logger.error(f"❌ Failed to schedule reconnect: {e}")
                        
            def on_close(self_inner, close_msg, **kwargs):
                """Handle connection close"""
                logger.info(f"🔌 Deepgram connection closed for {session_id}")
                if session_id in self.connections:
                    del self.connections[session_id]
                if session_id in self.callbacks:
                    del self.callbacks[session_id]
                if session_id in self.loops:
                    del self.loops[session_id]
                if session_id in self.connection_ready:
                    del self.connection_ready[session_id]
                # Cancel keepalive
                if session_id in self.keepalive_tasks:
                    keepalive_task = self.keepalive_tasks[session_id]
                    keepalive_task.cancel()
                    del self.keepalive_tasks[session_id]
            
            # Register event handlers
            dg_connection.on(LiveTranscriptionEvents.Open, on_open) 
            dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
            dg_connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
            dg_connection.on(LiveTranscriptionEvents.Error, on_error)
            dg_connection.on(LiveTranscriptionEvents.Close, on_close)
            logger.info(f" Registerd evebts handle : open, transcript, metadata, error, close for {session_id}")
            # Configure options
            options = LiveOptions(
                model=model,
                language=language,
                smart_format=smart_format,
                interim_results=interim_results,
                encoding="linear16",
                sample_rate=16000,
                channels=1,
                diarize=diarize,
                vad_events=True,  # Enable Voice Activity Detection events
            )
            
            # Start the connection
            if not dg_connection.start(options):
                logger.error(f"❌ Failed to start Deepgram connection for {session_id}")
                return False
            
            # Store connection
            self.connections[session_id] = dg_connection
            
            # Wait for connection to be ready (with timeout)
            try:
                await asyncio.wait_for(self.connection_ready[session_id].wait(), timeout=5.0)
                logger.info(f"✅ Connection ready for {session_id}")
            except asyncio.TimeoutError:
                logger.error(f"❌ Connection ready timeout for {session_id}")
                # Clean up
                if session_id in self.connections:
                    del self.connections[session_id]
                if session_id in self.connection_ready:
                    del self.connection_ready[session_id]
                return False
            
            # Start keepalive task
            loop = self.loops.get(session_id)
            if loop:
                keepalive_task = asyncio.create_task(self._keepalive_loop(session_id))
                self.keepalive_tasks[session_id] = keepalive_task
                logger.info(f"💓 Started keepalive task for {session_id}")

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
            
            # Verify connection is ready before sending
            ready_event = self.connection_ready.get(session_id)
            if ready_event and not ready_event.is_set():
                logger.warning(f"⚠️ Connection not ready for session {session_id}, waiting...")
                try:
                    await asyncio.wait_for(ready_event.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.error(f"❌ Connection ready timeout while sending audio for {session_id}")
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
            if session_id in self.loops:
                del self.loops[session_id]
            if session_id in self.connection_ready:
                del self.connection_ready[session_id]

            # Cancel keepalive task
            if session_id in self.keepalive_tasks:
                keepalive_task = self.keepalive_tasks[session_id]
                keepalive_task.cancel()
                del self.keepalive_tasks[session_id]
                logger.debug(f"💓 Stopped keepalive task for {session_id}")
            
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
                # Wrap synchronous callback
                await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    callback,
                    result
                )
        except Exception as e:
            logger.error(f"❌ Error in transcript callback: {e}", exc_info=True)

    async def _keepalive_loop(self, session_id: str):
        """Send keepalive messages every 5 seconds to maintain Deepgram connection."""
        try:
            while session_id in self.connections:
                await asyncio.sleep(5)  # Send keepalive every 5 seconds
                
                connection = self.connections.get(session_id)
                if connection:
                    try:
                        # Send a keepalive message (empty audio frame or KeepAlive message)
                        connection.keep_alive()
                        logger.debug(f"💓 Sent keepalive for {session_id}")
                    except Exception as e:
                        logger.warning(f"⚠️ Keepalive failed for {session_id}: {e}")
                        break
        except asyncio.CancelledError:
            logger.debug(f"Keepalive task cancelled for {session_id}")
        except Exception as e:
            logger.error(f"❌ Keepalive loop error for {session_id}: {e}")

    async def _reconnect_stream(self, session_id: str, on_transcript: Callable):
        """Reconnect Deepgram stream after timeout."""
        try:
            await asyncio.sleep(1)  # Brief delay before reconnect
            
            # Check if still needed
            if session_id not in self.loops:
                return
            
            logger.info(f"🔄 Reconnecting Deepgram stream for {session_id}")
            
            # Clean up old connection
            if session_id in self.connections:
                try:
                    old_conn = self.connections[session_id]
                    old_conn.finish()
                except:
                    pass
                del self.connections[session_id]
            
            # Restart stream with same callback
            await self.start_stream(
                session_id=session_id,
                on_transcript=on_transcript,
                language="en",
                model="nova-2",
                smart_format=True,
                interim_results=True,
                diarize=False
            )
            
            logger.info(f"✅ Reconnected Deepgram stream for {session_id}")
            
        except Exception as e:
            logger.error(f"❌ Reconnection failed for {session_id}: {e}")
    
    async def cleanup(self):
        """Clean up all active connections"""
        session_ids = list(self.connections.keys())
        for session_id in session_ids:
            await self.stop_stream(session_id)
        
        # Shutdown executor
        self.executor.shutdown(wait=False)
        
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