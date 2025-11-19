import axios from 'axios';
import config from '../config';

const api = axios.create({
  baseURL: config.BACKEND_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (reqConfig) => {
    if (config.DEBUG) {
      console.log(`[API] ${reqConfig.method?.toUpperCase()} ${reqConfig.url}`, reqConfig.data);
    }
    return reqConfig;
  },
  (error) => {
    console.error('[API] Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    if (config.DEBUG) {
      console.log(`[API] ${response.status} ${response.config.url}`, response.data);
    }
    return response;
  },
  (error) => {
    const message = error.response?.data?.detail || error.message || 'Unknown error';
    console.error('[API] Response Error:', message, error.response?.data);
    
    if (error.response?.status === 401) {
      console.warn('Unauthorized access');
    }
    
    return Promise.reject(new Error(message));
  }
);

// Meeting Room API
export const meetingAPI = {
  createRoom: async (roomData) => {  // ✅ Removed unused roomId parameter
    try {
      const response = await api.post(`/meeting/rooms/create`, roomData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create room: ${error.message}`);
    }
  },

  getRoomInfo: async (roomId) => {
    const response = await api.get(`/meeting/rooms/${roomId}`);
    return response.data;
  },

  listRooms: async () => {
    const response = await api.get('/meeting/rooms');
    return response.data;
  },

  endRoom: async (roomId, endedBy) => {
    const response = await api.delete(`/meeting/rooms/${roomId}?ended_by=${encodeURIComponent(endedBy)}`);
    return response.data;
  },

  getTranscript: async (roomId) => {
    const response = await api.get(`/meeting/rooms/${roomId}/transcript`);
    return response.data;
  },

  getTasks: async (roomId) => {
    const response = await api.get(`/meeting/rooms/${roomId}/tasks`);
    return response.data;
  },

  extractTasks: async (roomId) => {
    const response = await api.post(`/meeting/rooms/${roomId}/tasks/extract`);
    return response.data;
  },

  getSummary: async (roomId) => {
    const response = await api.get(`/meeting/rooms/${roomId}/summary`);
    return response.data;
  },

  exportMeeting: async (roomId, format = 'json') => {
    const response = await api.get(`/meeting/rooms/${roomId}/export?format=${format}`);
    return response.data;
  },

  downloadRecording: async (roomId) => {
    const response = await api.get(`/meeting/rooms/${roomId}/recording/download`, {
      responseType: 'blob'
    });
    return response.data;
  },

  downloadTranscript: async (roomId, format = 'txt') => {
    const response = await api.get(`/meeting/rooms/${roomId}/transcript/download?format=${format}`, {
      responseType: 'blob'
    });
    return response.data;
  },

  getRecordingMetadata: async (roomId) => {
    const response = await api.get(`/meeting/rooms/${roomId}/recording/metadata`);
    return response.data;
  },
};

// Analytics API
export const analyticsAPI = {
  getSessionAnalytics: async (sessionId) => {
    const response = await api.get(`/analytics/session/${sessionId}`);
    return response.data;
  },

  getDetailedAnalytics: async (sessionId) => {
    const response = await api.get(`/analytics/session/${sessionId}/detailed`);
    return response.data;
  },

  getEmotionAnalytics: async (sessionId) => {
    const response = await api.get(`/analytics/session/${sessionId}/emotions`);
    return response.data;
  },

  getSpeakerAnalytics: async (sessionId) => {
    const response = await api.get(`/analytics/session/${sessionId}/speakers`);
    return response.data;
  },

  listSessions: async () => {
    const response = await api.get('/analytics/sessions/list');
    return response.data;
  },
};

// Health Check API
export const healthAPI = {
  checkHealth: async () => {
    const response = await api.get('/health');
    return response.data;
  },

  checkDetailedHealth: async () => {
    const response = await api.get('/health/detailed');
    return response.data;
  },

  getMetrics: async () => {
    const response = await api.get('/metrics');
    return response.data;
  },
};

export default api;