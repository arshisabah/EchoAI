// Enhanced WebRTCService.js (multi-peer safe)
// Handles local media, toggles, screen share, track replacement

class WebRTCService {
  constructor() {
    this.localStream = null;
    this.screenStream = null;
    this.peerConnections = new Map();  // Filled from useWebRTC

    this.configuration = {
      iceServers: [
        { urls: "stun:stun.l.google.com:19302" },
        { urls: "stun:stun1.l.google.com:19302" },
        // Add TURN servers for NAT traversal (free public TURN servers)
        {
          urls: "turn:openrelay.metered.ca:80",
          username: "openrelayproject",
          credential: "openrelayproject",
        },
        {
          urls: "turn:openrelay.metered.ca:443",
          username: "openrelayproject",
          credential: "openrelayproject",
        },
        {
          urls: "turn:openrelay.metered.ca:443?transport=tcp",
          username: "openrelayproject",
          credential: "openrelayproject",
        },
      ],
      iceCandidatePoolSize: 10,
    };
  }

  //-------------------------------------------------------
  //  START / STOP LOCAL STREAM
  //-------------------------------------------------------

  async startLocalStream(audioOnly = false) {
    try {
      const constraints = audioOnly
        ? { audio: true }
        : {
            video: {
              width: { ideal: 1280 },
              height: { ideal: 720 },
              frameRate: { ideal: 30 },
            },
            audio: true,
          };

      this.localStream = await navigator.mediaDevices.getUserMedia(constraints);
      return this.localStream;
    } catch (error) {
      console.error("❌ Local stream error:", error);
      throw error;
    }
  }

  stopLocalStream() {
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => track.stop());
      this.localStream = null;
    }
  }

  //-------------------------------------------------------
  //  AUDIO / VIDEO TOGGLES
  //-------------------------------------------------------

  toggleAudio(enabled) {
    if (!this.localStream) return;

    this.localStream.getAudioTracks().forEach(track => {
      track.enabled = enabled;
    });
  }

  async toggleVideo(enabled) {
    if (!this.localStream) return;

    const videoTracks = this.localStream.getVideoTracks();
    
    if (!enabled) {
      // Turning video OFF - just disable the tracks
      console.log('📹 Disabling video tracks');
      videoTracks.forEach(track => {
        track.enabled = false;
      });
      return;
    }
    
    // Turning video ON
    // Check if we have valid video tracks that can be enabled
    const hasValidTracks = videoTracks.some(track => 
      track.readyState === 'live' && !track.enabled
    );
    
    if (hasValidTracks) {
      // Just enable existing tracks
      console.log('📹 Re-enabling existing video tracks');
      videoTracks.forEach(track => {
        if (track.readyState === 'live') {
          track.enabled = true;
        }
      });
      return;
    }
    
    // Need to get new video track (tracks are stopped or don't exist)
    console.log('📹 Getting new video track - existing tracks are stopped or invalid');
    try {
      const newVideoStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          frameRate: { ideal: 30 }
        }
      });
      
      const newVideoTrack = newVideoStream.getVideoTracks()[0];
      
      // Remove old video tracks from local stream
      videoTracks.forEach(track => {
        this.localStream.removeTrack(track);
        track.stop();
      });
      
      // Add new video track to local stream
      this.localStream.addTrack(newVideoTrack);
      
      // Update all peer connections with new video track
      console.log(`🔄 Updating ${this.peerConnections.size} peer connections with new video track`);
      this.peerConnections.forEach((pc, peerId) => {
        const sender = pc.getSenders().find(s => s.track?.kind === 'video');
        if (sender) {
          sender.replaceTrack(newVideoTrack)
            .then(() => console.log(`✅ Replaced video track for peer ${peerId}`))
            .catch(err => console.error(`❌ Failed to replace video track for peer ${peerId}:`, err));
        } else {
          // No video sender exists, add the track
          pc.addTrack(newVideoTrack, this.localStream);
          console.log(`➕ Added new video track for peer ${peerId}`);
        }
      });
      
      console.log('✅ Video track successfully recreated and updated');
      return newVideoTrack;
      
    } catch (err) {
      console.error('❌ Failed to get new video track:', err);
      throw err;
    }
  }

  //-------------------------------------------------------
  //  SCREEN SHARING (Multi-peer safe)
  //-------------------------------------------------------

  async startScreenShare() {
    try {
      const screenStream = await navigator.mediaDevices.getDisplayMedia({
        video: { cursor: "always" },
        audio: false,
      });

      const screenTrack = screenStream.getVideoTracks()[0];
      this.screenStream = screenStream;

      // Replace video track for all connected peers
      this.peerConnections.forEach(pc => {
        const sender = pc.getSenders().find(s => s.track?.kind === "video");
        if (sender) {
          sender.replaceTrack(screenTrack);
        }
      });

      // When user stops sharing through browser UI
      screenTrack.onended = () => {
        this.stopScreenShare();
      };

      return screenStream;
    } catch (err) {
      console.error("❌ Screen share error:", err);
      throw err;
    }
  }

  stopScreenShare() {
    if (this.screenStream) {
      this.screenStream.getTracks().forEach(t => t.stop());
      this.screenStream = null;
    }

    // Restore camera feed
    if (this.localStream) {
      const cameraTrack = this.localStream.getVideoTracks()[0];

      this.peerConnections.forEach(pc => {
        const sender = pc.getSenders().find(s => s.track?.kind === "video");
        if (sender && cameraTrack) sender.replaceTrack(cameraTrack);
      });
    }
  }

  //-------------------------------------------------------
  //  CLOSE ALL CONNECTIONS
  //-------------------------------------------------------

  closeAllConnections() {
    this.peerConnections.forEach(pc => {
      try {
        pc.close();
      } catch {}
    });

    this.peerConnections.clear();
    this.stopLocalStream();
  }
}

export default new WebRTCService();
