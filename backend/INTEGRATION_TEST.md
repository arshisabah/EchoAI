# Integration Test Guide for v3.0

This document provides step-by-step instructions for testing all new features in EchoAI v3.0.

## Prerequisites

1. Backend server running on `http://localhost:8000`
2. At least 2 test users/devices for multi-participant testing
3. Microphone access for audio recording
4. Browser with WebSocket support

## Test Suite

### Test 1: WebSocket Stability (30+ Minutes)

**Objective**: Verify extended timeout and keep-alive mechanism

**Steps**:
1. Connect WebSocket client to meeting room
2. Wait for 3 minutes without sending messages
3. Verify keep-alive ping received (type: "ping_timeout")
4. Continue for 30+ minutes
5. Send occasional audio chunks to maintain activity

**Expected Results**:
- ✅ No disconnection after 3 minutes of inactivity
- ✅ Keep-alive ping received every 180 seconds
- ✅ Connection remains stable for 30+ minutes
- ✅ Can send messages at any time without reconnection

**WebSocket Test Script**:
```javascript
// test_websocket_stability.html
const ws = new WebSocket(
  'ws://localhost:8000/meeting/rooms/test-stability/ws?user_id=test1&username=Tester'
);

let keepAliveCount = 0;
let startTime = Date.now();

ws.onopen = () => {
  console.log('Connected at:', new Date().toISOString());
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'ping_timeout') {
    keepAliveCount++;
    const elapsed = (Date.now() - startTime) / 1000 / 60;
    console.log(`Keep-alive #${keepAliveCount} after ${elapsed.toFixed(1)} minutes`);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  const elapsed = (Date.now() - startTime) / 1000 / 60;
  console.log(`Disconnected after ${elapsed.toFixed(1)} minutes`);
};
```

**Pass Criteria**:
- No disconnection before 180 seconds
- At least 10 keep-alive pings in 30 minutes
- Connection remains stable throughout

---

### Test 2: Meeting Recording

**Objective**: Verify audio recording and download functionality

**Setup**:
```bash
# Create meeting room
curl -X POST http://localhost:8000/meeting/rooms/create \
  -H "Content-Type: application/json" \
  -d '{
    "room_name": "test-recording",
    "created_by": "test@example.com",
    "max_participants": 10
  }'
```

**Steps**:
1. Join meeting with User 1 (recording should auto-start)
2. User 1 speaks for 10 seconds
3. Join with User 2
4. User 2 speaks for 10 seconds
5. Both users speak simultaneously for 5 seconds
6. End meeting
7. Download recording

**Download Recording**:
```bash
curl -O "http://localhost:8000/meeting/rooms/test-recording/recording/download"

# Verify WAV file
file meeting_test-recording_*.wav
# Should output: RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 16000 Hz
```

**Check Metadata**:
```bash
curl http://localhost:8000/meeting/rooms/test-recording/recording/metadata | jq
```

**Expected Results**:
- ✅ Recording starts automatically when first user joins
- ✅ Both user's audio is captured
- ✅ Mixed audio is properly normalized
- ✅ WAV file downloads successfully
- ✅ Metadata shows correct participant count (2)
- ✅ Duration matches meeting length (~25 seconds)

**Audio Quality Check**:
```bash
# Play recording (requires ffplay or similar)
ffplay meeting_test-recording_*.wav

