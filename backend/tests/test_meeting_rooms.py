# tests/test_meeting_rooms.py
"""
Tests for meeting room creation and management.
Validates fixes for room not found and WebSocket issues.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.meeting_room_manager import get_meeting_room_manager


@pytest.fixture
def client():
    """Test client for API testing."""
    return TestClient(app)


@pytest.fixture
async def cleanup_rooms():
    """Cleanup rooms after each test."""
    yield
    # Clean up any test rooms
    manager = get_meeting_room_manager()
    test_room_ids = [rid for rid in manager.rooms.keys() if "test_" in rid.lower()]
    for room_id in test_room_ids:
        try:
            if room_id in manager.rooms:
                manager.rooms.pop(room_id)
        except Exception:
            pass


class TestRoomCreation:
    """Test room creation fixes."""
    
    def test_create_room_with_room_name_as_id(self, client):
        """Test creating room using room_name as room_id."""
        room_name = "Test Room 123"
        
        response = client.post("/meeting/rooms/create", json={
            "room_name": room_name,
            "created_by": "test_user",
            "password": None,
            "max_participants": 50
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["room_id"] == room_name
        assert "room" in data
        assert data["room"]["room_name"] == room_name
    
    def test_create_room_with_password(self, client):
        """Test creating password-protected room."""
        room_name = "Test Protected Room"
        password = "secret123"
        
        response = client.post("/meeting/rooms/create", json={
            "room_name": room_name,
            "created_by": "test_user",
            "password": password,
            "max_participants": 10
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["room_id"] == room_name
    
    def test_create_room_without_password(self, client):
        """Test creating room without password."""
        room_name = "Test Open Room"
        
        response = client.post("/meeting/rooms/create", json={
            "room_name": room_name,
            "created_by": "test_user",
            "password": None,
            "max_participants": 50
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_create_duplicate_room(self, client):
        """Test creating duplicate room returns error."""
        room_name = "Duplicate Test Room"
        
        # Create first room
        response1 = client.post("/meeting/rooms/create", json={
            "room_name": room_name,
            "created_by": "test_user",
            "password": None,
            "max_participants": 50
        })
        assert response1.status_code == 200
        
        # Try to create duplicate
        response2 = client.post("/meeting/rooms/create", json={
            "room_name": room_name,
            "created_by": "test_user2",
            "password": None,
            "max_participants": 50
        })
        assert response2.status_code == 400


class TestRoomRetrieval:
    """Test room retrieval fixes."""
    
    def test_get_room_info_by_name(self, client):
        """Test retrieving room info using room name."""
        room_name = "Test Info Room"
        
        # Create room first
        client.post("/meeting/rooms/create", json={
            "room_name": room_name,
            "created_by": "test_user",
            "password": None,
            "max_participants": 50
        })
        
        # Get room info using room name as ID
        response = client.get(f"/meeting/rooms/{room_name}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["room_name"] == room_name
    
    def test_get_nonexistent_room(self, client):
        """Test getting non-existent room returns 404."""
        response = client.get("/meeting/rooms/NonExistentRoom123")
        assert response.status_code == 404


class TestPasswordValidation:
    """Test password validation fixes."""
    
    @pytest.mark.asyncio
    async def test_password_normalization(self):
        """Test that password normalization works correctly."""
        manager = get_meeting_room_manager()
        await manager.start_broadcasting()
        
        room_name = "Test Password Room"
        password = "mypassword"
        
        # Create room with password
        room = await manager.create_room(
            room_id=room_name,
            room_name=room_name,
            created_by="test_user",
            password=password,
            max_participants=50
        )
        
        # Test correct password
        class MockWebSocket:
            async def send_json(self, data): pass
            async def close(self): pass
        
        ws = MockWebSocket()
        
        # Should succeed with correct password
        participant = await manager.join_room(
            room_id=room_name,
            user_id="user1",
            username="user1",
            websocket=ws,
            password=password,
            role="participant"
        )
        assert participant is not None
        
        # Clean up
        manager.rooms.pop(room_name, None)
    
    @pytest.mark.asyncio
    async def test_password_validation_fails_with_wrong_password(self):
        """Test that wrong password fails validation."""
        manager = get_meeting_room_manager()
        await manager.start_broadcasting()
        
        room_name = "Test Wrong Password Room"
        password = "correctpassword"
        
        # Create room with password
        room = await manager.create_room(
            room_id=room_name,
            room_name=room_name,
            created_by="test_user",
            password=password,
            max_participants=50
        )
        
        class MockWebSocket:
            async def send_json(self, data): pass
            async def close(self): pass
        
        ws = MockWebSocket()
        
        # Should fail with wrong password
        with pytest.raises(ValueError, match="Invalid room password"):
            await manager.join_room(
                room_id=room_name,
                user_id="user1",
                username="user1",
                websocket=ws,
                password="wrongpassword",
                role="participant"
            )
        
        # Clean up
        manager.rooms.pop(room_name, None)
    
    @pytest.mark.asyncio
    async def test_no_password_room_accepts_any_password(self):
        """Test that room without password accepts any password value."""
        manager = get_meeting_room_manager()
        await manager.start_broadcasting()
        
        room_name = "Test No Password Room"
        
        # Create room without password
        room = await manager.create_room(
            room_id=room_name,
            room_name=room_name,
            created_by="test_user",
            password=None,
            max_participants=50
        )
        
        class MockWebSocket:
            async def send_json(self, data): pass
            async def close(self): pass
        
        ws = MockWebSocket()
        
        # Should succeed with any password (or no password)
        participant = await manager.join_room(
            room_id=room_name,
            user_id="user1",
            username="user1",
            websocket=ws,
            password="anypassword",  # Should be ignored
            role="participant"
        )
        assert participant is not None
        
        # Clean up
        manager.rooms.pop(room_name, None)


class TestRoleDetection:
    """Test role detection fixes."""
    
    @pytest.mark.asyncio
    async def test_creator_gets_host_role(self):
        """Test that room creator gets host role."""
        manager = get_meeting_room_manager()
        await manager.start_broadcasting()
        
        room_name = "Test Role Room"
        creator_username = "creator_user"
        
        # Create room
        room = await manager.create_room(
            room_id=room_name,
            room_name=room_name,
            created_by=creator_username,
            password=None,
            max_participants=50
        )
        
        class MockWebSocket:
            async def send_json(self, data): pass
            async def close(self): pass
        
        ws = MockWebSocket()
        
        # Creator joins - should get host role
        from app.services.meeting_room_manager import ParticipantRole
        participant = await manager.join_room(
            room_id=room_name,
            user_id="creator_id",
            username=creator_username,
            websocket=ws,
            password=None,
            role=ParticipantRole.HOST  # Server determines this
        )
        
        assert participant.role == ParticipantRole.HOST
        
        # Clean up
        manager.rooms.pop(room_name, None)
    
    @pytest.mark.asyncio
    async def test_non_creator_gets_participant_role(self):
        """Test that non-creator gets participant role."""
        manager = get_meeting_room_manager()
        await manager.start_broadcasting()
        
        room_name = "Test Participant Role Room"
        
        # Create room
        room = await manager.create_room(
            room_id=room_name,
            room_name=room_name,
            created_by="creator_user",
            password=None,
            max_participants=50
        )
        
        class MockWebSocket:
            async def send_json(self, data): pass
            async def close(self): pass
        
        ws = MockWebSocket()
        
        # Other user joins - should get participant role
        from app.services.meeting_room_manager import ParticipantRole
        participant = await manager.join_room(
            room_id=room_name,
            user_id="other_id",
            username="other_user",
            websocket=ws,
            password=None,
            role=ParticipantRole.PARTICIPANT
        )
        
        assert participant.role == ParticipantRole.PARTICIPANT
        
        # Clean up
        manager.rooms.pop(room_name, None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
