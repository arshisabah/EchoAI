import React, { useState, useEffect } from 'react';
import { BarChart3, Clock, MessageSquare, Heart, TrendingUp } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';

const EMOTION_COLORS = {
  happy: '#10b981',
  neutral: '#6b7280',
  sad: '#3b82f6',
  angry: '#ef4444',
  surprised: '#f59e0b',
  fearful: '#8b5cf6',
};

const AnalyticsPanel = ({ transcripts, participants, emotionHistory }) => {
  const [speakingTime, setSpeakingTime] = useState({});
  const [emotionStats, setEmotionStats] = useState({});

  useEffect(() => {
    calculateAnalytics();
  }, [transcripts, emotionHistory]);

  const calculateAnalytics = () => {
    // Calculate speaking time per participant
    const timeMap = {};
    const emotionMap = {};

    transcripts.forEach((t) => {
      const speaker = t.username || t.speaker || 'Unknown';
      
      // Count transcripts as a proxy for speaking time
      if (!timeMap[speaker]) {
        timeMap[speaker] = 0;
      }
      timeMap[speaker] += 1;

      // Count emotions
      const emotion = t.emotion || 'neutral';
      if (!emotionMap[emotion]) {
        emotionMap[emotion] = 0;
      }
      emotionMap[emotion] += 1;
    });

    setSpeakingTime(timeMap);
    setEmotionStats(emotionMap);
  };

  const speakingTimeData = Object.entries(speakingTime).map(([name, count]) => ({
    name,
    value: count,
  }));

  const emotionData = Object.entries(emotionStats).map(([emotion, count]) => ({
    name: emotion.charAt(0).toUpperCase() + emotion.slice(1),
    value: count,
    color: EMOTION_COLORS[emotion] || '#6b7280',
  }));

  const totalTranscripts = transcripts.length;
  const totalParticipants = participants.length;
  const avgTranscriptsPerPerson = totalParticipants > 0 
    ? (totalTranscripts / totalParticipants).toFixed(1) 
    : 0;

  return (
    <div className="analytics-panel">
      <div className="panel-header">
        <h3>
          <BarChart3 size={20} />
          Real-time Analytics
        </h3>
      </div>

      <div className="analytics-stats">
        <div className="stat-card">
          <div className="stat-icon">
            <MessageSquare size={20} />
          </div>
          <div className="stat-content">
            <div className="stat-value">{totalTranscripts}</div>
            <div className="stat-label">Total Messages</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">
            <Clock size={20} />
          </div>
          <div className="stat-content">
            <div className="stat-value">{avgTranscriptsPerPerson}</div>
            <div className="stat-label">Avg per Person</div>
          </div>
        </div>
      </div>

      {/* Speaking Time Chart */}
      {speakingTimeData.length > 0 && (
        <div className="analytics-section">
          <h4>Speaking Time Distribution</h4>
          <div className="speaking-time-list">
            {speakingTimeData.map((item, idx) => {
              const percentage = ((item.value / totalTranscripts) * 100).toFixed(1);
              return (
                <div key={idx} className="speaking-time-item">
                  <div className="speaker-name">{item.name}</div>
                  <div className="speaker-bar">
                    <div 
                      className="speaker-bar-fill" 
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                  <div className="speaker-percentage">{percentage}%</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Emotion Distribution Chart */}
      {emotionData.length > 0 && (
        <div className="analytics-section">
          <h4>Emotion Distribution</h4>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={emotionData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {emotionData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {emotionData.length === 0 && speakingTimeData.length === 0 && (
        <div className="empty-state">
          <TrendingUp size={48} />
          <p>Analytics will appear as the meeting progresses</p>
        </div>
      )}
    </div>
  );
};

export default AnalyticsPanel;
