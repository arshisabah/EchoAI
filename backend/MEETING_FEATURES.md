# EchoAI Meeting Features Documentation

This document describes the new production-ready meeting management features added to EchoAI.

## Overview

EchoAI now supports comprehensive meeting management with the following capabilities:
- **Meeting Recording**: Record complete audio from all participants
- **WebSocket Stability**: Extended timeout and keep-alive for long meetings (30+ minutes)
- **Enhanced Diarization**: Voice Activity Detection with silence boundary detection
- **Post-Meeting Analysis**: Download transcripts in multiple formats
- **Analytics Dashboard**: Comprehensive session analytics and metrics

## New Features

### 1. Meeting Recording System

#### Recording Download
**Endpoint**: `GET /meeting/rooms/{room_id}/recording/download`

Downloads the complete meeting recording as a WAV file.

**Features**:
- Records audio from all participants
- Automatically mixes multiple audio streams
- Stores in high-quality WAV format (16kHz, mono, 16-bit)
- Automatic recording start when first participant joins
- Automatic recording stop when meeting ends

**Response**:
```
Content-Type: audio/wav
Content-Disposition: attachment; filename=meeting_{room_id}_{timestamp}.wav
```

**Example**:
```bash
curl -O "http://localhost:8000/meeting/rooms/my-room/recording/download"
```

#### Recording Metadata
**Endpoint**: `GET /meeting/rooms/{room_id}/recording/metadata`

Get metadata about the meeting recording.

**Response**:
```json
{
  "room_id": "my-room",
  "sample_rate": 16000,
  "duration_seconds": 1234.5,
  "participant_count": 3,
  "start_time": "2024-01-01T10:00:00Z",
  "end_time": "2024-01-01T10:20:34Z",
  "is_recording": false
}
```

### 2. WebSocket Stability Improvements

#### Extended Timeout
- Connection timeout extended from 30 seconds to **180 seconds (3 minutes)**
- Supports meetings lasting 30+ minutes without disconnection
- Automatic keep-alive ping messages every 3 minutes

#### Keep-Alive Mechanism
The WebSocket now sends keep-alive messages:
```json
{
  "type": "ping_timeout",
  "message": "Keep-alive: No message received within 180 seconds.",
  "timestamp": "2024-01-01T10:15:00Z"
}
```

#### Reconnection Handling
- Graceful handling of temporary disconnections
- Preserves user state across reconnections
- Automatic cleanup of stale connections

### 3. Enhanced Diarization & VAD

#### Voice Activity Detection (VAD)
New VAD algorithm with:
- **Energy-based detection**: RMS energy threshold
- **Zero-crossing rate**: Distinguishes voice from noise
- **Adaptive thresholds**: Adjusts based on audio characteristics

#### Silence Boundary Detection
- Detects **1.5-second silence boundaries**
- Waits for speaker to finish before processing
- Prevents mid-speech interruptions
- Improves transcription accuracy

#### Smart Buffering
- Buffers audio chunks until natural speech boundary detected
- Minimum buffer: 4 seconds
- Maximum buffer: 8 seconds
- Processes when silence detected or maximum buffer reached

### 4. Post-Meeting Transcript Download

#### Transcript Download Endpoint
**Endpoint**: `GET /meeting/rooms/{room_id}/transcript/download?format={format}`

Download the complete diarized transcript in multiple formats.

**Parameters**:
- `format`: Output format - `txt`, `json`, or `srt` (default: `txt`)

#### Format: Plain Text (TXT)
Human-readable format with timestamps, speakers, and emotions:

```
================================================================================
MEETING TRANSCRIPT
================================================================================

[10:15:23] John [HAPPY 85%]:
  I think we should proceed with the new feature.

[10:15:45] Sarah [NEUTRAL 70%]:
  That sounds good to me.
```

**Example**:
```bash
curl -O "http://localhost:8000/meeting/rooms/my-room/transcript/download?format=txt"
```

#### Format: JSON
Structured data format for programmatic access:

```json
{
  "transcript": [
    {
      "timestamp": "2024-01-01T10:15:23Z",
      "speaker": "John",
      "text": "I think we should proceed with the new feature.",
      "confidence": 0.95,
      "emotions": {
        "emotion": "happy",
        "confidence": 0.85,
        "scores": {"happy": 0.85, "neutral": 0.10, "sad": 0.05}
      }
    }
  ],
  "total_entries": 42,
  "generated_at": "2024-01-01T10:30:00Z"
}
```

**Example**:
```bash
curl -O "http://localhost:8000/meeting/rooms/my-room/transcript/download?format=json"
```

#### Format: SRT (Subtitles)
Standard subtitle format compatible with video editors:

```
1
00:00:00,000 --> 00:00:03,000
John: I think we should proceed with the new feature.

2
00:00:03,000 --> 00:00:06,000
Sarah: That sounds good to me.
```

