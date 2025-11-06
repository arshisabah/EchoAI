// src/services/api.js
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
  // Create a new meeting room
  createRoom: async (roomId, roomData) => {
    const response = await api.post(`/meeting/rooms/create?room_id=${roomId}`, roomData);
    return response.data;
  },

  // Get room information
  getRoomInfo: async (roomId) => {
    const response = await api.get(`/meeting/rooms/${roomId}`);
    return response.data;
  },

  // List all rooms
  listRooms: async () => {
    const response = await api.get('/meeting/rooms');
    return response.data;
  },

  // End a meeting room
  endRoom: async (roomId, endedBy) => {
    const response = await api.delete(`/meeting/rooms/${roomId}?ended_by=${endedBy}`);
    return response.data;
  },

  // Get room transcript
  getTranscript: async (roomId) => {
    const response = await api.get(`/meeting/rooms/${roomId}/transcript`);
    return response.data;
  },

  // Get meeting tasks
  getTasks: async (roomId) => {
    const response = await api.get(`/meeting/rooms/${roomId}/tasks`);
    return response.data;
  },

  // Extract tasks from transcript
  extractTasks: async (roomId) => {
    const response = await api.post(`/meeting/rooms/${roomId}/tasks/extract`);
    return response.data;
  },

  // Get meeting summary
  getSummary: async (roomId) => {
    const response = await api.get(`/meeting/rooms/${roomId}/summary`);
    return response.data;
  },

  // Export meeting data
  exportMeeting: async (roomId, format = 'json') => {
    const response = await api.get(`/meeting/rooms/${roomId}/export?format=${format}`);
    return response.data;
  },
};

// Analytics API
export const analyticsAPI = {
  // Get session analytics
  getSessionAnalytics: async (sessionId) => {
    const response = await api.get(`/analytics/session/${sessionId}`);
    return response.data;
  },

  // Get detailed analytics
  getDetailedAnalytics: async (sessionId) => {
    const response = await api.get(`/analytics/session/${sessionId}/detailed`);
    return response.data;
  },

  // Get emotion analytics
  getEmotionAnalytics: async (sessionId) => {
    const response = await api.get(`/analytics/session/${sessionId}/emotions`);
    return response.data;
  },

  // Get speaker analytics
  getSpeakerAnalytics: async (sessionId) => {
    const response = await api.get(`/analytics/session/${sessionId}/speakers`);
    return response.data;
  },

  // List all sessions
  listSessions: async () => {
    const response = await api.get('/analytics/sessions/list');
    return response.data;
  },
};

// Health Check API
export const healthAPI = {
  // Basic health check
  checkHealth: async () => {
    const response = await api.get('/health');
    return response.data;
  },

  // Detailed health check
  checkDetailedHealth: async () => {
    const response = await api.get('/health/detailed');
    return response.data;
  },

  // Get metrics
  getMetrics: async () => {
    const response = await api.get('/metrics');
    return response.data;
  },
};

export default api;