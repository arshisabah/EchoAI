import React, { useState, useEffect } from 'react';
import { FileText, Download, RefreshCw, Loader, CheckCircle, AlertCircle } from 'lucide-react';
import { meetingAPI } from '../../services/api';

const SummaryPanel = ({ roomId }) => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    loadSummary();

    if (autoRefresh) {
      const interval = setInterval(loadSummary, 60000); // Refresh every minute
      return () => clearInterval(interval);
    }
  }, [roomId, autoRefresh]);

  const loadSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await meetingAPI.getSummary(roomId);
      setSummary(data);
    } catch (error) {
      console.error('Error loading summary:', error);
      setError('Failed to load summary');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const data = await meetingAPI.exportMeeting(roomId, 'json');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `meeting_summary_${roomId}_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Failed to export summary');
    }
  };

  if (loading && !summary) {
    return (
      <div className="summary-panel">
        <div className="summary-loading">
          <Loader className="spinner" size={48} />
          <p>Generating summary...</p>
        </div>
      </div>
    );
  }

  if (error && !summary) {
    return (
      <div className="summary-panel">
        <div className="summary-error">
          <AlertCircle size={48} />
          <p>{error}</p>
          <button className="btn-secondary btn-sm" onClick={loadSummary}>
            <RefreshCw size={16} />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="summary-panel">
      <div className="summary-header">
        <div className="header-left">
          <FileText size={20} />
          <h3>Meeting Summary</h3>
        </div>
        <div className="summary-actions">
          <button 
            className="btn-icon-sm" 
            onClick={loadSummary}
            disabled={loading}
            title="Refresh Summary"
          >
            <RefreshCw size={16} className={loading ? 'spinning' : ''} />
          </button>
          <button className="btn-secondary btn-sm" onClick={handleExport}>
            <Download size={16} />
            Export
          </button>
        </div>
      </div>

      <div className="summary-content">
        {/* Main Summary */}
        {summary?.summary?.summary && (
          <div className="summary-section">
            <h4>📋 Overview</h4>
            <div className="summary-text">
              {summary.summary.summary}
            </div>
          </div>
        )}

        {/* Key Points */}
        {summary?.summary?.key_points && summary.summary.key_points.length > 0 && (
          <div className="summary-section">
            <h4>🎯 Key Points</h4>
            <ul className="summary-list">
              {summary.summary.key_points.map((point, i) => (
                <li key={i}>
                  <CheckCircle size={16} className="list-icon" />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Action Items Summary */}
        {summary?.tasks && summary.tasks.length > 0 && (
          <div className="summary-section">
            <h4>✅ Action Items ({summary.tasks.length})</h4>
            <div className="action-items-preview">
              {summary.tasks.slice(0, 5).map((task, i) => (
                <div key={i} className="action-item-mini">
                  <div className="action-item-title">{task.title}</div>
                  <div className="action-item-meta">
                    <span className="assignee">@{task.assigned_to}</span>
                    <span className={`priority priority-${task.priority}`}>
                      {task.priority}
                    </span>
                  </div>
                </div>
              ))}
              {summary.tasks.length > 5 && (
                <div className="more-items">
                  +{summary.tasks.length - 5} more tasks
                </div>
              )}
            </div>
          </div>
        )}

        {/* Task Summary Stats */}
        {summary?.task_summary && (
          <div className="summary-section">
            <h4>📊 Task Statistics</h4>
            <div className="task-stats-grid">
              <div className="stat-box">
                <span className="stat-value">{summary.task_summary.total_tasks || 0}</span>
                <span className="stat-label">Total Tasks</span>
              </div>
              <div className="stat-box">
                <span className="stat-value">
                  {summary.task_summary.by_status?.pending || 0}
                </span>
                <span className="stat-label">Pending</span>
              </div>
              <div className="stat-box">
                <span className="stat-value">
                  {summary.task_summary.by_status?.completed || 0}
                </span>
                <span className="stat-label">Completed</span>
              </div>
              <div className="stat-box">
                <span className="stat-value">
                  {Math.round(summary.task_summary.completion_rate || 0)}%
                </span>
                <span className="stat-label">Completion</span>
              </div>
            </div>
          </div>
        )}

        {/* Emotion Analysis Summary */}
        {summary?.emotion_analysis && (
          <div className="summary-section">
            <h4>🎭 Emotion Overview</h4>
            <div className="emotion-summary">
              <div className="emotion-primary">
                <span className="emotion-label">Overall Mood:</span>
                <span className={`emotion-value emotion-${summary.emotion_analysis.session_summary?.overall_emotion || 'neutral'}`}>
                  {summary.emotion_analysis.session_summary?.overall_emotion || 'Neutral'}
                </span>
              </div>
              {summary.emotion_analysis.session_summary?.emotion_distribution && (
                <div className="emotion-distribution">
                  {Object.entries(summary.emotion_analysis.session_summary.emotion_distribution)
                    .slice(0, 3)
                    .map(([emotion, count]) => (
                      <div key={emotion} className="emotion-bar">
                        <span className="emotion-name">{emotion}</span>
                        <div className="bar-container">
                          <div 
                            className="bar-fill" 
                            style={{ width: `${count}%` }}
                          />
                        </div>
                        <span className="emotion-percentage">{Math.round(count)}%</span>
                      </div>
                    ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Meeting Metadata */}
        <div className="summary-section">
          <h4>ℹ️ Meeting Info</h4>
          <div className="metadata-grid">
            <div className="metadata-item">
              <span className="metadata-label">Participants:</span>
              <span className="metadata-value">{summary?.total_participants || 0}</span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Duration:</span>
              <span className="metadata-value">
                {summary?.session_duration_minutes 
                  ? `${Math.round(summary.session_duration_minutes)} min` 
                  : 'N/A'}
              </span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Total Words:</span>
              <span className="metadata-value">
                {summary?.emotion_analysis?.total_analyzed || 0}
              </span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Generated:</span>
              <span className="metadata-value">
                {summary?.generated_at 
                  ? new Date(summary.generated_at).toLocaleTimeString() 
                  : 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* Auto Refresh Toggle */}
        <div className="summary-footer">
          <label className="auto-refresh-toggle">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            <span>Auto-refresh every minute</span>
          </label>
        </div>
      </div>
    </div>
  );
};

export default SummaryPanel;