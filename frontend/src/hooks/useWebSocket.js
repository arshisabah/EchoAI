import { useState, useEffect, useRef, useCallback } from 'react';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
const RECONNECT_DELAY = 3000;
const MAX_RECONNECT_ATTEMPTS = 5;
const PING_INTERVAL = 60000;

export const useWebSocket = (roomId, userId, username, password, role = 'participant') => {
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

    const connect = useCallback((options = {}) => {
        connectOptionsRef.current = options;
        const { onSignalingMessage } = options;

        // Store in ref to avoid stale closure during reconnection
        if (onSignalingMessage) {
            onSignalingMessageRef.current = onSignalingMessage;
        }

        // Prevent multiple simultaneous connection attempts
        if (isConnectingRef.current || wsRef.current?.readyState === WebSocket.OPEN) {
            return;
        }

        isConnectingRef.current = true;

        try {
            const wsUrl =
                `${WS_BASE_URL}/meeting/rooms/${roomId}/ws` +
                `?user_id=${encodeURIComponent(userId)}` +
                `&username=${encodeURIComponent(username)}` +
                `&role=${encodeURIComponent(role)}` +
                `&password=${encodeURIComponent(password || "")}`;
            console.log('🔌 Connecting to WebSocket:', wsUrl);
            console.log("🔥 WS URL:", wsUrl);
            console.log("🚀 WS PARAMS →", { roomId, userId, username, role, password });
            wsRef.current = new WebSocket(wsUrl);

            wsRef.current.onopen = () => {
                console.log('✅ WebSocket connected');
                setIsConnected(true);
                setError(null);
                reconnectAttempts.current = 0;
                isConnectingRef.current = false;

                // Start ping interval
                if (pingIntervalRef.current) {
                    clearInterval(pingIntervalRef.current);
                }
                pingIntervalRef.current = setInterval(() => {
                    if (wsRef.current?.readyState === WebSocket.OPEN) {
                        wsRef.current.send(JSON.stringify({ type: 'ping' }));
                    }
                }, PING_INTERVAL);
            };

            wsRef.current.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('🔍 WebSocket received:', data);
                    setLastMessage(data);

                    switch (data.type) {
                        case 'welcome':
                        case 'connected':
                        case 'connection_ack':
                            console.log('📩 Welcome:', data.message);
                            setIsConnected(true);
                            if (data.room_info?.participants) {
                                setParticipants(data.room_info.participants);
                            }
                            break;
                        
                        case 'final_transcript':
                        case 'live_transcript':
                            console.log('✅ Transcript received:', {
                                entry_id: data.entry_id,
                                username: data.username,
                                text: data.text?.substring(0, 50),
                                is_final: data.is_final,
                                emotion: data.emotion,
                                has_guidance: !!data.emotion_guidance?.suggestion
                            });
                            
                            // 🚀 INCREMENTAL UPDATES: Update existing entry or create new
                            setTranscripts((prev) => {
                                if (data.entry_id) {
                                    // Check if entry already exists
                                    const existingIndex = prev.findIndex(t => t.entry_id === data.entry_id);
                                    
                                    if (existingIndex !== -1) {
                                        // Update existing entry (preserve emotion & guidance if not provided)
                                        const updated = [...prev];
                                        const existing = updated[existingIndex];
                                        updated[existingIndex] = {
                                            ...existing,
                                            text: data.text,
                                            is_final: data.is_final,
                                            confidence: data.confidence || existing.confidence,
                                            timestamp: data.timestamp || existing.timestamp,
                                            emotion: data.emotion || existing.emotion,
                                            emotion_confidence: data.emotion_confidence ?? existing.emotion_confidence,
                                            emotion_guidance: data.emotion_guidance || existing.emotion_guidance
                                        };
                                        console.log('📝 Updated entry:', data.entry_id.substring(0, 8), '| emotion:', updated[existingIndex].emotion);
                                        return updated;
                                    }
                                }
                                
                                // New entry
                                console.log('🆕 New transcript entry with emotion:', data.emotion);
                                return [data, ...prev].slice(0, 100);
                            });
                            break;
                        
                        case 'emotion_update':
                            console.log('🎭 Emotion update received:', {
                                entry_id: data.entry_id,
                                emotion: data.emotion,
                                guidance: data.emotion_guidance
                            });
                            
                            // Update emotion for specific entry only (preserve other entries' guidance)
                            setTranscripts((prev) => {
                                const existingIndex = prev.findIndex(t => t.entry_id === data.entry_id);
                                if (existingIndex !== -1) {
                                    const updated = [...prev];
                                    updated[existingIndex] = {
                                        ...updated[existingIndex],
                                        emotion: data.emotion,
                                        emotion_confidence: data.emotion_confidence,
                                        emotion_guidance: data.emotion_guidance || updated[existingIndex].emotion_guidance
                                    };
                                    console.log('🎭 Emotion + guidance updated for entry:', data.entry_id.substring(0, 8));
                                    return updated;
                                }
                                console.warn('⚠️ Entry not found for emotion update:', data.entry_id);
                                return prev;
                            });
                            break;

                        case 'participant_joined':
                            console.log('👤 User joined:', data.username);
                            // ✅ FIX: Use full participant list from backend if available
                            if (data.participants && Array.isArray(data.participants)) {
                                console.log('📋 Updating participant list from backend:', data.participants.length, 'participants');
                                setParticipants(data.participants);
                            } else {
                                // Fallback: add participant manually
                                setParticipants((prev) => {
                                    const exists = prev.some(p => p.user_id === data.user_id);
                                    if (!exists) {
                                        return [...prev, {
                                            user_id: data.user_id,
                                            username: data.username,
                                            role: data.role,
                                            is_speaking: false,
                                            is_muted: false,
                                            is_video_on: false,  // ✅ FIX: Match backend default
                                            is_audio_on: true
                                        }];
                                    }
                                    return prev;
                                });
                            }
                            break;

                        case 'participant_left':
                            console.log('👋 User left:', data.username);
                            setParticipants((prev) => prev.filter(p => p.user_id !== data.user_id));
                            break;

                        case 'participant_state_update':
                            setParticipants((prev) =>
                                prev.map(p =>
                                    p.user_id === data.user_id
                                        ? {
                                            ...p,
                                            is_speaking: data.is_speaking ?? p.is_speaking,
                                            is_muted: data.is_muted ?? p.is_muted,
                                            is_video_on: data.is_video_on ?? p.is_video_on,
                                            is_audio_on: data.is_audio_on ?? p.is_audio_on,
                                            emotion_state: data.emotion_state ?? p.emotion_state
                                        }
                                        : p
                                )
                            );
                            break;

                        case 'active_speaker':
                            setActiveSpeakerId(data.user_id);
                            break;

                        case 'ping_timeout':
                            console.log('💓 Ping timeout — sending heartbeat back');
                            wsRef.current?.send(JSON.stringify({ type: 'ping' }));
                            break;

                        case 'chat_message':
                            setChatMessages((prev) => [...prev, data]);
                            break;

                        case 'room_ended':
                            console.log('🛑 Room ended by:', data.ended_by);
                            setError('Meeting has ended');
                            disconnect();
                            break;

                        case 'pong':
                            // Heartbeat response
                            break;

                        case 'error':
                            console.error('❌ Server error:', data.message);
                            setError(data.message);
                            break;

                        case 'listening':
                            console.log(`🎧 Listening... buffered ${data.buffered_duration}s`);
                            break;

                        case 'ready_for_audio':
                            console.log('🎵 Server ready to receive audio - streaming enabled:', data.streaming_enabled);
                            break;

                        case 'peer_list':
                            // ✅ FIX: Handle peer_list to initiate WebRTC connections with existing participants
                            console.log('👥 Received peer list:', data.peers);
                            if (onSignalingMessageRef.current && data.peers) {
                                // Treat each existing peer as a new_participant so WebRTC connections are established
                                data.peers.forEach(peer => {
                                    console.log(`🤝 Initiating connection with existing peer: ${peer.username} (${peer.user_id})`);
                                    onSignalingMessageRef.current({
                                        type: 'new_participant',
                                        user_id: peer.user_id,
                                        username: peer.username,
                                        from_peer_list: true
                                    });
                                });
                            }
                            break;

                        case 'new_participant':
                        case 'webrtc_offer':
                        case 'webrtc_answer':
                        case 'ice_candidate':
                            if (onSignalingMessageRef.current) {
                                onSignalingMessageRef.current(data);
                            }
                            break;

                        default:
                            console.log('📨 Unknown message type:', data.type, data);
                    }
                } catch (err) {
                    console.error('❌ Error parsing message:', err);
                }
            };

            wsRef.current.onerror = (event) => {
                console.error('❌ WebSocket error:', event);
                setError('Connection error occurred');
                isConnectingRef.current = false;
            };

            wsRef.current.onclose = (event) => {
                console.log('🔌 WebSocket closed:', event.code, event.reason);
                setIsConnected(false);
                isConnectingRef.current = false;

                // Clear ping interval
                if (pingIntervalRef.current) {
                    clearInterval(pingIntervalRef.current);
                    pingIntervalRef.current = null;
                }

                // Attempt reconnection if not intentional
                if (event.code !== 1000 && reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
                    reconnectAttempts.current++;
                    const delay = Math.min(RECONNECT_DELAY * reconnectAttempts.current, 30000);
                    console.log(`🔄 Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current}/${MAX_RECONNECT_ATTEMPTS})`);

                    reconnectTimeoutRef.current = setTimeout(() => {
                        connect(connectOptionsRef.current);
                    }, delay);
                } else if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
                    setError('Failed to connect after multiple attempts. Please refresh the page.');
                }
            };
        } catch (err) {
            console.error('❌ Error creating WebSocket:', err);
            setError(err.message);
            isConnectingRef.current = false;
        }
    }, [roomId, userId, username, password, role]);

    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }

        if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current);
            pingIntervalRef.current = null;
        }

        if (wsRef.current) {
            wsRef.current.close(1000, 'User disconnected');
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
                console.error('❌ Error sending message:', err);
                return false;
            }
        } else {
            console.warn('⚠️ WebSocket not connected, cannot send message');
            return false;
        }
    }, []);

    const sendAudioChunk = useCallback((audioData, sampleRate = 16000) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) {
            console.warn('⚠️ Cannot send audio - WebSocket not connected');
            return false;
        }

        // Convert Uint8Array to base64 for JSON transmission
        // Use chunks to avoid call stack issues with large arrays
        let binaryString = '';
        const chunkSize = 8192;
        for (let i = 0; i < audioData.length; i += chunkSize) {
            const chunk = audioData.subarray(i, Math.min(i + chunkSize, audioData.length));
            binaryString += String.fromCharCode.apply(null, chunk);
        }
        const base64Audio = btoa(binaryString);
        
        console.log('🎤 Sent audio chunk:', audioData.length, 'bytes');
        
        return sendMessage({
            type: 'audio_chunk',
            audio_data: base64Audio,
            sample_rate: sampleRate,
            is_final: false
        });
    }, [sendMessage]);

    const sendChatMessage = useCallback((messageText) => {
        return sendMessage({
            type: 'chat',
            message: messageText,
        });
    }, [sendMessage]);

    const sendSignalingMessage = useCallback((message) => {
        return sendMessage(message);
    }, [sendMessage]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            disconnect();
        };
    }, [disconnect]);

    return {
        isConnected,
        isTranscriptConnected: isConnected, // Same connection handles transcription
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