// ============================================
// TranscriptViewer.jsx
// ============================================
import React from 'react';
import { MessageSquare } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const TranscriptViewer = ({ transcripts }) => {
  if (transcripts.length === 0) {
    return (
      <div className="transcript-empty">
        <MessageSquare size={48} />
        <p>No transcripts yet. Start speaking to see live transcription.</p>
      </div>
    );
  }

  return (
    <div className="transcript-viewer">
      {transcripts.map((entry, index) => (
        <div key={index} className="transcript-entry">
          <div className="transcript-header">
            <span className="speaker-name">{entry.username || entry.speaker}</span>
            <span className="transcript-time">
              {formatDistanceToNow(new Date(entry.timestamp), { addSuffix: true })}
            </span>
          </div>
          <p className="transcript-text">{entry.text}</p>
          <div className="transcript-meta">
            <span>Emotion: {entry.emotion}</span>
            <span>Confidence: {(entry.confidence * 100).toFixed(0)}%</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default TranscriptViewer;