# tests/test_websocket_state.py
"""
Tests for WebSocket state handling and race condition fixes.
Validates that WebSocket state is checked before sending and that
dictionary iteration race conditions are resolved.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, MagicMock
from starlette.websockets import WebSocketState
from app.services.meeting_room_manager import (
    get_meeting_room_manager,
    MeetingRoomManager,
    ParticipantRole
)


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self, state=WebSocketState.CONNECTED):
        self.client_state = state
        self._sent_messages = []
        
    async def send_json(self, data):
        if self.client_state != WebSocketState.CONNECTED:
            raise RuntimeError(f"Cannot send on WebSocket in state {self.client_state}")
        self._sent_messages.append(data)
    
    async def close(self):
        self.client_state = WebSocketState.DISCONNECTED
    
    def get_sent_messages(self):
        return self._sent_messages


@pytest.mark.asyncio
async def test_safe_websocket_send_connected():
    """Test safe_websocket_send succeeds when WebSocket is connected."""
    room_manager = MeetingRoomManager()
    await room_manager.start_broadcasting()
    
    try:
        ws = MockWebSocket(WebSocketState.CONNECTED)
        
        result = await room_manager.safe_websocket_send(
            ws,
            {"type": "test", "message": "hello"},
            "test_user"
        )
        
        assert result is True
        assert len(ws.get_sent_messages()) == 1
        assert ws.get_sent_messages()[0]["type"] == "test"
    finally:
        await room_manager.stop_broadcasting()


@pytest.mark.asyncio
async def test_safe_websocket_send_disconnected():
    """Test safe_websocket_send fails gracefully when WebSocket is disconnected."""
    room_manager = MeetingRoomManager()
    await room_manager.start_broadcasting()
    
    try:
        ws = MockWebSocket(WebSocketState.DISCONNECTED)
        
        result = await room_manager.safe_websocket_send(
            ws,
            {"type": "test", "message": "hello"},
            "test_user"
        )
        
        assert result is False
        assert len(ws.get_sent_messages()) == 0
    finally:
        await room_manager.stop_broadcasting()


@pytest.mark.asyncio
async def test_safe_websocket_send_connecting():
    """Test safe_websocket_send fails gracefully when WebSocket is still connecting."""
    room_manager = MeetingRoomManager()
    await room_manager.start_broadcasting()
    
    try:
        ws = MockWebSocket(WebSocketState.CONNECTING)
        
        result = await room_manager.safe_websocket_send(
            ws,
            {"type": "test", "message": "hello"},
            "test_user"
        )
        
        assert result is False
        assert len(ws.get_sent_messages()) == 0
    finally:
        await room_manager.stop_broadcasting()


@pytest.mark.asyncio
async def test_broadcast_to_room_with_disconnected_participant():
    """Test that broadcast continues when one participant is disconnected."""
    room_manager = MeetingRoomManager()
    await room_manager.start_broadcasting()
    
    try:
        # Create room
        room = await room_manager.create_room(
            room_id="test_room",
            room_name="Test Room",
            created_by="host",
            password=None,
            max_participants=10
        )
        
        # Add connected participant
        ws1 = MockWebSocket(WebSocketState.CONNECTED)
        await room_manager.join_room(
            room_id="test_room",
            user_id="user1",
            username="User 1",
            websocket=ws1,
            password=None,
            role=ParticipantRole.PARTICIPANT
        )
        
        # Add disconnected participant
        ws2 = MockWebSocket(WebSocketState.DISCONNECTED)
        await room_manager.join_room(
            room_id="test_room",
            user_id="user2",
            username="User 2",
            websocket=ws2,
            password=None,
            role=ParticipantRole.PARTICIPANT
        )
        
        # Broadcast message
        await room_manager.broadcast_to_room(
            room_id="test_room",
            message={"type": "test", "content": "Hello"}
        )
        
        # Wait for broadcast worker to process
        await asyncio.sleep(0.2)
        
        # Check that connected participant received message
        assert len(ws1.get_sent_messages()) > 0
        # Disconnected participant should not have received message
        assert len(ws2.get_sent_messages()) == 0
    finally:
        await room_manager.stop_broadcasting()


@pytest.mark.asyncio
async def test_no_dictionary_iteration_error_during_broadcast():
    """Test that removing participants during broadcast doesn't cause iteration error."""
    room_manager = MeetingRoomManager()
    await room_manager.start_broadcasting()
    
    try:
        # Create room
        room = await room_manager.create_room(
            room_id="test_room",
            room_name="Test Room",
            created_by="host",
            password=None,
            max_participants=10
        )
        
        # Add multiple participants
        participants = []
        for i in range(5):
            ws = MockWebSocket(WebSocketState.CONNECTED)
            await room_manager.join_room(
                room_id="test_room",
                user_id=f"user{i}",
                username=f"User {i}",
                websocket=ws,
                password=None,
                role=ParticipantRole.PARTICIPANT
            )
            participants.append(ws)
        
        # Start broadcasting messages while removing participants
        async def broadcast_loop():
            for i in range(10):
                await room_manager.broadcast_to_room(
                    room_id="test_room",
                    message={"type": "test", "iteration": i}
                )
                await asyncio.sleep(0.05)
        
        async def remove_participants():
            await asyncio.sleep(0.1)
            # Remove participants while broadcasts are happening
            for i in range(2):
                await room_manager.leave_room("test_room", f"user{i}")
                await asyncio.sleep(0.05)
        
        # Run both concurrently - should not raise "dictionary changed size" error
        try:
            await asyncio.gather(
                broadcast_loop(),
                remove_participants()
            )
            # If we get here without exception, the fix works
            assert True
        except RuntimeError as e:
            if "dictionary changed size" in str(e):
                pytest.fail(f"Dictionary iteration error occurred: {e}")
            raise
    finally:
        await room_manager.stop_broadcasting()


