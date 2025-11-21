import React, { useState } from 'react';
import { Settings, Volume2, Video, Mic, Bell, Download, Trash2 } from 'lucide-react';

const SettingsPanel = ({ 
  roomId, 
  isAudioEnabled, 
  isVideoEnabled, 
  onToggleAudio, 
  onToggleVideo,
  onExportTranscript,
  onLeaveRoom 
}) => {
  const [notifications, setNotifications] = useState(true);
  const [autoRecord, setAutoRecord] = useState(true);
  const [qualityMode, setQualityMode] = useState('balanced');

  return (
    <div className="settings-panel">
      <div className="panel-header">
        <h3>
          <Settings size={20} />
          Meeting Settings
        </h3>
      </div>

      <div className="settings-content">
        {/* Audio/Video Controls */}
        <div className="settings-section">
          <h4>Media Controls</h4>
          
          <div className="settings-item">
            <div className="settings-item-label">
              <Mic size={18} />
              <span>Microphone</span>
            </div>
            <button 
              className={`toggle-btn ${isAudioEnabled ? 'active' : ''}`}
              onClick={onToggleAudio}
            >
              {isAudioEnabled ? 'ON' : 'OFF'}
            </button>
          </div>

          <div className="settings-item">
            <div className="settings-item-label">
              <Video size={18} />
              <span>Camera</span>
            </div>
            <button 
              className={`toggle-btn ${isVideoEnabled ? 'active' : ''}`}
              onClick={onToggleVideo}
            >
              {isVideoEnabled ? 'ON' : 'OFF'}
            </button>
          </div>
        </div>

        {/* Notification Settings */}
        <div className="settings-section">
          <h4>Preferences</h4>
          
          <div className="settings-item">
            <div className="settings-item-label">
              <Bell size={18} />
              <span>Notifications</span>
            </div>
            <button 
              className={`toggle-btn ${notifications ? 'active' : ''}`}
              onClick={() => setNotifications(!notifications)}
            >
              {notifications ? 'ON' : 'OFF'}
            </button>
          </div>

          <div className="settings-item">
            <div className="settings-item-label">
              <Volume2 size={18} />
              <span>Auto Record</span>
            </div>
            <button 
              className={`toggle-btn ${autoRecord ? 'active' : ''}`}
              onClick={() => setAutoRecord(!autoRecord)}
            >
              {autoRecord ? 'ON' : 'OFF'}
            </button>
          </div>
        </div>

        {/* Quality Settings */}
        <div className="settings-section">
          <h4>Quality Mode</h4>
          
          <div className="quality-options">
            <button
              className={`quality-option ${qualityMode === 'low' ? 'active' : ''}`}
              onClick={() => setQualityMode('low')}
            >
              Low
              <span className="quality-desc">Save bandwidth</span>
            </button>
            <button
              className={`quality-option ${qualityMode === 'balanced' ? 'active' : ''}`}
              onClick={() => setQualityMode('balanced')}
            >
              Balanced
              <span className="quality-desc">Recommended</span>
            </button>
            <button
              className={`quality-option ${qualityMode === 'high' ? 'active' : ''}`}
              onClick={() => setQualityMode('high')}
            >
              High
              <span className="quality-desc">Best quality</span>
            </button>
          </div>
        </div>

        {/* Actions */}
        <div className="settings-section">
          <h4>Actions</h4>
          
          <button className="settings-action-btn" onClick={onExportTranscript}>
            <Download size={18} />
            Export Transcript
          </button>

          <button className="settings-action-btn danger" onClick={onLeaveRoom}>
            <Trash2 size={18} />
            Leave Meeting
          </button>
        </div>

        {/* Room Info */}
        <div className="settings-section">
          <h4>Room Information</h4>
          <div className="room-info">
            <div className="info-row">
              <span className="info-label">Room ID:</span>
              <span className="info-value">{roomId}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPanel;
