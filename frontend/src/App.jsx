import React, { useState, useEffect, Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ErrorBoundary from './components/ErrorBoundary';
import Navbar from './components/Navbar';
import Login from './components/Auth/Login';

import { useBackendStatus } from './hooks/useBackendStatus';
import { healthAPI } from './services/api';
import './App.css';


const Dashboard = lazy(() => import('./components/Dashboard'));
const MeetingRoom = lazy(() => import('./components/MeetingRoom'));
const AnalyticsDashboard = lazy(() => import('./components/AnalyticsDashboard'));


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
  const { backendStatus, checkBackendHealth } = useBackendStatus();

  return (
    <ErrorBoundary>
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
            <Suspense fallback={<div className="app-loading">Loading...</div>}>
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
                  path="/meeting/rooms/:roomId"
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
            </Suspense>
          </main>

          {backendStatus === 'disconnected' && user && (
            <div className="backend-status-alert">
              <span>⚠️ Backend disconnected. Attempting to reconnect...</span>
              <div className="loading-spinner small"></div>
              <button onClick={checkBackendHealth}>Retry</button>
            </div>
          )}
        </div>
      </Router>
    </ErrorBoundary >
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