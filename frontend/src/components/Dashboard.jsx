import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Video, Users, Clock, TrendingUp } from 'lucide-react';
import { meetingAPI, analyticsAPI } from '../services/api';

const Dashboard = ({ userInfo }) => {
  const navigate = useNavigate();

  const [rooms, setRooms] = useState([]);
  const [recentSessions, setRecentSessions] = useState([]);

  const [isCreating, setIsCreating] = useState(false);
  const [isJoining, setIsJoining] = useState(false);

  const [newRoomData, setNewRoomData] = useState({
    roomName: '',
    password: '',
    maxParticipants: 50,
  });

  const [joinData, setJoinData] = useState({
    roomId: '',
    password: '',
  });

  const [loading, setLoading] = useState(true);

  // Load rooms + analytics ----------------------------------------------------
  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [roomsData, sessionsData] = await Promise.all([
        meetingAPI.listRooms(),
        analyticsAPI.listSessions(),
      ]);

      setRooms(roomsData.rooms || []);
      setRecentSessions(sessionsData.sessions || []);
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  // CREATE ROOM ---------------------------------------------------------------
  const handleCreateRoom = async (e) => {
    e.preventDefault();

    const roomId = `room_${Date.now()}`;
    const cleanPassword = newRoomData.password.trim() === "" ? null : newRoomData.password;

    try {
      await meetingAPI.createRoom(roomId, {
        room_name: newRoomData.roomName,
        created_by: userInfo.username,
        password: cleanPassword,
        max_participants: parseInt(newRoomData.maxParticipants),
      });

      setIsCreating(false);
      setNewRoomData({ roomName: '', password: '', maxParticipants: 50 });

      navigate(`/meeting/rooms/${roomId}?password=${encodeURIComponent(cleanPassword || "")}`);

    } catch (error) {
      console.error('Error creating room:', error);
      alert('Failed to create room: ' + error.message);
    }
  };

  // Dashboard "Join" from Active Room list -----------------------------------
  const handleJoinRoom = (roomId, roomPassword) => {
    navigate(`/meeting/rooms/${roomId}?password=${encodeURIComponent(roomPassword || "")}`);
  };

  // LOADING STATE -------------------------------------------------------------
  if (loading) {
    return (
      <div className="dashboard-loading">
        <div className="loading-spinner"></div>
        <p>Loading dashboard...</p>
      </div>
    );
  }

  return (
    <div className="dashboard">

      {/* Header -------------------------------------------------------------- */}
      <div className="dashboard-header">
        <div>
          <h1>Welcome, {userInfo.username}!</h1>
          <p>Start a new meeting or join an existing one</p>
        </div>

        <div className="dashboard-actions">
          <button className="btn-primary" onClick={() => setIsCreating(true)}>
            <Plus size={18} /> Create Meeting
          </button>

          <button className="btn-secondary" onClick={() => setIsJoining(true)}>
            <Users size={18} /> Join Meeting
          </button>
        </div>
      </div>

      {/* CREATE ROOM MODAL --------------------------------------------------- */}
      {isCreating && (
        <div className="modal-overlay" onClick={() => setIsCreating(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Create New Meeting Room</h2>

            <form onSubmit={handleCreateRoom}>

              <div className="form-group">
                <label>Room Name *</label>
                <input
                  type="text"
                  value={newRoomData.roomName}
                  onChange={(e) =>
                    setNewRoomData({ ...newRoomData, roomName: e.target.value })
                  }
                  required
                />
              </div>

              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  value={newRoomData.password}
                  onChange={(e) =>
                    setNewRoomData({ ...newRoomData, password: e.target.value })
                  }
                  placeholder="Leave empty for no password"
                />
              </div>

              <div className="form-group">
                <label>Max Participants</label>
                <input
                  type="number"
                  min="2"
                  max="100"
                  value={newRoomData.maxParticipants}
                  onChange={(e) =>
                    setNewRoomData({ ...newRoomData, maxParticipants: e.target.value })
                  }
                />
              </div>

              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setIsCreating(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Create Room
                </button>
              </div>

            </form>
          </div>
        </div>
      )}

      {/* JOIN ROOM MODAL ----------------------------------------------------- */}
      {isJoining && (
        <div className="modal-overlay" onClick={() => setIsJoining(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Join Meeting</h2>

            <div className="form-group">
              <label>Room ID *</label>
              <input
                type="text"
                value={joinData.roomId}
                onChange={(e) => setJoinData({ ...joinData, roomId: e.target.value })}
                placeholder="Enter existing Room ID"
                required
              />
            </div>

            <div className="form-group">
              <label>Password</label>
              <input
                type="password"
                value={joinData.password}
                onChange={(e) => setJoinData({ ...joinData, password: e.target.value })}
                placeholder="Room password"
              />
            </div>

            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setIsJoining(false)}>
                Cancel
              </button>

              <button
                className="btn-primary"
                onClick={() => {
                  navigate(
                    `/meeting/rooms/${joinData.roomId}?password=${encodeURIComponent(
                      joinData.password || ""
                    )}`
                  );
                }}
              >
                Join
              </button>
            </div>
          </div>
        </div>
      )}

      {/* STAT CARDS ---------------------------------------------------------- */}
      <div className="stats-grid">

        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#3b82f6' }}>
            <Video size={24} />
          </div>
          <div className="stat-content">
            <h3>{rooms.length}</h3>
            <p>Active Rooms</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#10b981' }}>
            <Users size={24} />
          </div>
          <div className="stat-content">
            <h3>{rooms.reduce((sum, r) => sum + (r.participant_count || 0), 0)}</h3>
            <p>Total Participants</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#f59e0b' }}>
            <Clock size={24} />
          </div>
          <div className="stat-content">
            <h3>{recentSessions.length}</h3>
            <p>Recent Sessions</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#8b5cf6' }}>
            <TrendingUp size={24} />
          </div>
          <div className="stat-content">
            <h3>
              {recentSessions.reduce((sum, s) => sum + (s.total_entries || 0), 0)}
            </h3>
            <p>Total Transcripts</p>
          </div>
        </div>

      </div>

      {/* ACTIVE ROOMS -------------------------------------------------------- */}
      <div className="dashboard-section">
        <h2>Active Meeting Rooms</h2>

        {rooms.length === 0 ? (
          <div className="empty-state">
            <Video size={48} />
            <p>No active rooms</p>
            <button className="btn-primary" onClick={() => setIsCreating(true)}>
              Create First Room
            </button>
          </div>
        ) : (
          <div className="rooms-grid">
            {rooms.map((room) => (
              <div key={room.room_id} className="room-card">

                <div className="room-header">
                  <h3>{room.room_name}</h3>
                  <span className={`room-status status-${room.status}`}>
                    {room.status}
                  </span>
                </div>

                <div className="room-info">
                  <p>
                    <Users size={16} />
                    {room.participant_count || 0} / {room.max_participants}
                  </p>
                  <p>
                    <Clock size={16} />
                    Created {new Date(room.created_at).toLocaleString()}
                  </p>
                </div>

                <button
                  className="btn-primary btn-block"
                  onClick={() => handleJoinRoom(room.room_id, room.password)}
                >
                  Join Room
                </button>

              </div>
            ))}
          </div>
        )}
      </div>

      {/* RECENT SESSIONS ----------------------------------------------------- */}
      <div className="dashboard-section">
        <h2>Recent Sessions</h2>

        {recentSessions.length === 0 ? (
          <p className="text-muted">No recent sessions</p>
        ) : (
          <div className="sessions-list">
            {recentSessions.slice(0, 5).map((session) => (
              <div key={session.session_id} className="session-item">
                <div className="session-info">
                  <h4>{session.session_id}</h4>
                  <p>{session.speakers?.join(', ') || 'No speakers'}</p>
                </div>
                <div className="session-stats">
                  <span>{session.total_entries || 0} entries</span>
                  <span>{session.duration_minutes?.toFixed(1) || 0} min</span>
                </div>
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  );
};

export default Dashboard;
