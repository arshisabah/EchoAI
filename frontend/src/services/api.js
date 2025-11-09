import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    console.log(`API Response: ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    console.error('API Response Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// Meeting Room API
export const meetingAPI = {
  createRoom: async (roomId, roomData) => {
    const response = await api.post(`/meeting/rooms/create?room_id=${roomId}`, roomData);
    return response.data;
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
    const response = await api.delete(`/meeting/rooms/${roomId}?ended_by=${endedBy}`);
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