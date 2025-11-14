// src/components/Meeting/VideoGrid.jsx
import React, { useEffect, useRef } from 'react';
import { Mic, MicOff, Video as VideoIcon, VideoOff, User } from 'lucide-react';

const VideoTile = ({ stream, username, isLocal, isMuted, isVideoOff, isActiveSpeaker }) => {
  const videoRef = useRef(null);

  useEffect(() => {
    if (videoRef.current && stream instanceof MediaStream) {
      if (videoRef.current.srcObject !== stream) {
        videoRef.current.srcObject = stream;
      }
    }
  }, [stream]);

  return (
    <div className={`video-tile ${isLocal ? 'local' : 'remote'} ${isActiveSpeaker ? 'active-speaker' : ''}`}>
      {stream && !isVideoOff ? (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted={isLocal}
          className="video-element"
        />
      ) : (
        <div className="video-placeholder">
          <div className="avatar-large">
            {username?.charAt(0)?.toUpperCase() || <User size={48} />}
          </div>
        </div>
      )}

      <div className="video-overlay">
        <span className="username">{isLocal ? "You" : username}</span>
        <div className="video-controls">
          {isMuted ? <MicOff size={16} className="icon-muted" /> : <Mic size={16} className="icon-active" />}
          {isVideoOff && <VideoOff size={16} className="icon-muted" />}
        </div>
      </div>
    </div>
  );
};

const VideoGrid = ({
  localStream,
  remoteStreams,       // MUST be a Map<peerId, MediaStream>
  participants = [],
  currentUserId,
  isLocalVideoEnabled,
  isLocalAudioEnabled,
  activeSpeakerId
}) => {

  const participantList = Array.isArray(participants) ? participants : [];

  const otherParticipants = participantList.filter(p => p.user_id !== currentUserId);

  const combinedParticipants = [
    {
      user_id: currentUserId,
      username: participantList.find(p => p.user_id === currentUserId)?.username || "You",
      stream: localStream,
      isLocal: true,
      isMuted: !isLocalAudioEnabled,
      isVideoOff: !isLocalVideoEnabled
    },
    ...otherParticipants.map(p => ({
      user_id: p.user_id,
      username: p.username,
      stream: remoteStreams.get(p.user_id) || null,  // ✅ ALWAYS FROM MAP
      isLocal: false,
      isMuted: !p.is_audio_on,
      isVideoOff: !p.is_video_on
    }))
  ];

  return (
    <div className={`video-grid grid-${Math.min(combinedParticipants.length, 4)}`}>
      {combinedParticipants.map(p => (
        <VideoTile
          key={p.user_id}
          stream={p.stream}
          username={p.username}
          isLocal={p.isLocal}
          isMuted={p.isMuted}
          isVideoOff={p.isVideoOff}
          isActiveSpeaker={activeSpeakerId === p.user_id}
        />
      ))}
    </div>
  );
};

export default VideoGrid;
