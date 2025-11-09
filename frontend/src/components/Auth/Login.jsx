import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Video, User, Mail, LogIn } from 'lucide-react';

const Login = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (username.trim()) {
      login({ username: username.trim(), email: email.trim() });
      navigate('/');
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <div className="logo-large">
            <Video size={48} />
          </div>
          <h1>Welcome to EchoAI</h1>
          <p>AI-Powered Meeting Intelligence Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label>
              <User size={18} />
              Username *
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>
              <Mail size={18} />
              Email (optional)
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your.email@example.com"
            />
          </div>

          <button type="submit" className="btn-primary btn-block">
            <LogIn size={20} />
            Continue to Dashboard
          </button>
        </form>

        <div className="login-features">
          <h3>Features</h3>
          <ul>
            <li>✨ Real-time transcription with speaker identification</li>
            <li>🎭 Live emotion analysis and response guidance</li>
            <li>📹 Multi-user video conferencing</li>
            <li>💬 In-meeting chat</li>
            <li>📊 AI-powered meeting summaries</li>
            <li>✅ Automatic task extraction</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Login;