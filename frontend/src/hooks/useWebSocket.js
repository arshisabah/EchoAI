import { useState, useEffect, useRef, useCallback } from 'react';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export const useWebSocket = (roomId, userId, username, password = null, role = 'participant') => {
  const [isConnected, setIsConnected] = useState(false);
  const [transcripts, setTranscripts] = useState([]);
  const [participants, setParticipants] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [error, setError] = useState(null);
  const [lastMessage, setLastMessage] = useState(null);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    try {
      const wsUrl = `${WS_BASE_URL}/meeting/rooms/${roomId}/ws?user_id=${userId}&username=${encodeURIComponent(username)}&role=${role}${password ? `&password=${password}` : ''}`;
      
      console.log('Connecting to WebSocket:', wsUrl);
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('✅ WebSocket connected');
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
        
        sendMessage({ type: 'ping' });
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('WebSocket message:', data.type);
          
          setLastMessage(data);

          switch (data.type) {
            case 'welcome':
            case 'connected':
              console.log('Welcome message:', data.message);
              break;

            case 'live_transcript':
              setTranscripts((prev) => [data, ...prev].slice(0, 100));
              break;

            case 'participant_joined':
              setParticipants((prev) => {
                if (!prev.some(p => p.user_id === data.user_id)) {
                  return [...prev, { 
                    user_id: data.user_id, 
                    username: data.username, 
                    role: data.role,
                    is_speaking: false,
                    is_muted: false
                  }];
                }
                return prev;
              });
              break;

            case 'participant_left':
              setParticipants((prev) => prev.filter(p => p.user_id !== data.user_id));
              break;

            case 'participant_state_update':
              setParticipants((prev) =>
                prev.map(p =>
                  p.user_id === data.user_id
                    ? { ...p, is_speaking: data.is_speaking, is_muted: data.is_muted }
                    : p
                )
              );
              break;

            case 'chat_message':
              setChatMessages((prev) => [...prev, data]);
              break;

            case 'room_ended':
              console.log('Room ended by:', data.ended_by);
              disconnect();
              break;

            case 'pong':
              console.log('Pong received');
              break;

            case 'error':
              console.error('WebSocket error message:', data.message);
              setError(data.message);
              break;

            default:
              console.log('Unknown message type:', data.type);
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      wsRef.current.onerror = (event) => {
        console.error('WebSocket error:', event);
        setError('WebSocket connection error');
      };

      wsRef.current.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setIsConnected(false);

        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++;
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current}/${maxReconnectAttempts})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else {
          setError('Failed to connect after multiple attempts');
        }
      };
    } catch (err) {
      console.error('Error creating WebSocket:', err);
      setError(err.message);
    }
  }, [roomId, userId, username, password, role]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    } else {
      console.warn('WebSocket not connected, cannot send message');
      return false;
    }
  }, []);

  const sendAudioChunk = useCallback((audioData, sampleRate = 16000) => {
    return sendMessage({
      type: 'audio_chunk',
      audio_data: audioData,
      sample_rate: sampleRate,
    });
  }, [sendMessage]);

  const sendChatMessage = useCallback((messageText) => {
    return sendMessage({
      type: 'chat',
      message: messageText,
    });
  }, [sendMessage]);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  useEffect(() => {
    if (!isConnected) return;

    const pingInterval = setInterval(() => {
      sendMessage({ type: 'ping' });
    }, 30000);

    return () => clearInterval(pingInterval);
  }, [isConnected, sendMessage]);

  return {
    isConnected,
    transcripts,
    participants,
    chatMessages,
    error,
    lastMessage,
    connect,
    disconnect,
    sendMessage,
    sendAudioChunk,
    sendChatMessage,
  };
};