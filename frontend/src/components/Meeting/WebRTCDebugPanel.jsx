// WebRTC Debug Panel - Helps diagnose video connection issues
import React, { useState, useEffect } from 'react';

const WebRTCDebugPanel = ({ localStream, remoteStreamsMap, participants, isVisible }) => {
  const [stats, setStats] = useState({});

  useEffect(() => {
    if (!isVisible) return;

    const interval = setInterval(() => {
      const newStats = {
        localStream: localStream ? {
          id: localStream.id,
          videoTracks: localStream.getVideoTracks().map(t => ({
            id: t.id,
            label: t.label,
            enabled: t.enabled,
            readyState: t.readyState,
            muted: t.muted
          })),
          audioTracks: localStream.getAudioTracks().map(t => ({
            id: t.id,
            label: t.label,
            enabled: t.enabled,
            readyState: t.readyState,
            muted: t.muted
          }))
        } : 'No local stream',
        remoteStreams: Array.from(remoteStreamsMap.entries()).map(([peerId, stream]) => ({
          peerId,
          streamId: stream.id,
          videoTracks: stream.getVideoTracks().length,
          audioTracks: stream.getAudioTracks().length,
          videoActive: stream.getVideoTracks()[0]?.readyState === 'live',
          audioActive: stream.getAudioTracks()[0]?.readyState === 'live'
        })),
        participants: participants.map(p => ({
          user_id: p.user_id,
          username: p.username,
          hasRemoteStream: remoteStreamsMap.has(p.user_id)
        }))
      };
      setStats(newStats);
    }, 1000);

    return () => clearInterval(interval);
  }, [isVisible, localStream, remoteStreamsMap, participants]);

  if (!isVisible) return null;

  return (
    <div style={{
      position: 'fixed',
      bottom: '80px',
      right: '20px',
      background: 'rgba(0, 0, 0, 0.9)',
      color: '#0f0',
      padding: '15px',
      borderRadius: '8px',
      fontSize: '11px',
      fontFamily: 'monospace',
      maxWidth: '400px',
      maxHeight: '400px',
      overflow: 'auto',
      zIndex: 9999,
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.3)'
    }}>
      <h3 style={{ margin: '0 0 10px 0', color: '#fff' }}>WebRTC Debug Info</h3>
      
      <div style={{ marginBottom: '10px' }}>
        <strong style={{ color: '#ff0' }}>Local Stream:</strong>
        <pre style={{ margin: '5px 0', color: '#0f0' }}>
          {JSON.stringify(stats.localStream, null, 2)}
        </pre>
      </div>

      <div style={{ marginBottom: '10px' }}>
        <strong style={{ color: '#ff0' }}>Remote Streams ({stats.remoteStreams?.length || 0}):</strong>
        <pre style={{ margin: '5px 0', color: '#0ff' }}>
          {JSON.stringify(stats.remoteStreams, null, 2)}
        </pre>
      </div>

      <div>
        <strong style={{ color: '#ff0' }}>Participants ({stats.participants?.length || 0}):</strong>
        <pre style={{ margin: '5px 0', color: '#f0f' }}>
          {JSON.stringify(stats.participants, null, 2)}
        </pre>
      </div>
    </div>
  );
};

export default WebRTCDebugPanel;