**Example**:
```bash
curl -O "http://localhost:8000/meeting/rooms/my-room/transcript/download?format=srt"
```

### 5. Analytics Dashboard Support

#### List All Sessions
**Endpoint**: `GET /analytics/sessions/list` (alias for `/analytics/sessions`)

Get a list of all available sessions with basic statistics.

**Response**:
```json
{
  "sessions": [
    {
      "session_id": "room-123",
      "total_entries": 45,
      "speakers": ["John", "Sarah", "Mike"],
      "duration_minutes": 23.5
    }
  ],
  "total_count": 1,
  "generated_at": "2024-01-01T10:30:00Z"
}
```

#### Session Details
**Endpoint**: `GET /analytics/session/{session_id}/detailed`

Get comprehensive analytics including emotions and patterns.

**Response includes**:
- Basic analytics (duration, word count, speaker statistics)
- Emotion analysis (distribution, timeline, averages)
- Speaker patterns (talk time, turn count, interruptions)
- Conversation metrics (pace, vocabulary diversity)

#### Emotion Timeline
**Endpoint**: `GET /analytics/session/{session_id}/emotions`

Get the emotional progression throughout the meeting.

**Response**:
```json
{
  "session_id": "room-123",
  "emotion_analysis": {
    "emotion_distribution": {
      "neutral": 0.45,
      "happy": 0.30,
      "frustrated": 0.15,
      "surprised": 0.10
    },
    "dominant_emotion": "neutral",
    "emotion_transitions": 12
  }
}
```

## Implementation Details

### Audio Recording Architecture

```
┌─────────────────┐
│  Participant 1  │──┐
└─────────────────┘  │
                     │     ┌──────────────┐      ┌─────────────┐
┌─────────────────┐  │────▶│ AudioRecorder│─────▶│ AudioMixer  │
│  Participant 2  │──┘     │   (per room) │      │             │
└─────────────────┘        └──────────────┘      └──────┬──────┘
                                                         │
┌─────────────────┐                                     │
│  Participant N  │────────────────────────────────────▶│
└─────────────────┘                                     │
                                                         ▼
                                                  ┌────────────┐
                                                  │  WAV File  │
                                                  └────────────┘
```

### Voice Activity Detection Flow

```
Audio Chunk ──▶ Energy Check ──▶ Zero-Crossing ──▶ VAD Decision
                    │                Rate              │
                    │                  │               │
                    ▼                  ▼               ▼
              > threshold?      in range?         Voice Activity?
```

### Transcript Processing Pipeline

```
Audio ──▶ VAD ──▶ Buffer ──▶ Silence Detection ──▶ Transcribe ──▶ Store
         │         │              │                    │            │
         │         │              │                    │            │
         ▼         ▼              ▼                    ▼            ▼
     Skip if    Wait for      Check 1.5s          Whisper       Format
     silent     4-8 sec       silence at end       API/Local    & Save
```

## Usage Examples

### Complete Meeting Workflow

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. Create a meeting room
response = requests.post(f"{BASE_URL}/meeting/rooms/create", json={
    "room_name": "team-standup",
    "created_by": "john@example.com",
    "max_participants": 10
})
room_id = response.json()["room_id"]

# 2. Participants join via WebSocket
# (Recording starts automatically)

# 3. After meeting ends, download recording
recording = requests.get(
    f"{BASE_URL}/meeting/rooms/{room_id}/recording/download"
)
with open("meeting.wav", "wb") as f:
    f.write(recording.content)

# 4. Download transcript in JSON format
transcript = requests.get(
    f"{BASE_URL}/meeting/rooms/{room_id}/transcript/download?format=json"
)
with open("transcript.json", "wb") as f:
    f.write(transcript.content)

# 5. Get analytics
analytics = requests.get(
    f"{BASE_URL}/analytics/session/{room_id}/detailed"
)
print(analytics.json())
```

### WebSocket Client Example

```javascript
const ws = new WebSocket(
  `ws://localhost:8000/meeting/rooms/my-room/ws?user_id=user123&username=John`
);

// Handle keep-alive pings
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'ping_timeout') {
    console.log('Keep-alive ping received');
    // Send pong response
    ws.send(JSON.stringify({ type: 'pong' }));
  }
};

// Send audio chunks
function sendAudio(audioData) {
  ws.send(JSON.stringify({
    type: 'audio_chunk',
    audio_data: btoa(audioData)  // Base64 encode
  }));
}
```

## Configuration

### WebSocket Timeout Settings

Edit `backend/app/routers/meeting.py`:

```python
# Main receive loop with extended timeout
data = await asyncio.wait_for(websocket.receive_text(), timeout=180)
```

To change the timeout, modify the `timeout` parameter (value in seconds).

### VAD Thresholds

Edit `backend/app/services/transcription_service.py`:

```python
def detect_voice_activity(self, audio_array: np.ndarray) -> bool:
    energy_threshold = 0.01  # Adjust for sensitivity
    zcr_min = 0.01
    zcr_max = 0.5
    # ...
