# EchoAI v3.0 Quick Reference Guide

## New API Endpoints

### Meeting Recording
```bash
# Download recording
GET /meeting/rooms/{room_id}/recording/download
→ Returns: WAV file (audio/wav)

# Get recording metadata
GET /meeting/rooms/{room_id}/recording/metadata
→ Returns: JSON with duration, participant count, timestamps
```

### Transcript Download
```bash
# Download transcript (default: txt)
GET /meeting/rooms/{room_id}/transcript/download?format=txt
GET /meeting/rooms/{room_id}/transcript/download?format=json
GET /meeting/rooms/{room_id}/transcript/download?format=srt
→ Returns: Transcript in requested format
```

### Analytics
```bash
# List all sessions (fixed 404)
GET /analytics/sessions/list
GET /analytics/sessions  # Alternative endpoint
→ Returns: Array of session summaries

# Detailed session analytics
GET /analytics/session/{session_id}/detailed
→ Returns: Full analytics with emotions and patterns

# Emotion timeline
GET /analytics/session/{session_id}/emotions
→ Returns: Emotion distribution and timeline
```

## Key Changes Summary

### WebSocket
- **Timeout**: 30s → **180s** (3 minutes)
- **Keep-alive**: Automatic ping every 180s
- **Connection**: `ws://localhost:8000/meeting/rooms/{room_id}/ws`

### Voice Activity Detection (VAD)
- Energy-based detection (RMS > 0.01)
- Zero-crossing rate filtering (0.01 - 0.5)
- Silence boundary detection (1.5s threshold)

### Audio Buffering
- **Minimum**: 4 seconds before processing
- **Maximum**: 8 seconds with silence check
- **Silence**: 1.5s of silence triggers processing

### Recording Format
- **Format**: WAV
- **Sample Rate**: 16000 Hz
- **Channels**: 1 (mono)
- **Bit Depth**: 16-bit
- **Encoding**: PCM

## Code Examples

### Python: Download Recording
```python
import requests

room_id = "my-meeting-room"
response = requests.get(
    f"http://localhost:8000/meeting/rooms/{room_id}/recording/download"
)

with open(f"{room_id}.wav", "wb") as f:
    f.write(response.content)
```

### Python: Download Transcript (JSON)
```python
import requests
import json

room_id = "my-meeting-room"
response = requests.get(
    f"http://localhost:8000/meeting/rooms/{room_id}/transcript/download",
    params={"format": "json"}
)

transcript = json.loads(response.content)
for entry in transcript["transcript"]:
    print(f"{entry['speaker']}: {entry['text']}")
```

### JavaScript: WebSocket with Keep-Alive
```javascript
const ws = new WebSocket(
  `ws://localhost:8000/meeting/rooms/my-room/ws?user_id=user123&username=John`
);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'ping_timeout':
      // Keep-alive received - connection is healthy
      console.log('Keep-alive ping received');
      break;
    case 'transcript_entry':
      // New transcript received
      console.log(`${data.speaker}: ${data.text}`);
      break;
  }
};

// Send audio chunks
function sendAudio(audioBase64) {
  ws.send(JSON.stringify({
    type: 'audio_chunk',
    audio_data: audioBase64
  }));
}
```

### Curl: Get Analytics
```bash
# List all sessions
curl http://localhost:8000/analytics/sessions/list

# Get session details
curl http://localhost:8000/analytics/session/my-room/detailed

# Get emotions
curl http://localhost:8000/analytics/session/my-room/emotions
```

## Module Structure

```
backend/app/
├── modules/
│   └── audio_recorder.py          # NEW: Recording functionality
├── services/
│   ├── audio_mixer.py            # NEW: Audio mixing
│   ├── orchestrator_service.py   # UPDATED: Session management
│   └── transcription_service.py  # UPDATED: Enhanced VAD
└── routers/
    ├── meeting.py                # UPDATED: Recording endpoints
    └── analytics.py              # UPDATED: Sessions list alias
