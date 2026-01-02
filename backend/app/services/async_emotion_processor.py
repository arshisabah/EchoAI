# app/services/async_emotion_processor.py
"""
Asynchronous Emotion Detection and Guidance Pipeline
Processes finalized transcript bars in the background without blocking transcription.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
import numpy as np

from app.services.continuous_transcript_manager import (
    get_continuous_transcript_manager,
    TranscriptBar
)
from app.services.emotion_analysis import analyze_text_and_audio_combined
from app.services.emotion_guidance import get_emotion_guidance_engine

logger = logging.getLogger(__name__)


class AsyncEmotionProcessor:
    """
    Background worker that processes emotion detection for finalized transcript bars.
    Runs continuously without blocking the main transcription pipeline.
    """
    
    def __init__(self):
        self.transcript_manager = get_continuous_transcript_manager()
        self.guidance_engine = get_emotion_guidance_engine()
        self.running = False
        self.worker_task: Optional[asyncio.Task] = None
        
        # Cache for audio data (if needed for emotion analysis)
        # In practice, we might need to store audio snippets temporarily
        self.audio_cache: dict = {}
        
        # Track processed bars to prevent duplicates
        self.processed_bars: set = set()
        
        logger.info("✅ AsyncEmotionProcessor initialized")
    
    async def start(self):
        """Start the background emotion processing worker"""
        if self.running:
            logger.warning("Emotion processor already running")
            return
        
        self.running = True
        self.worker_task = asyncio.create_task(self._process_emotion_queue())
        logger.info("🚀 Async emotion processor started")
    
    async def stop(self):
        """Stop the background worker"""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Async emotion processor stopped")
    
    async def _process_emotion_queue(self):
        """
        Main worker loop - continuously processes bars from the emotion queue.
        This runs in the background and never blocks transcription.
        """
        logger.info("🔄 Emotion processing worker loop started")
        
        while self.running:
            try:
                # Wait for a finalized bar from the queue (non-blocking)
                bar = await asyncio.wait_for(
                    self.transcript_manager.emotion_queue.get(),
                    timeout=1.0  # Check running status every second
                )
                
                logger.info(f"🎭 Processing emotion for bar: {bar.id} (session: {bar.session_id})")
                
                # Process emotion asynchronously
                await self._analyze_bar_emotion(bar)
                
            except asyncio.TimeoutError:
                # No bars in queue - continue waiting
                continue
            except asyncio.CancelledError:
                logger.info("Worker cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in emotion processing worker: {e}", exc_info=True)
                await asyncio.sleep(1)  # Brief pause before continuing
    
    async def _analyze_bar_emotion(self, bar: TranscriptBar):
        """
        Analyze emotion for a single transcript bar.
        Updates the bar with emotion results and changes status to 'finalized'.
        """
        try:
            # Skip if already processed
            if bar.id in self.processed_bars:
                logger.debug(f"⏭️ Bar {bar.id} already processed, skipping")
                return
            
            # Mark as processed
            self.processed_bars.add(bar.id)
            
            start_time = datetime.utcnow()
            
            # Get audio from cache if available
            audio_array = self.audio_cache.get(bar.id)
            
            if audio_array is not None and len(audio_array) > 0:
                # Combined text + audio emotion analysis
                logger.debug(f"Running combined emotion analysis for bar {bar.id}")
                emotion_result = await analyze_text_and_audio_combined(
                    text=bar.text,
                    audio_array=audio_array,
                    sample_rate=16000,
                    text_weight=0.6,
                    audio_weight=0.4
                )
                
                # Clean up audio cache
                del self.audio_cache[bar.id]
            else:
                # Text-only emotion analysis (fallback)
                logger.debug(f"Running text-only emotion analysis for bar {bar.id}")
                emotion_result = await self._analyze_text_emotion(bar.text)
            
            # Extract emotion data
            emotion = emotion_result.get("emotion", "neutral")
            confidence = emotion_result.get("confidence", 0.0)
            scores = emotion_result.get("scores", {})
            
            # Get guidance from emotion guidance engine
            guidance = await self._get_emotion_guidance(emotion, bar.text)
            
            # Update bar with emotion results
            bar.emotion = emotion
            bar.emotion_confidence = confidence
            bar.emotion_scores = scores
            bar.emotion_guidance = guidance
            bar.status = "finalized"
            bar.updated_at = datetime.utcnow()
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(
                f"✅ Emotion analysis complete for bar {bar.id}: "
                f"emotion={emotion}, confidence={confidence:.2f}, "
                f"processing_time={processing_time:.2f}s"
            )
            
            # Broadcast emotion update via WebSocket
            await self._broadcast_emotion_update(bar)
            
        except Exception as e:
            logger.error(f"❌ Failed to analyze emotion for bar {bar.id}: {e}", exc_info=True)
            
            # Set fallback values
            bar.emotion = "neutral"
            bar.emotion_confidence = 0.0
            bar.emotion_scores = {}
            bar.emotion_guidance = "Analysis unavailable"
            bar.status = "finalized"
            bar.updated_at = datetime.utcnow()
    
    async def _broadcast_emotion_update(self, bar: TranscriptBar):
        """
        Broadcast emotion update to all connected clients in the session.
        This updates the UI to show finalized emotion data.
        """
        try:
            # Import here to avoid circular dependency
            from app.services.meeting_room_manager import get_meeting_room_manager
            
            room_manager = get_meeting_room_manager()
            
            # Prepare emotion update message - use transcript_bar format with append action
            update_message = {
                "type": "transcript_bar",
                "action": "append",
                "bar": bar.to_dict(),
                "timestamp": bar.updated_at.isoformat()
            }
            
            # Broadcast to all participants in the session
            await room_manager.broadcast_to_room(bar.session_id, update_message)
            
            logger.debug(f"📡 Broadcast emotion update for bar {bar.id} to session {bar.session_id}")
            
        except Exception as e:
            logger.warning(f"Failed to broadcast emotion update for bar {bar.id}: {e}")
    
    async def _analyze_text_emotion(self, text: str) -> dict:
        """
        Fallback text-only emotion analysis.
        This is a simplified version - you might want to use a proper text emotion model.
        """
        # Simple keyword-based emotion detection as fallback
        text_lower = text.lower()
        
        emotion_keywords = {
            "happy": ["happy", "great", "excellent", "wonderful", "fantastic", "awesome", "love", "perfect"],
            "sad": ["sad", "unfortunately", "sorry", "disappointed", "unhappy", "terrible", "awful"],
            "angry": ["angry", "furious", "annoyed", "frustrated", "irritated", "mad"],
            "confused": ["confused", "unclear", "don't understand", "what", "how", "why"],
            "excited": ["excited", "amazing", "incredible", "wow", "omg", "can't wait"],
            "anxious": ["worried", "nervous", "anxious", "concerned", "afraid", "scared"],
        }
        
        scores = {}
        for emotion, keywords in emotion_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                scores[emotion] = score / len(keywords)
        
        if scores:
            dominant_emotion = max(scores, key=scores.get)
            confidence = scores[dominant_emotion]
        else:
            dominant_emotion = "neutral"
            confidence = 0.5
            scores = {"neutral": 0.5}
        
        return {
            "emotion": dominant_emotion,
            "confidence": confidence,
            "scores": scores
        }
    
    async def _get_emotion_guidance(self, emotion: str, text: str) -> str:
        """Get contextual guidance for detected emotion"""
        try:
            guidance_data = self.guidance_engine.get_guidance(
                emotion=emotion,
                text=text,
                confidence=0.5
            )
            return guidance_data.get("suggestion", "")
        except Exception as e:
            logger.warning(f"Failed to get emotion guidance: {e}")
            return ""
    
    def cache_audio_for_bar(self, bar_id: str, audio_array: np.ndarray):
        """
        Cache audio data for a bar so it can be used in emotion analysis.
        Audio is automatically cleaned up after analysis.
        """
        self.audio_cache[bar_id] = audio_array
        logger.debug(f"Cached audio for bar {bar_id}: {len(audio_array)} samples")
        
        # Auto-cleanup old cached audio (keep max 100 entries)
        if len(self.audio_cache) > 100:
            # Remove oldest (first) entry
            oldest_key = next(iter(self.audio_cache))
            del self.audio_cache[oldest_key]
            logger.debug(f"Cleaned up old cached audio: {oldest_key}")


# Singleton instance
_async_emotion_processor = None


def get_async_emotion_processor() -> AsyncEmotionProcessor:
    """Get or create singleton instance"""
    global _async_emotion_processor
    if _async_emotion_processor is None:
        _async_emotion_processor = AsyncEmotionProcessor()
    return _async_emotion_processor


async def start_emotion_processor():
    """Convenience function to start the emotion processor"""
    processor = get_async_emotion_processor()
    await processor.start()
