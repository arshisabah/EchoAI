// ============================================
// SummaryPanel.jsx
// ============================================
import React, { useState, useEffect } from 'react';
import { FileText, Download } from 'lucide-react';
import { meetingAPI } from '../services/api';

const SummaryPanel = ({ roomId }) => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadSummary();
  }, [roomId]);

  const loadSummary = async () => {
    setLoading(true);
    try {
      const data = await meetingAPI.getSummary(roomId);
      setSummary(data);
    } catch (error) {
      console.error('Error loading summary:', error);
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
      a.download = `meeting_${roomId}_${Date.now()}.json`;
      a.click();
    } catch (error) {
      console.error('Export failed:', error);
    }
  };

  if (loading) {
    return <div className="loading-spinner"></div>;
  }

  if (!summary) {
    return <div className="empty-state">No summary available yet.</div>;
  }

  return (
    <div className="summary-panel">
      <div className="summary-header">
        <h3>
          <FileText size={18} />
          Meeting Summary
        </h3>
        <button className="btn-secondary btn-sm" onClick={handleExport}>
          <Download size={16} />
          Export
        </button>
      </div>

      <div className="summary-content">
        <div className="summary-section">
          <h4>Overview</h4>
          <p>{summary.summary?.summary || 'No summary available'}</p>
        </div>

        {summary.tasks && summary.tasks.length > 0 && (
          <div className="summary-section">
            <h4>Action Items ({summary.tasks.length})</h4>
            <ul>
              {summary.tasks.slice(0, 5).map((task, i) => (
                <li key={i}>{task.title}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="summary-stats">
          <div>
            <strong>Participants:</strong> {summary.total_participants}
          </div>
          <div>
            <strong>Duration:</strong> {summary.session_duration_minutes?.toFixed(1)} min
          </div>
        </div>
      </div>
    </div>
  );
};

export default SummaryPanel;