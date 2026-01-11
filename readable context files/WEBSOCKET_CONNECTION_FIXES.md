# WebSocket Connection & Video Stream Fixes

## Issues Fixed

### 1. WebSocket Reconnection Loop
**Problem:** Same client creating multiple WebSocket connections, causing session replacement and Faster-Whisper disruption.

**Root Causes:**
- Missing cleanup in MeetingRoom.jsx useEffect
- Missing dependency array caused re-initialization
- Insufficient connection state validation

**Fixes Applied:**
- ✅ Added cleanup function to disconnect WebSocket on component unmount
- ✅ Added proper dependency array to prevent unnecessary re-runs
- ✅ Enhanced connection state checks in useWebSocket.js:
  - Check for CONNECTING state
  - Better logging for connection attempts
  - Prevent concurrent connection attempts

### 2. Remote Video Streams Not Displaying
**Problem:** Backend successfully broadcasting video frames but frontend not showing remote video.

**Root Causes:**
- Remote streams with inactive tracks being passed to video elements
- Missing validation for track readyState

**Fixes Applied:**
- ✅ Enhanced stream validation in VideoGrid.jsx:
  - Check stream has tracks
  - Verify tracks are in 'live' state
  - Filter out invalid streams before rendering
  - Added comprehensive logging

### 3. Recording Start Logic
**Problem:** Recording might start multiple times due to effect dependencies.

**Fix Applied:**
- ✅ Added `startRecording` to dependency array to prevent stale closures

## Files Modified

### 1. `frontend/src/components/MeetingRoom.jsx`
```javascript
// Before:
useEffect(() => {
  loadRoom();
}, [roomId]);

// After:
useEffect(() => {
  loadRoom();
  
  return () => {
    console.log("🧹 Component unmounting - cleaning up WebSocket");
    disconnect();
  };
}, [roomId, connect, disconnect, handleSignalingMessage, userInfo.username, navigate]);

// Recording effect fix:
}, [isConnected, isServerReady, isRecording, startRecording]);
```

### 2. `frontend/src/hooks/useWebSocket.js`
```javascript
// Enhanced connection state checks:
if (isConnectingRef.current) {
  console.warn('⚠️ Connection attempt already in progress, skipping');
  return;
}

if (wsRef.current?.readyState === WebSocket.OPEN) {
  console.warn('⚠️ WebSocket already connected, skipping new connection');
  return;
}

if (wsRef.current?.readyState === WebSocket.CONNECTING) {
  console.warn('⚠️ WebSocket connection in progress, skipping');
  return;
}

isConnectingRef.current = true;
console.log('🔌 Starting new WebSocket connection...');
```

### 3. `frontend/src/components/Meeting/VideoGrid.jsx`
```javascript
// Enhanced stream validation:
const hasValidTracks = remoteStream && 
  remoteStream.getTracks().length > 0 &&
  remoteStream.getTracks().some(track => track.readyState === 'live');

if (!remoteStream) {
  console.warn(`⚠️ No remote stream found for participant ${p.username}`);
} else if (!hasValidTracks) {
  console.warn(`⚠️ Remote stream for ${p.username} has no valid tracks`);
} else {
  console.log(`✅ Valid remote stream for ${p.username}:`, {
    streamId: remoteStream.id,
    tracks: remoteStream.getTracks().map(t => `${t.kind}:${t.readyState}`)
  });
}

return {
  user_id: p.user_id,
  username: p.username,
  stream: hasValidTracks ? remoteStream : null,
  isLocal: false,
  isMuted: !p.is_audio_on,
  isVideoOff: !p.is_video_on
};
```

## Testing Checklist

### Single Device Tests
- [ ] Open meeting room
- [ ] Check console - should see ONE WebSocket connection
- [ ] No "Replacing existing connection" warnings in backend logs
- [ ] Video preview shows your camera
- [ ] Audio recording starts automatically

### Multi-Device Tests (2+ devices)
- [ ] Join from Device A
- [ ] Join from Device B
- [ ] Both devices show "2 participants"
- [ ] **Critical:** Check if you can see other participant's video
- [ ] Check backend logs - no connection replacement warnings
- [ ] Verify Faster-Whisper sessions remain active

### Video Stream Validation
- [ ] Remote video elements should have srcObject assigned
- [ ] Console shows "✅ Valid remote stream for [username]"
- [ ] No "⚠️ Remote stream has no valid tracks" warnings
- [ ] Video frames visible in UI

