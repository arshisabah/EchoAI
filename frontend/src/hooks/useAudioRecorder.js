import { useState, useRef, useCallback } from 'react';

const AUDIO_CONSTRAINTS = {
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
    sampleRate: 16000,
  },
};

const CHUNK_INTERVAL = 3000; // Send audio every 1 second

export const useAudioRecorder = (onAudioData) => {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState(null);
  
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);

  const startRecording = useCallback(async () => {
    try {
      setError(null);

      // Get user media
      const stream = await navigator.mediaDevices.getUserMedia(AUDIO_CONSTRAINTS);
      streamRef.current = stream;

      // Determine best MIME type
      let mimeType = 'audio/webm;codecs=opus';
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/webm';
        if (!MediaRecorder.isTypeSupported(mimeType)) {
          mimeType = 'audio/ogg;codecs=opus';
          if (!MediaRecorder.isTypeSupported(mimeType)) {
            mimeType = ''; // Use default
          }
        }
      }

      console.log('🎤 Using MIME type:', mimeType || 'default');

      const options = mimeType ? { mimeType } : {};
      const mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = async (event) => {
        if (event.data.size > 0) {
          try {
            const arrayBuffer = await event.data.arrayBuffer();
            const uint8Array = new Uint8Array(arrayBuffer);
            const base64Audio = btoa(String.fromCharCode(...uint8Array));
            
            if (onAudioData) {
              onAudioData(base64Audio);
            }
          } catch (err) {
            console.error('❌ Error processing audio data:', err);
          }
        }
      };

      mediaRecorder.onerror = (event) => {
        console.error('❌ MediaRecorder error:', event.error);
        setError('Recording error: ' + event.error?.message);
        stopRecording();
      };

      mediaRecorder.onstop = () => {
        console.log('🛑 MediaRecorder stopped');
        setIsRecording(false);
      };

      mediaRecorder.start(CHUNK_INTERVAL);
      setIsRecording(true);
      console.log('✅ Recording started');

    } catch (err) {
      console.error('❌ Error starting recording:', err);
      let errorMessage = 'Failed to access microphone';
      
      if (err.name === 'NotAllowedError') {
        errorMessage = 'Microphone access denied. Please allow microphone access and try again.';
      } else if (err.name === 'NotFoundError') {
        errorMessage = 'No microphone found. Please connect a microphone and try again.';
      } else {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
      setIsRecording(false);
    }
  }, [onAudioData]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      try {
        mediaRecorderRef.current.stop();
      } catch (err) {
        console.error('❌ Error stopping recorder:', err);
      }
      
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }

      mediaRecorderRef.current = null;
      setIsRecording(false);
      console.log('🛑 Recording stopped');
    }
  }, [isRecording]);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  return {
    isRecording,
    error,
    startRecording,
    stopRecording,
    toggleRecording,
  };
};