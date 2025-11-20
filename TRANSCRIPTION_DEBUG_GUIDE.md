# Transcription Debug Guide

## Overview
This guide helps diagnose and verify that the transcription pipeline is working correctly from audio input to frontend display.

## Testing Instructions

### 1. Backend Startup

Start the backend server:
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend Startup

Start the frontend dev server:
```bash
cd frontend
npm run dev
```

### 3. Test WebSocket Connectivity (Emergency Fallback)

If transcription doesn't appear, first verify WebSocket is working:

```bash
# Replace YOUR_ROOM_ID with your actual room ID
curl -X POST http://localhost:8000/meeting/rooms/YOUR_ROOM_ID/test-broadcast
```

Expected response:
```json
{
  "status": "Test broadcast sent",
  "room_id": "YOUR_ROOM_ID",
  "message": {
    "type": "live_transcript",
    "user_id": "test_user",
    "username": "Test User",
    "text": "This is a test transcript to verify WebSocket is working",
    ...
  }
}
```

**What to check in browser console:**
- `🔍 WebSocket received:` with the test message
- `📝 Adding transcript:` with the test text
- The test transcript should appear in the Transcript panel

### 4. Test Real Transcription

1. **Join a meeting room** in the browser
2. **Open Browser DevTools** (F12)
3. **Navigate to Console tab**
4. **Speak into microphone** for 3-4 seconds
5. **Watch for logs**

#### Expected Backend Logs (Terminal)

When audio is received:
```
✅ Decoded audio chunk from <username>: XXXX bytes
🔧 Calling orchestrator for room <room_id>, user <username> with XXXX bytes
```

When orchestrator processes:
```
✅ Orchestrator returned result for room <room_id>: dict
🔍 DEBUG - Full result from orchestrator: {
  "text": "your transcribed text",
  "speaker": "user_id",
  "emotion": "neutral",
  ...
}
🔍 DEBUG - Result keys: ['text', 'speaker', 'emotion', ...]
📋 Single entry result: 'your transcribed text...'
```

When broadcasting:
```
📢 Broadcasting transcript from <username> in <room_id>: 'your text...'
🔊 ABOUT TO BROADCAST:
   - room_id: <room_id>
   - user_id: <user_id>
   - username: <username>
   - text: 'your transcribed text...'
   - emotion: neutral
📡 broadcast_transcript called for room <room_id>, user <username>
📤 Broadcasting message to 2 participants: {...}
✅ Broadcast complete to room <room_id>
✅ BROADCAST COMPLETED for <username>
```

#### Expected Frontend Logs (Browser Console)

```
🎤 Sent audio chunk: XXXX bytes
🔍 WebSocket received: {type: "listening", buffered_duration: 1.5, ...}
🔍 WebSocket received: {type: "live_transcript", text: "your text", ...}
📝 Adding transcript: your text
```

### 5. Troubleshooting

#### No Backend Logs at All
- **Issue**: Audio not reaching backend
- **Check**: 
  - Microphone permissions granted?
  - WebSocket connected? (Check browser console for "✅ WebSocket connected")
  - Audio recording started? (Check for microphone icon)

#### Backend Receives Audio but No Orchestrator Result
- **Issue**: Orchestrator not processing
- **Check**:
  - Look for "⚠️ No result from orchestrator" in backend logs
  - Check if WhisperX or transcription model is loaded
  - Look for errors in orchestrator initialization

#### Orchestrator Returns Result but No Broadcast
- **Issue**: Result parsing or broadcast failure
- **Check**:
  - Look for "❌ No valid entries extracted" in backend logs
  - Look for "⚠️ Unexpected result structure" warnings
  - Check the "🔍 DEBUG - Full result" log to see exact structure
  - Verify room exists: "❌ Room XXX not found in rooms dict"

#### Backend Broadcasts but Frontend Doesn't Show
- **Issue**: WebSocket not receiving or handling messages
- **Check**:
  - Browser console shows "🔍 WebSocket received:" messages?
  - Look for "📝 Adding transcript:" messages
  - Check Network tab → WS → Messages to see raw WebSocket traffic
  - Verify `isTranscriptConnected` is true

### 6. Log Markers Reference

| Emoji | Meaning | Location |
|-------|---------|----------|
| 🔧 | Orchestrator call | meeting.py |
| ✅ | Success operation | All files |
| 🔍 | Debug information | meeting.py, useWebSocket.js |
| 📋 | Result parsing | meeting.py |
| 📢 | Starting broadcast | meeting.py |
| 🔊 | Broadcast details | meeting.py |
| 📡 | Broadcast method called | meeting_room_manager.py |
| 📤 | Broadcasting message | meeting_room_manager.py |
| 📝 | Frontend adding transcript | useWebSocket.js |
| ❌ | Error or failure | All files |
| ⚠️ | Warning | All files |

### 7. Common Issues and Solutions

#### Issue: "No valid entries extracted"
**Solution**: The orchestrator returned a result but it doesn't have a "text" field. Check the orchestrator output format.

#### Issue: "Room XXX not found in rooms dict"
**Solution**: The room was removed or never created. Check room creation and ensure users join properly.

#### Issue: WebSocket receives messages but transcript doesn't appear
**Solution**: Check the TranscriptPanel component is rendering and the transcripts array is being populated.

### 8. Success Criteria

✅ Backend logs show:
- `✅ Orchestrator returned result`
- `📋 Single entry result: 'text...'`
- `🔊 ABOUT TO BROADCAST`
- `✅ BROADCAST COMPLETED`

✅ Browser console shows:
- `🔍 WebSocket received: {type: "live_transcript", ...}`
- `📝 Adding transcript: your text`

✅ UI displays:
- Transcribed text appears in Transcript panel
- Emotion badge shows next to transcript
- Speaker name is correct

## Running Unit Tests

```bash
cd backend
python -m pytest tests/test_transcription_broadcast.py -v
```

Expected: All 4 tests pass ✅

## Security Note

All changes have been validated with CodeQL and show 0 security alerts.