### Transcription Tests
- [ ] Speak on Device A - transcription appears
- [ ] Speak on Device B - transcription appears
- [ ] Toggle mic off - recording stops
- [ ] Toggle mic on - recording resumes
- [ ] No "session is now inactive" in backend logs

## Expected Console Output

### Good Connection (Single Client)
```
🔌 Starting new WebSocket connection...
🔌 Connecting to WebSocket: wss://172.20.89.15:5173/ws/meeting/rooms/test/ws?...
✅ WebSocket connected
📩 Welcome: Connected to room test
🎥 Initializing camera and microphone...
✅ Local media initialized successfully
🎧 Starting transcription recording...
🎵 Server ready to receive audio
```

### Bad Connection (Multiple Replacements)
```
⚠️ Connection attempt already in progress, skipping
WARNING: Replacing existing connection for client_id: ...
INFO: Faster-Whisper session for ... is now inactive
```

### Good Remote Video
```
📹 ontrack fired for peer abc123
✅ Remote stream received from peer abc123
📺 Updated remote streams map, now has 1 streams
✅ Valid remote stream for John: { streamId: "...", tracks: ["video:live", "audio:live"] }
📺 Setting video srcObject for John
```

### Bad Remote Video
```
⚠️ No remote stream found for participant John
⚠️ Remote stream for John has no valid tracks
```

## Backend Log Monitoring

### Healthy Session
```
INFO: ('172.20.89.15', 57286) - "WebSocket /meeting/rooms/test/ws" [accepted]
INFO: Faster-Whisper session started for client_id: c7d5eb47...
INFO: Received video_frame from c7d5eb47... (776 bytes)
INFO: Broadcasting video frame to 1 other clients
```

### Problematic Session (SHOULD NOT SEE THIS ANYMORE)
```
WARNING: Replacing existing connection for client_id: 2b4879b4...
INFO: Faster-Whisper session for 2b4879b4... is now inactive
ERROR: WebSocket is not connected. Need to call 'accept' first
```

## Troubleshooting

### If WebSocket Still Reconnecting
1. Check browser console for multiple "🔌 Starting new WebSocket connection" messages
2. Verify no React StrictMode wrapping (causes double renders in dev)
3. Check if component is mounting/unmounting unexpectedly
4. Look for navigation/route changes triggering re-mounts

### If Remote Video Not Showing
1. Check console for "✅ Valid remote stream" messages
2. Verify "📹 ontrack fired for peer" events
3. Inspect video element in DevTools - check if srcObject is set
4. Look for track readyState (should be 'live', not 'ended')
5. Check backend logs for "Broadcasting video frame" messages

### If Transcription Stops Working
1. Check for "session is now inactive" in backend logs
2. Verify no WebSocket reconnections happening
3. Check if "🎵 Server ready to receive audio" message appears
4. Verify mic toggle state matches recording state
5. Look for "🎵 Sending audio chunk" messages in console

## Additional Improvements Needed

### Backend (Future Enhancement)
The backend should ideally:
1. **Reuse Faster-Whisper sessions** on connection replacement instead of marking inactive
2. **Maintain session by client_id** not connection object
3. **Graceful session migration** when connections are replaced
4. **Add connection lifecycle logging** with client_id tracking

### Frontend (Future Enhancement)
1. Add connection state indicator in UI
2. Implement reconnection notifications
3. Add video stream health monitoring
4. Better error recovery for failed connections

## Success Criteria

✅ **Single WebSocket connection per client**
- No "Replacing existing connection" warnings
- One stable connection throughout session

✅ **Remote video visible between all participants**
- Video elements have valid srcObject
- Tracks are in 'live' state
- No placeholder avatars when video should be showing

✅ **Transcription works continuously**
- No "session is now inactive" messages
- Audio chunks being sent and processed
- Faster-Whisper sessions remain active

✅ **Mic toggle controls recording**
- Recording stops when mic disabled
- Recording resumes when mic enabled
- State synchronized between WebRTC and transcription

## Next Steps

1. **Test the fixes:**
   ```bash
   # Start backend
   cd backend
   python -m app.main
   
   # Start frontend (in new terminal)
   cd frontend
   npm run dev
   ```

2. **Monitor logs carefully:**
   - Backend: Watch for "Replacing existing connection" warnings
   - Frontend console: Look for connection state messages
   - Check video stream validation messages

3. **Multi-device test:**
   - Join from 2-3 devices
   - Verify video visibility
   - Test transcription on all devices
   - Check connection stability

4. **If issues persist:**
   - Capture full console logs from frontend
   - Capture backend logs with timestamps
   - Note exact sequence of events leading to problem
   - Check for any React errors or warnings