# Check audio properties
ffprobe meeting_test-recording_*.wav
```

**Pass Criteria**:
- WAV file is valid and playable
- Both speakers are audible
- No audio clipping or distortion
- File size approximately 960 KB/minute

---

### Test 3: Enhanced VAD and Diarization

**Objective**: Verify silence detection and speaker identification

**Test Scenario**:
1. User speaks continuously for 5 seconds
2. User pauses (silence) for 2 seconds
3. User speaks again for 3 seconds
4. User pauses for 2 seconds
5. Different user speaks for 4 seconds

**Monitor WebSocket Messages**:
```javascript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'listening') {
    console.log('Buffering audio, duration:', data.buffered_duration);
  }
  
  if (data.type === 'transcript_entry') {
    console.log('Transcript:', {
      speaker: data.speaker,
      text: data.text,
      timestamp: new Date().toISOString()
    });
  }
};
```

**Expected Results**:
- ✅ "listening" messages appear during speech
- ✅ Transcript appears after 1.5s silence
- ✅ No mid-speech interruptions
- ✅ Different speakers get different IDs
- ✅ Same speaker gets consistent ID

**Timing Expectations**:
| Event | Expected Behavior |
|-------|-------------------|
| 0-5s (speech) | "listening" messages |
| 5-7s (silence) | Transcript 1 appears at ~6.5s |
| 7-10s (speech) | "listening" messages |
| 10-12s (silence) | Transcript 2 appears at ~11.5s |
| 12-16s (new speaker) | "listening", then transcript at ~17.5s |

**Pass Criteria**:
- Transcripts appear only after silence
- No transcript during continuous speech
- Speaker identification is consistent

---

### Test 4: Transcript Download (All Formats)

**Objective**: Verify transcript export in TXT, JSON, and SRT formats

**Setup**: Complete a 2-minute meeting with multiple speakers and various emotions

**Test TXT Format**:
```bash
curl "http://localhost:8000/meeting/rooms/test-room/transcript/download?format=txt" \
  -o transcript.txt

cat transcript.txt
```

**Expected TXT Output**:
```
================================================================================
MEETING TRANSCRIPT
================================================================================

[10:15:23] User1 [NEUTRAL 70%]:
  Hello everyone, welcome to the meeting.

[10:15:30] User2 [HAPPY 85%]:
  Thanks for having me!
```

**Test JSON Format**:
```bash
curl "http://localhost:8000/meeting/rooms/test-room/transcript/download?format=json" \
  -o transcript.json

# Validate JSON
jq '.' transcript.json

# Check structure
jq '.transcript | length' transcript.json  # Number of entries
jq '.transcript[0] | keys' transcript.json  # Keys in first entry
```

**Expected JSON Structure**:
```json
{
  "transcript": [
    {
      "timestamp": "2024-01-18T10:15:23Z",
      "speaker": "User1",
      "text": "Hello everyone, welcome to the meeting.",
      "confidence": 0.95,
      "emotions": {
        "emotion": "neutral",
        "confidence": 0.70,
        "scores": {"neutral": 0.70, "happy": 0.20, "sad": 0.10}
      }
    }
  ],
  "total_entries": 42,
  "generated_at": "2024-01-18T10:30:00Z"
}
```

**Test SRT Format**:
```bash
curl "http://localhost:8000/meeting/rooms/test-room/transcript/download?format=srt" \
  -o transcript.srt

cat transcript.srt
```

**Expected SRT Output**:
```
1
00:00:00,000 --> 00:00:03,000
User1: Hello everyone, welcome to the meeting.

2
00:00:03,000 --> 00:00:06,000
User2: Thanks for having me!
```

**Pass Criteria**:
- All three formats download successfully
- TXT is human-readable with timestamps and emotions
- JSON is valid and parseable
- SRT follows standard subtitle format
- All formats contain the same content

---

### Test 5: Analytics Endpoints

**Objective**: Verify analytics endpoints are working

**Test Sessions List** (Fixed 404):
```bash
# Both endpoints should work
curl http://localhost:8000/analytics/sessions/list | jq
curl http://localhost:8000/analytics/sessions | jq
```

**Expected Response**:
```json
{
  "sessions": [
    {
      "session_id": "test-room",
      "total_entries": 15,
      "speakers": ["User1", "User2"],
      "duration_minutes": 5.5
    }
  ],
  "total_count": 1,
  "generated_at": "2024-01-18T10:30:00Z"
}
```

**Test Detailed Analytics**:
```bash
curl http://localhost:8000/analytics/session/test-room/detailed | jq
```

**Expected Sections**:
- ✅ `basic_analytics` - duration, word count, etc.
- ✅ `emotion_analysis` - emotion distribution
- ✅ `speaker_patterns` - speaking time, turns
- ✅ `conversation_metrics` - pace, vocabulary

**Test Emotion Timeline**:
```bash
curl http://localhost:8000/analytics/session/test-room/emotions | jq
```

**Expected Response**:
```json
{
  "session_id": "test-room",
  "emotion_analysis": {
    "emotion_distribution": {
      "neutral": 0.45,
      "happy": 0.30,
      "frustrated": 0.15,
      "surprised": 0.10
    },
    "dominant_emotion": "neutral",
    "emotion_transitions": 12
  },
  "analyzed_at": "2024-01-18T10:30:00Z"
}
```

**Pass Criteria**:
- `/analytics/sessions/list` returns 200 (not 404)
- Session list contains all active/recent sessions
- Detailed analytics includes all sections
- Emotion timeline shows emotion progression
- All responses are valid JSON

---

### Test 6: End-to-End Multi-Participant

**Objective**: Complete workflow with 3+ participants for 10 minutes

**Scenario**:
1. Host creates room
2. Participant 1 joins
3. Participant 2 joins
4. Participant 3 joins
5. 10 minutes of conversation
6. Meeting ends
7. Download recording and transcripts
8. Check analytics

**Automated Test Script**:
```python
#!/usr/bin/env python3
import requests
import time
import json

