// src/components/Meeting/VideoGrid.jsx
import React, { useEffect, useRef } from 'react';
import { Mic, MicOff, Video as VideoIcon, VideoOff, User } from 'lucide-react';

const VideoTile = ({ stream, username, isLocal, isMuted, isVideoOff, isActiveSpeaker }) => {
  const videoRef = useRef(null);

  useEffect(() => {
    console.log(`🔄 Video effect TRIGGERED for ${username}:`, {
      hasStream: !!stream,
      streamType: stream?.constructor?.name,
      isLocal,
      isMuted
    });
    
    const video = videoRef.current;
    if (!video) {
      console.warn(`⚠️ Video ref not ready for ${username}`);
      return;
    }

    if (stream instanceof MediaStream) {
      const videoTracks = stream.getVideoTracks();
      const audioTracks = stream.getAudioTracks();
      const trackIds = videoTracks.map(t => t.id).join(',');
      
      console.log(`📺 Video effect triggered for ${username}:`, {
        streamId: stream.id,
        videoTracks: videoTracks.length,
        trackIds: trackIds.substring(0, 30),
        audioTracks: audioTracks.length,
        videoTrackStates: videoTracks.map(t => ({
          id: t.id.substring(0, 8),
          enabled: t.enabled,
          readyState: t.readyState,
          muted: t.muted
        })),
        audioTrackStates: audioTracks.map(t => ({
          id: t.id.substring(0, 8),
          enabled: t.enabled,
          readyState: t.readyState,
          muted: t.muted
        }))
      });
      
      // Always set srcObject to ensure tracks are picked up
      console.log(`🔄 Setting/updating srcObject for ${username}`);
      video.srcObject = stream;
      
      // Ensure video properties are set correctly
      video.autoplay = true;
      video.playsInline = true;
      
      // CRITICAL FIX: Only mute local video, NOT remote video
      // Remote video muted=false allows us to see their video
      if (isLocal) {
        video.muted = true; // Local video must be muted to prevent echo
      } else {
        video.muted = false; // Remote video NOT muted - we want to see/hear them
        video.volume = 1.0; // Ensure volume is at max for remote participants
      }
      
      // Force play with retry logic and timeout
      const attemptPlay = async (retries = 5) => {
        for (let i = 0; i < retries; i++) {
          try {
            // Wait a bit before attempting to ensure element is in DOM
            if (i > 0) {
              await new Promise(resolve => setTimeout(resolve, 100 * i));
            }
            
            // Check if video element still exists and is in the DOM
            if (!document.contains(video)) {
              console.warn(`⚠️ Video element for ${username} not in DOM, skipping play attempt`);
              return;
            }
            
            // Load metadata first
            video.load();
            
            await video.play();
            console.log(`✅ Video playing for ${username}`, {
              paused: video.paused,
              currentTime: video.currentTime,
              readyState: video.readyState,
              networkState: video.networkState
            });
            return;
          } catch (err) {
            console.warn(`⚠️ Video play attempt ${i + 1}/${retries} failed for ${username}:`, err.message);
          }
        }
        console.error(`❌ All ${retries} play attempts failed for ${username}`);
      };
      
      // Use setTimeout to ensure render cycle completes
      setTimeout(() => attemptPlay(), 50);
      
    } else if (!stream) {
      console.warn(`⚠️ No stream available for ${username}`);
      if (video.srcObject) {
        video.srcObject = null;
      }
    } else {
      console.error(`❌ Invalid stream type for ${username}:`, typeof stream);
    }
  }, [stream, username, isLocal, isMuted]);

  // Monitor stream track changes
  useEffect(() => {
    if (!stream || !(stream instanceof MediaStream)) return;

    const handleTrackEvent = (event) => {
      console.log(`🎵 Track ${event.type} for ${username}:`, event.track.kind, event.track.id);
      
      // Force video element update when tracks change
      if (videoRef.current && event.track.kind === 'video') {
        if (event.type === 'addtrack') {
          console.log(`✅ New video track added for ${username}, refreshing video element`);
          // Set srcObject again to pick up new track
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(err => {
            console.warn(`⚠️ Failed to play video after track added:`, err);
          });
        }
      }
    };

    stream.addEventListener('addtrack', handleTrackEvent);
    stream.addEventListener('removetrack', handleTrackEvent);

    return () => {
      stream.removeEventListener('addtrack', handleTrackEvent);
      stream.removeEventListener('removetrack', handleTrackEvent);
    };
  }, [stream, username]);
  
  // Monitor video track enabled state changes
  useEffect(() => {
    if (!stream || !(stream instanceof MediaStream)) return;
    
    const videoTracks = stream.getVideoTracks();
    if (videoTracks.length === 0) return;
    
    // Check if tracks are enabled/disabled periodically
    const checkInterval = setInterval(() => {
      const currentStates = videoTracks.map(t => ({ id: t.id, enabled: t.enabled, readyState: t.readyState }));
      console.log(`🔍 Checking video tracks for ${username}:`, currentStates);
    }, 2000);
    
    return () => clearInterval(checkInterval);
  }, [stream, username]);

  // Check if stream has video tracks (regardless of enabled state)
  const hasVideoTrack = stream && stream.getVideoTracks().length > 0;
  
  // Check if video track is actually enabled and live
  const hasEnabledVideo = stream && stream.getVideoTracks().some(track => 
    track.readyState === 'live' && track.enabled
  );
  
  // For debugging
  if (stream && hasVideoTrack && !hasEnabledVideo) {
    const videoTracks = stream.getVideoTracks();
    console.log(`📹 Video tracks disabled for ${username}:`, videoTracks.map(t => ({
      kind: t.kind,
      enabled: t.enabled,
      readyState: t.readyState,
      muted: t.muted
    })));
  }

  return (
    <div className={`video-tile ${isLocal ? 'local' : 'remote'} ${isActiveSpeaker ? 'active-speaker' : ''}`}>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted={isLocal}
        className="video-element"
        style={{ 
          display: 'block',
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          backgroundColor: '#1a1a2e'
        }}
      />
      
      {!stream && (
        <div className="video-placeholder">
          <div className="avatar-large">
            {username?.charAt(0)?.toUpperCase() || <User size={48} />}
          </div>
        </div>
      )}
      
      {/* Show placeholder when video track is disabled */}
      {stream && hasVideoTrack && !hasEnabledVideo && (
        <div className="video-placeholder">
          <div className="avatar-large">
            {username?.charAt(0)?.toUpperCase() || <VideoOff size={48} />}
          </div>
        </div>
      )}

      <div className="video-overlay">
        <span className="username">{isLocal ? "You" : username}</span>
        <div className="video-controls">
          {isMuted ? <MicOff size={16} className="icon-muted" /> : <Mic size={16} className="icon-active" />}
          {!hasEnabledVideo && <VideoOff size={16} className="icon-muted" />}
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
  
  console.log(`🎬 VideoGrid Debug:`, {
    totalParticipants: participantList.length,
    otherParticipants: otherParticipants.length,
    remoteStreamsSize: remoteStreams.size,
    remoteStreamKeys: Array.from(remoteStreams.keys()),
    participantIds: otherParticipants.map(p => p.user_id)
  });

  const combinedParticipants = [
    {
      user_id: currentUserId,
      username: participantList.find(p => p.user_id === currentUserId)?.username || "You",
      stream: localStream,
      isLocal: true,
      isMuted: !isLocalAudioEnabled,
      isVideoOff: !isLocalVideoEnabled
    },
    ...otherParticipants.map(p => {
      const remoteStream = remoteStreams.get(p.user_id);
      
      console.log(`🔍 Mapping participant ${p.username} (${p.user_id}):`, {
        hasStream: !!remoteStream,
        streamId: remoteStream?.id,
        videoTracks: remoteStream?.getVideoTracks().length,
        audioTracks: remoteStream?.getAudioTracks().length
      });
      
      // Validate stream has tracks (even if disabled)
      // A track can be live but disabled (camera off), we still want to show the stream
      const hasValidTracks = remoteStream && 
        remoteStream.getTracks().length > 0 &&
        remoteStream.getTracks().some(track => track.readyState === 'live' || track.readyState === 'ended');
      
      if (!remoteStream) {
        console.warn(`⚠️ No remote stream found for participant ${p.username} (${p.user_id})`);
      } else if (!hasValidTracks) {
        console.warn(`⚠️ Remote stream for ${p.username} has no tracks`);
      } else {
        console.log(`✅ Remote stream for ${p.username}:`, {
          streamId: remoteStream.id,
          tracks: remoteStream.getTracks().map(t => `${t.kind}:${t.enabled ? 'enabled' : 'disabled'}:${t.readyState}`)
        });
      }
      
      // Always pass the stream if it exists and has tracks (regardless of enabled state)
      return {
        user_id: p.user_id,
        username: p.username,
        stream: remoteStream && remoteStream.getTracks().length > 0 ? remoteStream : null,
        isLocal: false,
        isMuted: !p.is_audio_on,
        isVideoOff: !p.is_video_on
      };
    })
  ];

  console.log(`📊 VideoGrid rendering ${combinedParticipants.length} participants, remote streams: ${remoteStreams.size}`);

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
