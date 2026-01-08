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

  const toggleVideo = useCallback(async () => {
    const newState = !isVideoEnabled;
    try {
      console.log(`📹 Toggling video: ${isVideoEnabled} -> ${newState}`);
      
      // toggleVideo is now async and might return a new track
      const result = await WebRTCService.toggleVideo(newState);
      
      setIsVideoEnabled(newState);
      
      // Force re-render by updating localStream state
      // This ensures VideoGrid picks up track changes
      if (localStreamRef.current) {
        console.log('🔄 Forcing localStream re-render');
        setLocalStream(new MediaStream(localStreamRef.current.getTracks()));
      }
      
      // Notify server about video state change
      if (sendSignalingMessage) {
        console.log(`📹 Notifying server: video ${newState ? 'enabled' : 'disabled'}`);
        sendSignalingMessage({
          type: 'media_state',
          is_video_on: newState,
          is_audio_on: undefined // Don't change audio state
        });
      }
    } catch (err) {
      console.error('❌ Video toggle error:', err);
      setError(err?.message || String(err));
    }
  }, [isVideoEnabled, sendSignalingMessage]);

  const toggleAudio = useCallback(() => {
    const newState = !isAudioEnabled;
    try {
      WebRTCService.toggleAudio(newState);
      setIsAudioEnabled(newState);
      
      // Notify server about audio state change
      if (sendSignalingMessage) {
        console.log(`🎤 Notifying server: audio ${newState ? 'enabled' : 'disabled'}`);
        sendSignalingMessage({
          type: 'media_state',
          is_audio_on: newState,
          is_video_on: undefined // Don't change video state
        });
      }
    } catch (err) {
      setError(err?.message || String(err));
    }
  }, [isAudioEnabled, sendSignalingMessage]);

  const createPeerConnection = useCallback((peerId) => {
    // don't create a connection to ourselves
    if (!peerId || peerId === userId) {
      console.log(`⏭️ Skipping peer connection creation (self or invalid): ${peerId}`);
      return null;
    }

    if (peerConnectionsRef.current.has(peerId)) {
      const existingPc = peerConnectionsRef.current.get(peerId);
      console.log(`♻️ Found existing peer connection for ${peerId}, state: ${existingPc.signalingState}`);
      
      // If the connection is in a bad state, close and recreate
      if (existingPc.signalingState === 'closed' || existingPc.iceConnectionState === 'failed') {
        console.log(`🔄 Closing failed connection for ${peerId} and creating new one`);
        existingPc.close();
        peerConnectionsRef.current.delete(peerId);
        WebRTCService.peerConnections.delete(peerId);
      } else {
        return existingPc;
      }
    }

    // ✅ CRITICAL: Wait for local stream before creating connections
    const local = localStreamRef.current || WebRTCService.localStream;
    if (!local || local.getTracks().length === 0) {
      console.error(`❌ CRITICAL: Cannot create peer connection - no local stream available yet for ${peerId}`);
      console.error(`Please wait for camera/mic to initialize before joining`);
      return null;
    }

    const videoTracks = local.getVideoTracks();
    const audioTracks = local.getAudioTracks();
    console.log(`📹 Local stream status:`, {
      totalTracks: local.getTracks().length,
      videoTracks: videoTracks.length,
      audioTracks: audioTracks.length,
      videoEnabled: videoTracks[0]?.enabled,
      audioEnabled: audioTracks[0]?.enabled
    });

    console.log(`🔧 Creating new peer connection for ${peerId}`);
    const pc = new RTCPeerConnection(RTC_CONFIGURATION);

    // add local tracks (verified available)
    const tracks = local.getTracks();
    console.log(`📤 Adding ${tracks.length} local tracks to peer connection for ${peerId}:`, 
                tracks.map(t => `${t.kind} (enabled: ${t.enabled}, readyState: ${t.readyState})`));
    try {
      tracks.forEach(track => {
        // Ensure track is enabled and live before adding
        if (track.readyState === 'live') {
          const sender = pc.addTrack(track, local);
          console.log(`✅ Added ${track.kind} track to peer ${peerId} (enabled: ${track.enabled})`);
        } else {
          console.warn(`⚠️ Skipping ${track.kind} track for ${peerId} - readyState: ${track.readyState}`);
        }
      });
      
      // Verify tracks were added
      const senders = pc.getSenders();
      console.log(`📊 Peer ${peerId} has ${senders.length} senders after adding tracks`);
      senders.forEach(sender => {
        if (sender.track) {
          console.log(`  - ${sender.track.kind}: ${sender.track.enabled ? 'enabled' : 'disabled'}`);
        }
      });
    } catch (err) {
      console.error(`❌ Failed to add local tracks to peer ${peerId}:`, err);
      pc.close();
      return null;
    }

    // when remote track arrives, save it under peerId
    pc.ontrack = (event) => {
      console.log(`📹 ontrack fired for peer ${peerId}`, event);
      console.log(`📊 Track details:`, {
        kind: event.track.kind,
        id: event.track.id,
        label: event.track.label,
        enabled: event.track.enabled,
        muted: event.track.muted,
        readyState: event.track.readyState,
        streams: event.streams?.length
      });

      const stream = event.streams && event.streams[0] ? event.streams[0] : null;
      if (!stream) {
        console.warn(`⚠️ No stream in ontrack event for peer ${peerId}`);
        // Create a new MediaStream with this track
        const newStream = new MediaStream([event.track]);
        console.log(`🔧 Created new MediaStream from track for peer ${peerId}`);
        
        setRemoteStreamsMap(prev => {
          const updated = new Map(prev);
          const existing = updated.get(peerId);
          if (existing) {
            existing.addTrack(event.track);
            console.log(`➕ Added ${event.track.kind} track to existing stream for ${peerId}`);
          } else {
            updated.set(peerId, newStream);
            console.log(`🆕 Created new stream entry for ${peerId}`);
          }
          remoteStreamsMapRef.current = updated;
          console.log(`📺 Updated remote streams map, now has ${updated.size} streams`);
          return updated;
        });
        return;
      }

      console.log(`✅ Remote stream received from peer ${peerId}:`, stream.id, 
                  `video tracks: ${stream.getVideoTracks().length}`, 
                  `audio tracks: ${stream.getAudioTracks().length}`);

      // Verify tracks are active
      stream.getVideoTracks().forEach((track, idx) => {
        console.log(`📹 Video track ${idx}:`, {
          id: track.id,
          label: track.label,
          enabled: track.enabled,
          muted: track.muted,
          readyState: track.readyState
        });
      });

      setRemoteStreamsMap(prev => {
        const updated = new Map(prev);
        updated.set(peerId, stream);
        remoteStreamsMapRef.current = updated;
        console.log(`📺 Updated remote streams map for peer ${peerId}:`, {
          totalStreams: updated.size,
          streamId: stream.id,
          videoTracks: stream.getVideoTracks().length,
          audioTracks: stream.getAudioTracks().length,
          allPeerIds: Array.from(updated.keys())
        });
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
      const iceState = pc.iceConnectionState;
      console.log(`🔗 Connection state changed for peer ${peerId}: ${state} (ICE: ${iceState})`);
      
      if (state === "connected") {
        console.log(`✅ WebRTC connection established with peer ${peerId}`);
      } else if (state === "failed") {
        console.warn(`⚠️ Connection failed for peer ${peerId} (ICE: ${iceState}), will attempt reconnection if peer sends new offer`);
        // Don't immediately cleanup - peer might send new offer for reconnection
        // Just log the failure and wait for potential reconnection
      } else if (state === "disconnected") {
        console.warn(`⚠️ Connection disconnected for peer ${peerId}, waiting for reconnection...`);
        // Don't cleanup on disconnect - connection might recover
      } else if (state === "closed") {
        console.warn(`❌ Connection closed for peer ${peerId}, cleaning up`);
        // Only cleanup when explicitly closed
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
    
    // Monitor ICE connection state separately for better debugging
    pc.oniceconnectionstatechange = () => {
      const iceState = pc.iceConnectionState;
      console.log(`🧊 ICE connection state for peer ${peerId}: ${iceState}`);
      
      if (iceState === "failed") {
        console.error(`❌ ICE connection failed for peer ${peerId} - network connectivity issue`);
        console.log(`💡 Suggestion: Check if both devices can reach each other. May need TURN server.`);
      } else if (iceState === "disconnected") {
        console.warn(`⚠️ ICE connection disconnected for peer ${peerId}`);
      } else if (iceState === "connected" || iceState === "completed") {
        console.log(`✅ ICE connection successful for peer ${peerId}`);
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
        let pc = peerConnectionsRef.current.get(from);
        
        // If no connection exists, create one
        if (!pc) {
          pc = createPeerConnection(from);
          if (!pc) {
            console.error(`❌ Failed to create peer connection for ${from}`);
            return;
          }
        }

        // ✅ Handle offer collision with rollback
        const isStable = pc.signalingState === 'stable';
        const isSettingRemoteOffer = pc.signalingState === 'have-local-offer';
        
        if (isSettingRemoteOffer) {
          // Offer collision detected - use polite peer pattern
          // Determine who should yield (use userId comparison for consistency)
          const shouldYield = userId < from;
          
          if (shouldYield) {
            console.log(`🔄 Offer collision with ${from} - rolling back our offer`);
            await pc.setLocalDescription({ type: 'rollback' });
          } else {
            console.log(`⏭️ Offer collision with ${from} - ignoring their offer (we're polite)`);
            return;
          }
        }

        if (!isStable && !isSettingRemoteOffer && pc.signalingState !== 'stable') {
          console.warn(`⚠️ Cannot accept offer from ${from} - current state: ${pc.signalingState}`);
          return;
        }

        await pc.setRemoteDescription({ type: "offer", sdp });
        console.log(`✅ Set remote description (offer) for peer ${from}`);

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
          // ✅ Check signaling state before setting remote answer
          if (pc.signalingState === 'have-local-offer') {
            await pc.setRemoteDescription({ type: "answer", sdp });
            console.log(`✅ Set remote description (answer) for peer ${from}`);
          } else {
            console.warn(`⚠️ Ignoring answer from ${from} - wrong state: ${pc.signalingState} (expected: have-local-offer)`);
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

        // ✅ CRITICAL: Verify local stream is ready before creating connection
        const local = localStreamRef.current || WebRTCService.localStream;
        if (!local || local.getTracks().length === 0) {
          console.warn(`⚠️ Local stream not ready yet, retrying connection to ${newPeerId} in 500ms...`);
          setTimeout(() => {
            handleSignalingMessage({ type: "new_participant", user_id: newPeerId });
          }, 500);
          return;
        }

        console.log(`🤝 Creating peer connection and sending offer to ${newPeerId}`);
        console.log(`📹 Local stream status:`, {
          id: local.id,
          videoTracks: local.getVideoTracks().length,
          audioTracks: local.getAudioTracks().length,
          allTracksActive: local.getTracks().every(t => t.readyState === 'live')
        });

        // create pc and start offer
        const pc = createPeerConnection(newPeerId);
        if (!pc) {
          console.error(`❌ Failed to create peer connection for ${newPeerId}`);
          return;
        }

        // Tracks are already added in createPeerConnection, but verify
        const senders = pc.getSenders();
        console.log(`📊 Peer connection senders for ${newPeerId}:`, senders.map(s => ({
          kind: s.track?.kind,
          trackId: s.track?.id,
          enabled: s.track?.enabled
        })));

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
