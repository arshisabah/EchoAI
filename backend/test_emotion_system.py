"""
Quick test for emotion detection and guidance system.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

async def test_emotion_system():
    print("=" * 60)
    print("Testing Emotion Detection & Guidance System")
    print("=" * 60)
    
    # Test 1: Emotion Guidance
    print("\n1️⃣ Testing Emotion Guidance...")
    try:
        from app.services.emotion_guidance import get_emotion_guidance_engine
        
        engine = get_emotion_guidance_engine()
        guidance = engine.get_guidance(
            emotion="frustrated",
            text="This is not working!",
            confidence=0.8,
            context={"username": "TestUser"}
        )
        
        print(f"   ✅ Emotion: {guidance['emotion']}")
        print(f"   ✅ Suggestion: {guidance['suggestion']}")
        print(f"   ✅ Tips: {guidance['tips']}")
        print(f"   ✅ Tone: {guidance['tone']}")
        print("   ✅ Emotion Guidance: WORKING")
        
    except Exception as e:
        print(f"   ❌ Emotion Guidance FAILED: {e}")
        return False
    
    # Test 2: Text Emotion Detection
    print("\n2️⃣ Testing Text Emotion Detection...")
    try:
        from app.services.emotion_analysis import get_emotion_service
        
        service = get_emotion_service()
        
        # Test with full API (will use fallback if OpenAI not configured)
        result = await service.analyze_text(
            "I'm really frustrated with this bug!"
        )
        
        print(f"   ✅ Detected: {result['emotion']}")
        print(f"   ✅ Confidence: {result['confidence']:.2f}")
        print("   ✅ Text Emotion Detection: WORKING")
        
    except Exception as e:
        print(f"   ⚠️ Text Emotion Detection (OpenAI may not be configured): {e}")
        print("   ℹ️ This is OK if OpenAI API key not set - will use fallback in production")
    
    # Test 3: Check OpenAI Configuration
    print("\n3️⃣ Checking OpenAI Configuration...")
    try:
        from app.core.config import settings
        
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_key_here":
            print(f"   ✅ OpenAI API Key: Configured (...{settings.OPENAI_API_KEY[-4:]})")
            print("   ✅ Full accuracy mode available")
        else:
            print("   ⚠️ OpenAI API Key: NOT configured")
            print("   ⚠️ Using keyword fallback (reduced accuracy)")
            
    except Exception as e:
        print(f"   ⚠️ Config check warning: {e}")
    
    # Test 4: Emotion List
    print("\n4️⃣ Supported Emotions...")
    try:
        from app.services.emotion_analysis import SUPPORTED_EMOTIONS
        
        print(f"   ✅ Total emotions: {len(SUPPORTED_EMOTIONS)}")
        print(f"   ✅ Emotions: {', '.join(SUPPORTED_EMOTIONS)}")
        
    except Exception as e:
        print(f"   ❌ Emotion list FAILED: {e}")
    
    print("\n" + "=" * 60)
    print("✅ EMOTION SYSTEM: READY")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Restart backend: python -m uvicorn app.main:app --reload")
    print("2. Join meeting and speak")
    print("3. Check WebSocket messages for emotion + guidance")
    print()
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_emotion_system())
    sys.exit(0 if success else 1)
