import { useState, useRef, useCallback, useEffect } from "react";

/**
 * useAudioRecorder
 * - Produces 16kHz, mono, 16-bit PCM (Int16 little-endian) Uint8Array chunks
 * - Internal buffer + flush interval (CHUNK_MS)
 * - Simple RMS-based VAD to avoid sending long silence
 * - onAudioData(Uint8Array) callback
 */

const CHUNK_MS = 500; // send ~500ms of audio per chunk
const VAD_RMS_THRESHOLD = 0.0012; // adjust if you have noisy mic or quiet voice
const INPUT_BUFFER_SIZE = 4096; // script processor buffer

export const useAudioRecorder = (onAudioData, opts = {}) => {
  const {
    sampleRate = 16000,
    channelCount = 1,
    vadThreshold = VAD_RMS_THRESHOLD,
    chunkMs = CHUNK_MS,
  } = opts;

  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState(null);

  const audioCtxRef = useRef(null);
  const sourceRef = useRef(null);
  const processorRef = useRef(null);
  const streamRef = useRef(null);

  // accumulate Int16 samples (as number array) before converting to Uint8Array
  const sampleBufferRef = useRef([]);
  const flushTimerRef = useRef(null);

  // helper: convert Float32Array to Int16 array
  function floatTo16BitPCM(float32Array) {
    const l = float32Array.length;
    const output = new Int16Array(l);
    for (let i = 0; i < l; i++) {
      let s = Math.max(-1, Math.min(1, float32Array[i]));
      output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return output;
  }

  // helper: concat Int16Array pieces into single Uint8Array (little endian)
  function int16ArrayToUint8(int16arr) {
    const buffer = new ArrayBuffer(int16arr.length * 2);
    const view = new DataView(buffer);
    for (let i = 0; i < int16arr.length; i++) {
      view.setInt16(i * 2, int16arr[i], true);
    }
    return new Uint8Array(buffer);
  }

  // compute RMS for simple VAD
  function computeRMS(float32Array) {
    let sum = 0;
    for (let i = 0; i < float32Array.length; i++) {
      const v = float32Array[i];
      sum += v * v;
    }
    return Math.sqrt(sum / float32Array.length);
  }

  const flushBuffer = useCallback(() => {
    const sampleBuffer = sampleBufferRef.current;
    if (!sampleBuffer || sampleBuffer.length === 0) return;

    // concat all Int16 arrays to single Int16Array
    let totalLen = 0;
    for (let i = 0; i < sampleBuffer.length; i++) totalLen += sampleBuffer[i].length;
    const out = new Int16Array(totalLen);
    let pos = 0;
    for (let i = 0; i < sampleBuffer.length; i++) {
      out.set(sampleBuffer[i], pos);
      pos += sampleBuffer[i].length;
    }

    // clear buffer
    sampleBufferRef.current = [];

    // convert to Uint8Array bytes
    const bytes = int16ArrayToUint8(out);

    // send only if callback is provided
    try {
      if (onAudioData && bytes && bytes.length > 0) {
        onAudioData(bytes);
      }
    } catch (err) {
      console.error("useAudioRecorder.onAudioData callback error:", err);
    }
  }, [onAudioData]);

  const scheduleFlush = useCallback(() => {
    if (flushTimerRef.current) return;
    flushTimerRef.current = setInterval(() => {
      // If there's data, flush it
      if (sampleBufferRef.current.length > 0) flushBuffer();
    }, chunkMs);
  }, [chunkMs, flushBuffer]);

  const clearFlush = useCallback(() => {
    if (flushTimerRef.current) {
      clearInterval(flushTimerRef.current);
      flushTimerRef.current = null;
    }
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);

    if (isRecording) return;
    try {
      // Check if mediaDevices is supported
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('getUserMedia not supported. Please use HTTPS or localhost.');
      }

      // request microphone
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount,
          sampleRate: sampleRate, // we will re-sample if necessary via AudioContext
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      // create audio context with our target sampleRate
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioContext({ sampleRate }); // desired 16kHz
      audioCtxRef.current = audioCtx;

      // create source
      const source = audioCtx.createMediaStreamSource(stream);
      sourceRef.current = source;

      // create script processor
      const processor = audioCtx.createScriptProcessor(INPUT_BUFFER_SIZE, channelCount, channelCount);
      processorRef.current = processor;

      // onaudioprocess will be called with audio at audioCtx.sampleRate (16kHz)
      processor.onaudioprocess = (e) => {
        try {
          const floatData = e.inputBuffer.getChannelData(0); // mono
          // basic VAD: if RMS below threshold, we still accumulate but optionally drop
          const rms = computeRMS(floatData);

          // convert chunk to Int16
          const int16 = floatTo16BitPCM(floatData);

          // if silence and buffer empty, we can skip adding to buffer (avoid sending silence)
          const bufferEmpty = sampleBufferRef.current.length === 0;
          if (rms < vadThreshold && bufferEmpty) {
            // skip pushing pure silence when buffer is empty
            return;
          }

          sampleBufferRef.current.push(int16);
        } catch (err) {
          console.error("Processor error:", err);
        }
      };

      // connect nodes
      source.connect(processor);
      // do not connect processor to destination (avoid echo). On some browsers you must connect to destination to keep processing; if so, we can connect and set volume 0:
      try {
        processor.connect(audioCtx.destination);
      } catch {
        // ignore if not allowed
      }

      scheduleFlush();
      setIsRecording(true);
      console.log("useAudioRecorder: started (PCM 16kHz)");
    } catch (err) {
      console.error("useAudioRecorder start error:", err);
      let msg = "Failed to start microphone";
      
      if (err?.name === "NotAllowedError") {
        msg = "Microphone permission denied. Please allow microphone access.";
      } else if (err?.name === "NotFoundError") {
        msg = "No microphone found. Please connect a microphone.";
      } else if (err?.message?.includes('getUserMedia')) {
        msg = "Browser security: Please use localhost or HTTPS to access microphone.";
      } else if (err?.message) {
        msg = err.message;
      }
      
      setError(msg);
      setIsRecording(false);
      clearFlush();
    }
  }, [channelCount, sampleRate, vadThreshold, scheduleFlush, clearFlush, isRecording]);

  const stopRecording = useCallback(() => {
    try {
      // flush any remaining frames
      flushBuffer();
    } catch (e) {
      // ignore
    }

    try {
      if (processorRef.current) {
        try { processorRef.current.disconnect(); } catch {}
        processorRef.current.onaudioprocess = null;
        processorRef.current = null;
      }
      if (sourceRef.current) {
        try { sourceRef.current.disconnect(); } catch {}
        sourceRef.current = null;
      }
      if (audioCtxRef.current) {
        try { audioCtxRef.current.close(); } catch {}
        audioCtxRef.current = null;
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => {
          try { t.stop(); } catch {}
        });
        streamRef.current = null;
      }
    } catch (err) {
      console.error("stopRecording cleanup error:", err);
    } finally {
      setIsRecording(false);
      clearFlush();
      console.log("useAudioRecorder: stopped");
    }
  }, [clearFlush, flushBuffer]);

  // ensure cleanup on unmount
  useEffect(() => {
    return () => {
      clearFlush();
      try {
        if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
      } catch {}
      if (audioCtxRef.current) {
        try { audioCtxRef.current.close(); } catch {}
      }
    };
  }, [clearFlush]);

  return {
    isRecording,
    error,
    startRecording,
    stopRecording,
    // toggle kept out to avoid accidental misuse; caller can easily call start/stop
  };
};
