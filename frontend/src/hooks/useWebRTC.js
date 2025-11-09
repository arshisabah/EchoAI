import { useState, useEffect, useCallback } from 'react';
import webrtcService from '../services/webrtc';

export const useWebRTC = (roomId, userId) => {
  const [localStream, setLocalStream] = useState(null);
  const [remoteStreams, setRemoteStreams] = useState(new Map());
  const [isVideoEnabled, setIsVideoEnabled] = useState(true);
  const [isAudioEnabled, setIsAudioEnabled] = useState(true);
  const [error, setError] = useState(null);

  const startLocalMedia = useCallback(async (videoEnabled = true) => {
    try {
      setError(null);
      const stream = await webrtcService.startLocalStream(!videoEnabled);
      setLocalStream(stream);
      setIsVideoEnabled(videoEnabled);
      setIsAudioEnabled(true);
      return stream;
    } catch (err) {
      console.error('Error starting local media:', err);
      setError('Failed to access camera/microphone');
      throw err;
    }
  }, []);

  const stopLocalMedia = useCallback(() => {
    webrtcService.stopLocalStream();
    setLocalStream(null);
  }, []);

  const toggleVideo = useCallback(() => {
    const newState = !isVideoEnabled;
    webrtcService.toggleVideo(newState);
    setIsVideoEnabled(newState);
  }, [isVideoEnabled]);

  const toggleAudio = useCallback(() => {
    const newState = !isAudioEnabled;
    webrtcService.toggleAudio(newState);
    setIsAudioEnabled(newState);
  }, [isAudioEnabled]);

  useEffect(() => {
    webrtcService.onRemoteStream = (userId, stream) => {
      setRemoteStreams((prev) => new Map(prev).set(userId, stream));
    };

    webrtcService.onRemoveStream = (userId) => {
      setRemoteStreams((prev) => {
        const next = new Map(prev);
        next.delete(userId);
        return next;
      });
    };

    return () => {
      webrtcService.closeAllConnections();
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
  };
};