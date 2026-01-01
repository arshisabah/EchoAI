"""
Helper functions for Google Meet-style transcript broadcasting with emotion analysis
"""
import logging
import asyncio
import numpy as np
from typing import Dict, Any
from app.services.emotion_analysis import analyze_text_and_audio_combined

logger = logging.getLogger(__name__)

# Global audio buffers for emotion analysis
_room_audio_buffers: Dict[str, list] = {}

async def analyze_and_broadcast_emotion(
    entry: Dict[str, Any],
    room_id: str,
    stream_id: str,
    room_manager: Any
) -> None:
    """
    Analyze emotion for a completed transcript entry and broadcast update.
    Only called when speaker turn ends or transcript is finalized.
    
    Args:
        entry: Transcript entry dict with text, speaker, etc.
        room_id: Meeting room ID
        stream_id: Audio stream ID for buffer lookup
        room_manager: MeetingRoomManager instance
    """
    try:
        text = entry.get("text", "")
        user_id = entry.get("user_id")
        username = entry.get("username")
        entry_id = entry.get("id")
        
        logger.info(f"🎭 Analyzing emotion for completed transcript: {entry_id}")
        
        # Get audio buffer for emotion analysis
        audio_array = None
        if stream_id in _room_audio_buffers and len(_room_audio_buffers[stream_id]) > 0:
            try:
                # Use last 15 chunks (about 1-2 seconds)
                recent_chunks = _room_audio_buffers[stream_id][-15:]
                audio_array = np.concatenate(recent_chunks)
                logger.info(f"🎤 Using {len(audio_array)} samples for emotion analysis")
            except Exception as e:
                logger.warning(f"⚠️ Failed to get audio buffer: {e}")
        
        # Emotion analysis
        emotion = {"emotion": "neutral", "confidence": 0, "scores": {}}
        if audio_array is not None and len(audio_array) >= 1600:  # At least 0.1 seconds
            try:
                emotion = await analyze_text_and_audio_combined(
                    text=text, audio_array=audio_array,
                    sample_rate=16000, text_weight=0.6, audio_weight=0.4
                )
                logger.info(f"🎭 Emotion detected: {emotion['emotion']} (confidence: {emotion.get('confidence', 0):.2f})")
            except Exception as e:
                logger.warning(f"⚠️ Emotion analysis failed: {e}")
        else:
            logger.info(f"⚠️ No audio for emotion analysis (buffer has {len(_room_audio_buffers.get(stream_id, []))} chunks)")
        
        # Get emotion guidance (with timeout)
        guidance = {}
        try:
            from app.services.emotion_guidance import get_emotion_guidance_engine
            guidance_engine = get_emotion_guidance_engine()
            guidance = await asyncio.wait_for(
                asyncio.to_thread(
                    guidance_engine.get_guidance,
                    emotion["emotion"], text, emotion.get("confidence", 0),
                    context={"username": username, "room_id": room_id, "speaker": user_id}
                ),
                timeout=2.0  # 2 second timeout
            )
            logger.debug(f"✅ Got emotion guidance for {username}")
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Guidance generation timeout")
        except Exception as e:
            logger.warning(f"⚠️ Guidance generation failed: {e}")
        
        # Broadcast emotion update
        await room_manager.broadcast_transcript(
            room_id=room_id,
            user_id=user_id,
            username=username,
            text=text,
            emotion=emotion["emotion"],
            confidence=emotion.get("confidence", 0),
            emotion_guidance=guidance,
            entry_id=entry_id,
            is_emotion_update=True  # Flag to indicate this is just emotion update
        )
        
        # Update entry with emotion
        entry["emotion"] = emotion["emotion"]
        entry["emotion_confidence"] = emotion.get("confidence", 0)
        entry["emotion_scores"] = emotion.get("scores", {})
        entry["emotion_guidance"] = guidance
        
        logger.info(f"✅ Emotion broadcast complete for entry {entry_id}: {emotion['emotion']}")
        
    except Exception as e:
        logger.error(f"❌ Error in analyze_and_broadcast_emotion: {e}", exc_info=True)


def add_audio_to_buffer(stream_id: str, audio_array: np.ndarray):
    """Add audio chunk to buffer for emotion analysis"""
    if stream_id not in _room_audio_buffers:
        _room_audio_buffers[stream_id] = []
    
    _room_audio_buffers[stream_id].append(audio_array)
    
    # Keep only last 20 chunks (about 2-3 seconds)
    if len(_room_audio_buffers[stream_id]) > 20:
        _room_audio_buffers[stream_id].pop(0)


def clear_audio_buffer(stream_id: str):
    """Clear audio buffer for a stream"""
    if stream_id in _room_audio_buffers:
        del _room_audio_buffers[stream_id]
