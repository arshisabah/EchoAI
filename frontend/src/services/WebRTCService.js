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
  //screen sharing logic but not implemented
  
  // async startScreenShare() {
  //   try {
  //     // Capture screen stream
  //     const screenStream = await navigator.mediaDevices.getDisplayMedia({
  //       video: { cursor: "always" },
  //       audio: false, // most browsers block screen audio unless explicitly allowed
  //     });

  //     // Replace video track in all peer connections (so everyone sees your screen)
  //     const screenTrack = screenStream.getVideoTracks()[0];
  //     this.peerConnections.forEach((pc) => {
  //       const sender = pc.getSenders().find(s => s.track && s.track.kind === 'video');
  //       if (sender) {
  //         sender.replaceTrack(screenTrack);
  //       }
  //     });

  //     // When user stops sharing
  //     screenTrack.onended = () => {
  //       console.log('🛑 Screen sharing stopped');
  //       this.stopScreenShare();
  //     };

  //     this.screenStream = screenStream;
  //     console.log('🖥️ Screen sharing started');
  //     return screenStream;
  //   } catch (err) {
  //     console.error('❌ Error starting screen share:', err);
  //     throw err;
  //   }
  // }

  // stopScreenShare() {
  //   if (this.screenStream) {
  //     this.screenStream.getTracks().forEach(track => track.stop());
  //     this.screenStream = null;
  //     console.log('🛑 Screen share stream closed');
  //   }

  //   // Revert back to webcam stream
  //   if (this.localStream) {
  //     const cameraTrack = this.localStream.getVideoTracks()[0];
  //     this.peerConnections.forEach((pc) => {
  //       const sender = pc.getSenders().find(s => s.track && s.track.kind === 'video');
  //       if (sender && cameraTrack) {
  //         sender.replaceTrack(cameraTrack);
  //       }
  //     });
  //     console.log('🎥 Restored camera feed after screen share');
  //   }
  // }

  closeAllConnections() {
    this.peerConnections.forEach((pc) => pc.close());
    this.peerConnections.clear();
    this.stopLocalStream();
  }
}

export default new WebRTCService();