BASE_URL = "http://localhost:8000"

# 1. Create room
print("1. Creating room...")
response = requests.post(f"{BASE_URL}/meeting/rooms/create", json={
    "room_name": "e2e-test",
    "created_by": "host@test.com",
    "max_participants": 10
})
assert response.status_code == 200
room_id = response.json()["room_id"]
print(f"   Room created: {room_id}")

# 2. Simulate meeting (would need WebSocket clients)
print("2. Simulating 10-minute meeting...")
print("   (Manual step: Connect 3+ WebSocket clients)")
input("   Press Enter when meeting is complete...")

# 3. End meeting
print("3. Ending meeting...")
response = requests.delete(
    f"{BASE_URL}/meeting/rooms/{room_id}",
    params={"ended_by": "host@test.com"}
)
assert response.status_code == 200
print(f"   Meeting ended: {response.json()}")

# 4. Download recording
print("4. Downloading recording...")
response = requests.get(f"{BASE_URL}/meeting/rooms/{room_id}/recording/download")
assert response.status_code == 200
with open(f"recording_{room_id}.wav", "wb") as f:
    f.write(response.content)
print(f"   Recording saved: {len(response.content)} bytes")

# 5. Download transcripts
print("5. Downloading transcripts...")
for fmt in ["txt", "json", "srt"]:
    response = requests.get(
        f"{BASE_URL}/meeting/rooms/{room_id}/transcript/download",
        params={"format": fmt}
    )
    assert response.status_code == 200
    with open(f"transcript_{room_id}.{fmt}", "wb") as f:
        f.write(response.content)
    print(f"   Transcript saved: {fmt} ({len(response.content)} bytes)")

# 6. Get analytics
print("6. Fetching analytics...")
response = requests.get(f"{BASE_URL}/analytics/session/{room_id}/detailed")
assert response.status_code == 200
analytics = response.json()
print(f"   Participants: {analytics['speaker_patterns']['total_speakers']}")
print(f"   Duration: {analytics['basic_analytics']['duration_minutes']} min")
print(f"   Total words: {analytics['basic_analytics']['total_words']}")

print("\n✅ End-to-end test complete!")
```

**Pass Criteria**:
- All API calls return expected status codes
- Recording contains audio from all 3 participants
- Transcripts show all speakers
- Analytics reflect 10-minute meeting with multiple speakers
- No errors in server logs

---

## Performance Benchmarks

### Expected Performance Metrics

| Metric | Target | Actual | Pass/Fail |
|--------|--------|--------|-----------|
| WebSocket Timeout | 180s | ___ | ___ |
| Keep-alive Interval | 180s | ___ | ___ |
| VAD Processing | <10ms | ___ | ___ |
| Recording Memory | ~1 MB/min | ___ | ___ |
| Recording File Size | ~960 KB/min | ___ | ___ |
| Transcript Download | <500ms | ___ | ___ |
| Analytics Query | <1s | ___ | ___ |

### Load Testing

**Concurrent Connections**:
```bash
# Use a tool like 'websocket-bench' or custom script
# Target: 50+ concurrent WebSocket connections
```

**Multiple Rooms**:
```bash
# Create 10 simultaneous rooms
for i in {1..10}; do
  curl -X POST http://localhost:8000/meeting/rooms/create \
    -H "Content-Type: application/json" \
    -d "{\"room_name\":\"load-test-$i\",\"created_by\":\"test@test.com\"}" &
