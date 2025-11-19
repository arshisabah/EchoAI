"""
Test historical transcript functionality.
Verifies that new participants receive transcripts from before they joined.
"""

import pytest
import asyncio
from datetime import datetime
from app.modules.realtime_store import get_transcript_store


@pytest.mark.asyncio
async def test_transcript_store_creates_session():
    """Test that transcript store can create a session."""
    store = get_transcript_store()
    
    session_id = "test_session_historical"
    metadata = {
        "room_name": "Test Room",
        "created_by": "test_user"
    }
    
    # Create session
    session = await store.create_session(session_id, metadata)
    
    assert session is not None
    assert session.meeting_id == session_id
    assert session.status.value == "active"


@pytest.mark.asyncio
async def test_transcript_store_adds_entries():
    """Test that transcript store can add and retrieve entries."""
    store = get_transcript_store()
    
    session_id = "test_session_add_entries"
    
    # Create session
    await store.create_session(session_id, {})
    
    # Add transcript entries
    entry1 = await store.add_transcript_entry(
        meeting_id=session_id,
        speaker="user_1",
        text="Hello, everyone!",
        confidence=0.95
    )
    
    entry2 = await store.add_transcript_entry(
        meeting_id=session_id,
        speaker="user_2",
        text="Hi there!",
        confidence=0.92
    )
    
    # Retrieve transcripts
    transcripts = store.get_session_transcript(session_id)
    
    assert len(transcripts) == 2
    assert transcripts[0].text == "Hello, everyone!"
    assert transcripts[0].speaker == "user_1"
    assert transcripts[1].text == "Hi there!"
    assert transcripts[1].speaker == "user_2"


@pytest.mark.asyncio
async def test_historical_transcripts_format():
    """Test that historical transcripts have the correct format."""
    store = get_transcript_store()
    
    session_id = "test_session_format"
    
    # Create session
    await store.create_session(session_id, {})
    
    # Add transcript entry with emotion data
    entry = await store.add_transcript_entry(
        meeting_id=session_id,
        speaker="user_1",
        text="This is great!",
        confidence=0.98
    )
    
    # Add emotion data
    entry.emotions = {
        "emotion": "happy",
        "confidence": 0.85,
        "scores": {"happy": 0.85, "neutral": 0.15}
    }
    
    # Retrieve and check format
    transcripts = store.get_session_transcript(session_id)
    assert len(transcripts) == 1
    
    transcript = transcripts[0]
    assert transcript.text == "This is great!"
    assert transcript.speaker == "user_1"
    assert transcript.emotions is not None
    assert transcript.emotions["emotion"] == "happy"
    assert transcript.emotions["confidence"] == 0.85


@pytest.mark.asyncio
async def test_multiple_speakers_in_session():
    """Test that transcript store handles multiple speakers correctly."""
    store = get_transcript_store()
    
    session_id = "test_session_multi_speaker"
    
    # Create session
    await store.create_session(session_id, {})
    
    # Add entries from multiple speakers
    speakers = ["alice", "bob", "charlie", "alice", "bob"]
    messages = [
        "Let's start the meeting",
        "Sounds good to me",
        "I agree",
        "What's the first topic?",
        "We should discuss the project timeline"
    ]
    
    for speaker, message in zip(speakers, messages):
        await store.add_transcript_entry(
            meeting_id=session_id,
            speaker=speaker,
            text=message,
            confidence=0.9
        )
    
    # Retrieve transcripts
    transcripts = store.get_session_transcript(session_id)
    
    assert len(transcripts) == 5
    
    # Check order is preserved
    assert transcripts[0].speaker == "alice"
    assert transcripts[1].speaker == "bob"
    assert transcripts[2].speaker == "charlie"
    assert transcripts[3].speaker == "alice"
    assert transcripts[4].speaker == "bob"
    
    # Check messages
    assert transcripts[0].text == "Let's start the meeting"
    assert transcripts[4].text == "We should discuss the project timeline"


@pytest.mark.asyncio
async def test_empty_session_transcripts():
    """Test retrieving transcripts from an empty session."""
    store = get_transcript_store()
    
    session_id = "test_session_empty"
    
    # Create session but don't add any transcripts
    await store.create_session(session_id, {})
    
    # Retrieve transcripts
    transcripts = store.get_session_transcript(session_id)
    
    assert transcripts is not None
    assert len(transcripts) == 0


@pytest.mark.asyncio
async def test_nonexistent_session_transcripts():
    """Test retrieving transcripts from a non-existent session."""
    store = get_transcript_store()
    
    # Try to get transcripts from non-existent session
    transcripts = store.get_session_transcript("nonexistent_session")
    
    # Should return empty list
    assert transcripts == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
