// src/App.jsx
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import MeetingRoom from './components/MeetingRoom';
import AnalyticsDashboard from './components/AnalyticsDashboard';
import { healthAPI } from './services/api';
import './App.css';

function App() {
  const [backendStatus, setBackendStatus] = useState('checking');
  const [userInfo, setUserInfo] = useState(null);

  // Check backend health on mount
  useEffect(() => {
    checkBackendHealth();
  }, []);

  const checkBackendHealth = async () => {
    try {
      const health = await healthAPI.checkHealth();
      setBackendStatus(health.status === 'healthy' ? 'connected' : 'degraded');
    } catch (error) {
      console.error('Backend health check failed:', error);
      setBackendStatus('disconnected');
    }
  };

  // Initialize user (in production, this would be from authentication)
  useEffect(() => {
    const storedUser = localStorage.getItem('echoai_user');
    if (storedUser) {
      setUserInfo(JSON.parse(storedUser));
    } else {
      // Create default user
      const defaultUser = {
        user_id: `user_${Date.now()}`,
        username: `User_${Math.floor(Math.random() * 1000)}`,
        role: 'participant',
      };
      setUserInfo(defaultUser);
      localStorage.setItem('echoai_user', JSON.stringify(defaultUser));
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('echoai_user');
    setUserInfo(null);
    window.location.reload();
  };

  if (!userInfo) {
    return (
      <div className="app-loading">
        <div className="loading-spinner"></div>
        <p>Loading EchoAI...</p>
      </div>
    );
  }

  return (
    <Router>
      <div className="app">
        <Navbar 
          backendStatus={backendStatus} 
          userInfo={userInfo}
          onLogout={handleLogout}
        />
        
        <main className="app-main">
          <Routes>
            <Route path="/" element={<Dashboard userInfo={userInfo} />} />
            <Route path="/meeting/:roomId" element={<MeetingRoom userInfo={userInfo} />} />
            <Route path="/analytics" element={<AnalyticsDashboard />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>

        {backendStatus === 'disconnected' && (
          <div className="backend-status-alert">
            <span>⚠️ Backend disconnected. Attempting to reconnect...</span>
            <button onClick={checkBackendHealth}>Retry</button>
          </div>
        )}
      </div>
    </Router>
  );
}

export default App;