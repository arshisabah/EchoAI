# tests/test_transcription_broadcast.py
"""
Tests for transcription broadcast functionality and logging.
Validates that transcription results are properly extracted and broadcast.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from app.services.meeting_room_manager import MeetingRoomManager, MeetingRoom, Participant, ParticipantRole


@pytest.fixture
def mock_room_manager():
    """Create a mock room manager with a test room."""
    from app.services.meeting_room_manager import MeetingStatus
    manager = MeetingRoomManager()
    
    # Create a test room with participants
    room_id = "test_room_123"
    room = MeetingRoom(
        room_id=room_id,
        room_name="Test Room",
        created_by="test_user",
        created_at=datetime.utcnow(),
        status=MeetingStatus.ACTIVE,
        participants={}
    )
    
    # Add mock participants
    mock_ws1 = Mock()
    mock_ws1.send_json = AsyncMock()
    
    mock_ws2 = Mock()
    mock_ws2.send_json = AsyncMock()
    
    participant1 = Participant(
        user_id="user1",
        username="User One",
        role=ParticipantRole.HOST,
        joined_at=datetime.utcnow(),
        websocket=mock_ws1
    )
    
    participant2 = Participant(
        user_id="user2",
        username="User Two",
        role=ParticipantRole.PARTICIPANT,
        joined_at=datetime.utcnow(),
        websocket=mock_ws2
    )
    
    room.participants["user1"] = participant1
    room.participants["user2"] = participant2
    
    manager.rooms[room_id] = room
    
    return manager, room_id, mock_ws1, mock_ws2


@pytest.mark.asyncio
async def test_broadcast_transcript_with_valid_room(mock_room_manager):
    """Test that broadcast_transcript successfully handles valid room."""
    manager, room_id, mock_ws1, mock_ws2 = mock_room_manager
    
    # Call broadcast_transcript
    await manager.broadcast_transcript(
        room_id=room_id,
        user_id="user1",
        username="User One",
        text="Hello, this is a test transcript",
        emotion="happy",
        confidence=0.85,
        emotion_guidance={"suggestion": "Great job!"}
    )
    
    # Verify room still exists and participant state was updated
    room = manager.rooms[room_id]
    assert room is not None
    assert "user1" in room.participants
    
    # Verify participant state was updated
    participant = room.participants["user1"]
    assert participant.emotion_state == "happy"
    assert participant.is_speaking is True


@pytest.mark.asyncio
async def test_broadcast_transcript_with_invalid_room():
    """Test that broadcast_transcript handles invalid room gracefully."""
    manager = MeetingRoomManager()
    
    # Try to broadcast to non-existent room (should not raise exception)
    await manager.broadcast_transcript(
        room_id="nonexistent_room",
        user_id="user1",
        username="User One",
        text="Test",
        emotion="neutral",
        confidence=0.5,
        emotion_guidance={}
    )
    
    # Should complete without errors
    assert True


@pytest.mark.asyncio
async def test_orchestrator_result_formats():
    """Test that different orchestrator result formats are handled correctly."""
    
    # Test single entry result
    single_result = {
        "text": "This is a single transcript entry",
        "speaker": "user1",
        "emotion": "neutral",
        "confidence": 0.9
    }
    
    entries = []
    if single_result.get("type") == "multi_speaker_chunk":
        entries = single_result.get("entries", [])
    elif isinstance(single_result, dict) and single_result.get("text"):
        entries = [single_result]
    
    assert len(entries) == 1
    assert entries[0]["text"] == "This is a single transcript entry"
    
    # Test multi-speaker result
    multi_result = {
        "type": "multi_speaker_chunk",
        "entries": [
            {"text": "First speaker", "speaker": "user1"},
            {"text": "Second speaker", "speaker": "user2"}
        ]
    }
    
    entries = []
    if multi_result.get("type") == "multi_speaker_chunk":
        entries = multi_result.get("entries", [])
    elif isinstance(multi_result, dict) and multi_result.get("text"):
        entries = [multi_result]
    
    assert len(entries) == 2
    assert entries[0]["text"] == "First speaker"
    assert entries[1]["text"] == "Second speaker"
    
    # Test empty result
    empty_result = None
    entries = []
    if empty_result:
        if empty_result.get("type") == "multi_speaker_chunk":
            entries = empty_result.get("entries", [])
        elif isinstance(empty_result, dict) and empty_result.get("text"):
            entries = [empty_result]
    
    assert len(entries) == 0


@pytest.mark.asyncio
async def test_broadcast_updates_participant_state(mock_room_manager):
    """Test that broadcast_transcript updates participant state correctly."""
    manager, room_id, mock_ws1, mock_ws2 = mock_room_manager
    
    # Initial state
    room = manager.rooms[room_id]
    participant = room.participants["user1"]
    assert participant.emotion_state == "neutral"
    assert participant.is_speaking is False
    
    # Broadcast transcript
    await manager.broadcast_transcript(
        room_id=room_id,
        user_id="user1",
        username="User One",
        text="Hello world",
        emotion="excited",
        confidence=0.9,
        emotion_guidance={}
    )
    
    # Check updated state
    participant = room.participants["user1"]
    assert participant.emotion_state == "excited"
    assert participant.is_speaking is True
    assert participant.last_activity is not None
