import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  Mic, MicOff, Video, VideoOff, PhoneOff, MessageSquare,
  FileText, Users, Heart, CheckSquare, FileText as Summary, Monitor, MonitorOff,
  PanelRightOpen, PanelRightClose, Maximize2, Minimize2, Maximize
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
import WebRTCDebugPanel from './Meeting/WebRTCDebugPanel';

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
  const [isSidePanelOpen, setIsSidePanelOpen] = useState(true);
  const [panelWidth, setPanelWidth] = useState(400);
  const [isResizing, setIsResizing] = useState(false);
  const [isPanelMaximized, setIsPanelMaximized] = useState(false);
  const [isRoomFullscreen, setIsRoomFullscreen] = useState(false);
  const [showDebugPanel, setShowDebugPanel] = useState(false);
  const resizeRef = useRef(null);
  const meetingRoomRef = useRef(null);

  // ✅ FIX: Use ref to always have latest connection state
  const isTranscriptConnectedRef = useRef(false);
  const isServerReadyRef = useRef(false);
  const isAudioEnabledRef = useRef(true); // Track mic state for audio transmission

  console.log("MeetingRoom Loaded → roomId:", roomId, "password:", roomPassword);

  // Panel resize handlers
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing) return;
      const newWidth = window.innerWidth - e.clientX;
      setPanelWidth(Math.max(300, Math.min(newWidth, window.innerWidth - 400)));
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  const handleResizeStart = () => {
    setIsResizing(true);
  };

  const togglePanelMaximize = () => {
    const newState = !isPanelMaximized;
    setIsPanelMaximized(newState);
    logger.info(`Panel ${newState ? 'maximized' : 'restored'}`);
    console.log('Panel maximize toggled:', newState);
  };

  const toggleRoomFullscreen = async () => {
    if (!meetingRoomRef.current) return;

    try {
      if (!document.fullscreenElement) {
        await meetingRoomRef.current.requestFullscreen();
        setIsRoomFullscreen(true);
      } else {
        await document.exitFullscreen();
        setIsRoomFullscreen(false);
      }
    } catch (error) {
      console.error('Fullscreen error:', error);
    }
  };

  // Listen for fullscreen changes (e.g., ESC key)
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsRoomFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // Add keyboard shortcut for debug panel (Ctrl/Cmd + Shift + D)
  useEffect(() => {
    const handleKeyPress = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'D') {
        e.preventDefault();
        setShowDebugPanel(prev => !prev);
        console.log(`🐛 Debug panel ${!showDebugPanel ? 'enabled' : 'disabled'}`);
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [showDebugPanel]);

  // ------------------------------
  // WEBSOCKET (Role + Password applied)
  // ------------------------------
  const {
    isConnected,
    isServerReady,
    isTranscriptConnected,  // ✅ FIX: Added this from useWebSocket return
    transcripts,
    participants,
    activeSpeakerId,
    chatMessages,
    error: wsError,
    lastMessage,
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
    toggleAudio: toggleAudioWebRTC,
    handleSignalingMessage,
    startScreenShare,
    stopScreenShare
  } = useWebRTC(roomId, userInfo.user_id, sendSignalingMessage);

  // ------------------------------
  // AUDIO RECORDER - ✅ FIXED: Use ref to avoid stale closure
  // Recording stays ON throughout meeting, but only sends audio when mic is enabled
  // ------------------------------
  const {
    isRecording,
    error: recorderError,
    startRecording,
    stopRecording,
  } = useAudioRecorder((pcmBytes) => {
    // ✅ FIX: Check connection state AND mic state before sending
    if (isTranscriptConnectedRef.current && isServerReadyRef.current && isAudioEnabledRef.current) {
        console.log("🎵 Sending audio chunk:", pcmBytes.length, "bytes");
        sendAudioChunk(pcmBytes);
    } else if (!isAudioEnabledRef.current) {
        console.log("🔇 Mic muted - audio chunk not sent (recording continues)");
    } else {
        console.warn("⚠️ Audio chunk dropped - Server not ready or WebSocket not connected", {
          isTranscriptConnected: isTranscriptConnectedRef.current,
          isServerReady: isServerReadyRef.current
        });
    }
  });

  // ------------------------------
  // CUSTOM AUDIO TOGGLE - Controls WebRTC audio and audio transmission
  // Recording stays ON throughout meeting - mic state only controls audio transmission
  // ------------------------------
  const toggleAudio = useCallback(() => {
    console.log(`🎤 Toggling audio: ${isAudioEnabled} -> ${!isAudioEnabled}`);
    
    // Toggle WebRTC audio (mute/unmute for other participants)
    toggleAudioWebRTC();
    
    // Note: Recording continues regardless of mic state
    // Audio chunks are only sent when mic is enabled (checked in useAudioRecorder callback)
    if (!isAudioEnabled) {
      console.log("🔊 Microphone enabled - audio will be transmitted");
    } else {
      console.log("🔇 Microphone muted - audio will NOT be transmitted (recording continues)");
    }
  }, [isAudioEnabled, toggleAudioWebRTC]);

  // ------------------------------
  // UPDATE REFS - ✅ FIX: Keep refs in sync with state
  // ------------------------------
  useEffect(() => {
    isTranscriptConnectedRef.current = isTranscriptConnected;
    console.log("📡 Connection state updated - isTranscriptConnected:", isTranscriptConnected);
  }, [isTranscriptConnected]);

  useEffect(() => {
    isAudioEnabledRef.current = isAudioEnabled;
    console.log("🎤 Mic state updated - isAudioEnabled:", isAudioEnabled);
  }, [isAudioEnabled]);

  // ------------------------------
  // UPDATE SERVER READY REF - ✅ FIX: Keep ref in sync with server ready state from useWebSocket
  // ------------------------------
  useEffect(() => {
    isServerReadyRef.current = isServerReady;
    console.log("🚀 Server ready state updated - isServerReady:", isServerReady);
  }, [isServerReady]);

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
    
    // Cleanup: disconnect WebSocket when component unmounts
    return () => {
      console.log("🧹 Component unmounting - cleaning up WebSocket");
      disconnect();
    };
  }, [roomId, connect, disconnect, handleSignalingMessage, userInfo.username, navigate]);

  // ------------------------------
  // START CAMERA/MIC IMMEDIATELY - CRITICAL FOR WEBRTC
  // ------------------------------
  useEffect(() => {
    let mounted = true;
    
    const initMedia = async () => {
      try {
        console.log("🎥 Initializing camera and microphone...");
        const stream = await startLocalMedia(true);  // ✅ Enable video by default
        
        if (mounted && stream) {
          console.log("✅ Local media initialized successfully:", {
            id: stream.id,
            videoTracks: stream.getVideoTracks().length,
            audioTracks: stream.getAudioTracks().length,
            tracks: stream.getTracks().map(t => ({
              kind: t.kind,
              label: t.label,
              enabled: t.enabled,
              readyState: t.readyState
            }))
          });
        }
      } catch (err) {
        console.error("❌ Media init failed:", err);
        alert("Failed to access camera/microphone. Please check your browser permissions.");
      }
    };

    initMedia();

    return () => {
      mounted = false;
      console.log("🧹 Cleaning up MeetingRoom resources...");
      stopRecording();
      stopLocalMedia();
      disconnect();
    };
  }, []);

  // Start recording once WebSocket is connected AND server is ready
  // Recording stays ON throughout meeting regardless of mic state
  useEffect(() => {
    if (isConnected && isServerReady && !isRecording) {
      console.log("✅ WebSocket connected AND server ready, starting audio recording...");
      console.log("📊 Connection state:", {
        isConnected,
        isServerReady,
        isTranscriptConnected,
        isRecording
      });
      console.log("📌 Recording will stay ON throughout meeting. Mic state controls audio transmission only.");
      
      // Start recording with error handling
      const startAudioRecording = async () => {
        try {
          console.log("🎤 Requesting microphone access...");
          await startRecording();
          console.log("✅ Audio recording started successfully");
        } catch (error) {
          console.error("❌ Failed to start audio recording:", error);
          alert("Microphone access required! Please allow microphone access and refresh the page.");
        }
      };
      
      startAudioRecording();
    } else if (!isConnected) {
      console.log("⏳ Waiting for WebSocket connection...");
    } else if (!isServerReady) {
      console.log("⏳ Waiting for server ready signal...");
    } else if (isRecording) {
      console.log("🎤 Recording already in progress");
    }
  }, [isConnected, isServerReady, isRecording, startRecording]);

  // ------------------------------
  // UPDATE EMOTION UI
  // ------------------------------
  useEffect(() => {
    if (!transcripts.length) return;

    // ✅ FIX: Get the LATEST transcript (last in array, not first)
    const latest = transcripts[transcripts.length - 1];
    
    // Debug logging (only in development)
    if (import.meta.env.DEV) {
      console.log("🎭 Emotion update check:", {
        hasEmotion: !!latest.emotion,
        emotion: latest.emotion,
        hasGuidance: !!latest.emotion_guidance,
        guidance: latest.emotion_guidance
      });
    }

    if (latest.emotion) {
      if (import.meta.env.DEV) {
        console.log(`✅ Setting emotion to: ${latest.emotion}`);
      }
      setCurrentEmotion(latest.emotion);
      setEmotionHistory((prev) => [...prev, latest.emotion].slice(-10));
    } else if (import.meta.env.DEV) {
      console.warn("⚠️ Latest transcript has no emotion field");
    }

    if (latest.emotion_guidance) {
      if (import.meta.env.DEV) {
        console.log("✅ Setting emotion guidance:", latest.emotion_guidance);
      }
      setEmotionGuidance(latest.emotion_guidance);
    } else if (import.meta.env.DEV) {
      console.warn("⚠️ Latest transcript has no emotion_guidance field");
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
    <div className={`meeting-room ${isRoomFullscreen ? 'fullscreen' : ''}`} ref={meetingRoomRef}>

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

        <div className="meeting-header-actions">
          <button 
            className="btn-fullscreen"
            onClick={toggleRoomFullscreen}
            title={isRoomFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
          >
            {isRoomFullscreen ? <Minimize2 size={18} /> : <Maximize size={18} />}
            <span>{isRoomFullscreen ? "Exit Fullscreen" : "Fullscreen"}</span>
          </button>
        </div>
      </div>

      {/* CONTROLS BAR */}
      <div className="meeting-controls-bar">
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
          
          {/* Panel Toggle Button (floating) */}
          <button 
            className="panel-toggle-btn"
            onClick={() => setIsSidePanelOpen(!isSidePanelOpen)}
            title={isSidePanelOpen ? "Hide side panel" : "Show side panel"}
          >
            {isSidePanelOpen ? <PanelRightClose size={20} /> : <PanelRightOpen size={20} />}
          </button>
        </div>

        <div className={`meeting-side-panel ${isSidePanelOpen ? 'open' : 'closed'} ${isPanelMaximized ? 'maximized' : ''}`} style={{ width: isPanelMaximized ? '100%' : `${panelWidth}px` }}>
          {isSidePanelOpen && !isPanelMaximized && (
            <div className="panel-resize-handle" onMouseDown={handleResizeStart} />
          )}
          <div className="panel-tabs">
            <button 
              className="panel-maximize-btn" 
              onClick={togglePanelMaximize}
              title={isPanelMaximized ? "Restore panel" : "Maximize panel"}
            >
              {isPanelMaximized ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            </button>
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

      {(wsError || rtcError) && (
        <div className="error-banner">
          ⚠️ {wsError || rtcError}
        </div>
      )}

      {recorderError && (
        <div className="error-banner warning">
          <span>🎤 {recorderError}</span>
          {recorderError.includes('localhost or HTTPS') && (
            <div style={{ marginTop: '8px', fontSize: '0.9em' }}>
              💡 Tip: Access via <strong>http://localhost:5173</strong> instead of IP address for microphone access
            </div>
          )}
        </div>
      )}

      {showPostMeetingModal && (
        <PostMeetingModal 
          roomId={roomId}
          onClose={handleCloseModal}
        />
      )}

      {/* WebRTC Debug Panel - Press Ctrl/Cmd + Shift + D to toggle */}
      <WebRTCDebugPanel
        localStream={localStream}
        remoteStreamsMap={remoteStreamsMap}
        participants={participants}
        isVisible={showDebugPanel}
      />
    </div>
  );
};

export default MeetingRoom;