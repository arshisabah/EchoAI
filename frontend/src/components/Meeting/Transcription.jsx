import React, { useRef, useEffect } from 'react';
import { FileText, Download } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const TranscriptPanel = ({ transcripts, onExport }) => {
  const transcriptEndRef = useRef(null);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcripts]);

  const getEmotionColor = (emotion) => {
    const colors = {
      happy: '#10b981',
      excited: '#f59e0b',
      neutral: '#64748b',
      sad: '#6366f1',
      angry: '#ef4444',
      frustrated: '#f97316',
      confused: '#8b5cf6',
      anxious: '#ec4899',
    };
    return colors[emotion] || colors.neutral;
  };

  return (
    <div className="transcript-panel">
      <div className="transcript-header">
        <div className="header-left">
          <FileText size={20} />
          <h3>Live Transcript</h3>
          <span className="badge">{transcripts.length}</span>
        </div>
        {transcripts.length > 0 && (
          <button className="btn-secondary btn-sm" onClick={onExport}>
            <Download size={16} />
            Export
          </button>
        )}
      </div>

      <div className="transcript-content">
        {transcripts.length === 0 ? (
          <div className="transcript-empty">
            <FileText size={48} />
            <p>No transcripts yet</p>
            <span>Start speaking to see live transcription</span>
          </div>
        ) : (
          transcripts.map((entry, index) => (
            <div key={index} className="transcript-entry">
              <div className="transcript-entry-header">
                <div className="speaker-info">
                  <div className="speaker-avatar">
                    {entry.username?.charAt(0).toUpperCase() || 'S'}
                  </div>
                  <span className="speaker-name">
                    {entry.username || entry.speaker}
                  </span>
                </div>
                <span className="transcript-time">
                  {formatDistanceToNow(new Date(entry.timestamp), { addSuffix: true })}
                </span>
              </div>

              <div className="transcript-text">{entry.text}</div>

              <div className="transcript-meta">
                <div 
                  className="emotion-badge"
                  style={{ 
                    backgroundColor: `${getEmotionColor(entry.emotion)}15`,
                    color: getEmotionColor(entry.emotion)
                  }}
                >
                  {entry.emotion}
                </div>
                <span className="confidence-badge">
                  {(entry.confidence * 100).toFixed(0)}% confident
                </span>
              </div>
            </div>
          ))
        )}
        <div ref={transcriptEndRef} />
      </div>
    </div>
  );
};

export default TranscriptPanel;