import { useState, useEffect, useCallback, useRef } from "react";
import WebRTCService from "../services/WebRTCService";

const RTC_CONFIGURATION = WebRTCService.configuration;

export const useWebRTC = (roomId, userId, sendSignalingMessage) => {
  const [localStream, setLocalStream] = useState(null);
  const [remoteStreams, setRemoteStreams] = useState(new Map());
  const [isVideoEnabled, setIsVideoEnabled] = useState(true);
  const [isAudioEnabled, setIsAudioEnabled] = useState(true);
  const [error, setError] = useState(null);

  const peerConnectionsRef = useRef(new Map());

  const startLocalMedia = useCallback(async (audioOnly = false) => {
    try {
      const stream = await WebRTCService.startLocalStream(audioOnly);
      setLocalStream(stream);

      setIsAudioEnabled(stream.getAudioTracks().some(t => t.enabled));
      setIsVideoEnabled(stream.getVideoTracks().some(t => t.enabled));

      return stream;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, []);

  const stopLocalMedia = useCallback(() => {
    WebRTCService.stopLocalStream();
    setLocalStream(null);
  }, []);

  const toggleVideo = useCallback(() => {
    const newState = !isVideoEnabled;
    WebRTCService.toggleVideo(newState);
    setIsVideoEnabled(newState);
  }, [isVideoEnabled]);

  const toggleAudio = useCallback(() => {
    const newState = !isAudioEnabled;
    WebRTCService.toggleAudio(newState);
    setIsAudioEnabled(newState);
  }, [isAudioEnabled]);

  const createPeerConnection = useCallback(
    (peerId) => {
      if (peerConnectionsRef.current.has(peerId)) {
        return peerConnectionsRef.current.get(peerId);
      }

      const pc = new RTCPeerConnection(RTC_CONFIGURATION);

      if (WebRTCService.localStream) {
        WebRTCService.localStream.getTracks().forEach(track => {
          pc.addTrack(track, WebRTCService.localStream);
        });
      }

      pc.ontrack = (event) => {
        setRemoteStreams(prev => {
          const updated = new Map(prev);
          updated.set(peerId, event.streams[0]);
          return updated;
        });
      };

      pc.onicecandidate = (event) => {
        if (event.candidate) {
          sendSignalingMessage({
            type: "ice_candidate",
            target_id: peerId,
            candidate: event.candidate,
            from_id: userId,
          });
        }
      };

      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "failed" || pc.connectionState === "disconnected") {
          setRemoteStreams(prev => {
            const updated = new Map(prev);
            updated.delete(peerId);
            return updated;
          });
        }
      };

      peerConnectionsRef.current.set(peerId, pc);
      WebRTCService.peerConnections.set(peerId, pc);

      return pc;
    },
    [sendSignalingMessage, userId]
  );

  const handleSignalingMessage = useCallback(
    async (data) => {
      const { type, sdp, candidate, from_id } = data;

      try {
        if (type === "webrtc_offer") {
          const pc = createPeerConnection(from_id);
          await pc.setRemoteDescription({ type: "offer", sdp });

          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);

          sendSignalingMessage({
            type: "webrtc_answer",
            target_id: from_id,
            sdp: answer.sdp,
            from_id: userId,
          });
        }

        if (type === "webrtc_answer") {
          const pc = peerConnectionsRef.current.get(from_id);
          if (pc) {
            await pc.setRemoteDescription({ type: "answer", sdp });
          }
        }

        if (type === "ice_candidate" && candidate) {
          const pc = peerConnectionsRef.current.get(from_id);
          if (pc) {
            await pc.addIceCandidate(candidate);
          }
        }

        if (type === "new_participant") {
          const pc = createPeerConnection(data.user_id);
          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);

          sendSignalingMessage({
            type: "webrtc_offer",
            target_id: data.user_id,
            sdp: offer.sdp,
            from_id: userId,
          });
        }
      } catch (err) {
        setError(err.message);
      }
    },
    [createPeerConnection, sendSignalingMessage, userId]
  );

  const handleParticipantLeft = useCallback((peerId) => {
    const pc = peerConnectionsRef.current.get(peerId);
    if (pc) {
      pc.close();
      peerConnectionsRef.current.delete(peerId);
    }

    setRemoteStreams(prev => {
      const updated = new Map(prev);
      updated.delete(peerId);
      return updated;
    });
  }, []);

  useEffect(() => {
    return () => {
      WebRTCService.closeAllConnections();
      peerConnectionsRef.current.clear();
      setRemoteStreams(new Map());
    };
  }, []);

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
    handleSignalingMessage,
    handleParticipantLeft,
  };
};
