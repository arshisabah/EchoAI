// ============================================
// AnalyticsDashboard.jsx
// ============================================
import React, { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, Users } from 'lucide-react';
import { analyticsAPI } from '../services/api';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

const AnalyticsDashboard = () => {
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [analytics, setAnalytics] = useState(null);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const data = await analyticsAPI.listSessions();
      setSessions(data.sessions || []);
    } catch (error) {
      console.error('Error loading sessions:', error);
    }
  };

  const loadAnalytics = async (sessionId) => {
    try {
      const data = await analyticsAPI.getDetailedAnalytics(sessionId);
      setAnalytics(data);
      setSelectedSession(sessionId);
    } catch (error) {
      console.error('Error loading analytics:', error);
    }
  };

  const emotionData = analytics?.emotion_analysis?.session_summary?.emotion_distribution
    ? Object.entries(analytics.emotion_analysis.session_summary.emotion_distribution).map(([emotion, count]) => ({
        name: emotion,
        value: count,
      }))
    : [];

  const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

  return (
    <div className="analytics-dashboard">
      <h1>
        <BarChart3 size={24} />
        Analytics Dashboard
      </h1>

      <div className="analytics-grid">
        <div className="analytics-sidebar">
          <h3>Recent Sessions</h3>
          <div className="sessions-list">
            {sessions.map((session) => (
              <div
                key={session.session_id}
                className={`session-item ${selectedSession === session.session_id ? 'active' : ''}`}
                onClick={() => loadAnalytics(session.session_id)}
              >
                <div>{session.session_id}</div>
                <div className="text-muted">{session.total_entries} entries</div>
              </div>
            ))}
          </div>
        </div>

        <div className="analytics-main">
          {!analytics ? (
            <div className="empty-state">
              <BarChart3 size={48} />
              <p>Select a session to view analytics</p>
            </div>
          ) : (
            <>
              <div className="analytics-section">
                <h2>Emotion Distribution</h2>
                {emotionData.length > 0 && (
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={emotionData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={100}
                        label
                      >
                        {emotionData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>

              <div className="analytics-section">
                <h2>
                  <Users size={20} />
                  Speaker Statistics
                </h2>
                {analytics.speaker_patterns?.speaker_statistics && (
                  <div className="speaker-stats">
                    {Object.entries(analytics.speaker_patterns.speaker_statistics).map(([speaker, stats]) => (
                      <div key={speaker} className="speaker-stat-item">
                        <strong>{speaker}</strong>
                        <span>{stats.total_speaking_time?.toFixed(1)}s speaking time</span>
                        <span>{stats.total_words} words</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;