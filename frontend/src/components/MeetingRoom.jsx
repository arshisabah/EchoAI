import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  Mic, MicOff, Video, VideoOff, PhoneOff, MessageSquare,
  FileText, Users, Heart, CheckSquare, FileText as Summary, Monitor, MonitorOff
} from 'lucide-react';

import { useWebSocket } from '../hooks/useWebSocket';
import { useWebRTC } from '../hooks/useWebRTC';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { meetingAPI } from '../services/api';

import VideoGrid from './Meeting/VideoGrid';
import ChatPanel from './Meeting/ChatPanel';
import TranscriptPanel from './Meeting/Transcription';
import EmotionPanel from './Meeting/EmotionPanel';
import TaskPanel from './Meeting/TaskPanel';
import SummaryPanel from './Meeting/SummaryPanel';

const MeetingRoom = ({ userInfo }) => {

  const navigate = useNavigate();
  const { roomId } = useParams();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);

  const roomPassword = queryParams.get("password") || "";

  console.log("LOADED CORRECT MEETING ROOM COMPONENT");
  console.log("roomId from useParams:", roomId);

  const [activeTab, setActiveTab] = useState('transcript');
  const [roomInfo, setRoomInfo] = useState(null);
  const [userRole, setUserRole] = useState("participant");
  const [currentEmotion, setCurrentEmotion] = useState('neutral');
  const [emotionGuidance, setEmotionGuidance] = useState(null);
  const [emotionHistory, setEmotionHistory] = useState([]);
  const [isScreenSharing, setIsScreenSharing] = useState(false);

  // -------------------------------
  // 1️⃣ Setup WebSocket (role will update later)
  // -------------------------------
  const {
    isConnected,
    transcripts,
    participants,
    activeSpeakerId,
    chatMessages,
    error: wsError,
    connect,
    disconnect,
    sendChatMessage,
    sendSignalingMessage,
    sendMessage,
  } = useWebSocket(roomId, userInfo.user_id, userInfo.username, roomPassword, userRole);

  // -------------------------------
  // 2️⃣ Setup WebRTC
  // -------------------------------
  const {
    localStream,
    remoteStreams,
    isVideoEnabled,
    isAudioEnabled,
    error: rtcError,
    startLocalMedia,
    stopLocalMedia,
    toggleVideo,
    toggleAudio,
    handleSignalingMessage,
    handleParticipantLeft,
    startScreenShare,
    stopScreenShare,
  } = useWebRTC(roomId, userInfo.user_id, sendSignalingMessage);

  // -------------------------------
  // 3️⃣ Audio Recorder
  // -------------------------------
  const {
    isRecording,
    error: recorderError,
    startRecording,
    stopRecording,
  } = useAudioRecorder((audioData) => {
    if (isConnected && audioData) {
      sendMessage({
        type: 'audio_chunk',
        audio_data: audioData,
        sample_rate: 16000,
      });
    }
  });

  // -------------------------------
  // 4️⃣ Load Room Info → Determine Role (HOST or PARTICIPANT)
  // -------------------------------
  useEffect(() => {
    const loadRoomInfo = async () => {
      try {
        const data = await meetingAPI.getRoomInfo(roomId);
        setRoomInfo(data);

        const detectedRole = data.created_by === userInfo.username ? "host" : "participant";
        console.log("🎭 DETECTED ROLE:", detectedRole);

        setUserRole(detectedRole);

      } catch (error) {
        console.error('Failed to load room info:', error);
        alert('Room not found or access denied');
        navigate('/');
      }
    };

    loadRoomInfo();
  }, [roomId, navigate]);

  // ---------------------------------------------------
  // 5️⃣ Reconnect WebSocket once ROLE is detected
  // ---------------------------------------------------
  useEffect(() => {
    if (!roomInfo) return;

    console.log("🔁 Reconnecting WebSocket with role:", userRole);

    disconnect();

    setTimeout(() => {
      connect({ onSignalingMessage: handleSignalingMessage });
    }, 300);

  }, [userRole]);

  // ---------------------------------------------------
  // 6️⃣ Initial media + websocket connection
  // ---------------------------------------------------
  useEffect(() => {
    const initialize = async () => {
      try {
        await startLocalMedia(false);
        connect({ onSignalingMessage: handleSignalingMessage });
      } catch (error) {
        console.error('Failed to initialize meeting:', error);
      }
    };

    initialize();

    return () => {
      stopRecording();
      stopLocalMedia();
      disconnect();
    };
  }, []);

  // ---------------------------------------------------
  // 7️⃣ Update Emotion States
  // ---------------------------------------------------
  useEffect(() => {
    if (transcripts.length > 0) {
      const latest = transcripts[0];
      if (latest.emotion) {
        setCurrentEmotion(latest.emotion);
        setEmotionHistory(prev => [...prev, latest.emotion].slice(-10));
      }
      if (latest.emotion_guidance) {
        setEmotionGuidance(latest.emotion_guidance);
      }
    }
  }, [transcripts]);

  // -------------------------------
  // 8️⃣ Leaving Room
  // -------------------------------
  const handleLeaveRoom = async () => {
    const confirmLeave = window.confirm('Are you sure you want to leave the meeting?');
    if (confirmLeave) {
      stopRecording();
      stopLocalMedia();
      disconnect();
      navigate('/');
    }
  };

  // -------------------------------
  // 9️⃣ Export Transcript
  // -------------------------------
  const handleExportTranscript = async () => {
    try {
      const data = await meetingAPI.exportMeeting(roomId, 'json');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `transcript_${roomId}_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Failed to export transcript');
    }
  };

  // -------------------------------
  // 🔟 Toggle Screen Share
  // -------------------------------
  const handleToggleScreenShare = async () => {
    try {
      if (isScreenSharing) {
        stopScreenShare();
        setIsScreenSharing(false);
      } else {
        await startScreenShare();
        setIsScreenSharing(true);
      }
    } catch (error) {
      console.error('Screen share error:', error);
      alert('Failed to share screen');
    }
  };

  // -------------------------------
  // UI Rendering
  // -------------------------------
  return (
    <div className="meeting-room">

      {/* TOP BAR */}
      <div className="meeting-top-bar">
        <div className="meeting-info">
          <h2>{roomInfo?.room_name || roomId}</h2>

          <div className="meeting-status">
            <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
            <span>{isConnected ? 'Connected' : 'Connecting...'}</span>
            <span className="separator">•</span>
            <span>{participants.length} participants</span>

            {isRecording && (
              <>
                <span className="separator">•</span>
                <span>🔴 Recording</span>
              </>
            )}
          </div>
        </div>

        {/* CONTROL BUTTONS */}
        <div className="meeting-controls">
          <button className={`btn-control ${!isAudioEnabled ? 'muted' : ''}`} onClick={toggleAudio}>
            {isAudioEnabled ? <Mic size={20} /> : <MicOff size={20} />}
          </button>

          <button className={`btn-control ${!isVideoEnabled ? 'muted' : ''}`} onClick={toggleVideo}>
            {isVideoEnabled ? <Video size={20} /> : <VideoOff size={20} />}
          </button>

          <button className={`btn-control ${isScreenSharing ? 'recording' : ''}`} onClick={handleToggleScreenShare}>
            {isScreenSharing ? <MonitorOff size={20} /> : <Monitor size={20} />}
          </button>

          <div className="control-divider" />

          <button className={`btn-control ${isRecording ? 'recording' : ''}`} onClick={isRecording ? stopRecording : startRecording}>
            <Mic size={20} />
            {isRecording && <span className="recording-indicator" />}
          </button>

          <div className="control-divider" />

          <button className="btn-control-danger" onClick={handleLeaveRoom}>
            <PhoneOff size={20} />
            <span>Leave</span>
          </button>
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div className="meeting-content">

        {/* VIDEO GRID */}
        <div className="meeting-video-section">
          <VideoGrid
            localStream={localStream}
            remoteStreams={remoteStreams}
            participants={participants}
            currentUserId={userInfo.user_id}
            isLocalVideoEnabled={isVideoEnabled}
            isLocalAudioEnabled={isAudioEnabled}
            activeSpeakerId={activeSpeakerId}
          />
        </div>

        {/* RIGHT SIDE PANEL */}
        <div className="meeting-side-panel">
          <div className="panel-tabs">

            <button className={`panel-tab ${activeTab === 'transcript' ? 'active' : ''}`} onClick={() => setActiveTab('transcript')}>
              <FileText size={18} />
              <span>Transcript</span>
              <span className="tab-badge">{transcripts.length}</span>
            </button>

            <button className={`panel-tab ${activeTab === 'chat' ? 'active' : ''}`} onClick={() => setActiveTab('chat')}>
              <MessageSquare size={18} />
              <span>Chat</span>
              {chatMessages.length > 0 && <span className="tab-badge">{chatMessages.length}</span>}
            </button>

            <button className={`panel-tab ${activeTab === 'emotion' ? 'active' : ''}`} onClick={() => setActiveTab('emotion')}>
              <Heart size={18} />
              <span>Emotion</span>
            </button>

            <button className={`panel-tab ${activeTab === 'tasks' ? 'active' : ''}`} onClick={() => setActiveTab('tasks')}>
              <CheckSquare size={18} />
              <span>Tasks</span>
            </button>

            <button className={`panel-tab ${activeTab === 'summary' ? 'active' : ''}`} onClick={() => setActiveTab('summary')}>
              <Summary size={18} />
              <span>Summary</span>
            </button>
          </div>

          <div className="panel-content">
            {activeTab === 'transcript' && (
              <TranscriptPanel transcripts={transcripts} onExport={handleExportTranscript} />
            )}

            {activeTab === 'chat' && (
              <ChatPanel messages={chatMessages} onSendMessage={sendChatMessage} currentUser={userInfo} />
            )}

            {activeTab === 'emotion' && (
              <EmotionPanel currentEmotion={currentEmotion} emotionGuidance={emotionGuidance} emotionHistory={emotionHistory} />
            )}

            {activeTab === 'tasks' && (
              <TaskPanel roomId={roomId} currentUser={userInfo} />
            )}

            {activeTab === 'summary' && (
              <SummaryPanel roomId={roomId} />
            )}
          </div>
        </div>
      </div>

      {(wsError || rtcError || recorderError) && (
        <div className="error-banner">
          ⚠️ {wsError || rtcError || recorderError}
        </div>
      )}
    </div>
  );
};

export default MeetingRoom;
