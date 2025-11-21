import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download, FileText, Music, Clock, Users, CheckCircle, AlertCircle, Sparkles } from 'lucide-react';
import { meetingAPI } from '../../services/api';

const PostMeetingModal = ({ roomId, onClose }) => {
  const navigate = useNavigate();
  const [metadata, setMetadata] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloadingRecording, setDownloadingRecording] = useState(false);
  const [downloadingTranscript, setDownloadingTranscript] = useState(null);
  const [generatingSummary, setGeneratingSummary] = useState(false);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  useEffect(() => {
    const loadMetadata = async () => {
      try {
        const data = await meetingAPI.getRecordingMetadata(roomId);
        setMetadata(data);
      } catch (err) {
        console.error('Failed to load metadata:', err);
        setError('Could not load recording metadata');
      } finally {
        setLoading(false);
      }
    };

    loadMetadata();
  }, [roomId]);

  const handleDownloadRecording = async () => {
    setDownloadingRecording(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const blob = await meetingAPI.downloadRecording(roomId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `meeting_${roomId}_${Date.now()}.wav`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setSuccessMessage('Recording downloaded successfully!');
    } catch (err) {
      console.error('Download failed:', err);
      setError('Failed to download recording. Please try again.');
    } finally {
      setDownloadingRecording(false);
    }
  };

  const handleDownloadTranscript = async (format) => {
    setDownloadingTranscript(format);
    setError(null);
    setSuccessMessage(null);

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
      setSuccessMessage(`Transcript downloaded successfully as ${format.toUpperCase()}!`);
    } catch (err) {
      console.error('Download failed:', err);
      setError('Failed to download transcript. Please try again.');
    } finally {
      setDownloadingTranscript(null);
    }
  };

  const handleGenerateSummary = async () => {
    setGeneratingSummary(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const data = await meetingAPI.getSummary(roomId);
      setSummary(data);
      setSuccessMessage('Summary generated successfully!');
    } catch (err) {
      console.error('Summary generation failed:', err);
      setError('Failed to generate summary. Please try again.');
    } finally {
      setGeneratingSummary(false);
    }
  };

  const handleGoToDashboard = () => {
    navigate('/');
    onClose();
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return 'N/A';
    const mb = (bytes / (1024 * 1024)).toFixed(2);
    return `${mb} MB`;
  };

  return (
    <div className="post-meeting-modal" onClick={onClose}>
      <div className="post-meeting-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <CheckCircle size={48} color="#10b981" />
          <h2>Meeting Ended Successfully</h2>
        </div>

        {loading ? (
          <div className="loading-section">
            <div className="loading-spinner"></div>
            <p>Loading meeting data...</p>
          </div>
        ) : (
          <>
            {metadata && (
              <div className="meeting-metadata">
                <div className="metadata-item">
                  <Clock size={20} />
                  <span>Duration: {formatDuration(metadata.duration)}</span>
                </div>
                <div className="metadata-item">
                  <Users size={20} />
                  <span>Participants: {metadata.total_chunks || 'N/A'}</span>
                </div>
                <div className="metadata-item">
                  <Music size={20} />
                  <span>Size: {formatFileSize(metadata.file_size)}</span>
                </div>
              </div>
            )}

            <div className="download-section">
              <h3>Download Your Meeting Resources</h3>

              <div className="download-group">
                <div className="download-header">
                  <Music size={20} />
                  <span>Recording (WAV)</span>
                </div>
                <button
                  className="btn-primary btn-download"
                  onClick={handleDownloadRecording}
                  disabled={downloadingRecording}
                >
                  {downloadingRecording ? (
                    <>
                      <div className="loading-spinner small"></div>
                      Downloading...
                    </>
                  ) : (
                    <>
                      <Download size={16} />
                      Download Recording
                    </>
                  )}
                </button>
              </div>

              <div className="download-group">
                <div className="download-header">
                  <FileText size={20} />
                  <span>Transcript</span>
                </div>
                <div className="download-buttons">
                  <button
                    className="btn-secondary btn-sm"
                    onClick={() => handleDownloadTranscript('txt')}
                    disabled={downloadingTranscript === 'txt'}
                  >
                    {downloadingTranscript === 'txt' ? (
                      <div className="loading-spinner small"></div>
                    ) : (
                      'TXT'
                    )}
                  </button>
                  <button
                    className="btn-secondary btn-sm"
                    onClick={() => handleDownloadTranscript('json')}
                    disabled={downloadingTranscript === 'json'}
                  >
                    {downloadingTranscript === 'json' ? (
                      <div className="loading-spinner small"></div>
                    ) : (
                      'JSON'
                    )}
                  </button>
                  <button
                    className="btn-secondary btn-sm"
                    onClick={() => handleDownloadTranscript('srt')}
                    disabled={downloadingTranscript === 'srt'}
                  >
                    {downloadingTranscript === 'srt' ? (
                      <div className="loading-spinner small"></div>
                    ) : (
                      'SRT'
                    )}
                  </button>
                </div>
              </div>

              <div className="download-group">
                <div className="download-header">
                  <Sparkles size={20} />
                  <span>AI-Generated Summary</span>
                </div>
                <button
                  className="btn-primary btn-download"
                  onClick={handleGenerateSummary}
                  disabled={generatingSummary}
                >
                  {generatingSummary ? (
                    <>
                      <div className="loading-spinner small"></div>
                      Generating Summary...
                    </>
                  ) : (
                    <>
                      <Sparkles size={16} />
                      Generate Summary
                    </>
                  )}
                </button>
              </div>
            </div>

            {summary && (
              <div className="summary-section">
                <h3>Meeting Summary</h3>
                <div className="summary-content">
                  {typeof summary.summary === 'string' ? (
                    <p>{summary.summary}</p>
                  ) : (
                    <>
                      {summary.summary?.overview && (
                        <div className="summary-block">
                          <h4>Overview</h4>
                          <p>{summary.summary.overview}</p>
                        </div>
                      )}
                      {summary.summary?.key_points && summary.summary.key_points.length > 0 && (
                        <div className="summary-block">
                          <h4>Key Points</h4>
                          <ul>
                            {summary.summary.key_points.map((point, idx) => (
                              <li key={idx}>{point}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {summary.summary?.decisions && summary.summary.decisions.length > 0 && (
                        <div className="summary-block">
                          <h4>Decisions Made</h4>
                          <ul>
                            {summary.summary.decisions.map((decision, idx) => (
                              <li key={idx}>{decision}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {summary.summary?.action_items && summary.summary.action_items.length > 0 && (
                        <div className="summary-block">
                          <h4>Action Items</h4>
                          <ul>
                            {summary.summary.action_items.map((item, idx) => (
                              <li key={idx}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </>
                  )}
                  {summary.total_participants && (
                    <div className="summary-meta">
                      <span><Users size={14} /> {summary.total_participants} participants</span>
                      {summary.generated_at && (
                        <span><Clock size={14} /> Generated at {new Date(summary.generated_at).toLocaleTimeString()}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {error && (
              <div className="message-banner error">
                <AlertCircle size={16} />
                {error}
              </div>
            )}

            {successMessage && (
              <div className="message-banner success">
                <CheckCircle size={16} />
                {successMessage}
              </div>
            )}

            <div className="modal-actions">
              <button className="btn-secondary" onClick={onClose}>
                Skip
              </button>
              <button className="btn-primary" onClick={handleGoToDashboard}>
                Go to Dashboard
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default PostMeetingModal;
