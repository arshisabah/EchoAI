import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download, FileText, Music, Clock, Users, CheckCircle, AlertCircle } from 'lucide-react';
import { meetingAPI } from '../../services/api';

const PostMeetingModal = ({ roomId, onClose }) => {
  const navigate = useNavigate();
  const [metadata, setMetadata] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloadingRecording, setDownloadingRecording] = useState(false);
  const [downloadingTranscript, setDownloadingTranscript] = useState(null);
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
                  <span>Duration: {formatDuration(metadata.duration_seconds)}</span>
                </div>
                <div className="metadata-item">
                  <Users size={20} />
                  <span>Participants: {metadata.participant_count || 'N/A'}</span>
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
                <button
                  className="btn-primary btn-download"
                  onClick={() => handleDownloadTranscript('txt')}
                  disabled={downloadingTranscript === 'txt'}
                >
                  {downloadingTranscript === 'txt' ? (
                    <>
                      <div className="loading-spinner small"></div>
                      Downloading...
                    </>
                  ) : (
                    <>
                      <Download size={16} />
                      Download Transcript (TXT)
                    </>
                  )}
                </button>
              </div>
            </div>

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
