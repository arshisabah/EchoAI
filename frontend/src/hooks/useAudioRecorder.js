import { useState, useRef, useCallback } from 'react';

export const useAudioRecorder = (onAudioData) => {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState(null);
  
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);

  const startRecording = useCallback(async () => {
    try {
      setError(null);

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
        },
      });

      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType,
        audioBitsPerSecond: 128000,
      });

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
            console.error('Error processing audio data:', err);
          }
        }
      };

      mediaRecorder.onerror = (event) => {
        console.error('MediaRecorder error:', event.error);
        setError('Recording error: ' + event.error?.message);
      };

      mediaRecorder.onstop = () => {
        console.log('MediaRecorder stopped');
        setIsRecording(false);
      };

      mediaRecorder.start(1000);
      setIsRecording(true);
      console.log('✅ Recording started');

    } catch (err) {
      console.error('Error starting recording:', err);
      setError('Failed to access microphone: ' + err.message);
      setIsRecording(false);
    }
  }, [onAudioData]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      
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