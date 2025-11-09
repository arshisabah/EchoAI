import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, BarChart3, User, LogOut } from 'lucide-react';

const Navbar = ({ backendStatus, userInfo, onLogout }) => {
  const location = useLocation();

  const getStatusColor = () => {
    switch (backendStatus) {
      case 'connected': return '#10b981';
      case 'degraded': return '#f59e0b';
      case 'disconnected': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const isActive = (path) => location.pathname === path;

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <div className="navbar-brand">
          <div className="logo">
            <span className="logo-icon">🎙️</span>
            <span className="logo-text">EchoAI</span>
          </div>
          <div className="status-indicator">
            <span 
              className="status-dot" 
              style={{ backgroundColor: getStatusColor() }}
            ></span>
            <span className="status-text">{backendStatus}</span>
          </div>
        </div>

        <div className="navbar-links">
          <Link 
            to="/" 
            className={`nav-link ${isActive('/') ? 'active' : ''}`}
          >
            <Home size={18} />
            <span>Dashboard</span>
          </Link>
          
          <Link 
            to="/analytics" 
            className={`nav-link ${isActive('/analytics') ? 'active' : ''}`}
          >
            <BarChart3 size={18} />
            <span>Analytics</span>
          </Link>
        </div>

        <div className="navbar-user">
          <div className="user-info">
            <User size={18} />
            <span className="username">{userInfo?.username}</span>
            <span className="user-role">{userInfo?.role}</span>
          </div>
          <button className="logout-button" onClick={onLogout} title="Logout">
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;