import { useState, useEffect, useRef, useCallback } from "react";

const WS_BASE_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000";
const RECONNECT_DELAY = 2000;
const MAX_RECONNECT_ATTEMPTS = 10;
const TRANSCRIPT_PING_INTERVAL = 5000; // must be <= backend timeout window (we used 80s backend)

export const useWebSocket = (
  roomId,
  userId,
  username,
  password = "",
  role = "participant"
) => {
  const [isConnected, setIsConnected] = useState(false);
  const [isTranscriptConnected, setIsTranscriptConnected] = useState(false);

  const [transcripts, setTranscripts] = useState([]);
  const [participants, setParticipants] = useState([]);
  const [activeSpeakerId, setActiveSpeakerId] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [error, setError] = useState(null);
  const [lastMessage, setLastMessage] = useState(null);

  const meetingWS = useRef(null);
  const transcriptWS = useRef(null);

  const transcriptPingRef = useRef(null);
  const meetingReconnectRef = useRef(null);
  const transcriptReconnectRef = useRef(null);

  const reconnectAttemptsMeeting = useRef(0);
  const reconnectAttemptsTranscript = useRef(0);

  const onSignalingMessageRef = useRef(null);

  const cleanPassword = password && password.trim().length > 0 ? password.trim() : "";

  // ---------- Meeting WS ----------
  const connectMeetingWS = useCallback(() => {
    if (meetingWS.current && meetingWS.current.readyState === WebSocket.OPEN) return;

    const wsUrl =
      `${WS_BASE_URL}/meeting/rooms/${roomId}/ws` +
      `?user_id=${encodeURIComponent(userId)}` +
      `&username=${encodeURIComponent(username)}` +
      `&role=${encodeURIComponent(role)}` +
      `&password=${encodeURIComponent(cleanPassword)}`;

    meetingWS.current = new WebSocket(wsUrl);
    meetingWS.current.onopen = () => {
      reconnectAttemptsMeeting.current = 0;
      setIsConnected(true);
      setError(null);
      console.log("Meeting WS connected");
    };

    meetingWS.current.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        setLastMessage(data);
        // handle messages (same logic you had)
        switch (data.type) {
          case "welcome":
          case "connected":
          case "connection_ack":
            setIsConnected(true);
            if (data.room_info?.participants) setParticipants(data.room_info.participants);
            break;
          case "live_transcript":
            setTranscripts(prev => [data, ...prev].slice(0, 200));
            break;
          case "participant_joined":
            setParticipants(prev => {
              if (prev.some(p => p.user_id === data.user_id)) return prev;
              return [...prev, { user_id: data.user_id, username: data.username, role: data.role }];
            });
            break;
          case "participant_left":
            setParticipants(prev => prev.filter(p => p.user_id !== data.user_id));
            break;
          case "participant_state_update":
            setParticipants(prev => prev.map(p => p.user_id === data.user_id ? { ...p, ...data } : p));
            break;
          case "active_speaker":
            setActiveSpeakerId(data.user_id);
            break;
          case "chat_message":
            setChatMessages(prev => [...prev, data]);
            break;
          case "new_participant":
          case "webrtc_offer":
          case "webrtc_answer":
          case "ice_candidate":
            if (onSignalingMessageRef.current) onSignalingMessageRef.current(data);
            break;
          case "error":
            setError(data.message || "WebSocket error");
            console.error("Meeting WS error:", data);
            break;
          default:
            // console.log("Meeting WS unknown:", data);
            break;
        }
      } catch (err) {
        console.error("Meeting WS message parse error:", err);
      }
    };

    meetingWS.current.onerror = (err) => {
      console.error("Meeting WS error", err);
      setError("Meeting WS error");
    };

    meetingWS.current.onclose = (evt) => {
      setIsConnected(false);
      console.log("Meeting WS closed", evt.code, evt.reason);
      if (reconnectAttemptsMeeting.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttemptsMeeting.current++;
        const delay = RECONNECT_DELAY * reconnectAttemptsMeeting.current;
        meetingReconnectRef.current = setTimeout(connectMeetingWS, delay);
      }
    };
  }, [roomId, userId, username, role, cleanPassword]);

  // ---------- Transcript WS ----------
  const connectTranscriptWS = useCallback(() => {
    if (transcriptWS.current && transcriptWS.current.readyState === WebSocket.OPEN) return;

    const url = `${WS_BASE_URL}/transcript/ws/${roomId}`;
    transcriptWS.current = new WebSocket(url);
    // allow binary frames
    transcriptWS.current.binaryType = "arraybuffer";

    transcriptWS.current.onopen = () => {
      reconnectAttemptsTranscript.current = 0;
      setIsTranscriptConnected(true);
      setError(null);
      console.log("Transcript WS connected");

      // start pinging (so backend keeps session alive)
      if (transcriptPingRef.current) clearInterval(transcriptPingRef.current);
      transcriptPingRef.current = setInterval(() => {
        try {
          if (transcriptWS.current && transcriptWS.current.readyState === WebSocket.OPEN) {
            transcriptWS.current.send(JSON.stringify({ type: "ping" }));
          }
        } catch (e) {
          // ignore
        }
      }, TRANSCRIPT_PING_INTERVAL);
    };

    transcriptWS.current.onmessage = (evt) => {
      // evt.data might be ArrayBuffer (binary) or string (json)
      if (typeof evt.data === "string") {
        try {
          const data = JSON.parse(evt.data);
          if (data.type === "transcript_entry") {
            // data.data contains transcript payload
            setTranscripts(prev => [data.data, ...prev].slice(0, 200));
          }
          // handle other text types: pong, summary, etc.
        } catch (err) {
          console.error("Transcript WS JSON parse error", err);
        }
      } else {
        // binary data from server (rare) — ignore or handle if you send binary responses
        // console.log("Transcript WS binary message length", evt.data.byteLength);
      }
    };

    transcriptWS.current.onerror = (err) => {
      console.error("Transcript WS error", err);
      setIsTranscriptConnected(false);
      setError("Transcript WS error");
    };

    transcriptWS.current.onclose = (evt) => {
      setIsTranscriptConnected(false);
      console.log("Transcript WS closed", evt.code, evt.reason);
      if (transcriptPingRef.current) {
        clearInterval(transcriptPingRef.current);
        transcriptPingRef.current = null;
      }
      if (reconnectAttemptsTranscript.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttemptsTranscript.current++;
        const delay = RECONNECT_DELAY * reconnectAttemptsTranscript.current;
        transcriptReconnectRef.current = setTimeout(connectTranscriptWS, delay);
      }
    };
  }, [roomId]);

  // send binary PCM to transcript WS
  const sendAudioChunk = useCallback((uint8array) => {
    try {
      if (transcriptWS.current && transcriptWS.current.readyState === WebSocket.OPEN) {
        // if argument is Uint8Array, send its buffer
        if (uint8array instanceof Uint8Array) {
          transcriptWS.current.send(uint8array.buffer);
          return true;
        } else if (uint8array instanceof ArrayBuffer) {
          transcriptWS.current.send(uint8array);
          return true;
        } else {
          // try to coerce
          const coerced = new Uint8Array(uint8array);
          transcriptWS.current.send(coerced.buffer);
          return true;
        }
      }
    } catch (err) {
      console.error("sendAudioChunk error:", err);
    }
    return false;
  }, []);

  // meeting send JSON messages
  const sendMessage = useCallback((msg) => {
    try {
      if (meetingWS.current && meetingWS.current.readyState === WebSocket.OPEN) {
        meetingWS.current.send(JSON.stringify(msg));
        return true;
      }
    } catch (err) {
      console.error("sendMessage error:", err);
    }
    return false;
  }, []);

  const sendChatMessage = useCallback((text) => sendMessage({ type: "chat", message: text }), [sendMessage]);
  const sendSignalingMessage = useCallback((m) => sendMessage(m), [sendMessage]);

  const connect = useCallback((options = {}) => {
    if (options.onSignalingMessage) onSignalingMessageRef.current = options.onSignalingMessage;
    connectMeetingWS();
    connectTranscriptWS();
  }, [connectMeetingWS, connectTranscriptWS]);

  const disconnect = useCallback(() => {
    try {
      if (meetingReconnectRef.current) clearTimeout(meetingReconnectRef.current);
      if (transcriptReconnectRef.current) clearTimeout(transcriptReconnectRef.current);
      if (transcriptPingRef.current) { clearInterval(transcriptPingRef.current); transcriptPingRef.current = null; }

      if (meetingWS.current) {
        try { meetingWS.current.close(1000, "Client disconnect"); } catch {}
        meetingWS.current = null;
      }
      if (transcriptWS.current) {
        try { transcriptWS.current.close(1000, "Client disconnect"); } catch {}
        transcriptWS.current = null;
      }
    } catch (err) {
      // ignore
    } finally {
      setIsConnected(false);
      setIsTranscriptConnected(false);
    }
  }, []);

  // cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    isTranscriptConnected,
    transcripts,
    participants,
    activeSpeakerId,
    chatMessages,
    error,
    lastMessage,

    connect,
    disconnect,
    sendMessage,
    sendChatMessage,
    sendSignalingMessage,
    sendAudioChunk,
  };
};
