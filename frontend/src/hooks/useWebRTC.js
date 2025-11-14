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
    if (!peerId || peerId === userId) return null;

    if (peerConnectionsRef.current.has(peerId)) {
      return peerConnectionsRef.current.get(peerId);
    }

    const pc = new RTCPeerConnection(RTC_CONFIGURATION);

    // add local tracks (if already available)
    const local = localStreamRef.current || WebRTCService.localStream;
    if (local) {
      try {
        local.getTracks().forEach(track => pc.addTrack(track, local));
      } catch (err) {
        console.warn("Failed to add local tracks to pc:", err);
      }
    }

    // when remote track arrives, save it under peerId
    pc.ontrack = (event) => {
      const stream = event.streams && event.streams[0] ? event.streams[0] : null;
      if (!stream) return;

      setRemoteStreamsMap(prev => {
        const updated = new Map(prev);
        updated.set(peerId, stream);
        remoteStreamsMapRef.current = updated;
        return updated;
      });
    };

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        // send candidate to the specific peer via signaling server
        try {
          sendSignalingMessage({
            type: "ice_candidate",
            target_id: peerId,
            candidate: event.candidate,
            from_id: userId,
          });
        } catch (err) {
          console.warn("Failed to send ICE candidate:", err);
        }
      }
    };

    pc.onconnectionstatechange = () => {
      const state = pc.connectionState;
      if (state === "failed" || state === "disconnected" || state === "closed") {
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

    try {
      if (type === "webrtc_offer") {
        // incoming offer from another peer -> create PC, set remote desc, answer
        const from = from_id || data.from || user_id;
        if (!from) return;

        const pc = createPeerConnection(from);
        if (!pc) return;

        await pc.setRemoteDescription({ type: "offer", sdp });

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

        sendSignalingMessage({
          type: "webrtc_answer",
          target_id: from,
          sdp: answer.sdp,
          from_id: userId,
        });
      }

      if (type === "webrtc_answer") {
        const from = from_id || data.from || user_id;
        const pc = peerConnectionsRef.current.get(from);
        if (pc && sdp) {
          await pc.setRemoteDescription({ type: "answer", sdp });
        }
      }

      if (type === "ice_candidate" && candidate) {
        const from = from_id || data.from || user_id;
        const pc = peerConnectionsRef.current.get(from);
        if (pc) {
          try {
            // candidate might already be an RTCIceCandidateInit
            await pc.addIceCandidate(new RTCIceCandidate(candidate));
          } catch (err) {
            console.warn("addIceCandidate failed:", err);
          }
        }
      }

      if (type === "new_participant") {
        // server informs that a new participant is available (peerId)
        const newPeerId = data.user_id || data.userId;
        if (!newPeerId || newPeerId === userId) return;

        // create pc and start offer
        const pc = createPeerConnection(newPeerId);
        if (!pc) return;

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

        sendSignalingMessage({
          type: "webrtc_offer",
          target_id: newPeerId,
          sdp: offer.sdp,
          from_id: userId,
        });
      }
    } catch (err) {
      console.error("Signaling handler error:", err);
      setError(err?.message || String(err));
    }
  }, [createPeerConnection, sendSignalingMessage, userId]);

  const handleParticipantLeft = useCallback((peerId) => {
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
  };
};

export default useWebRTC;