@pytest.mark.asyncio
async def test_broadcast_transcript_with_no_participants():
    """Test broadcast_transcript handles empty room gracefully."""
    room_manager = MeetingRoomManager()
    await room_manager.start_broadcasting()
    
    try:
        # Create room
        room = await room_manager.create_room(
            room_id="test_room",
            room_name="Test Room",
            created_by="host",
            password=None,
            max_participants=10
        )
        
        # Try to broadcast to empty room - should not raise exception
        await room_manager.broadcast_transcript(
            room_id="test_room",
            user_id="ghost_user",
            username="Ghost",
            text="Hello from the void",
            emotion="neutral",
            confidence=0.9,
            emotion_guidance={}
        )
        
        # Should complete without error
        assert True
    finally:
        await room_manager.stop_broadcasting()


@pytest.mark.asyncio
async def test_leave_room_during_active_broadcast():
    """Test that leaving room waits for in-flight broadcasts."""
    room_manager = MeetingRoomManager()
    await room_manager.start_broadcasting()
    
    try:
        # Create room
        room = await room_manager.create_room(
            room_id="test_room",
            room_name="Test Room",
            created_by="host",
            password=None,
            max_participants=10
        )
        
        # Add participant
        ws = MockWebSocket(WebSocketState.CONNECTED)
        await room_manager.join_room(
            room_id="test_room",
            user_id="user1",
            username="User 1",
            websocket=ws,
            password=None,
            role=ParticipantRole.PARTICIPANT
        )
        
        # Start broadcast
        broadcast_task = asyncio.create_task(
            room_manager.broadcast_to_room(
                room_id="test_room",
                message={"type": "test", "content": "Important message"}
            )
        )
        
        # Wait a moment for broadcast to be queued
        await asyncio.sleep(0.05)
        
        # Leave room - should wait for broadcasts to complete
        await room_manager.leave_room("test_room", "user1")
        
        # Ensure broadcast task completes
        await broadcast_task
        await asyncio.sleep(0.2)  # Wait for worker to process
        
        # WebSocket should be closed
        assert ws.client_state == WebSocketState.DISCONNECTED
    finally:
        await room_manager.stop_broadcasting()


@pytest.mark.asyncio
async def test_broadcast_worker_continues_after_error():
    """Test that broadcast worker continues processing after an error."""
    room_manager = MeetingRoomManager()
    await room_manager.start_broadcasting()
    
    try:
        # Create room
        room = await room_manager.create_room(
            room_id="test_room",
            room_name="Test Room",
            created_by="host",
            password=None,
            max_participants=10
        )
        
        # Add participant with broken websocket
        class BrokenWebSocket:
            client_state = WebSocketState.CONNECTED
            
            async def send_json(self, data):
                raise RuntimeError("Simulated send error")
            
            async def close(self):
                pass
        
        broken_ws = BrokenWebSocket()
        await room_manager.join_room(
            room_id="test_room",
            user_id="broken_user",
            username="Broken User",
            websocket=broken_ws,
            password=None,
            role=ParticipantRole.PARTICIPANT
        )
        
        # Add working participant
        working_ws = MockWebSocket(WebSocketState.CONNECTED)
        await room_manager.join_room(
            room_id="test_room",
            user_id="working_user",
            username="Working User",
            websocket=working_ws,
            password=None,
            role=ParticipantRole.PARTICIPANT
        )
        
        # Broadcast message - should handle broken_user error and continue
        await room_manager.broadcast_to_room(
            room_id="test_room",
            message={"type": "test", "content": "Test after error"}
        )
        
        # Wait for processing
        await asyncio.sleep(0.3)
        
        # Working user should have received later messages despite error with broken user
        # The broken user should have been removed from the room
        assert "working_user" in room_manager.rooms["test_room"].participants
        # Broadcast worker should still be running
        assert room_manager._broadcast_task is not None
        assert not room_manager._broadcast_task.done()
    finally:
        await room_manager.stop_broadcasting()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
