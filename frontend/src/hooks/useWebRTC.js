import { useState, useEffect, useCallback, useRef } from 'react';
import WebRTCService from '../services/WebRTCService'; // ✅ centralized media service

const RTC_CONFIGURATION = WebRTCService.configuration;

export const useWebRTC = (roomId, userId, sendSignalingMessage) => {
  const [localStream, setLocalStream] = useState(null);
  const [remoteStreams, setRemoteStreams] = useState(new Map());
  const [isVideoEnabled, setIsVideoEnabled] = useState(true);
  const [isAudioEnabled, setIsAudioEnabled] = useState(true);
  const [error, setError] = useState(null);

  const peerConnectionsRef = useRef(new Map());

  // ✅ Start local camera + mic using the WebRTCService
  const startLocalMedia = useCallback(async (audioOnly = false) => {
    try {
      const stream = await WebRTCService.startLocalStream(audioOnly);
      setLocalStream(stream);
      setIsAudioEnabled(stream.getAudioTracks().some(t => t.enabled));
      setIsVideoEnabled(stream.getVideoTracks().some(t => t.enabled));
      console.log('🎥 Local media started via WebRTCService');
      return stream;
    } catch (err) {
      console.error('❌ Failed to start local media:', err);
      setError(err.message);
      throw err;
    }
  }, []);

  // ✅ Stop media via WebRTCService
  const stopLocalMedia = useCallback(() => {
    WebRTCService.stopLocalStream();
    setLocalStream(null);
    console.log('🛑 Local media stopped');
  }, []);

  // ✅ Toggle video
  const toggleVideo = useCallback(() => {
    const newState = !isVideoEnabled;
    WebRTCService.toggleVideo(newState);
    setIsVideoEnabled(newState);
    console.log('📹 Video toggled:', newState ? 'ON' : 'OFF');
  }, [isVideoEnabled]);

  // ✅ Toggle audio
  const toggleAudio = useCallback(() => {
    const newState = !isAudioEnabled;
    WebRTCService.toggleAudio(newState);
    setIsAudioEnabled(newState);
    console.log('🎤 Audio toggled:', newState ? 'ON' : 'OFF');
  }, [isAudioEnabled]);

  // ✅ Create new PeerConnection for a user
  const createPeerConnection = useCallback(
    (peerId) => {
      if (peerConnectionsRef.current.has(peerId)) {
        return peerConnectionsRef.current.get(peerId);
      }

      console.log('🔗 Creating peer connection for:', peerId);
      const pc = new RTCPeerConnection(RTC_CONFIGURATION);

      // Add local tracks
      if (WebRTCService.localStream) {
        WebRTCService.localStream.getTracks().forEach((track) => {
          pc.addTrack(track, WebRTCService.localStream);
        });
      }

      // Handle remote stream
      pc.ontrack = (event) => {
        console.log('📥 Remote stream from:', peerId);
        setRemoteStreams((prev) => {
          const updated = new Map(prev);
          updated.set(peerId, event.streams[0]);
          return updated;
        });
      };

      // ICE candidate handling (send to backend)
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          sendSignalingMessage({
            type: 'ice_candidate',
            target_id: peerId,
            candidate: event.candidate,
            from_id: userId,
          });
        }
      };

      // Handle disconnects
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
          console.log(`❌ Peer ${peerId} disconnected`);
          setRemoteStreams((prev) => {
            const updated = new Map(prev);
            updated.delete(peerId);
            return updated;
          });
        }
      };

      peerConnectionsRef.current.set(peerId, pc);
      WebRTCService.peerConnections.set(peerId, pc); // keep global state synced
      return pc;
    },
    [sendSignalingMessage, userId]
  );

  // ✅ Handle signaling messages received from the WebSocket
  const handleSignalingMessage = useCallback(
    async (data) => {
      try {
        const { type, sdp, candidate, from_id } = data;

        switch (type) {
          case 'webrtc_offer': {
            console.log('📨 Received offer from', from_id);
            const pc = createPeerConnection(from_id);
            await pc.setRemoteDescription(new RTCSessionDescription({ type: 'offer', sdp }));
            const answer = await pc.createAnswer();
            await pc.setLocalDescription(answer);

            sendSignalingMessage({
              type: 'webrtc_answer',
              target_id: from_id,
              sdp: answer.sdp,
              from_id: userId,
            });
            break;
          }

          case 'webrtc_answer': {
            console.log('📨 Received answer from', from_id);
            const pc = peerConnectionsRef.current.get(from_id);
            if (pc) {
              await pc.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp }));
            }
            break;
          }

          case 'ice_candidate': {
            const pc = peerConnectionsRef.current.get(from_id);
            if (pc && candidate) {
              await pc.addIceCandidate(new RTCIceCandidate(candidate));
              console.log('🧊 Added ICE candidate from', from_id);
            }
            break;
          }

          case 'new_participant': {
            console.log('👋 New participant joined:', data.user_id);
            const pc = createPeerConnection(data.user_id);
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);

            sendSignalingMessage({
              type: 'webrtc_offer',
              target_id: data.user_id,
              sdp: offer.sdp,
              from_id: userId,
            });
            break;
          }

          case 'participant_left': {
            console.log('👋 Participant left, cleaning up connection:', data.user_id);
            const pc = peerConnectionsRef.current.get(data.user_id);
            if (pc) {
              pc.close();
              peerConnectionsRef.current.delete(data.user_id);
              WebRTCService.peerConnections.delete(data.user_id);
            }
            setRemoteStreams((prev) => {
              const updated = new Map(prev);
              updated.delete(data.user_id);
              return updated;
            });
            break;
          }

          default:
            break;
        }
      } catch (err) {
        console.error('❌ Error handling signaling message:', err, data);
        setError(err.message);
      }
    },
    [createPeerConnection, sendSignalingMessage, userId]
  );
  const startScreenShare = useCallback(async () => {
    try {
      const stream = await WebRTCService.startScreenShare();
      setLocalStream(stream); // show it in your local preview
    } catch (err) {
      console.error("❌ Failed to start screen share:", err);
    }
  }, []);

  const stopScreenShare = useCallback(() => {
    WebRTCService.stopScreenShare();
    setLocalStream(WebRTCService.localStream); // revert to camera
  }, []);

  // ✅ Cleanup all connections & streams
  useEffect(() => {
    return () => {
      WebRTCService.closeAllConnections();
      peerConnectionsRef.current.clear();
      setRemoteStreams(new Map());
      console.log('🧹 Cleaned up WebRTC connections');
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
    startScreenShare, 
  stopScreenShare, 
  };
};