```

### Silence Detection Duration

Edit `backend/app/services/orchestrator_service.py`:

```python
# Check for silence boundary (1.5s)
tail_samples = min(int(16000 * 1.5), len(combined))
```

Change `1.5` to desired silence duration in seconds.

## Performance Considerations

### Memory Usage
- Each active recorder stores audio in memory until meeting ends
- Typical usage: ~1 MB per minute of mono audio (16kHz, 16-bit)
- 30-minute meeting: ~30 MB per room

### CPU Usage
- VAD processing: Minimal overhead (<1% CPU per stream)
- Audio mixing: Linear with participant count
- Transcription: Depends on model (Whisper API recommended for production)

### Storage
- WAV files: ~960 KB per minute (16kHz, mono, 16-bit)
- 30-minute meeting: ~28 MB storage
- Transcripts: <1 MB per meeting (JSON format)

## Best Practices

### 1. Meeting Recording
- ✅ Recording starts automatically when first participant joins
- ✅ Download recordings within 24 hours (implement cleanup policy)
- ✅ Use compression for long-term storage if needed

### 2. WebSocket Connections
- ✅ Implement exponential backoff for reconnections
- ✅ Handle `ping_timeout` messages gracefully
- ✅ Close connections properly when leaving meeting

### 3. Transcription
- ✅ Use OpenAI Whisper API for best quality (set `OPENAI_API_KEY`)
- ✅ Fallback to local Whisper for offline scenarios
- ✅ Tune VAD thresholds based on audio quality

### 4. Analytics
- ✅ Query analytics after meeting ends for complete data
- ✅ Use `/sessions/list` to discover available sessions
- ✅ Cache analytics results to reduce computation

## Troubleshooting

### Recording Issues

**Problem**: No recording available after meeting
- Check if recording was started (first participant joined)
- Verify `recorder.is_recording` status
- Check server logs for recording errors

**Problem**: Poor audio quality in recording
- Ensure proper audio normalization
- Check participant audio levels
- Verify sample rate (should be 16000 Hz)

### WebSocket Issues

**Problem**: Connection drops frequently
- Verify timeout is set to 180 seconds
- Check network stability
- Implement ping/pong heartbeat

**Problem**: "WebSocket is not connected" error
- Ensure `await websocket.accept()` is called first
- Check for connection state before sending messages
- Verify proper error handling in WebSocket loop

### Transcription Issues

**Problem**: Missing transcriptions
- Check VAD thresholds (might be filtering valid speech)
- Verify audio buffer duration settings
- Check transcription service logs

**Problem**: Mid-speech interruptions
- Increase silence detection threshold
- Adjust buffer duration settings
- Check for audio chunk timing issues

## Security Considerations

### Recording Access Control
- Recordings should only be accessible to meeting participants
- Implement authentication checks before download
- Consider encryption for sensitive meetings

### Data Privacy
- Transcripts contain sensitive conversation data
- Implement retention policies
- Support GDPR compliance (right to deletion)
- Add consent mechanisms

### WebSocket Security
- Use WSS (WebSocket Secure) in production
- Validate user tokens
- Rate limit connections per user
- Implement room access controls

## Future Enhancements

Potential improvements for future versions:

1. **Real-time Recording Streaming**: Stream recording while meeting is in progress
2. **Speaker Enrollment**: Pre-register speaker voice profiles for better identification
3. **Multi-language Support**: Detect and transcribe multiple languages
4. **Cloud Storage Integration**: Direct upload to S3, Azure Blob, etc.
5. **Live Captions**: Real-time caption broadcast to all participants
6. **Recording Highlights**: AI-generated highlights and key moments
7. **Noise Cancellation**: Advanced audio preprocessing
8. **Video Recording**: Support video along with audio

## API Reference Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/meeting/rooms/{room_id}/recording/download` | GET | Download meeting recording (WAV) |
| `/meeting/rooms/{room_id}/recording/metadata` | GET | Get recording metadata |
| `/meeting/rooms/{room_id}/transcript/download` | GET | Download transcript (TXT/JSON/SRT) |
| `/analytics/sessions/list` | GET | List all sessions |
| `/analytics/session/{id}/detailed` | GET | Get detailed analytics |
| `/analytics/session/{id}/emotions` | GET | Get emotion timeline |

## Support

For issues or questions:
- Check server logs in `backend/logs/`
- Review this documentation
- Check existing issues on GitHub
- Create a new issue with logs and reproduction steps

## Version History

- **v3.0.0** - Initial release with recording, enhanced VAD, and analytics
  - Meeting recording system
  - WebSocket stability improvements (180s timeout)
  - Enhanced diarization with VAD
  - Multi-format transcript download
  - Analytics dashboard support
