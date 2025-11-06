// src/components/MeetingRoom.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Mic, MicOff, LogOut, Users, FileText, CheckSquare } from 'lucide-react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import TranscriptViewer from './TranscriptViewer';
import EmotionIndicator from './EmotionIndicator';
import TaskManager from './TaskManager';
import SummaryPanel from './SummaryPanel';
import { meetingAPI } from '../services/api';

const MeetingRoom = ({ userInfo }) => {
  const { roomId } = useParams();
  const navigate = useNavigate();
  
  const [roomInfo, setRoomInfo] = useState(null);
  const [activeTab, setActiveTab] = useState('transcript');
  const [showPassword, setShowPassword] = useState(false);
  const [password, setPassword] = useState('');

  // WebSocket connection
  const {
    isConnected,
    transcripts,
    participants,
    error: wsError,
    lastMessage,
    sendAudioChunk,
    disconnect,
  } = useWebSocket(roomId, userInfo.user_id, userInfo.username, password);

  // Audio recording
  const {
    isRecording,
    error: audioError,
    toggleRecording,
  } = useAudioRecorder((audioData) => {
    if (isConnected) {
      sendAudioChunk(audioData, 16000);
    }
  });

  // Load room info
  useEffect(() => {
    loadRoomInfo();
  }, [roomId]);

  const loadRoomInfo = async () => {
    try {
      const data = await meetingAPI.getRoomInfo(roomId);
      setRoomInfo(data);
      
      // Check if password required
      if (data.password && !password) {
        setShowPassword(true);
      }
    } catch (error) {
      console.error('Error loading room:', error);
      if (error.response?.status === 404) {
        alert('Room not found');
        navigate('/');
      }
    }
  };

  const handleLeaveRoom = async () => {
    if (isRecording) {
      toggleRecording();
    }
    disconnect();
    navigate('/');
  };

  const handlePasswordSubmit = (e) => {
    e.preventDefault();
    setShowPassword(false);
    // WebSocket will reconnect with password
  };

  // Get current emotion from last message
  const currentEmotion = lastMessage?.type === 'live_transcript' 
    ? lastMessage.emotion 
    : 'neutral';

  const emotionGuidance = lastMessage?.type === 'live_transcript'
    ? lastMessage.emotion_guidance
    : null;

  if (showPassword) {
    return (
      <div className="password-prompt">
        <div className="password-card">
          <h2>Room Password Required</h2>
          <form onSubmit={handlePasswordSubmit}>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter room password"
              autoFocus
              required
            />
            <div className="modal-actions">
              <button type="button" className="btn-secondary" onClick={() => navigate('/')}>
                Cancel
              </button>
              <button type="submit" className="btn-primary">
                Join
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="meeting-room">
      {/* Room Header */}
      <div className="room-header">
        <div className="room-title">
          <h2>{roomInfo?.room_name || roomId}</h2>
          <span className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
          </span>
        </div>

        <div className="room-controls">
          <button
            className={`btn-icon ${isRecording ? 'recording' : ''}`}
            onClick={toggleRecording}
            title={isRecording ? 'Stop Recording' : 'Start Recording'}
          >
            {isRecording ? <MicOff size={20} /> : <Mic size={20} />}
            {isRecording && <span className="recording-pulse"></span>}
          </button>

          <button className="btn-danger" onClick={handleLeaveRoom} title="Leave Room">
            <LogOut size={20} />
            Leave
          </button>
        </div>
      </div>

      {/* Error Display */}
      {(wsError || audioError) && (
        <div className="error-banner">
          ⚠️ {wsError || audioError}
        </div>
      )}

      {/* Main Content Area */}
      <div className="room-content">
        {/* Left Panel - Transcripts */}
        <div className="room-left-panel">
          <div className="panel-tabs">
            <button
              className={`tab ${activeTab === 'transcript' ? 'active' : ''}`}
              onClick={() => setActiveTab('transcript')}
            >
              <FileText size={18} />
              Transcript
            </button>
            <button
              className={`tab ${activeTab === 'tasks' ? 'active' : ''}`}
              onClick={() => setActiveTab('tasks')}
            >
              <CheckSquare size={18} />
              Tasks
            </button>
            <button
              className={`tab ${activeTab === 'summary' ? 'active' : ''}`}
              onClick={() => setActiveTab('summary')}
            >
              <FileText size={18} />
              Summary
            </button>
          </div>

          <div className="panel-content">
            {activeTab === 'transcript' && (
              <TranscriptViewer transcripts={transcripts} />
            )}
            {activeTab === 'tasks' && (
              <TaskManager roomId={roomId} />
            )}
            {activeTab === 'summary' && (
              <SummaryPanel roomId={roomId} />
            )}
          </div>
        </div>

        {/* Right Panel - Participants & Emotion */}
        <div className="room-right-panel">
          {/* Participants */}
          <div className="participants-panel">
            <h3>
              <Users size={18} />
              Participants ({participants.length})
            </h3>
            <div className="participants-list">
              {participants.map((p) => (
                <div key={p.user_id} className="participant-item">
                  <div className="participant-avatar">
                    {p.username.charAt(0).toUpperCase()}
                  </div>
                  <div className="participant-info">
                    <span className="participant-name">{p.username}</span>
                    <span className="participant-role">{p.role}</span>
                  </div>
                  {p.is_speaking && (
                    <span className="speaking-indicator">🎤</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Emotion Indicator */}
          <EmotionIndicator 
            emotion={currentEmotion}
            guidance={emotionGuidance}
          />
        </div>
      </div>
    </div>
  );
};

export default MeetingRoom;