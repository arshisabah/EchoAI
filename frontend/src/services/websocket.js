import config from '../config';

class WebSocketService {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 3000;
    this.listeners = {};
  }

  connect(roomId, userId, username) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return this.ws;
    }

    const wsUrl = `${config.WS_URL}/meeting/rooms/${roomId}/ws?user_id=${userId}&username=${encodeURIComponent(username)}`;
    
    if (config.DEBUG) {
      console.log('🔌 Connecting to WebSocket:', wsUrl);
    }

    try {
      this.ws = new WebSocket(wsUrl);
      this.setupEventHandlers();
      return this.ws;
    } catch (error) {
      console.error('❌ WebSocket connection failed:', error);
      this.attemptReconnect(roomId, userId, username);
    }
  }

  setupEventHandlers() {
    this.ws.onopen = () => {
      console.log('✅ WebSocket Connected');
      this.reconnectAttempts = 0;
      this.emit('connected');
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (config.DEBUG) {
          console.log('📩 WebSocket Message:', data);
        }
        this.emit('message', data);
        
        // Emit specific event types
        if (data.type) {
          this.emit(data.type, data);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('❌ WebSocket Error:', error);
      this.emit('error', error);
    };

    this.ws.onclose = (event) => {
      console.log('🔌 WebSocket Disconnected:', event.code, event.reason);
      this.emit('disconnected', event);
      
      if (!event.wasClean) {
        this.attemptReconnect();
      }
    };
  }

  attemptReconnect(roomId, userId, username) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Reconnecting... Attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
      
      setTimeout(() => {
        this.connect(roomId, userId, username);
      }, this.reconnectDelay);
    } else {
      console.error('Max reconnection attempts reached');
      this.emit('reconnect_failed');
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      if (config.DEBUG) {
        console.log('📤 Sent:', data);
      }
    } else {
      console.error('WebSocket is not connected');
    }
  }

  sendAudio(audioData, sampleRate = 16000) {
    this.send({
      type: 'audio_chunk',
      audio_data: audioData,
      sample_rate: sampleRate,
    });
  }

  disconnect() {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  // Event emitter pattern
  on(event, callback) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  }

  off(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    }
  }

  emit(event, data) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(callback => callback(data));
    }
  }
}

// Export singleton instance
export const wsService = new WebSocketService();
export default wsService;