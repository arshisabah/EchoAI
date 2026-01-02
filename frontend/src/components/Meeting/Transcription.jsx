import React, { useRef, useEffect, useState } from 'react';
import { FileText, Download, ChevronDown } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { meetingAPI } from '../../services/api';

const TranscriptPanel = ({ transcripts, onExport, roomId }) => {
  const transcriptEndRef = useRef(null);
  const containerRef = useRef(null);
  const dropdownRef = useRef(null);
  const [showFormatMenu, setShowFormatMenu] = useState(false);
  const [downloading, setDownloading] = useState(null);
  const [userScrolled, setUserScrolled] = useState(false);

  // Auto-scroll only if user is near bottom
  useEffect(() => {
    const container = containerRef.current;
    if (!container || userScrolled) return;
    
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    if (isNearBottom) {
      transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [transcripts, userScrolled]);

  // Detect user scrolling up
  const handleScroll = (e) => {
    const container = e.target;
    const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 50;
    setUserScrolled(!isAtBottom);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowFormatMenu(false);
      }
    };

    if (showFormatMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showFormatMenu]);

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
          <div className="export-dropdown" ref={dropdownRef}>
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

      <div className="transcript-content" ref={containerRef} onScroll={handleScroll}>
        {transcripts.length === 0 ? (
          <div className="transcript-empty">
            <FileText size={48} />
            <p>No transcripts yet</p>
            <span>Start speaking to see live transcription</span>
          </div>
        ) : (
          transcripts.map((entry, index) => (
            <div 
              key={entry.entry_id || index} 
              className={`transcript-entry ${!entry.is_final ? 'partial' : ''}`}
            >
              <div className="transcript-entry-header">
                <div className="speaker-info">
                  <div className="speaker-avatar">
                    {entry.username?.charAt(0).toUpperCase() || 'S'}
                  </div>
                  <span className="speaker-name">
                    {entry.username || entry.speaker}
                  </span>
                  {!entry.is_final && (
                    <span className="partial-indicator" title="Transcribing...">●</span>
                  )}
                </div>
                <span className="transcript-time">
                  {formatDistanceToNow(new Date(entry.timestamp), { addSuffix: true })}
                </span>
              </div>

              <div className="transcript-text">{entry.text}</div>

              {entry.is_final !== false && (
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
                    {((entry.emotion_confidence || entry.confidence || 1) * 100).toFixed(0)}% confident
                  </span>
                  {entry.emotion_guidance && entry.emotion_guidance.suggestion && (
                    <div className="emotion-guidance" style={{ marginTop: '8px', fontSize: '0.85em', color: '#64748b' }}>
                      💡 {entry.emotion_guidance.suggestion}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={transcriptEndRef} />
      </div>
    </div>
  );
};

export default TranscriptPanel;