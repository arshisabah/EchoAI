# app/routers/debug.py
"""
Debug endpoints for testing emotion detection and other features.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.emotion_analysis import get_emotion_service, analyze_text_and_audio_combined
from app.modules.audio_emotion_analyzer import analyze_audio_emotion, _MODEL_AVAILABLE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug", tags=["Debug"])


class TestEmotionRequest(BaseModel):
    """Request model for emotion testing."""
    text: str
    include_audio_analysis: bool = False


class TestEmotionResponse(BaseModel):
    """Response model for emotion testing."""
    success: bool
    text_emotion: dict
    audio_model_available: bool
    combined_emotion: Optional[dict] = None
    error: Optional[str] = None


@router.post("/test-emotion", response_model=TestEmotionResponse)
async def test_emotion_detection(request: TestEmotionRequest):
    """
    Test emotion detection with a text sample.
    
    This endpoint allows testing the emotion detection pipeline independently:
    - Text-based emotion analysis (OpenAI GPT-4o-mini)
    - Audio emotion model availability check
    - Combined text+audio analysis (if audio provided)
    
    Example:
        POST /debug/test-emotion
        {
            "text": "I'm so frustrated with this!",
            "include_audio_analysis": false
        }
    """
    try:
        logger.info(f"🧪 Testing emotion detection for text: '{request.text[:100]}...'")
        
        # Get emotion service
        emotion_service = get_emotion_service()
        
        # Analyze text emotion
        logger.debug("📝 Starting text-based emotion analysis...")
        text_emotion = await emotion_service.analyze_text(request.text)
        logger.info(f"✅ Text emotion result: {text_emotion.get('emotion', 'unknown')} (confidence: {text_emotion.get('confidence', 0):.2f})")
        
        # Check audio model availability
        audio_available = _MODEL_AVAILABLE
        logger.debug(f"🎤 Audio emotion model available: {audio_available}")
        
        # Prepare response
        response = {
            "success": True,
            "text_emotion": {
                "emotion": text_emotion.get("emotion", "unknown"),
                "confidence": text_emotion.get("confidence", 0.0),
                "scores": text_emotion.get("scores", {}),
                "source": "openai_gpt4o_mini" if text_emotion.get("confidence", 0) > 0.5 else "keyword_fallback"
            },
            "audio_model_available": audio_available,
            "combined_emotion": None
        }
        
        # Add detailed analysis info
        logger.info("=" * 80)
        logger.info("EMOTION DETECTION TEST RESULTS")
        logger.info("=" * 80)
        logger.info(f"Input Text: {request.text}")
        logger.info(f"Detected Emotion: {text_emotion.get('emotion', 'unknown')}")
        logger.info(f"Confidence: {text_emotion.get('confidence', 0):.2%}")
        logger.info(f"Audio Model Available: {audio_available}")
        if text_emotion.get("scores"):
            logger.info("Emotion Scores:")
            for emotion, score in sorted(text_emotion.get("scores", {}).items(), key=lambda x: x[1], reverse=True)[:5]:
                logger.info(f"  - {emotion}: {score:.2%}")
        logger.info("=" * 80)
        
        return response
        
    except ValueError as e:
        # Configuration error (e.g., missing API key)
        logger.error(f"❌ Configuration error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Configuration error: {str(e)}. Please check your OpenAI API key configuration."
        )
    except Exception as e:
        logger.error(f"❌ Error testing emotion: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error testing emotion: {str(e)}"
        )


@router.get("/emotion-model-status")
async def get_emotion_model_status():
    """
    Get the status of emotion detection models.
    
    Returns information about:
    - OpenAI text emotion model (API key configured)
    - Audio emotion model (Wav2Vec2 model loaded)
    """
    try:
        from app.core.config import settings
        
        # Check OpenAI configuration
        openai_configured = bool(
            settings.OPENAI_API_KEY and 
            settings.OPENAI_API_KEY != "your_openai_key_here"
        )
        
        # Check audio model
        audio_model_loaded = _MODEL_AVAILABLE
        
        status = {
            "text_emotion": {
                "available": openai_configured,
                "provider": "OpenAI GPT-4o-mini",
                "fallback": "keyword-based analysis",
                "status": "configured" if openai_configured else "not_configured"
            },
            "audio_emotion": {
                "available": audio_model_loaded,
                "model": "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
                "fallback": "neutral emotion",
                "status": "loaded" if audio_model_loaded else "not_loaded"
            },
            "combined_analysis": {
                "available": True,
                "description": "Combines text and audio emotions with configurable weights"
            }
        }
        
        logger.info("📊 Emotion model status:")
        logger.info(f"  - Text emotion (OpenAI): {'✅' if openai_configured else '❌'}")
        logger.info(f"  - Audio emotion (Wav2Vec2): {'✅' if audio_model_loaded else '❌'}")
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting emotion model status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting status: {str(e)}"
        )


@router.post("/test-emotion-phrases")
async def test_emotion_with_phrases():
    """
    Test emotion detection with common phrases.
    
    Tests the emotion detection system with predefined phrases
    representing different emotions.
    """
    test_phrases = {
        "happy": "I'm so excited about this! This is amazing!",
        "sad": "I'm really disappointed. This is terrible news.",
        "angry": "This is absolutely unacceptable! I'm furious!",
        "frustrated": "This is so frustrating. Nothing is working.",
        "confused": "I don't understand. Can you clarify this?",
        "neutral": "The meeting is scheduled for 3 PM tomorrow.",
        "anxious": "I'm worried this might not work. What if it fails?",
        "confident": "I'm absolutely certain this will succeed."
    }
    
    try:
        emotion_service = get_emotion_service()
        results = {}
        
        logger.info("🧪 Testing emotion detection with predefined phrases...")
        
        for expected_emotion, phrase in test_phrases.items():
            logger.info(f"\nTesting phrase for '{expected_emotion}': {phrase}")
            
            emotion_result = await emotion_service.analyze_text(phrase)
            detected = emotion_result.get("emotion", "unknown")
            confidence = emotion_result.get("confidence", 0.0)
            
            matches = detected == expected_emotion
            results[expected_emotion] = {
                "phrase": phrase,
                "expected": expected_emotion,
                "detected": detected,
                "confidence": confidence,
                "matches": matches,
                "status": "✅" if matches else "❌"
            }
            
            logger.info(f"  Expected: {expected_emotion}")
            logger.info(f"  Detected: {detected} (confidence: {confidence:.2%})")
            logger.info(f"  Match: {'✅' if matches else '❌'}")
        
        # Calculate accuracy
        matches = sum(1 for r in results.values() if r["matches"])
        total = len(results)
        accuracy = matches / total if total > 0 else 0
        
        logger.info(f"\n📊 Overall accuracy: {accuracy:.1%} ({matches}/{total} matches)")
        
        return {
            "results": results,
            "summary": {
                "total_tests": total,
                "matches": matches,
                "accuracy": accuracy
            }
        }
        
    except Exception as e:
        logger.error(f"Error testing emotion phrases: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error testing phrases: {str(e)}"
        )
