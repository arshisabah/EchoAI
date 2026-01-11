"""Quick test for emotion detection"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_emotion():
    print("🧪 Testing Emotion Detection System")
    print("=" * 60)
    
    try:
        from app.services.emotion_analysis import get_emotion_service
        
        service = get_emotion_service()
        
        test_texts = [
            "I am so happy and excited about this!",
            "This is terrible and I'm very angry!",
            "I'm feeling a bit sad and disappointed today.",
            "Everything is going well, thank you!",
        ]
        
        for text in test_texts:
            print(f"\n📝 Text: '{text}'")
            result = await service.analyze_text(text)
            print(f"   Emotion: {result['emotion']}")
            print(f"   Confidence: {result['confidence']:.2f}")
            
            # Show top 3 scores
            scores = result.get('scores', {})
            if scores:
                top_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
                print(f"   Top scores: {', '.join([f'{e}: {s:.2f}' for e, s in top_scores])}")
        
        print("\n✅ Emotion detection test completed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_emotion())
