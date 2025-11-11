import { useState, useEffect, useCallback, useRef } from 'react';

const RTC_CONFIGURATION = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
    { urls: 'stun:stun2.l.google.com:19302' },
  ],
};

const MEDIA_CONSTRAINTS = {
  video: {
    width: { ideal: 1280, max: 1920 },
    height: { ideal: 720, max: 1080 },
    frameRate: { ideal: 30, max: 30 },
  },
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  },
};

export const useWebRTC = (roomId, userId) => {
  const [localStream, setLocalStream] = useState(null);
  const [remoteStreams, setRemoteStreams] = useState(new Map());
  const [isVideoEnabled, setIsVideoEnabled] = useState(true);
  const [isAudioEnabled, setIsAudioEnabled] = useState(true);
  const [error, setError] = useState(null);

  const localStreamRef = useRef(null);
  const peerConnectionsRef = useRef(new Map());

  const startLocalMedia = useCallback(async (videoEnabled = true) => {
    try {
      setError(null);

      const constraints = videoEnabled
        ? MEDIA_CONSTRAINTS
        : {
            audio: MEDIA_CONSTRAINTS.audio,
            video: false,
          };

      console.log('🎥 Requesting media with constraints:', constraints);
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      
      localStreamRef.current = stream;
      setLocalStream(stream);
      setIsVideoEnabled(videoEnabled && stream.getVideoTracks().length > 0);
      setIsAudioEnabled(stream.getAudioTracks().length > 0);
      
      console.log('✅ Local media started');
      return stream;
    } catch (err) {
      console.error('❌ Error accessing media devices:', err);
      
      let errorMessage = 'Failed to access camera/microphone';
      if (err.name === 'NotAllowedError') {
        errorMessage = 'Camera/microphone access denied. Please allow access in your browser settings.';
      } else if (err.name === 'NotFoundError') {
        errorMessage = 'No camera/microphone found. Please connect a device and try again.';
      } else {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
      throw err;
    }
  }, []);

  const stopLocalMedia = useCallback(() => {
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => {
        track.stop();
        console.log('🛑 Stopped track:', track.kind);
      });
      localStreamRef.current = null;
      setLocalStream(null);
    }

    // Close all peer connections
    peerConnectionsRef.current.forEach((pc, peerId) => {
      pc.close();
      console.log('🔌 Closed peer connection:', peerId);
    });
    peerConnectionsRef.current.clear();
    setRemoteStreams(new Map());
  }, []);

  const toggleVideo = useCallback(() => {
    if (localStreamRef.current) {
      const videoTracks = localStreamRef.current.getVideoTracks();
      if (videoTracks.length > 0) {
        const newState = !isVideoEnabled;
        videoTracks.forEach((track) => {
          track.enabled = newState;
        });
        setIsVideoEnabled(newState);
        console.log('📹 Video toggled:', newState ? 'ON' : 'OFF');
      }
    }
  }, [isVideoEnabled]);

  const toggleAudio = useCallback(() => {
    if (localStreamRef.current) {
      const audioTracks = localStreamRef.current.getAudioTracks();
      if (audioTracks.length > 0) {
        const newState = !isAudioEnabled;
        audioTracks.forEach((track) => {
          track.enabled = newState;
        });
        setIsAudioEnabled(newState);
        console.log('🎤 Audio toggled:', newState ? 'ON' : 'OFF');
      }
    }
  }, [isAudioEnabled]);

  const createPeerConnection = useCallback((peerId) => {
    if (peerConnectionsRef.current.has(peerId)) {
      return peerConnectionsRef.current.get(peerId);
    }

    console.log('🔗 Creating peer connection for:', peerId);
    const pc = new RTCPeerConnection(RTC_CONFIGURATION);

    // Add local stream tracks to peer connection
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => {
        pc.addTrack(track, localStreamRef.current);
      });
    }

    // Handle remote stream
    pc.ontrack = (event) => {
      console.log('📥 Received remote track from:', peerId);
      setRemoteStreams((prev) => {
        const newMap = new Map(prev);
        newMap.set(peerId, event.streams[0]);
        return newMap;
      });
    };

    // Handle ICE candidates
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        console.log('🧊 ICE candidate:', event.candidate);
        // In a real implementation, send this to the signaling server
      }
    };

    // Handle connection state changes
    pc.onconnectionstatechange = () => {
      console.log(`🔗 Peer ${peerId} connection state:`, pc.connectionState);
      
      if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
        setRemoteStreams((prev) => {
          const newMap = new Map(prev);
          newMap.delete(peerId);
          return newMap;
        });
      }
    };

    peerConnectionsRef.current.set(peerId, pc);
    return pc;
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopLocalMedia();
    };
  }, [stopLocalMedia]);

  return {
    localStream,
    remoteStreams,
    isVideoEnabled,
    isAudioEnabled,
    error,
    startLocalMedia,
    stopLocalMedia,
    toggleVideo,
    toggleAudio,
    createPeerConnection,
  };
};