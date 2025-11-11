// Simplified WebRTC service
// Most logic is now in useWebRTC hook for better React integration

class WebRTCService {
  constructor() {
    this.localStream = null;
    this.peerConnections = new Map();
    
    this.configuration = {
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
      ],
    };
  }

  async startLocalStream(audioOnly = false) {
    try {
      const constraints = audioOnly
        ? { audio: true }
        : {
            video: { width: 1280, height: 720 },
            audio: true,
          };

      this.localStream = await navigator.mediaDevices.getUserMedia(constraints);
      return this.localStream;
    } catch (error) {
      console.error('Error accessing media devices:', error);
      throw error;
    }
  }

  stopLocalStream() {
    if (this.localStream) {
      this.localStream.getTracks().forEach((track) => track.stop());
      this.localStream = null;
    }
  }

  toggleAudio(enabled) {
    if (this.localStream) {
      this.localStream.getAudioTracks().forEach((track) => {
        track.enabled = enabled;
      });
    }
  }

  toggleVideo(enabled) {
    if (this.localStream) {
      this.localStream.getVideoTracks().forEach((track) => {
        track.enabled = enabled;
      });
    }
  }

  closeAllConnections() {
    this.peerConnections.forEach((pc) => pc.close());
    this.peerConnections.clear();
    this.stopLocalStream();
  }
}

export default new WebRTCService();