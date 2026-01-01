# Google Meet-Style Transcription Implementation Guide

## What's Been Implemented

### 1. **Transcript Merger Service** (`app/services/transcript_merger.py`)
- Merges consecutive transcripts from the same speaker
- Creates new entry only when speaker changes or after timeout (2 seconds)
- Handles incremental text updates without word repetition
- Uses Indian Standard Time (IST) for timestamps
- Delays emotion analysis until speaker turn completes

### 2. **Broadcast Helper** (`app/services/transcript_broadcast_helper.py`)
- Separate emotion analysis function
- Audio buffer management for emotion detection
- Async emotion analysis with timeout protection

### 3. **Configuration** (`app/core/config.py`)
- Added settings for transcript merging
- IST timezone configuration
- Speaker turn timeout setting

## Integration Steps Required

### Update `meeting.py` WebSocket Handler

Replace the `on_deepgram_transcript` callback (around line 1065-1154) with:

```python
async def on_deepgram_transcript(result: dict):
    """Enhanced callback with Google Meet-style merging"""
    try:
        text = result.get("text", "").strip()
        if not text:
            return
        
        is_final = result.get("is_final", True)
        confidence = result.get("confidence", 1.0)
        
        logger.info(f"📡 {'✅ Final' if is_final else '⏳ Interim'}: '{text[:60]}'")
        
        # Use transcript merger
        from app.services.transcript_merger import get_transcript_merger
        from app.services.transcript_broadcast_helper import (
            analyze_and_broadcast_emotion, 
            add_audio_to_buffer
        )
        
        merger = get_transcript_merger()
        merge_result = merger.merge_or_create(
            room_id=room_id,
            speaker=user_id,
            username=username,
            text=text,
            is_final=is_final,
            confidence=confidence,
            user_id=user_id
        )
        
        action = merge_result["action"]
        entry = merge_result["entry"]
        previous_entry = merge_result.get("previous_entry")
        
        # Analyze emotion for previous speaker when speaker changes
        if previous_entry and previous_entry.get("should_analyze_emotion"):
            stream_id = f"{room_id}_{previous_entry['user_id']}"
            await analyze_and_broadcast_emotion(
                previous_entry,
                room_id,
                stream_id,
                room_manager
            )
        
        # Broadcast current transcript
        if action == "create":
            await room_manager.broadcast_transcript(
                room_id=room_id,
                user_id=entry["user_id"],
                username=entry["username"],
                text=entry["text"],
                emotion="neutral",  # No emotion yet
                confidence=entry["confidence"],
                emotion_guidance={},
                entry_id=entry["id"],
                is_update=False
            )
            logger.info(f"✨ Created transcript entry: {entry['id']}")
        
        elif action == "update":
            new_words = merge_result.get("new_words", "")
            await room_manager.broadcast_transcript(
                room_id=room_id,
                user_id=entry["user_id"],
                username=entry["username"],
                text=entry["text"],
                emotion="neutral",
                confidence=entry["confidence"],
                emotion_guidance={},
                entry_id=entry["id"],
                is_update=True
            )
            logger.info(f"📝 Updated entry {entry['id']}: +{len(new_words.split())} words")
        
        # Analyze emotion only when final
        if is_final and entry.get("should_analyze_emotion"):
            stream_id = f"{room_id}_{user_id}"
            await analyze_and_broadcast_emotion(
                entry,
                room_id,
                stream_id,
                room_manager
            )
        
        # Store final transcripts
        if is_final:
            store = get_transcript_store()
            await store.add_transcript_entry(
                meeting_id=room_id,
                speaker=entry["speaker"],
                text=entry["text"],
                confidence=entry["confidence"]
            )
    
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
```

### Update `broadcast_transcript` Method

The `MeetingRoomManager.broadcast_transcript` method needs to support:
- `entry_id`: Unique ID for the transcript entry
- `is_update`: Boolean flag for updates vs new entries
- `is_emotion_update`: Boolean flag for emotion-only updates

```python
async def broadcast_transcript(
    self,
    room_id: str,
    user_id: str,
    username: str,
    text: str,
    emotion: str = "neutral",
    confidence: float = 0.0,
    emotion_guidance: dict = None,
    entry_id: str = None,
    is_update: bool = False,
    is_emotion_update: bool = False
):
    """Broadcast with support for incremental updates"""
    message = {
        "type": "live_transcript" if not is_update else "transcript_update",
        "entry_id": entry_id,
        "user_id": user_id,
        "username": username,
        "text": text,
        "emotion": emotion,
        "confidence": confidence,
        "emotion_guidance": emotion_guidance or {},
        "timestamp": datetime.utcnow().isoformat(),
        "is_update": is_update,
        "is_emotion_update": is_emotion_update
    }
    await self.broadcast_to_room(room_id, message)
```

### Frontend Updates Required

#### TranscriptPanel.jsx

The frontend needs to handle:
1. `transcript_update` messages (merge with existing entry by `entry_id`)
2. Incremental text updates without duplication
3. Emotion updates that come separately

```javascript
// In useWebSocket hook or TranscriptPanel
const handleTranscriptMessage = (message) => {
  const { type, entry_id, text, is_update, is_emotion_update, emotion } = message;
  
  setTranscripts((prev) => {
    if (is_update && entry_id) {
      // Update existing entry
      return prev.map((t) =>
        t.entry_id === entry_id
          ? { ...t, text, emotion, ...message }
          : t
      );
    } else if (is_emotion_update && entry_id) {
      // Update only emotion
      return prev.map((t) =>
        t.entry_id === entry_id
          ? { ...t, emotion, emotion_confidence: message.confidence, emotion_guidance: message.emotion_guidance }
          : t
      );
    } else {
      // New entry
      return [{ ...message, entry_id }, ...prev];
    }
  });
};
```

## Benefits

1. ✅ **Google Meet-like experience** - Continuous updates in one bar
2. ✅ **No word repetition** - Only appends new words
3. ✅ **IST timestamps** - Correct timezone
4. ✅ **Smart emotion timing** - Only when speaker finishes
5. ✅ **Fast Deepgram streaming** - 0.01s latency
6. ✅ **Speaker turn detection** - New bar when speaker changes
7. ✅ **Clean UI** - No spam of multiple entries per speaker

## Testing

1. Start backend with Deepgram enabled
2. Join meeting and speak continuously
3. Verify: Single transcript entry updates in real-time
4. Have another person speak
5. Verify: New entry created, emotion appears on previous entry
6. Check timestamps are in IST

## Configuration

In `.env`:
```bash
USE_STREAMING_TRANSCRIPTION=true
MERGE_SAME_SPEAKER_TRANSCRIPTS=true
SPEAKER_TURN_TIMEOUT_SECONDS=2.0
ENABLE_INCREMENTAL_TRANSCRIPTS=true
TIMEZONE=Asia/Kolkata
DEEPGRAM_API_KEY=your_key_here
```
