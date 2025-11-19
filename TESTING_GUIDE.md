# EchoAI Testing Guide

## Testing the Fixes for Transcription and Video Issues

This guide helps you verify that the transcription and video streaming issues have been resolved.

---

## Prerequisites

1. **Backend Setup**:
   - Ensure `OPENAI_API_KEY` is set in your environment (for transcription)
   - Backend should be running on `http://localhost:8000`

2. **Frontend Setup**:
   - Frontend should be running on `http://localhost:5173`
   - Check that `VITE_WS_URL` points to `ws://localhost:8000`

3. **Browser Requirements**:
   - Use Chrome, Firefox, or Edge (latest versions)
   - Grant camera and microphone permissions when prompted
   - Open browser console (F12) to monitor logs

---

## Test Scenario 1: Transcription Logging

**Objective**: Verify that audio chunks are being processed and transcribed

### Steps:

1. Start the backend:
   ```bash
   cd backend
   python -m app.main
   ```

2. Watch the backend logs - you should see:
   ```
   ✅ OrchestratorService initialized
   ✅ TranscriptionService initialized
   ```

3. Open the frontend and create a meeting room

4. Join the room and speak into your microphone

5. **Expected Backend Logs**:
   ```
   🎵 Processing audio chunk - session: <room_id>, participant: <user_id>, bytes: XXXX
   ⏳ Buffering audio for session <room_id>: X.XXs / 1.5s minimum
   🎙️ Starting transcription for session <room_id> - X.XXs audio (XXXX samples)
   🌐 Calling OpenAI Whisper API - audio length: XXXX samples
   ✅ OpenAI API response received: 'your spoken text...'
   📝 Transcription complete for session <room_id> - 1 result(s)
   💬 Transcribed text for session <room_id>: 'your spoken text...'
   ```

6. **Expected Frontend Logs** (in browser console):
   ```
   🎵 Sending audio chunk: XXXX bytes
   📨 Received message: live_transcript
   ```

### Success Criteria:
- ✅ Backend logs show audio chunks being received
- ✅ Backend logs show transcription API calls
- ✅ Transcripts appear in the UI within 2-5 seconds of speaking
- ✅ No errors in backend or frontend logs

---

## Test Scenario 2: Multi-User Video Streaming

**Objective**: Verify that users can see each other's video streams

### Steps:

1. Open **two browser windows** (or use incognito mode for the second)

2. **User 1** (First Window):
   - Create a new meeting room
   - Note the room name
   - Grant camera/microphone permissions
   - Wait for connection

3. **User 2** (Second Window):
   - Join the same room using the room name
   - Grant camera/microphone permissions

4. **Expected Frontend Logs for User 1**:
   ```
   📡 WebRTC signaling: new_participant from <user2_id>
   🔧 Creating new peer connection for <user2_id>
   📤 Adding 2 local tracks to peer connection for <user2_id>
   📤 Sent WebRTC offer to peer <user2_id>
   📨 Received WebRTC answer from <user2_id>
   🧊 ICE candidate generated for peer <user2_id>
   🔗 Connection state changed for peer <user2_id>: connected
   📹 ontrack fired for peer <user2_id>
   ✅ Remote stream received from peer <user2_id>
   ```

5. **Expected Frontend Logs for User 2**:
   ```
   👥 Received peer list: [{ user_id: <user1_id>, username: ... }]
   🤝 Initiating connection with existing peer: <user1_name>
   🔧 Creating new peer connection for <user1_id>
   📤 Sent WebRTC offer to peer <user1_id>
   📨 Received WebRTC answer from <user1_id>
   🔗 Connection state changed for peer <user1_id>: connected
   📹 ontrack fired for peer <user1_id>
   ✅ Remote stream received from peer <user1_id>
   ```

6. **Expected Backend Logs**:
   ```
   ✅ <user1> joined <room_id> as participant
   📡 WebRTC signaling: webrtc_offer from <user1_id> to <user2_id>
   ✅ Forwarded webrtc_offer from <user1> to <user2_id>
   📡 WebRTC signaling: webrtc_answer from <user2_id> to <user1_id>
   ✅ Forwarded webrtc_answer from <user2> to <user1_id>
   ```

### Success Criteria:
- ✅ User 1 sees User 2's video tile with live video
- ✅ User 2 sees User 1's video tile with live video
- ✅ Both users see their own video (local preview)
- ✅ Video tiles show correct usernames
- ✅ Console shows "connected" state for peer connections
- ✅ No WebRTC errors in console

