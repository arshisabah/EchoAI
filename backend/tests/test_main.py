# tests/test_main.py
"""
Comprehensive test suite for EchoAI Backend.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
import numpy as np
import base64

from app.main import app
from app.services.audio_utils import bytes_to_numpy
from app.services.transcription_service import get_transcription_service
from app.services.emotion_analysis import get_emotion_service
from app.modules.realtime_store import get_transcript_store


# Fixtures
@pytest.fixture
def client():
    """Test client for API testing."""
    return TestClient(app)


@pytest.fixture
def sample_audio():
    """Generate sample audio data."""
    # Generate 1 second of sine wave audio
    sample_rate = 16000
    duration = 1.0
    frequency = 440.0  # A4 note
    
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.sin(2 * np.pi * frequency * t) * 0.3
    
    # Convert to int16
    audio_int16 = (audio * 32767).astype(np.int16)
    
    return audio_int16.tobytes()


@pytest.fixture
def sample_audio_base64(sample_audio):
    """Base64 encoded sample audio."""
    return base64.b64encode(sample_audio).decode('utf-8')


# API Tests
class TestHealthEndpoints:
    """Test health and status endpoints."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestSessionManagement:
    """Test session creation and management."""
    
    def test_create_session(self, client):
        """Test creating a new session."""
        session_id = "test_session_123"
        response = client.post(f"/transcript/session/{session_id}/create")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
    
    def test_get_session_transcript(self, client):
        """Test getting session transcript."""
        session_id = "test_session_123"
        # Create session first
        client.post(f"/transcript/session/{session_id}/create")
        
        # Get transcript
        response = client.get(f"/transcript/session/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "transcript" in data
    
    def test_list_sessions(self, client):
        """Test listing all sessions."""
        response = client.get("/transcript/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total_sessions" in data
    
    def test_delete_session(self, client):
        """Test deleting a session."""
        session_id = "test_delete_session"
        # Create session
        client.post(f"/transcript/session/{session_id}/create")
        
        # Delete session
        response = client.delete(f"/transcript/session/{session_id}")
        assert response.status_code == 200


class TestAnalyticsEndpoints:
    """Test analytics endpoints."""
    
    def test_get_session_analytics(self, client):
        """Test getting session analytics."""
        session_id = "test_analytics_session"
        # Create session
        client.post(f"/transcript/session/{session_id}/create")
        
        # Get analytics
        response = client.get(f"/analytics/session/{session_id}")
        # May return 404 if no data, but shouldn't crash
        assert response.status_code in [200, 404]
    
    def test_list_all_sessions_analytics(self, client):
        """Test listing all sessions."""
        response = client.get("/analytics/sessions/list")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data


# Service Tests
class TestAudioUtils:
    """Test audio utility functions."""
    
    def test_bytes_to_numpy_conversion(self, sample_audio):
        """Test converting audio bytes to numpy array."""
        audio_array, sample_rate = bytes_to_numpy(sample_audio, 16000)
        
        assert isinstance(audio_array, np.ndarray)
        assert audio_array.dtype == np.float32
        assert len(audio_array) > 0
        assert sample_rate == 16000
    
    def test_empty_audio_handling(self):
        """Test handling of empty audio."""
        audio_array, sample_rate = bytes_to_numpy(b'', 16000)
        assert len(audio_array) == 0


class TestEmotionService:
    """Test emotion analysis service."""
    
    @pytest.mark.asyncio
    async def test_analyze_text(self):
        """Test emotion analysis on text."""
        service = get_emotion_service()
        
        result = await service.analyze_text("I am very happy today!")
        
        assert "emotion" in result
        assert "confidence" in result
        assert "scores" in result
        assert isinstance(result["emotion"], str)
        assert 0 <= result["confidence"] <= 1
    
    @pytest.mark.asyncio
    async def test_empty_text(self):
        """Test emotion analysis with empty text."""
        service = get_emotion_service()
        
        result = await service.analyze_text("")
        
        assert result["emotion"] == "neutral"
        assert result["confidence"] == 0.0
    
    @pytest.mark.asyncio
    async def test_batch_analysis(self):
        """Test analyzing multiple texts."""
        service = get_emotion_service()
        
        texts = [
            "I am happy!",
            "I am sad.",
            "I am angry!"
        ]
        
        results = await service.analyze_batch(texts)
        
        assert len(results) == len(texts)
        assert all("emotion" in r for r in results)


class TestTranscriptStore:
    """Test transcript storage."""
    
    @pytest.mark.asyncio
    async def test_create_session_store(self):
        """Test creating a session in the store."""
        store = get_transcript_store()
        
        session = await store.create_session("test_store_session")
        
        assert session.meeting_id == "test_store_session"
        assert len(session.participants) == 0
    
    @pytest.mark.asyncio
    async def test_add_transcript_entry(self):
        """Test adding a transcript entry."""
        store = get_transcript_store()
        
        await store.create_session("test_transcript_session")
        
        entry = await store.add_transcript_entry(
            "test_transcript_session",
            "Speaker_1",
            "Hello world",
            0.95
        )
        
        assert entry.text == "Hello world"
        assert entry.speaker == "Speaker_1"
        assert entry.confidence == 0.95
    
    @pytest.mark.asyncio
    async def test_get_transcripts(self):
        """Test retrieving transcripts."""
        store = get_transcript_store()
        session_id = "test_get_transcripts"
        
        await store.create_session(session_id)
        await store.add_transcript_entry(session_id, "Speaker_1", "Test 1", 0.9)
        await store.add_transcript_entry(session_id, "Speaker_2", "Test 2", 0.8)
        
        transcripts = await store.get_transcripts(session_id)
        
        assert len(transcripts) == 2
        assert transcripts[0].text == "Test 1"
        assert transcripts[1].text == "Test 2"


# Integration Tests
class TestWebSocketIntegration:
    """Test WebSocket integration."""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection."""
        from httpx import ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Note: Full WebSocket testing requires more complex setup
            # This is a placeholder for WebSocket integration tests
            pass


# Performance Tests
class TestPerformance:
    """Test performance benchmarks."""
    
    @pytest.mark.asyncio
    async def test_emotion_analysis_speed(self):
        """Test emotion analysis performance."""
        service = get_emotion_service()
        
        import time
        start = time.time()
        
        for _ in range(10):
            await service.analyze_text("This is a test sentence for performance testing.")
        
        duration = time.time() - start
        avg_time = duration / 10
        
        # Should complete in reasonable time (adjust threshold as needed)
        assert avg_time < 2.0, f"Average time {avg_time}s exceeds threshold"
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling concurrent requests."""
        service = get_emotion_service()
        
        tasks = []
        for i in range(20):
            tasks.append(service.analyze_text(f"Test sentence {i}"))
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 20
        assert all("emotion" in r for r in results)


# Edge Cases
class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_invalid_session_id(self, client):
        """Test accessing non-existent session."""
        response = client.get("/transcript/session/nonexistent_session")
        # Should handle gracefully
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_very_long_text_emotion(self):
        """Test emotion analysis on very long text."""
        service = get_emotion_service()
        
        long_text = "This is a test. " * 1000  # Very long text
        
        result = await service.analyze_text(long_text)
        
        # Should not crash
        assert "emotion" in result
    
    def test_special_characters_in_session_id(self, client):
        """Test session creation with special characters."""
        # Should handle or reject gracefully
        session_id = "test@#$%session"
        response = client.post(f"/transcript/session/{session_id}/create")
        # Accept either success or validation error
        assert response.status_code in [200, 400, 422]


# Cleanup
@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Cleanup after each test."""
    yield
    # Ensure all async tasks complete
    try:
        await asyncio.sleep(0.1)  # Allow pending tasks to complete
    except Exception:
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])