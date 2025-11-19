import React, { useState, useEffect, useRef } from 'react';
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
import PostMeetingModal from './Meeting/PostMeetingModal';

const MeetingRoom = ({ userInfo }) => {

  const navigate = useNavigate();
  const { roomId } = useParams();
  const location = useLocation();

  const queryParams = new URLSearchParams(location.search);
  const roomPassword = queryParams.get("password") || "";

  const [activeTab, setActiveTab] = useState("transcript");
  const [roomInfo, setRoomInfo] = useState(null);
  const [userRole, setUserRole] = useState("participant");
  const [currentEmotion, setCurrentEmotion] = useState("neutral");
  const [emotionGuidance, setEmotionGuidance] = useState(null);
  const [emotionHistory, setEmotionHistory] = useState([]);
  const [isScreenSharing, setIsScreenSharing] = useState(false);
  const [showPostMeetingModal, setShowPostMeetingModal] = useState(false);

  // ✅ FIX: Use ref to always have latest connection state
  const isTranscriptConnectedRef = useRef(false);

  console.log("MeetingRoom Loaded → roomId:", roomId, "password:", roomPassword);

  // ------------------------------
  // WEBSOCKET (Role + Password applied)
  // ------------------------------
  const {
    isConnected,
    isTranscriptConnected,  // ✅ FIX: Added this from useWebSocket return
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
    sendAudioChunk,
  } = useWebSocket(roomId, userInfo.user_id, userInfo.username, roomPassword, userRole);
  
  // ------------------------------
  // WEBRTC SETUP
  // ------------------------------
  const {
    localStream,
    remoteStreamsMap,    // Map<peerId, MediaStream>
    isVideoEnabled,
    isAudioEnabled,
    error: rtcError,
    startLocalMedia,
    stopLocalMedia,
    toggleVideo,
    toggleAudio,
    handleSignalingMessage,
    startScreenShare,
    stopScreenShare
  } = useWebRTC(roomId, userInfo.user_id, sendSignalingMessage);

  // ------------------------------
  // AUDIO RECORDER - ✅ FIXED: Use ref to avoid stale closure
  // ------------------------------
  const {
    isRecording,
    error: recorderError,
    startRecording,
    stopRecording,
  } = useAudioRecorder((pcmBytes) => {
    // ✅ FIX: Use ref.current to always get latest connection state
    if (isTranscriptConnectedRef.current) {
        console.log("🎵 Sending audio chunk:", pcmBytes.length, "bytes");
        sendAudioChunk(pcmBytes);
    } else {
        console.warn("⚠️ Audio chunk dropped - WebSocket not connected");
    }
  });

  // ------------------------------
  // UPDATE CONNECTION REF - ✅ FIX: Keep ref in sync with connection state
  // ------------------------------
  useEffect(() => {
    isTranscriptConnectedRef.current = isTranscriptConnected;
    console.log("📡 Connection state updated - isTranscriptConnected:", isTranscriptConnected);
  }, [isTranscriptConnected]);

  // ------------------------------
  // LOAD ROOM INFO → DETERMINE ROLE
  // ------------------------------
  useEffect(() => {
    const loadRoom = async () => {
      try {
        const data = await meetingAPI.getRoomInfo(roomId);
        setRoomInfo(data);

        const detectedRole =
          data.created_by === userInfo.username ? "host" : "participant";

        console.log("Detected Role →", detectedRole);

        setUserRole(detectedRole);

        // 👉 Now connect WebSocket with correct password & role
        connect({ onSignalingMessage: handleSignalingMessage });

      } catch (err) {
        console.error("Room load failed:", err);
        alert("Room not found");
        navigate("/");
      }
    };

    loadRoom();
  }, [roomId]);

  // ------------------------------
  // START CAMERA/MIC AFTER WEBSOCKET CONNECTS
  // ------------------------------
  useEffect(() => {
    const initMedia = async () => {
      try {
        await startLocalMedia(false);
      } catch (err) {
        console.error("Media init failed:", err);
      }
    };

    initMedia();

    return () => {
      stopRecording();
      stopLocalMedia();
      disconnect();
    };
  }, []);

  // Start recording once WebSocket is connected
  useEffect(() => {
    if (isConnected && !isRecording) {
      console.log("✅ WebSocket connected, starting audio recording...");
      console.log("📊 Connection state - isConnected:", isConnected, "isTranscriptConnected:", isTranscriptConnected);
      startRecording();
    } else if (!isConnected) {
      console.log("⏳ Waiting for WebSocket connection...");
    } else if (isRecording) {
      console.log("🎤 Recording already in progress");
    }
  }, [isConnected]);

  // ------------------------------
  // UPDATE EMOTION UI
  // ------------------------------
  useEffect(() => {
    if (!transcripts.length) return;

    const latest = transcripts[0];

    if (latest.emotion) {
      setCurrentEmotion(latest.emotion);
      setEmotionHistory((prev) => [...prev, latest.emotion].slice(-10));
    }

    if (latest.emotion_guidance) {
      setEmotionGuidance(latest.emotion_guidance);
    }
  }, [transcripts]);

  // ------------------------------
  // LEAVE MEETING
  // ------------------------------
  const handleLeaveRoom = () => {
    stopRecording();
    stopLocalMedia();
    disconnect();
    
    // Show post-meeting modal instead of navigating immediately
    setShowPostMeetingModal(true);
  };

  const handleCloseModal = () => {
    setShowPostMeetingModal(false);
    navigate("/");
  };

  // ------------------------------
  // EXPORT TRANSCRIPT
  // ------------------------------
  const handleExportTranscript = async () => {
    try {
      const data = await meetingAPI.exportMeeting(roomId, "json");
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");

      a.href = url;
      a.download = `transcript_${roomId}_${Date.now()}.json`;
      a.click();

      URL.revokeObjectURL(url);
    } catch (err) {
      alert("Export failed");
    }
  };

  // ------------------------------
  // TOGGLE SCREEN SHARE
  // ------------------------------
  const handleToggleScreenShare = async () => {
    try {
      if (isScreenSharing) {
        stopScreenShare();
        setIsScreenSharing(false);
      } else {
        await startScreenShare();
        setIsScreenSharing(true);
      }
    } catch (err) {
      console.error("Screen share error:", err);
    }
  };

  // ------------------------------
  // UI
  // ------------------------------
  return (
    <div className="meeting-room">

      {/* TOP BAR */}
      <div className="meeting-top-bar">
        <div className="meeting-info">
          <h2>{roomInfo?.room_name || roomId}</h2>

          <div className="meeting-status">
            <span className={`status-dot ${isConnected ? "connected" : "disconnected"}`} />
            <span>{isConnected ? "Connected" : "Connecting…"}</span>
            <span className="separator">•</span>
            <span>{participants.length} participants</span>
            {isRecording && <span>• 🔴 Recording</span>}
          </div>
        </div>

        <div className="meeting-controls">
          {/* Audio */}
          <button className={`btn-control ${!isAudioEnabled ? "muted" : ""}`} onClick={toggleAudio}>
            {isAudioEnabled ? <Mic size={20} /> : <MicOff size={20} />}
          </button>

          {/* Video */}
          <button className={`btn-control ${!isVideoEnabled ? "muted" : ""}`} onClick={toggleVideo}>
            {isVideoEnabled ? <Video size={20} /> : <VideoOff size={20} />}
          </button>

          {/* Screen Share */}
          <button className={`btn-control ${isScreenSharing ? "recording" : ""}`} onClick={handleToggleScreenShare}>
            {isScreenSharing ? <MonitorOff size={20} /> : <Monitor size={20} />}
          </button>

          <div className="control-divider" />

          {/* Recorder */}
          <button className={`btn-control ${isRecording ? "recording" : ""}`} onClick={isRecording ? stopRecording : startRecording}>
            <Mic size={20} />
          </button>

          <div className="control-divider" />

          {/* Leave */}
          <button className="btn-control-danger" onClick={handleLeaveRoom}>
            <PhoneOff size={20} />
            <span>Leave</span>
          </button>
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div className="meeting-content">
        <div className="meeting-video-section">
          <VideoGrid
            localStream={localStream}
            remoteStreams={remoteStreamsMap}
            participants={participants}
            currentUserId={userInfo.user_id}
            isLocalVideoEnabled={isVideoEnabled}
            isLocalAudioEnabled={isAudioEnabled}
            activeSpeakerId={activeSpeakerId}
          />
        </div>

        <div className="meeting-side-panel">
          <div className="panel-tabs">
            <button className={`panel-tab ${activeTab === "transcript" ? "active" : ""}`} onClick={() => setActiveTab("transcript")}>
              <FileText size={18} /> Transcript <span className="tab-badge">{transcripts.length}</span>
            </button>

            <button className={`panel-tab ${activeTab === "chat" ? "active" : ""}`} onClick={() => setActiveTab("chat")}>
              <MessageSquare size={18} /> Chat {chatMessages.length > 0 && <span className="tab-badge">{chatMessages.length}</span>}
            </button>

            <button className={`panel-tab ${activeTab === "emotion" ? "active" : ""}`} onClick={() => setActiveTab("emotion")}>
              <Heart size={18} /> Emotion
            </button>

            <button className={`panel-tab ${activeTab === "tasks" ? "active" : ""}`} onClick={() => setActiveTab("tasks")}>
              <CheckSquare size={18} /> Tasks
            </button>

            <button className={`panel-tab ${activeTab === "summary" ? "active" : ""}`} onClick={() => setActiveTab("summary")}>
              <Summary size={18} /> Summary
            </button>
          </div>

          <div className="panel-content">
            {activeTab === "transcript" && <TranscriptPanel transcripts={transcripts} onExport={handleExportTranscript} roomId={roomId} />}
            {activeTab === "chat" && <ChatPanel messages={chatMessages} onSendMessage={sendChatMessage} currentUser={userInfo} />}
            {activeTab === "emotion" && <EmotionPanel currentEmotion={currentEmotion} emotionGuidance={emotionGuidance} emotionHistory={emotionHistory} />}
            {activeTab === "tasks" && <TaskPanel roomId={roomId} currentUser={userInfo} />}
            {activeTab === "summary" && <SummaryPanel roomId={roomId} />}
          </div>
        </div>
      </div>

      {(wsError || rtcError || recorderError) && (
        <div className="error-banner">
          ⚠️ {wsError || rtcError || recorderError}
        </div>
      )}

      {showPostMeetingModal && (
        <PostMeetingModal 
          roomId={roomId}
          onClose={handleCloseModal}
        />
      )}
    </div>
  );
};

export default MeetingRoom;