#!/usr/bin/env python3
"""
Local test script for emotion detection without running the full server.
This tests the emotion analysis service directly.
"""

import asyncio
import logging
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable OpenAI requirement for local testing
os.environ['OPENAI_API_KEY'] = 'test_key_for_fallback'


async def test_emotion_detection():
    """Test emotion detection with various phrases."""
    from app.services.emotion_analysis import get_emotion_service
    
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
    
    logger.info("=" * 80)
    logger.info("TESTING EMOTION DETECTION")
    logger.info("=" * 80)
    
    try:
        emotion_service = get_emotion_service()
        logger.info("✅ Emotion service initialized")
        
        results = {}
        for expected_emotion, phrase in test_phrases.items():
            logger.info(f"\n{'='*80}")
            logger.info(f"Testing phrase for '{expected_emotion}'")
            logger.info(f"Text: {phrase}")
            logger.info(f"{'='*80}")
            
            try:
                emotion_result = await emotion_service.analyze_text(phrase)
                detected = emotion_result.get("emotion", "unknown")
                confidence = emotion_result.get("confidence", 0.0)
                
                matches = detected == expected_emotion
                status = "✅" if matches else "❌"
                
                results[expected_emotion] = {
                    "phrase": phrase,
                    "expected": expected_emotion,
                    "detected": detected,
                    "confidence": confidence,
                    "matches": matches,
                    "status": status
                }
                
                logger.info(f"\n{status} Result:")
                logger.info(f"  Expected: {expected_emotion}")
                logger.info(f"  Detected: {detected}")
                logger.info(f"  Confidence: {confidence:.2%}")
                logger.info(f"  Match: {matches}")
                
            except Exception as e:
                logger.error(f"❌ Error testing '{expected_emotion}': {e}", exc_info=True)
                results[expected_emotion] = {
                    "phrase": phrase,
                    "expected": expected_emotion,
                    "detected": "error",
                    "error": str(e)
                }
        
        # Calculate accuracy
        matches = sum(1 for r in results.values() if r.get("matches", False))
        total = len(results)
        accuracy = matches / total if total > 0 else 0
        
        logger.info("\n" + "=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total tests: {total}")
        logger.info(f"Matches: {matches}")
        logger.info(f"Accuracy: {accuracy:.1%}")
        
        for emotion, result in results.items():
            if "error" not in result:
                logger.info(f"{result['status']} {emotion}: {result['detected']} ({result['confidence']:.1%})")
            else:
                logger.info(f"❌ {emotion}: ERROR - {result['error']}")
        
        logger.info("=" * 80)
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return None


async def test_fallback_only():
    """Test keyword-based fallback directly."""
    from app.services.emotion_analysis import get_emotion_service
    
    logger.info("\n" + "=" * 80)
    logger.info("TESTING KEYWORD-BASED FALLBACK")
    logger.info("=" * 80)
    
    emotion_service = get_emotion_service()
    
    test_phrases = [
        ("I'm so happy and excited!", "happy"),
        ("This is terrible and sad", "sad"),
        ("I'm angry and furious about this!", "angry"),
        ("So frustrated with this problem", "frustrated"),
        ("I'm confused and don't understand", "confused"),
    ]
    
    for phrase, expected in test_phrases:
        logger.info(f"\nTesting: '{phrase}'")
        result = emotion_service._fallback_emotion_analysis(phrase)
        detected = result.get("emotion", "unknown")
        confidence = result.get("confidence", 0)
        
        matches = detected == expected
        status = "✅" if matches else "❌"
        
        logger.info(f"{status} Expected: {expected}, Detected: {detected} ({confidence:.2%})")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("EMOTION DETECTION LOCAL TEST")
    print("=" * 80)
    print("\nThis test will:")
    print("1. Test keyword-based emotion fallback")
    print("2. Test emotion detection with various phrases")
    print("\nNote: OpenAI API key not configured, using fallback only\n")
    
    # Run tests
    asyncio.run(test_fallback_only())
    asyncio.run(test_emotion_detection())
    
    print("\n✅ Tests complete!")
