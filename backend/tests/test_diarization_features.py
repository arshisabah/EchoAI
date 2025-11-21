"""
Test for Deepgram connection validation and diarization features.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock


class TestDeepgramConnectionValidation:
    """Test Deepgram connection validation improvements."""
    
    @pytest.mark.asyncio
    async def test_connection_ready_event_created(self):
        """Test that connection ready event is created on stream start."""
        with patch('app.services.deepgram_transcription.DeepgramClient'):
            from app.services.deepgram_transcription import DeepgramStreamingService
            
            service = DeepgramStreamingService(api_key="test_key")
            
            # Mock connection
            mock_connection = MagicMock()
            mock_connection.start = MagicMock(return_value=True)
            
            with patch.object(service, 'client') as mock_client:
                mock_client.listen.live.v.return_value = mock_connection
                
                # Start stream
                callback = AsyncMock()
                await service.start_stream(
                    session_id="test_session",
                    on_transcript=callback
                )
                
                # Verify ready event was created
                assert "test_session" in service.connection_ready
                assert isinstance(service.connection_ready["test_session"], asyncio.Event)
    
    @pytest.mark.asyncio
    async def test_send_audio_waits_for_ready(self):
        """Test that send_audio waits for connection to be ready."""
        with patch('app.services.deepgram_transcription.DeepgramClient'):
            from app.services.deepgram_transcription import DeepgramStreamingService
            
            service = DeepgramStreamingService(api_key="test_key")
            
            # Add a connection that's not ready yet
            mock_connection = MagicMock()
            service.connections["test_session"] = mock_connection
            
            # Create ready event but don't set it
            ready_event = asyncio.Event()
            service.connection_ready["test_session"] = ready_event
            
            # Try to send audio in background
            send_task = asyncio.create_task(
                service.send_audio("test_session", b"test_audio")
            )
            
            # Give it a moment to start waiting
            await asyncio.sleep(0.1)
            
            # Verify it's still waiting
            assert not send_task.done()
            
            # Set ready and verify it completes
            ready_event.set()
            await asyncio.sleep(0.1)
            
            # Should complete now
            result = await send_task
            # Should succeed after ready event is set
            assert result is True


class TestRoomDiarization:
    """Test room-level diarization features."""
    
    @pytest.mark.asyncio
    async def test_room_diarization_service_init(self):
        """Test room diarization service initialization."""
        from app.services.room_diarization_service import RoomDiarizationService
        
        service = RoomDiarizationService(deepgram_api_key=None)
        
        assert service.room_buffers is not None
        assert service.room_connections is not None
        assert service.speaker_mapping is not None
        assert service.participant_info is not None
    
    def test_participant_registration(self):
        """Test participant registration for speaker mapping."""
        from app.services.room_diarization_service import RoomDiarizationService
        
        service = RoomDiarizationService(deepgram_api_key=None)
        
        # Register a participant
        service.register_participant("room1", "user123", "John Doe")
        
        # Verify registration
        assert "room1" in service.participant_info
        assert "user123" in service.participant_info["room1"]
        assert service.participant_info["room1"]["user123"] == "John Doe"
        
        # Get participant name
        name = service.get_participant_name("room1", "user123")
        assert name == "John Doe"
    
    def test_speaker_mapping(self):
        """Test mapping Deepgram speaker IDs to participants."""
        from app.services.room_diarization_service import RoomDiarizationService
        
        service = RoomDiarizationService(deepgram_api_key=None)
        
        # Map speaker
        service.map_speaker("room1", 0, "user123")
        
        # Verify mapping
        assert "room1" in service.speaker_mapping
        assert 0 in service.speaker_mapping["room1"]
        assert service.speaker_mapping["room1"][0] == "user123"
        
        # Resolve speaker
        participant = service.resolve_speaker("room1", 0)
        assert participant == "user123"
        
        # Unknown speaker
        unknown = service.resolve_speaker("room1", 99)
        assert unknown is None


class TestOfflineDiarization:
    """Test offline diarization endpoint."""
    
    def test_diarization_endpoint_exists(self):
        """Test that diarization endpoint is registered."""
        from app.routers.meeting import router
        
        # Find the diarization route
        diarization_route = None
        for route in router.routes:
            if hasattr(route, 'path') and '/diarize' in route.path:
                diarization_route = route
                break
        
        assert diarization_route is not None
        assert 'POST' in diarization_route.methods


class TestAudioMixing:
    """Test audio mixing functionality."""
    
    def test_audio_mixer_creation(self):
        """Test audio mixer service creation."""
        from app.services.audio_mixer import get_audio_mixer
        
        mixer = get_audio_mixer()
        assert mixer is not None
        assert mixer.sample_rate == 16000
    
    def test_mix_empty_streams(self):
        """Test mixing with no audio streams."""
        from app.services.audio_mixer import get_audio_mixer
        import numpy as np
        
        mixer = get_audio_mixer()
        
        # Mix empty list
        result = mixer.mix_streams([])
        assert len(result) == 0
        
        # Mix list with empty arrays
        result = mixer.mix_streams([np.array([]), np.array([])])
        assert len(result) == 0
    
    def test_mix_basic_streams(self):
        """Test basic audio stream mixing."""
        from app.services.audio_mixer import get_audio_mixer
        import numpy as np
        
        mixer = get_audio_mixer()
        
        # Create two simple audio streams
        stream1 = np.array([0.5, 0.5, 0.5], dtype=np.float32)
        stream2 = np.array([0.3, 0.3, 0.3], dtype=np.float32)
        
        # Mix streams
        result = mixer.mix_streams([stream1, stream2], normalize=True)
        
        # Should be averaged
        assert len(result) == 3
        assert all(result >= 0)
        assert all(result <= 1.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
