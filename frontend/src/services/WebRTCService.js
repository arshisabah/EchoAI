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
      ],
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

  toggleVideo(enabled) {
    if (!this.localStream) return;

    this.localStream.getVideoTracks().forEach(track => {
      track.enabled = enabled;
    });
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
