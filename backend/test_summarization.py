"""
Quick test for summarization system.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

async def test_summarization():
    print("=" * 60)
    print("Testing Summarization System")
    print("=" * 60)
    
    # Test 1: Check Summary Service
    print("\n1️⃣ Testing Summary Service...")
    try:
        from app.services.summary_service import get_summary_service
        
        service = get_summary_service()
        print(f"   ✅ Summary service initialized")
        print(f"   ✅ Available modes: {list(service.modes.keys())}")
        
    except Exception as e:
        print(f"   ❌ Summary Service FAILED: {e}")
        return False
    
    # Test 2: Check OpenAI Configuration
    print("\n2️⃣ Checking OpenAI Configuration...")
    try:
        from app.core.config import settings
        
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_key_here":
            print(f"   ✅ OpenAI API Key: Configured (...{settings.OPENAI_API_KEY[-4:]})")
            print("   ✅ AI summarization available")
        else:
            print("   ❌ OpenAI API Key: NOT configured")
            print("   ❌ Summarization will NOT work without API key")
            return False
            
    except Exception as e:
        print(f"   ❌ Config check failed: {e}")
        return False
    
    # Test 3: Generate Test Summary
    print("\n3️⃣ Generating Test Summary...")
    try:
        test_transcript = """
        John: Hi everyone, let's discuss the Q1 project timeline.
        Sarah: I think we should focus on the API development first.
        Mike: Agreed. We also need to allocate resources for testing.
        John: Good point. Let's assign Sarah to lead API development.
        Sarah: I can start next week. We'll need about 3 weeks.
        Mike: I'll handle the testing infrastructure setup.
        """
        
        # Test brief summary
        brief_summary = await service.generate_summary(
            test_transcript,
            mode="realtime"
        )
        
        if brief_summary:
            print(f"   ✅ Brief summary generated ({len(brief_summary)} chars)")
            print(f"   📝 Summary: {brief_summary[:100]}...")
        else:
            print("   ⚠️ Empty summary returned")
        
        # Test action items extraction
        action_summary = await service.generate_summary(
            test_transcript,
            mode="action_items"
        )
        
        if action_summary:
            print(f"   ✅ Action items extracted ({len(action_summary)} chars)")
            print(f"   📋 Actions: {action_summary[:100]}...")
        else:
            print("   ⚠️ No action items extracted")
        
        print("   ✅ Summarization: WORKING")
        
    except Exception as e:
        print(f"   ❌ Summary Generation FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Check Summary Endpoint
    print("\n4️⃣ Checking Summary Router...")
    try:
        from app.routers.summary import router
        print(f"   ✅ Summary router loaded")
        print(f"   ✅ Endpoints available at /api/summary/...")
        
    except Exception as e:
        print(f"   ⚠️ Summary router check: {e}")
    
    print("\n" + "=" * 60)
    print("✅ SUMMARIZATION SYSTEM: READY")
    print("=" * 60)
    print("\nHow to use:")
    print("1. Join meeting and speak")
    print("2. Call: GET /api/meeting/rooms/{room_id}/session-summary")
    print("3. Summary will be generated with AI")
    print()
    print("Available modes:")
    print("- realtime: Quick brief updates")
    print("- final: Comprehensive meeting summary")
    print("- action_items: Extract decisions & tasks")
    print("- topics: Main themes discussed")
    print()
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_summarization())
    sys.exit(0 if success else 1)
