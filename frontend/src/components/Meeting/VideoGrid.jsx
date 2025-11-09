import React, { useEffect, useRef } from 'react';
import { Mic, MicOff, Video as VideoIcon, VideoOff, User } from 'lucide-react';

const VideoTile = ({ stream, username, userId, isLocal, isMuted, isVideoOff }) => {
  const videoRef = useRef(null);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  return (
    <div className={`video-tile ${isLocal ? 'local' : 'remote'}`}>
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
  isLocalAudioEnabled 
}) => {
  const participantCount = participants.length;
  const gridClass = `video-grid grid-${Math.min(participantCount, 4)}`;

  return (
    <div className={gridClass}>
      {/* Local Video */}
      <VideoTile
        stream={localStream}
        username="You"
        userId={currentUserId}
        isLocal={true}
        isMuted={!isLocalAudioEnabled}
        isVideoOff={!isLocalVideoEnabled}
      />

      {/* Remote Videos */}
      {Array.from(remoteStreams.entries()).map(([userId, stream]) => {
        const participant = participants.find(p => p.user_id === userId);
        return (
          <VideoTile
            key={userId}
            stream={stream}
            username={participant?.username || 'Guest'}
            userId={userId}
            isLocal={false}
            isMuted={participant?.is_muted}
            isVideoOff={false}
          />
        );
      })}

      {/* Placeholder tiles for empty slots */}
      {participants.length < 4 && [...Array(4 - participantCount)].map((_, i) => (
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