```

## Configuration Quick Reference

### WebSocket Timeout
File: `backend/app/routers/meeting.py`
```python
# Line ~631
data = await asyncio.wait_for(websocket.receive_text(), timeout=180)
```

### VAD Energy Threshold
File: `backend/app/services/transcription_service.py`
```python
# Line ~93
energy_threshold = 0.01  # Lower = more sensitive
```

### Silence Detection Duration
File: `backend/app/services/orchestrator_service.py`
```python
# Line ~149
tail_samples = min(int(16000 * 1.5), len(combined))  # 1.5s silence
```

### Audio Buffer Duration
File: `backend/app/services/orchestrator_service.py`
```python
# Line ~144
if duration_sec < 4.0:  # Minimum buffer
    return {"type": "listening", "buffered_duration": duration_sec}

if duration_sec < 8.0:  # Maximum buffer
    # Check for silence...
```

## Testing Checklist

- [ ] WebSocket connects successfully
- [ ] Keep-alive ping received after 3 minutes
- [ ] Audio chunks accepted and processed
- [ ] Transcripts appear after natural pauses
- [ ] Recording starts when first participant joins
- [ ] Recording stops when meeting ends
- [ ] Recording download returns valid WAV file
- [ ] Transcript download works (txt, json, srt)
- [ ] `/analytics/sessions/list` returns 200
- [ ] Emotion timeline shows emotion data
- [ ] Meeting runs for 30+ minutes without disconnection

## Troubleshooting Quick Fixes

### WebSocket disconnects early
```python
# Check timeout in meeting.py:
timeout=180  # Should be 180, not 30
```

### No recording available
```python
# Verify recorder was started:
recorder = get_or_create_recorder(room_id)
print(recorder.is_recording)  # Should be True during meeting
```

### Transcripts incomplete
```python
# Check VAD threshold (might be filtering too much):
energy_threshold = 0.005  # Try lower value
```

### Analytics 404 error
```bash
# Use new endpoint:
curl http://localhost:8000/analytics/sessions/list
# Not: /analytics/sessions (this works too, but /list is the alias)
```

## Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| WebSocket Timeout | 180s | 3 minute inactivity before keep-alive |
| Audio Buffer Min | 4s | Minimum duration before processing |
| Audio Buffer Max | 8s | Maximum with silence check |
| Silence Threshold | 1.5s | Duration to consider speaker finished |
| VAD Energy | 0.01 | RMS energy threshold |
| Recording Memory | ~1 MB/min | Per room, 16kHz mono |
| Recording Storage | ~960 KB/min | WAV file size |

## Version Changes

### v3.0.0 (Current)
- ✅ Meeting recording with download
- ✅ Extended WebSocket timeout (180s)
- ✅ Enhanced VAD with silence detection
- ✅ Multi-format transcript export
- ✅ Analytics sessions list endpoint

### v2.x.x (Previous)
- Real-time transcription
- Speaker identification
- Emotion analysis
- Basic analytics

## Support

- 📖 Full Documentation: `MEETING_FEATURES.md`
- 🔧 Main README: `Readme.md`
- 🐛 Issues: GitHub Issues
- 📡 API Docs: http://localhost:8000/docs

## Quick Start

```bash
# 1. Start server
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 2. Test recording download
curl -O "http://localhost:8000/meeting/rooms/test-room/recording/download"

# 3. Test transcript download
curl -O "http://localhost:8000/meeting/rooms/test-room/transcript/download?format=json"

# 4. Test analytics
curl http://localhost:8000/analytics/sessions/list
```

## Migration from v2.x

No breaking changes. All existing functionality preserved.

**New functionality added**:
- Recording endpoints (opt-in)
- Transcript download endpoints (opt-in)
- Analytics list endpoint (alias, no impact)
- WebSocket timeout extended (transparent improvement)
- VAD improvements (transparent improvement)

**Action required**: None. All changes are backward compatible.

## License

MIT License - Same as main project
