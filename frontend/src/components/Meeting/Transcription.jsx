import React, { useRef, useEffect, useState } from 'react';
import { FileText, Download, ChevronDown } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { meetingAPI } from '../../services/api';

const TranscriptPanel = ({ transcripts, onExport, roomId }) => {
  const transcriptEndRef = useRef(null);
  const [showFormatMenu, setShowFormatMenu] = useState(false);
  const [downloading, setDownloading] = useState(null);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcripts]);

  const handleDownloadTranscript = async (format) => {
    if (!roomId) {
      console.error('No roomId provided');
      alert('Cannot download transcript: Room ID not available');
      return;
    }

    setDownloading(format);
    setShowFormatMenu(false);

    try {
      const blob = await meetingAPI.downloadTranscript(roomId, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `transcript_${roomId}_${Date.now()}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
      alert('Failed to download transcript');
    } finally {
      setDownloading(null);
    }
  };

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
        {transcripts.length > 0 && roomId && (
          <div className="export-dropdown">
            <button 
              className="btn-secondary btn-sm" 
              onClick={() => setShowFormatMenu(!showFormatMenu)}
              disabled={downloading}
            >
              {downloading ? (
                <>
                  <div className="loading-spinner small"></div>
                  Downloading...
                </>
              ) : (
                <>
                  <Download size={16} />
                  Download
                  <ChevronDown size={14} />
                </>
              )}
            </button>
            {showFormatMenu && (
              <div className="format-menu">
                <button onClick={() => handleDownloadTranscript('txt')}>
                  <FileText size={14} />
                  Text (.txt)
                </button>
                <button onClick={() => handleDownloadTranscript('json')}>
                  <FileText size={14} />
                  JSON (.json)
                </button>
                <button onClick={() => handleDownloadTranscript('srt')}>
                  <FileText size={14} />
                  Subtitles (.srt)
                </button>
              </div>
            )}
          </div>
        )}
        {transcripts.length > 0 && !roomId && (
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