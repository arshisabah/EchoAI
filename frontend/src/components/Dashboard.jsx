import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Video, Users, Clock, TrendingUp, Download, FileText, Eye, EyeOff } from 'lucide-react';
import { meetingAPI, analyticsAPI } from '../services/api';

const Dashboard = ({ userInfo }) => {
  const navigate = useNavigate();
  const [rooms, setRooms] = useState([]);
  const [recentSessions, setRecentSessions] = useState([]);
  const [isCreating, setIsCreating] = useState(false);
  const [isJoining, setIsJoining] = useState(false);
  const [showCreatePassword, setShowCreatePassword] = useState(false);
  const [showJoinPassword, setShowJoinPassword] = useState(false);
  const [newRoomData, setNewRoomData] = useState({
    roomName: '',
    password: '',
    maxParticipants: 50,
  });
  const [joinRoomData, setJoinRoomData] = useState({
    roomName: '',
    password: '',
  });
  const [passwordPrompt, setPasswordPrompt] = useState({ show: false, roomId: null, hasPassword: false });
  const [showPasswordPrompt, setShowPasswordPrompt] = useState(false);
  const [loading, setLoading] = useState(true);

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

const handleCreateRoom = async (e) => {
  e.preventDefault();

  try {
    // Validate room name
    const roomName = newRoomData.roomName?.trim();
    if (!roomName) {
      alert('Please enter a room name');
      return;
    }

    // Normalize and validate max participants
    const maxParticipants = (() => {
      const n = parseInt(newRoomData.maxParticipants, 10);
      return Number.isFinite(n) && n >= 2 && n <= 100 ? n : 50;
    })();

    // Normalize password
    const passwordForApi = newRoomData.password?.trim() || null;

    // Call API with validated payload
    const result = await meetingAPI.createRoom({
      room_name: roomName,
      created_by: userInfo?.username || 'Guest',
      password: passwordForApi,
      max_participants: maxParticipants,
    });

    console.log('✅ Room created:', result);

    // Capture password for navigation before clearing state
    const passwordForNav = passwordForApi || '';
    const roomId = result.room_id;

    // Reset modal state
    setIsCreating(false);
    setNewRoomData({ roomName: '', password: '', maxParticipants: 50 });
    
    // Navigate immediately to the created room
    navigate(
      `/meeting/rooms/${encodeURIComponent(roomId)}?password=${encodeURIComponent(passwordForNav)}`
    );

  } catch (error) {
    console.error('❌ Error creating room:', error);
    
    // Check if room already exists
    const errorMessage = error.response?.data?.detail || error.message || 'Unknown error occurred';
    
    if (errorMessage.includes('already exists')) {
      // Room was created but navigation failed - try to join it
      console.log('Room already exists, attempting to join...');
      const passwordForNav = newRoomData.password?.trim() || '';
      const roomName = newRoomData.roomName?.trim();
      
      // Reset modal state
      setIsCreating(false);
      setNewRoomData({ roomName: '', password: '', maxParticipants: 50 });
      
      // Navigate to the existing room
      navigate(
        `/meeting/rooms/${encodeURIComponent(roomName)}?password=${encodeURIComponent(passwordForNav)}`
      );
    } else {
      alert(`Failed to create room: ${errorMessage}`);
    }
  }
};

  const handleJoinRoom = (roomId, hasPassword) => {
    if (hasPassword) {
      // Show password prompt modal
      setPasswordPrompt({ show: true, roomId, hasPassword: true });
    } else {
      // No password required - join directly
      navigate(`/meeting/rooms/${encodeURIComponent(roomId)}`);
    }
  };

  const handlePasswordSubmit = (e) => {
    e.preventDefault();
    const password = e.target.password.value;
    setPasswordPrompt({ show: false, roomId: null, hasPassword: false });
    navigate(`/meeting/rooms/${encodeURIComponent(passwordPrompt.roomId)}?password=${encodeURIComponent(password)}`);
  };

  const handleJoinRoomManually = (e) => {
    e.preventDefault();
    
    if (!joinRoomData.roomName.trim()) {
      alert('Please enter a room name');
      return;
    }
    
    setIsJoining(false);
    setJoinRoomData({ roomName: '', password: '' });
    navigate(`/meeting/rooms/${encodeURIComponent(joinRoomData.roomName)}?password=${encodeURIComponent(joinRoomData.password || "")}`);
  };

  const handleDownloadRecording = async (sessionId) => {
    try {
      const blob = await meetingAPI.downloadRecording(sessionId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `meeting_${sessionId}_${Date.now()}.wav`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
      alert('Failed to download recording');
    }
  };

  const handleDownloadTranscript = async (sessionId, format = 'txt') => {
    try {
      const blob = await meetingAPI.downloadTranscript(sessionId, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `transcript_${sessionId}_${Date.now()}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
      alert('Failed to download transcript');
    }
  };

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
      <div className="dashboard-header">
        <div>
          <h1>Welcome, {userInfo.username}!</h1>
          <p>Start a new meeting or join an existing one</p>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button
            className="btn-primary"
            onClick={() => {
              console.log("Creating new room...");
              setIsCreating(true);
            }}
          >
            <Plus size={18} />
            Create New Meeting
          </button>
          <button
            className="btn-secondary"
            onClick={() => {
              console.log("Opening join room modal...");
              setIsJoining(true);
            }}
            title="Join an existing room by entering its name"
          >
            <Video size={18} />
            Join Meeting
          </button>
        </div>
      </div>

      {/* Create Room Modal */}
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
                  onChange={(e) => setNewRoomData({ ...newRoomData, roomName: e.target.value })}
                  placeholder="e.g., Team Standup, Client Call"
                  required
                />
              </div>

              <div className="form-group">
                <label>Password </label>
                <div className="password-input-wrapper">
                  <input
                    type={showCreatePassword ? "text" : "password"}
                    value={newRoomData.password}
                    onChange={(e) => setNewRoomData({ ...newRoomData, password: e.target.value })}
                    placeholder="Leave empty for no password"
                  />
                  <button
                    type="button"
                    className="password-toggle-btn"
                    onClick={() => setShowCreatePassword(!showCreatePassword)}
                    tabIndex="-1"
                  >
                    {showCreatePassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <div className="form-group">
                <label>Max Participants</label>
                <input
                  type="number"
                  value={newRoomData.maxParticipants}
                  onChange={(e) => setNewRoomData({ ...newRoomData, maxParticipants: e.target.value })}
                  min="2"
                  max="100"
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

      {/* Join Room Modal */}
      {isJoining && (
        <div className="modal-overlay" onClick={() => setIsJoining(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Join Meeting Room</h2>
            <form onSubmit={handleJoinRoomManually}>
              <div className="form-group">
                <label>Room Name *</label>
                <input
                  type="text"
                  value={joinRoomData.roomName}
                  onChange={(e) => setJoinRoomData({ ...joinRoomData, roomName: e.target.value })}
                  placeholder="Enter room name"
                  required
                />
              </div>

              <div className="form-group">
                <label>Password (if required)</label>
                <div className="password-input-wrapper">
                  <input
                    type={showJoinPassword ? "text" : "password"}
                    value={joinRoomData.password}
                    onChange={(e) => setJoinRoomData({ ...joinRoomData, password: e.target.value })}
                    placeholder="Leave empty if no password"
                  />
                  <button
                    type="button"
                    className="password-toggle-btn"
                    onClick={() => setShowJoinPassword(!showJoinPassword)}
                    tabIndex="-1"
                  >
                    {showJoinPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setIsJoining(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Join Room
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Statistics Cards */}
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

      {/* Active Rooms */}
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
                    {room.participant_count || 0} / {room.max_participants} participants
                  </p>
                  <p>
                    <Clock size={16} />
                    Created {new Date(room.created_at).toLocaleString()}
                  </p>
                </div>
                <button
                  className="btn-primary btn-block"
                  onClick={() => handleJoinRoom(room.room_id, room.has_password)}
                >
                  Join Room
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Sessions */}
      <div className="dashboard-section">
        <h2>Recent Meetings</h2>
        {recentSessions.length === 0 ? (
          <p className="text-muted">No recent sessions</p>
        ) : (
          <div className="sessions-list">
            {recentSessions.slice(0, 5).map((session) => (
              <div key={session.session_id} className="session-card">
                <div className="session-info">
                  <h4>{session.session_id}</h4>
                  <p>{session.speakers?.join(', ') || 'No speakers'}</p>
                  <div className="session-stats">
                    <span>{session.total_entries || 0} entries</span>
                    <span>•</span>
                    <span>{session.duration_minutes?.toFixed(1) || 0} min</span>
                  </div>
                </div>
                <div className="session-actions">
                  <button 
                    className="btn-secondary btn-sm"
                    onClick={() => handleDownloadRecording(session.session_id)}
                    title="Download Recording"
                  >
                    <Download size={16} />
                    Recording
                  </button>
                  <button 
                    className="btn-secondary btn-sm"
                    onClick={() => handleDownloadTranscript(session.session_id, 'txt')}
                    title="Download Transcript"
                  >
                    <FileText size={16} />
                    Transcript
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Password Prompt Modal */}
      {passwordPrompt.show && (
        <div className="modal-overlay" onClick={() => setPasswordPrompt({ show: false, roomId: null, hasPassword: false })}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>🔐 Password Required</h2>
            <p>This room is password-protected. Please enter the password to join.</p>
            <form onSubmit={handlePasswordSubmit}>
              <div className="form-group">
                <label>Password *</label>
                <div className="password-input-wrapper">
                  <input
                    type={showPasswordPrompt ? "text" : "password"}
                    name="password"
                    placeholder="Enter room password"
                    required
                    autoFocus
                  />
                  <button
                    type="button"
                    className="password-toggle-btn"
                    onClick={() => setShowPasswordPrompt(!showPasswordPrompt)}
                    tabIndex="-1"
                  >
                    {showPasswordPrompt ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setPasswordPrompt({ show: false, roomId: null, hasPassword: false })}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Join Room
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;