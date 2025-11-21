import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import WebRTCService from "../services/WebRTCService";

const RTC_CONFIGURATION = WebRTCService.configuration;

export const useWebRTC = (roomId, userId, sendSignalingMessage) => {
  const [localStream, setLocalStream] = useState(null);
  const localStreamRef = useRef(null);

  // keep remote streams as a Map<peerId, MediaStream>
  const [remoteStreamsMap, setRemoteStreamsMap] = useState(new Map());
  const remoteStreamsMapRef = useRef(remoteStreamsMap);

  const [isVideoEnabled, setIsVideoEnabled] = useState(true);
  const [isAudioEnabled, setIsAudioEnabled] = useState(true);
  const [error, setError] = useState(null);

  // peerConnections map: peerId -> RTCPeerConnection
  const peerConnectionsRef = useRef(new Map());
  // store peerConnections also in WebRTCService for debugging / cleanup
  WebRTCService.peerConnections = peerConnectionsRef.current;

  // keep refs in sync
  useEffect(() => { localStreamRef.current = localStream; }, [localStream]);
  useEffect(() => { remoteStreamsMapRef.current = remoteStreamsMap; }, [remoteStreamsMap]);

  // helper: convert remote streams map to array for UI components
  const remoteStreamsArray = useMemo(() => Array.from(remoteStreamsMap.values()), [remoteStreamsMap]);

  const startLocalMedia = useCallback(async (audioOnly = false) => {
    try {
      const stream = await WebRTCService.startLocalStream(audioOnly);
      setLocalStream(stream);
      localStreamRef.current = stream;

      setIsAudioEnabled(stream.getAudioTracks().some(t => t.enabled));
      setIsVideoEnabled(stream.getVideoTracks().some(t => t.enabled));

      return stream;
    } catch (err) {
      setError(err?.message || String(err));
      throw err;
    }
  }, []);

  const stopLocalMedia = useCallback(() => {
    try {
      WebRTCService.stopLocalStream();
    } catch (e) {
      // ignore
    }
    setLocalStream(null);
    localStreamRef.current = null;
  }, []);

  const toggleVideo = useCallback(() => {
    const newState = !isVideoEnabled;
    try {
      WebRTCService.toggleVideo(newState);
      setIsVideoEnabled(newState);
    } catch (err) {
      setError(err?.message || String(err));
    }
  }, [isVideoEnabled]);

  const toggleAudio = useCallback(() => {
    const newState = !isAudioEnabled;
    try {
      WebRTCService.toggleAudio(newState);
      setIsAudioEnabled(newState);
    } catch (err) {
      setError(err?.message || String(err));
    }
  }, [isAudioEnabled]);

  const createPeerConnection = useCallback((peerId) => {
    // don't create a connection to ourselves
    if (!peerId || peerId === userId) {
      console.log(`⏭️ Skipping peer connection creation (self or invalid): ${peerId}`);
      return null;
    }

    if (peerConnectionsRef.current.has(peerId)) {
      console.log(`♻️ Reusing existing peer connection for ${peerId}`);
      return peerConnectionsRef.current.get(peerId);
    }

    console.log(`🔧 Creating new peer connection for ${peerId}`);
    const pc = new RTCPeerConnection(RTC_CONFIGURATION);

    // add local tracks (if already available)
    const local = localStreamRef.current || WebRTCService.localStream;
    if (local) {
      const tracks = local.getTracks();
      console.log(`📤 Adding ${tracks.length} local tracks to peer connection for ${peerId}:`, 
                  tracks.map(t => `${t.kind} (enabled: ${t.enabled})`));
      try {
        tracks.forEach(track => {
          const sender = pc.addTrack(track, local);
          console.log(`✅ Added ${track.kind} track to peer ${peerId}`);
        });
      } catch (err) {
        console.error(`❌ Failed to add local tracks to peer ${peerId}:`, err);
      }
    } else {
      console.warn(`⚠️ No local stream available when creating peer connection for ${peerId}`);
    }

    // when remote track arrives, save it under peerId
    pc.ontrack = (event) => {
      console.log(`📹 ontrack fired for peer ${peerId}`, event);
      const stream = event.streams && event.streams[0] ? event.streams[0] : null;
      if (!stream) {
        console.warn(`⚠️ No stream in ontrack event for peer ${peerId}`);
        return;
      }

      console.log(`✅ Remote stream received from peer ${peerId}:`, stream.id, 
                  `video tracks: ${stream.getVideoTracks().length}`, 
                  `audio tracks: ${stream.getAudioTracks().length}`);

      setRemoteStreamsMap(prev => {
        const updated = new Map(prev);
        updated.set(peerId, stream);
        remoteStreamsMapRef.current = updated;
        console.log(`📺 Updated remote streams map, now has ${updated.size} streams`);
        return updated;
      });
    };

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        console.log(`🧊 ICE candidate generated for peer ${peerId}:`, event.candidate.candidate.substring(0, 50) + '...');
        // send candidate to the specific peer via signaling server
        try {
          sendSignalingMessage({
            type: "ice_candidate",
            target_id: peerId,
            candidate: event.candidate,
            from_id: userId,
          });
          console.log(`✅ ICE candidate sent to peer ${peerId}`);
        } catch (err) {
          console.error(`❌ Failed to send ICE candidate to peer ${peerId}:`, err);
        }
      }
    };

    pc.onconnectionstatechange = () => {
      const state = pc.connectionState;
      console.log(`🔗 Connection state changed for peer ${peerId}: ${state}`);
      
      if (state === "connected") {
        console.log(`✅ WebRTC connection established with peer ${peerId}`);
      } else if (state === "failed" || state === "disconnected" || state === "closed") {
        console.warn(`❌ Connection ${state} for peer ${peerId}, cleaning up`);
        // cleanup remote stream and pc
        setRemoteStreamsMap(prev => {
          const updated = new Map(prev);
          updated.delete(peerId);
          remoteStreamsMapRef.current = updated;
          return updated;
        });

        try {
          pc.close();
        } catch (e) {}
        peerConnectionsRef.current.delete(peerId);
      }
    };

    // store
    peerConnectionsRef.current.set(peerId, pc);
    WebRTCService.peerConnections.set(peerId, pc);

    return pc;
  }, [sendSignalingMessage, userId]);

  // handle all incoming signaling messages
  const handleSignalingMessage = useCallback(async (data) => {
    const { type, sdp, candidate, from_id, user_id } = data;

    console.log(`📡 Handling signaling message:`, type, `from:`, from_id || user_id);

    try {
      if (type === "webrtc_offer") {
        // incoming offer from another peer -> create PC, set remote desc, answer
        const from = from_id || data.from || user_id;
        if (!from) {
          console.error('❌ webrtc_offer: no from_id');
          return;
        }

        console.log(`📨 Received WebRTC offer from ${from}`);
        const pc = createPeerConnection(from);
        if (!pc) {
          console.error(`❌ Failed to create peer connection for ${from}`);
          return;
        }

        // ✅ CHECK STATE BEFORE SETTING OFFER
        if (pc.signalingState === 'stable' || pc.signalingState === 'have-local-offer') {
          try {
            await pc.setRemoteDescription({ type: "offer", sdp });
            console.log(`✅ Set remote description (offer) for peer ${from}`);
          } catch (error) {
            console.error(`❌ Failed to set remote offer from ${from}:`, error);
            console.error(`   Current state: ${pc.signalingState}`);
            return;
          }
        } else {
          console.warn(`⚠️ Cannot set remote offer from ${from} - wrong state: ${pc.signalingState}`);
          return;
        }

        // ensure local tracks are attached before creating answer
        const local = localStreamRef.current || WebRTCService.localStream;
        if (local) {
          // add tracks if not already added
          try {
            local.getTracks().forEach(track => {
              // avoid adding duplicate senders
              const has = pc.getSenders().some(s => s.track === track);
              if (!has) pc.addTrack(track, local);
            });
          } catch (e) { /* ignore */ }
        }

        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        console.log(`✅ Created and set local description (answer) for peer ${from}`);

        sendSignalingMessage({
          type: "webrtc_answer",
          target_id: from,
          sdp: answer.sdp,
          from_id: userId,
        });
        console.log(`📤 Sent WebRTC answer to peer ${from}`);
      }

      if (type === "webrtc_answer") {
        const from = from_id || data.from || user_id;
        console.log(`📨 Received WebRTC answer from ${from}`);
        const pc = peerConnectionsRef.current.get(from);
        if (pc && sdp) {
          // ✅ CHECK STATE BEFORE SETTING ANSWER
          if (pc.signalingState === 'have-local-offer') {
            try {
              await pc.setRemoteDescription({ type: "answer", sdp });
              console.log(`✅ Set remote description (answer) for peer ${from}`);
            } catch (error) {
              console.error(`❌ Failed to set remote answer from ${from}:`, error);
              console.error(`   Current state: ${pc.signalingState}`);
            }
          } else {
            console.warn(`⚠️ Ignoring answer from ${from} - wrong state: ${pc.signalingState}`);
          }
        } else {
          console.error(`❌ No peer connection found for ${from} or missing SDP`);
        }
      }

      if (type === "ice_candidate" && candidate) {
        const from = from_id || data.from || user_id;
        console.log(`🧊 Received ICE candidate from ${from}`);
        const pc = peerConnectionsRef.current.get(from);
        if (pc) {
          try {
            // candidate might already be an RTCIceCandidateInit
            await pc.addIceCandidate(new RTCIceCandidate(candidate));
            console.log(`✅ Added ICE candidate for peer ${from}`);
          } catch (err) {
            console.error(`❌ addIceCandidate failed for peer ${from}:`, err);
          }
        } else {
          console.warn(`⚠️ No peer connection found for ${from} when adding ICE candidate`);
        }
      }

      if (type === "new_participant") {
        // server informs that a new participant is available (peerId)
        const newPeerId = data.user_id || data.userId;
        console.log(`👤 New participant notification:`, newPeerId, `(self: ${data.self})`);
        
        if (!newPeerId || newPeerId === userId) {
          console.log(`⏭️ Skipping self or invalid peer ID`);
          return;
        }

        console.log(`🤝 Creating peer connection and sending offer to ${newPeerId}`);
        // create pc and start offer
        const pc = createPeerConnection(newPeerId);
        if (!pc) {
          console.error(`❌ Failed to create peer connection for ${newPeerId}`);
          return;
        }

        // ensure local tracks attached
        const local = localStreamRef.current || WebRTCService.localStream;
        if (local) {
          try {
            local.getTracks().forEach(track => {
              const has = pc.getSenders().some(s => s.track === track);
              if (!has) pc.addTrack(track, local);
            });
          } catch (e) {}
        }

        // create offer and send
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        console.log(`✅ Created and set local description (offer) for peer ${newPeerId}`);

        sendSignalingMessage({
          type: "webrtc_offer",
          target_id: newPeerId,
          sdp: offer.sdp,
          from_id: userId,
        });
        console.log(`📤 Sent WebRTC offer to peer ${newPeerId}`);
      }
    } catch (err) {
      console.error("❌ Signaling handler error:", err);
      setError(err?.message || String(err));
    }
  }, [createPeerConnection, sendSignalingMessage, userId]);

  const handleParticipantLeft = useCallback((peerId) => {
    console.log(`👋 Participant left: ${peerId}, cleaning up connection`);
    const pc = peerConnectionsRef.current.get(peerId);
    if (pc) {
      try { pc.close(); } catch (e) {}
      peerConnectionsRef.current.delete(peerId);
    }

    setRemoteStreamsMap(prev => {
      const updated = new Map(prev);
      updated.delete(peerId);
      remoteStreamsMapRef.current = updated;
      return updated;
    });

    // also remove from WebRTCService map
    try { WebRTCService.peerConnections.delete(peerId); } catch (e) {}
  }, []);

  const startScreenShare = useCallback(async () => {
    try {
      console.log('🖥️ Starting screen share');
      const screenStream = await WebRTCService.startScreenShare();
      console.log('✅ Screen share started successfully');
      return screenStream;
    } catch (err) {
      console.error('❌ Failed to start screen share:', err);
      setError(err?.message || String(err));
      throw err;
    }
  }, []);

  const stopScreenShare = useCallback(() => {
    try {
      console.log('🛑 Stopping screen share');
      WebRTCService.stopScreenShare();
      console.log('✅ Screen share stopped');
    } catch (err) {
      console.error('❌ Failed to stop screen share:', err);
      setError(err?.message || String(err));
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // close peer connections
      for (const [id, pc] of peerConnectionsRef.current) {
        try { pc.close(); } catch (e) {}
      }
      peerConnectionsRef.current.clear();

      // stop local media
      try { WebRTCService.stopLocalStream(); } catch (e) {}

      setLocalStream(null);
      setRemoteStreamsMap(new Map());
      localStreamRef.current = null;
      remoteStreamsMapRef.current = new Map();
      WebRTCService.peerConnections = peerConnectionsRef.current;
    };
  }, []);

  return {
    localStream,
    remoteStreamsMap,     // Map<peerId, MediaStream> — useful when you need peer -> stream mapping
    remoteStreamsArray,   // array of MediaStream (for simple rendering)
    isVideoEnabled,
    isAudioEnabled,
    error,
    startLocalMedia,
    stopLocalMedia,
    toggleVideo,
    toggleAudio,
    handleSignalingMessage,
    handleParticipantLeft,
    startScreenShare,
    stopScreenShare,
  };
};

export default useWebRTC;