done
wait
```

---

## Troubleshooting Test Failures

### Recording Not Available
```bash
# Check if recorder was created
curl http://localhost:8000/meeting/rooms/{room_id}/recording/metadata

# If 404, recording wasn't started
# Ensure at least one participant joined
```

### WebSocket Disconnects Early
```python
# Check timeout setting in meeting.py
# Should be: timeout=180 (not 30)
grep "timeout=" backend/app/routers/meeting.py
```

### Transcript Missing Entries
```python
# Check VAD threshold
# File: backend/app/services/transcription_service.py
# Line ~93: energy_threshold = 0.01
# Try lowering to 0.005 for more sensitivity
```

### Analytics 404
```bash
# Verify endpoint alias exists
curl http://localhost:8000/analytics/sessions/list
# If still 404, check router registration in main.py
```

---

## Test Results Template

```
===============================================================================
EchoAI v3.0 Integration Test Results
===============================================================================
Date: _______________
Tester: _______________
Environment: _______________

Test 1: WebSocket Stability
  [ ] No disconnection after 3 minutes
  [ ] Keep-alive pings received
  [ ] 30+ minute stability
  Notes: _______________

Test 2: Meeting Recording
  [ ] Recording auto-starts
  [ ] Multi-participant audio captured
  [ ] WAV file valid
  [ ] Metadata correct
  Notes: _______________

Test 3: Enhanced VAD
  [ ] Silence detection works (1.5s)
  [ ] No mid-speech interruptions
  [ ] Speaker identification consistent
  Notes: _______________

Test 4: Transcript Export
  [ ] TXT format correct
  [ ] JSON format valid
  [ ] SRT format follows standard
  Notes: _______________

Test 5: Analytics
  [ ] /sessions/list returns 200
  [ ] Detailed analytics complete
  [ ] Emotion timeline accurate
  Notes: _______________

Test 6: End-to-End
  [ ] Full workflow successful
  [ ] All files generated correctly
  [ ] No errors in logs
  Notes: _______________

Overall Result: [ PASS / FAIL ]

===============================================================================
```

---

## Automated Test Script

```bash
#!/bin/bash
# automated_test.sh

echo "Starting EchoAI v3.0 Integration Tests..."

# Test 1: Health Check
echo "1. Testing health endpoint..."
curl -f http://localhost:8000/health || exit 1
echo "   ✅ Health check passed"

# Test 2: Create Room
echo "2. Creating test room..."
ROOM_ID=$(curl -s -X POST http://localhost:8000/meeting/rooms/create \
  -H "Content-Type: application/json" \
  -d '{"room_name":"auto-test","created_by":"test@test.com"}' \
  | jq -r '.room_id')
echo "   ✅ Room created: $ROOM_ID"

# Test 3: Check Analytics (should return empty list initially)
echo "3. Testing analytics endpoint..."
curl -f http://localhost:8000/analytics/sessions/list || exit 1
echo "   ✅ Analytics endpoint working"

# Test 4: Room Info
echo "4. Getting room info..."
curl -f http://localhost:8000/meeting/rooms/$ROOM_ID || exit 1
echo "   ✅ Room info retrieved"

# Test 5: End Room
echo "5. Ending room..."
curl -f -X DELETE "http://localhost:8000/meeting/rooms/$ROOM_ID?ended_by=test@test.com" || exit 1
echo "   ✅ Room ended"

echo ""
echo "✅ All automated tests passed!"
```

---

## Sign-off

After completing all tests, document your findings:

- Test Date: _______________
- Version Tested: v3.0.0
- All Tests Passed: [ YES / NO ]
- Issues Found: _______________
- Sign-off: _______________

---

For support or questions, refer to:
- **MEETING_FEATURES.md** - Detailed documentation
- **QUICK_REFERENCE.md** - Developer quick reference
- **CHANGELOG.md** - Version history
