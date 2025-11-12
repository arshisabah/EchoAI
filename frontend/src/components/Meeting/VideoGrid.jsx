import React, { useEffect, useRef } from 'react';
import { Mic, MicOff, Video as VideoIcon, VideoOff, User } from 'lucide-react';


const VideoTile = ({ stream, username, userId, isLocal, isMuted, isVideoOff, isActiveSpeaker }) => {
  const videoRef = useRef(null);

  useEffect(() => {
    if (videoRef.current && stream && stream instanceof MediaStream) {
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
            {username ? username.charAt(0).toUpperCase() : <User size={48} />}
          </div>
        </div>
      )}

      <div className="video-overlay">
        <span className="username">{isLocal ? 'You' : username}</span>
        <div className="video-controls">
          {isMuted ? (
            <MicOff size={16} className="icon-muted" />
          ) : (
            <Mic size={16} className="icon-active" />
          )}
          {isVideoOff && <VideoOff size={16} className="icon-muted" />}
        </div>
      </div>
    </div>
  );
};

const VideoGrid = ({
  localStream,
  remoteStreams,
  participants,
  currentUserId,
  isLocalVideoEnabled,
  isLocalAudioEnabled,
  activeSpeakerId
}) => {
  // Filter out current user from participants to avoid duplication
  const remoteParticipants = participants.filter(p => p.user_id !== currentUserId);
  
  // Combine local + remote participants
  const combinedParticipants = [
    {
      user_id: currentUserId,
      username: participants.find(p => p.user_id === currentUserId)?.username || 'You',
      stream: localStream,
      isLocal: true,
      isMuted: !isLocalAudioEnabled,
      isVideoOff: !isLocalVideoEnabled,
    },
    ...remoteParticipants.map((p) => ({
      ...p,
      isLocal: false,
      stream: remoteStreams.get(p.user_id),
      isVideoOff: !p.is_video_on,
      isMuted: !p.is_audio_on,
    })),
  ];

  const participantCount = combinedParticipants.length;
  const gridClass = `video-grid grid-${Math.min(participantCount, 4)}`;

  return (
    <div className={gridClass}>
      {combinedParticipants.map((p) => (
        <VideoTile
          key={p.user_id}
          stream={p.stream}
          username={p.username}
          userId={p.user_id}
          isLocal={p.isLocal}
          isMuted={p.isMuted}
          isVideoOff={p.isVideoOff}
          isActiveSpeaker={activeSpeakerId === p.user_id}
        />
      ))}


      {/* Placeholder tiles for empty slots */}
      {participantCount < 4 && [...Array(4 - participantCount)].map((_, i) => (
        <div key={`empty-${i}`} className="video-tile empty">
          <div className="video-placeholder">
            <User size={32} className="placeholder-icon" />
            <span>Waiting for participants...</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default VideoGrid;