# Historical Transcripts Fix

## Problem
Newly joined participants in a meeting couldn't see the transcription history from before they joined. The WebSocket only broadcast new transcripts in real-time, causing participants who joined late to miss important context and conversation history.

## Solution
Implemented automatic delivery of historical transcripts to newly joined participants when they connect to the meeting room WebSocket.

## How It Works

### 1. Transcript Storage
- All transcripts are stored in the `RealtimeStore` when they are generated
- Each transcript includes: speaker ID, text, timestamp, confidence, and emotion data
- Transcripts persist for the duration of the meeting room

### 2. Participant Join Flow
When a new participant joins a meeting:

```python
# 1. WebSocket connection established
# 2. Participant joins the room
# 3. Welcome messages sent
# 4. Room info and participant list sent
# 5. **NEW** Historical transcripts retrieved and sent
# 6. Live transcripts continue to be broadcast in real-time
```

### 3. Historical Transcript Delivery
Located in `backend/app/routers/meeting.py` in the `meeting_websocket` function:

```python
# Retrieve historical transcripts from store
store = get_transcript_store()
historical_transcripts = store.get_session_transcript(room_id)

# Send in batches of 10 to prevent overwhelming the connection
batch_size = 10
for i in range(0, len(historical_transcripts), batch_size):
    batch = historical_transcripts[i:i + batch_size]
    
    for entry in batch:
        # Format and send each transcript
        await websocket.send_json({
            "type": "live_transcript",
            "user_id": speaker_id,
            "username": speaker_name,
            "text": entry.text,
            "emotion": entry.emotions.get("emotion", "neutral"),
            "confidence": entry.emotions.get("confidence", 0.0),
            "timestamp": entry.timestamp.isoformat(),
            "is_historical": True  # Special flag
        })
    
    # Small delay between batches
    await asyncio.sleep(0.05)
```

## Key Features

### Batch Processing
- Transcripts are sent in batches of 10 to prevent overwhelming the WebSocket connection
- 50ms delay between batches ensures smooth delivery without blocking

### Speaker Identification
- Attempts to map speaker user_ids to actual usernames from current room participants
- Falls back to speaker_id if username not found
- Ensures consistent identification across historical and live transcripts

### Historical Flag
- All historical transcripts include `is_historical: true` flag
- Frontend can use this to distinguish historical from live transcripts
- Allows for different UI treatment (e.g., showing a "history" marker)

### Format Consistency
- Historical transcripts use the same format as live transcripts
- `type: "live_transcript"` ensures frontend handles them identically
- Includes all metadata: emotion, confidence, timestamp

## Benefits

1. **Complete Context**: New participants see the full conversation history
2. **Seamless Experience**: Historical transcripts appear in the same UI as live ones
3. **No Data Loss**: All transcripts are preserved for the meeting duration
4. **Scalable**: Batch processing handles meetings with many transcripts efficiently
5. **Fault Tolerant**: Error handling ensures one failed transcript doesn't break the flow

## Testing
Comprehensive test coverage in `backend/tests/test_historical_transcripts.py`:

- ✅ Session creation and management
- ✅ Adding and retrieving transcript entries
- ✅ Transcript format with emotion data
- ✅ Multiple speakers in a session
- ✅ Empty sessions and edge cases
- ✅ Non-existent session handling

All 6 tests pass successfully.

## Technical Details

### Dependencies
- No new dependencies required
- Uses existing `RealtimeStore` from `app/modules/realtime_store.py`
- Uses existing WebSocket infrastructure

### Performance Considerations
- Batch size of 10 prevents memory spikes
- 50ms delays prevent connection throttling
- Historical transcripts sent once per participant (not repeatedly)
- Store cleanup happens automatically for inactive sessions

### Error Handling
- Try-catch wrapper ensures errors don't break WebSocket connection
- Detailed logging for debugging
- Failed historical transcript delivery doesn't prevent live transcription

## Code Changes
Files modified:
- `backend/app/routers/meeting.py`: Added historical transcript sending logic (+49 lines)
- `backend/tests/test_historical_transcripts.py`: Added comprehensive tests (+178 lines)

Total: 227 lines added

## Future Enhancements
Potential improvements for future iterations:

1. **Pagination**: For very long meetings (>1000 transcripts), implement pagination
2. **Compression**: Compress historical transcripts before sending
3. **Caching**: Cache formatted historical transcripts to reduce processing
4. **Selective History**: Allow participants to request specific time ranges
5. **UI Improvements**: Add visual separator between historical and live transcripts in frontend

## Monitoring
Added logging statements to track:
- Number of historical transcripts sent
- Audio chunk processing
- Transcript broadcasting
- Errors in historical transcript delivery

Check logs for patterns like:
```
📜 Sending 25 historical transcripts to Alice
✅ Historical transcripts sent to Alice
📢 Broadcasting transcript from Bob in room_123: 'Hello everyone...'
```

## Related Files
- `backend/app/routers/meeting.py` - WebSocket handler with historical transcript logic
- `backend/app/modules/realtime_store.py` - Transcript storage and retrieval
- `backend/app/services/orchestrator_service.py` - Audio processing and transcript generation
- `backend/tests/test_historical_transcripts.py` - Test suite
- `frontend/src/hooks/useWebSocket.js` - Frontend WebSocket handling
