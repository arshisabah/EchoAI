import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Mic, MicOff, Video, VideoOff, LogOut, Users,
  MessageSquare, FileText, Heart, Phone, Settings, CheckSquare
} from 'lucide-react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { useWebRTC } from '../hooks/useWebRTC';
import VideoGrid from './Meeting/VideoGrid';
import ChatPanel from './Meeting/ChatPanel';
import TranscriptPanel from './Meeting/Transcription';
import EmotionPanel from './Meeting/EmotionPanel';
import SummaryPanel from './Meeting/SummaryPanel';
import TaskPanel from './Meeting/TaskPanel';
import { meetingAPI } from '../services/api';

const MeetingRoom = ({ userInfo }) => {
  const { roomId } = useParams();
  const navigate = useNavigate();

  const [roomInfo, setRoomInfo] = useState(null);
  const [activePanel, setActivePanel] = useState('transcript');
  const [showPassword, setShowPassword] = useState(false);
  const [password, setPassword] = useState('');
  const [emotionHistory, setEmotionHistory] = useState([]);
  
  // WebSocket connection
  const {
    isConnected,
    transcripts,
    participants,
    chatMessages,
    error: wsError,
    lastMessage,
    sendAudioChunk,
    sendChatMessage,
    sendSignalingMessage, 
    disconnect,
    connect,
  } = useWebSocket(roomId, userInfo.user_id, userInfo.username, password);

  // WebRTC for video
  const {
    localStream,
    remoteStreams,
    isVideoEnabled,
    isAudioEnabled,
    startLocalMedia,
    stopLocalMedia,
    toggleVideo,
    toggleAudio,
    handleSignalingMessage, 
  } = useWebRTC(roomId, userInfo.user_id, sendSignalingMessage);

  // Audio recording for transcription
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
  
  // Start WebSocket + WebRTC media
useEffect(() => {
  let active = true;

  if (active) {
    // ✅ Connect WebSocket and pass signaling handler
    connect({ onSignalingMessage: handleSignalingMessage });

    // ✅ Start camera + microphone
    startLocalMedia(true).catch(console.error);
  }

  // ✅ Cleanup on exit (close connections + media)
  return () => {
    active = false;
    stopLocalMedia();
    disconnect();
  };
}, [connect, handleSignalingMessage, startLocalMedia, stopLocalMedia, disconnect]);

  // Track emotion history
  useEffect(() => {
    if (lastMessage?.type === 'live_transcript' && lastMessage.emotion) {
      setEmotionHistory(prev => [...prev, lastMessage.emotion].slice(-10));
    }
  }, [lastMessage]);

  const loadRoomInfo = async () => {
    try {
      const data = await meetingAPI.getRoomInfo(roomId);
      setRoomInfo(data);

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
    stopLocalMedia();
    disconnect();
    navigate('/');
  };

  const handlePasswordSubmit = (e) => {
    e.preventDefault();
    setShowPassword(false);

    // ✅ Now that password is known, connect the WebSocket
    connect();
  };

  const handleExportTranscript = async () => {
    try {
      const data = await meetingAPI.exportMeeting(roomId, 'json');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `meeting_${roomId}_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Failed to export transcript');
    }
  };

  const handleSendChat = (message) => {
    sendChatMessage(message);
  };

  const currentEmotion = lastMessage?.type === 'live_transcript'
    ? lastMessage.emotion
    : 'neutral';

  const emotionGuidance = lastMessage?.type === 'live_transcript'
    ? lastMessage.emotion_guidance
    : null;

  // Password modal
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
      {/* Top Bar */}
      <div className="meeting-top-bar">
        <div className="meeting-info">
          <h2>{roomInfo?.room_name || roomId}</h2>
          <div className="meeting-status">
            <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
            <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
            <span className="separator">•</span>
            <Users size={14} />
            <span>{participants.length} participant{participants.length !== 1 ? 's' : ''}</span>
          </div>
        </div>

        <div className="meeting-controls">
          <button
            className={`btn-control ${!isAudioEnabled ? 'muted' : ''}`}
            onClick={toggleAudio}
            title={isAudioEnabled ? 'Mute' : 'Unmute'}
          >
            {isAudioEnabled ? <Mic size={20} /> : <MicOff size={20} />}
          </button>

          <button
            className={`btn-control ${!isVideoEnabled ? 'muted' : ''}`}
            onClick={toggleVideo}
            title={isVideoEnabled ? 'Stop Video' : 'Start Video'}
          >
            {isVideoEnabled ? <Video size={20} /> : <VideoOff size={20} />}
          </button>

          <button
            className={`btn-control ${isRecording ? 'recording' : ''}`}
            onClick={toggleRecording}
            title={isRecording ? 'Stop Transcription' : 'Start Transcription'}
          >
            <FileText size={20} />
            {isRecording && <span className="recording-indicator"></span>}
          </button>

          <div className="control-divider"></div>

          <button className="btn-control-danger" onClick={handleLeaveRoom}>
            <Phone size={20} />
            Leave
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {(wsError || audioError) && (
        <div className="error-banner">
          ⚠️ {wsError || audioError}
        </div>
      )}

      {/* Main Content */}
      <div className="meeting-content">
        {/* Left Side - Video Grid */}
        <div className="meeting-video-section">
          <VideoGrid
            localStream={localStream}
            remoteStreams={remoteStreams}
            participants={[
              { user_id: userInfo.user_id, username: userInfo.username, is_muted: !isAudioEnabled },
              ...participants
            ]}
            currentUserId={userInfo.user_id}
            isLocalVideoEnabled={isVideoEnabled}
            isLocalAudioEnabled={isAudioEnabled}
          />
        </div>

        {/* Right Side - Panels */}
        <div className="meeting-side-panel">
          {/* Panel Tabs */}
          <div className="panel-tabs">
            <button
              className={`panel-tab ${activePanel === 'transcript' ? 'active' : ''}`}
              onClick={() => setActivePanel('transcript')}
            >
              <FileText size={18} />
              <span>Transcript</span>
              {transcripts.length > 0 && (
                <span className="tab-badge">{transcripts.length}</span>
              )}
            </button>
            <button
              className={`panel-tab ${activePanel === 'chat' ? 'active' : ''}`}
              onClick={() => setActivePanel('chat')}
            >
              <MessageSquare size={18} />
              <span>Chat</span>
              {chatMessages.length > 0 && (
                <span className="tab-badge">{chatMessages.length}</span>
              )}
            </button>
            <button
              className={`panel-tab ${activePanel === 'emotion' ? 'active' : ''}`}
              onClick={() => setActivePanel('emotion')}
            >
              <Heart size={18} />
              <span>Emotion</span>
            </button>
            <button
              className={`panel-tab ${activePanel === 'tasks' ? 'active' : ''}`}
              onClick={() => setActivePanel('tasks')}
            >
              <CheckSquare size={18} />
              <span>Tasks</span>
            </button>
            <button
              className={`panel-tab ${activePanel === 'summary' ? 'active' : ''}`}
              onClick={() => setActivePanel('summary')}
            >
              <FileText size={18} />
              <span>Summary</span>
            </button>
          </div>

          {/* Panel Content */}
          <div className="panel-content">
            {activePanel === 'transcript' && (
              <TranscriptPanel
                transcripts={transcripts}
                onExport={handleExportTranscript}
              />
            )}
            {activePanel === 'chat' && (
              <ChatPanel
                messages={chatMessages}
                onSendMessage={handleSendChat}
                currentUser={userInfo}
              />
            )}
            {activePanel === 'emotion' && (
              <EmotionPanel
                currentEmotion={currentEmotion}
                emotionGuidance={emotionGuidance}
                emotionHistory={emotionHistory}
              />
            )}
            {activePanel === 'tasks' && (
              <TaskPanel
                roomId={roomId}
                currentUser={userInfo}
              />
            )}
            {activePanel === 'summary' && (
              <SummaryPanel roomId={roomId} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MeetingRoom;