---

## Test Scenario 3: Historical Transcripts

**Objective**: Verify that newly joined users see previous transcripts

### Steps:

1. **User 1**: Create and join a room
2. **User 1**: Speak several sentences (wait for transcripts to appear)
3. **User 2**: Join the same room
4. **User 2**: Check the transcript panel

### Expected Behavior:
- ✅ User 2 sees all transcripts that occurred before they joined
- ✅ Transcripts are marked with correct speaker names
- ✅ Transcripts appear in chronological order

### Expected Backend Logs:
```
📜 Sending X historical transcripts to <user2_name>
✅ Historical transcripts sent to <user2_name>
```

---

## Test Scenario 4: Screen Sharing

**Objective**: Verify screen sharing works

### Steps:

1. Join a meeting room (can be solo or with another user)
2. Click the screen share button (Monitor icon)
3. Select a window/screen to share
4. Verify the local video switches to screen content
5. Click screen share button again to stop
6. Verify video switches back to camera

### Expected Logs:
```
🖥️ Starting screen share
✅ Screen share started successfully
🛑 Stopping screen share
✅ Screen share stopped
```

### Success Criteria:
- ✅ Screen share starts without errors
- ✅ Other users see the shared screen (if in multi-user test)
- ✅ Stopping screen share restores camera feed
- ✅ No tracks are left open after stopping

---

## Troubleshooting

### Transcription Not Working

**Check Backend Logs for:**
- `❌ No transcription backend available` → OpenAI API key not set
- `❌ OpenAI API transcription failed: 401` → Invalid API key
- `⚠️ Empty transcription result` → Audio quality too low or silence
- `🔇 Skipping silence` → Voice Activity Detection blocking audio

**Solutions:**
1. Verify `OPENAI_API_KEY` is set correctly
2. Check microphone is working and not muted
3. Speak louder or closer to microphone
4. Check browser microphone permissions

### Video Not Visible

**Check Frontend Console for:**
- `⚠️ No stream available for <username>` → WebRTC connection failed
- `❌ Connection failed for peer <id>` → Network/firewall issue
- `⚠️ No local stream available when creating peer connection` → Camera not started

**Check Backend Logs for:**
- `⚠️ Target <user_id> not found in room` → Signaling routing issue
- `❌ Failed to forward webrtc_offer` → WebSocket connection broken

**Solutions:**
1. Ensure both users have granted camera permissions
2. Check that WebSocket connection is established (`isConnected: true`)
3. Try refreshing the page and rejoining
4. Check firewall/antivirus is not blocking WebRTC
5. Try using Chrome (best WebRTC support)

### Audio Chunks Not Sent

**Check Frontend Console for:**
- `⚠️ Audio chunk dropped - WebSocket not connected` → Connection issue
- Verify `isTranscriptConnected: true` in logs

**Solutions:**
1. Wait for WebSocket to fully connect before speaking
2. Check network connection
3. Restart frontend and try again

---

## Log Interpretation Guide

### Good Signs:
- ✅ `Starting transcription for session`
- ✅ `WebRTC connection established with peer`
- ✅ `Remote stream received from peer`
- ✅ `Transcription complete for session`

### Warning Signs (Non-Critical):
- ⏳ `Buffering audio` → Normal, waiting for enough audio
- 🔇 `Skipping silence` → Normal, no speech detected
- ⚠️ `No voice activity detected` → Normal if not speaking

### Error Signs (Need Attention):
- ❌ `OpenAI API transcription failed`
- ❌ `Failed to create peer connection`
- ❌ `WebSocket error`
- ❌ `No transcription backend available`

---

## Performance Benchmarks

### Expected Transcription Latency:
- Audio buffering: 1.5-3 seconds
- OpenAI API call: 0.5-2 seconds
- **Total latency**: 2-5 seconds from speaking to transcript appearance

### Expected WebRTC Connection Time:
- Offer/Answer exchange: 100-500ms
- ICE candidate exchange: 500-2000ms
- **Total connection time**: 1-3 seconds to see remote video

---

## Summary

If all test scenarios pass:
- ✅ Transcription is working with proper logging
- ✅ Multi-user video streaming is functional
- ✅ Historical transcripts are sent to new users
- ✅ Screen sharing is operational
- ✅ All major issues have been resolved

**If any test fails, review the troubleshooting section and check logs for specific error messages.**
