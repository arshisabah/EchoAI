import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import Login from './components/Auth/Login';
import Dashboard from './components/Dashboard';
import MeetingRoom from './components/MeetingRoom';
import AnalyticsDashboard from './components/AnalyticsDashboard';
import { healthAPI } from './services/api';
import './App.css';

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="app-loading">
        <div className="loading-spinner"></div>
        <p>Loading...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

const AppContent = () => {
  const { user, logout } = useAuth();
  const [backendStatus, setBackendStatus] = useState('checking');

  useEffect(() => {
    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 30000);
    return () => clearInterval(interval);
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

  return (
    <Router>
      <div className="app">
        {user && (
          <Navbar 
            backendStatus={backendStatus} 
            userInfo={user}
            onLogout={logout}
          />
        )}
        
        <main className="app-main">
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Dashboard userInfo={user} />
                </ProtectedRoute>
              }
            />
            <Route
              path="/meeting/:roomId"
              element={
                <ProtectedRoute>
                  <MeetingRoom userInfo={user} />
                </ProtectedRoute>
              }
            />
            <Route
              path="/analytics"
              element={
                <ProtectedRoute>
                  <AnalyticsDashboard />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>

        {backendStatus === 'disconnected' && user && (
          <div className="backend-status-alert">
            <span>⚠️ Backend disconnected. Attempting to reconnect...</span>
            <button onClick={checkBackendHealth}>Retry</button>
          </div>
        )}
      </div>
    </Router>
  );
};

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;