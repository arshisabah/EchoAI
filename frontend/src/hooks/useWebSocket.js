import { useState, useEffect, useRef, useCallback } from "react";

const WS_BASE_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000";
const RECONNECT_DELAY = 3000;
const MAX_RECONNECT_ATTEMPTS = 5;
const PING_INTERVAL = 30000;

export const useWebSocket = (
  roomId,
  userId,
  username,
  password = "",
  role = "participant"
) => {
  const [isConnected, setIsConnected] = useState(false);
  const [transcripts, setTranscripts] = useState([]);
  const [participants, setParticipants] = useState([]);
  const [activeSpeakerId, setActiveSpeakerId] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [error, setError] = useState(null);
  const [lastMessage, setLastMessage] = useState(null);

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const isConnectingRef = useRef(false);
  const connectOptionsRef = useRef({});
  const onSignalingMessageRef = useRef(null);

  // 📌 CLEAN PASSWORD BEFORE SENDING
  const cleanPassword =
    password && password.trim().length > 0 ? password.trim() : null;

  const connect = useCallback(
    (options = {}) => {
      connectOptionsRef.current = options;
      const { onSignalingMessage } = options;

      if (onSignalingMessage) {
        onSignalingMessageRef.current = onSignalingMessage;
      }

      // Avoid duplicate connections
      if (isConnectingRef.current || wsRef.current?.readyState === WebSocket.OPEN) {
        return;
      }

      isConnectingRef.current = true;

      try {
        // FINAL WS URL (correct)
        const wsUrl =
          `${WS_BASE_URL}/meeting/rooms/${roomId}/ws` +
          `?user_id=${encodeURIComponent(userId)}` +
          `&username=${encodeURIComponent(username)}` +
          `&role=${encodeURIComponent(role)}` +
          `&password=${encodeURIComponent(cleanPassword || "")}`;

        console.log("🔌 Connecting to WebSocket:", wsUrl);
        console.log("➡️ Params Sent:", {
          roomId,
          userId,
          username,
          role,
          cleanPassword,
        });

        wsRef.current = new WebSocket(wsUrl);

        wsRef.current.onopen = () => {
          console.log("✅ WebSocket connected");
          setIsConnected(true);
          setError(null);
          reconnectAttempts.current = 0;
          isConnectingRef.current = false;

          // Start heartbeat
          if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = setInterval(() => {
            if (wsRef.current?.readyState === WebSocket.OPEN) {
              wsRef.current.send(JSON.stringify({ type: "ping" }));
            }
          }, PING_INTERVAL);
        };

        wsRef.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            setLastMessage(data);

            switch (data.type) {
              case "welcome":
              case "connected":
              case "connection_ack":
                setIsConnected(true);
                if (data.room_info?.participants)
                  setParticipants(data.room_info.participants);
                break;

              case "live_transcript":
                setTranscripts((prev) => [data, ...prev].slice(0, 100));
                break;

              case "participant_joined":
                setParticipants((prev) => {
                  const exists = prev.some((p) => p.user_id === data.user_id);
                  if (exists) return prev;

                  return [
                    ...prev,
                    {
                      user_id: data.user_id,
                      username: data.username,
                      role: data.role,
                      is_speaking: false,
                      is_muted: false,
                      is_video_on: true,
                      is_audio_on: true,
                    },
                  ];
                });
                break;

              case "participant_left":
                setParticipants((prev) =>
                  prev.filter((p) => p.user_id !== data.user_id)
                );
                break;

              case "participant_state_update":
                setParticipants((prev) =>
                  prev.map((p) =>
                    p.user_id === data.user_id
                      ? {
                          ...p,
                          is_speaking: data.is_speaking ?? p.is_speaking,
                          is_muted: data.is_muted ?? p.is_muted,
                          is_video_on: data.is_video_on ?? p.is_video_on,
                          is_audio_on: data.is_audio_on ?? p.is_audio_on,
                          emotion_state: data.emotion_state ?? p.emotion_state,
                        }
                      : p
                  )
                );
                break;

              case "active_speaker":
                setActiveSpeakerId(data.user_id);
                break;

              case "chat_message":
                setChatMessages((prev) => [...prev, data]);
                break;

              case "ping_timeout":
                wsRef.current?.send(JSON.stringify({ type: "ping" }));
                break;

              case "error":
                console.error("❌ WS Error:", data.message);
                setError(data.message);
                break;

              case "room_ended":
                setError("Meeting has ended");
                disconnect();
                break;

              case "new_participant":
              case "webrtc_offer":
              case "webrtc_answer":
              case "ice_candidate":
                if (onSignalingMessageRef.current) {
                  onSignalingMessageRef.current(data);
                }
                break;

              default:
                console.log("❓ Unknown WS message:", data);
            }
          } catch (err) {
            console.error("❌ WS message parse error:", err);
          }
        };

        wsRef.current.onerror = (event) => {
          console.error("❌ WebSocket error:", event);
          setError("WebSocket error");
          isConnectingRef.current = false;
        };

        wsRef.current.onclose = (event) => {
          console.log("🔌 WS closed:", event.code, event.reason);
          setIsConnected(false);
          isConnectingRef.current = false;

          if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);

          // reconnect
          if (event.code !== 1000 && reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
            reconnectAttempts.current++;
            const delay = Math.min(RECONNECT_DELAY * reconnectAttempts.current, 30000);
            console.log(`🔄 Reconnecting in ${delay}ms`);

            reconnectTimeoutRef.current = setTimeout(() => {
              connect(connectOptionsRef.current);
            }, delay);
          }
        };
      } catch (err) {
        console.error("❌ Failed to create WebSocket:", err);
        setError(err.message);
        isConnectingRef.current = false;
      }
    },
    [roomId, userId, username, cleanPassword, role]
  );

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);

    if (wsRef.current) {
      wsRef.current.close(1000, "User disconnected");
      wsRef.current = null;
    }

    setIsConnected(false);
    isConnectingRef.current = false;
  }, []);

  const sendMessage = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify(message));
        return true;
      } catch (err) {
        console.error("❌ Message send error:", err);
        return false;
      }
    }
    return false;
  }, []);

  const sendChatMessage = useCallback(
    (text) => sendMessage({ type: "chat", message: text }),
    [sendMessage]
  );

  const sendSignalingMessage = useCallback(
    (message) => sendMessage(message),
    [sendMessage]
  );

  const sendAudioChunk = useCallback(
    (audioData, sampleRate = 16000) =>
      sendMessage({
        type: "audio_chunk",
        audio_data: audioData,
        sample_rate: sampleRate,
      }),
    [sendMessage]
  );

  // Cleanup on unmount
  useEffect(() => disconnect, [disconnect]);

  return {
    isConnected,
    transcripts,
    participants,
    activeSpeakerId,
    chatMessages,
    error,
    lastMessage,
    connect,
    disconnect,
    sendMessage,
    sendSignalingMessage,
    sendAudioChunk,
    sendChatMessage,
  };
};
