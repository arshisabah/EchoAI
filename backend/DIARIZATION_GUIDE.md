# Speaker Diarization Guide

This guide explains how to use EchoAI's speaker diarization features for multi-participant meetings.

## Overview

EchoAI supports two types of speaker diarization:

1. **Real-Time Diarization** - Live speaker identification during meetings
2. **Offline Diarization** - Post-meeting analysis of recorded audio

## Features

### Real-Time Diarization
- Mixed audio stream from all participants
- Real-time speaker identification
- Live speaker attribution in transcripts
- Automatic speaker mapping to participant names

### Offline Diarization
- Process saved meeting recordings
- Accurate speaker segmentation
- Speaker statistics and analytics
- Exportable diarization results

## Configuration

### Enable Real-Time Diarization

Add to your `.env` file:

```bash
# Enable Deepgram streaming transcription
USE_STREAMING_TRANSCRIPTION=true
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# Enable room-level diarization
USE_ROOM_DIARIZATION=true
```

**Note:** Room-level diarization uses a single Deepgram connection per room, mixing audio from all participants.

### Per-User Streaming (Default)

For per-user streaming without room-level diarization:

```bash
USE_STREAMING_TRANSCRIPTION=true
USE_ROOM_DIARIZATION=false
```

This mode creates separate Deepgram streams for each user, using `user_id` for speaker attribution.

## API Endpoints

### POST /meeting/rooms/{room_id}/diarize

Perform offline diarization on a saved meeting recording.

**Parameters:**
- `room_id` (path): Room identifier

**Response:**
```json
{
  "room_id": "meeting123",
  "diarization_complete": true,
  "segments": [
    {
      "speaker_id": "Speaker 0",
      "text": "Hello everyone, let's start the meeting.",
      "start_time": 0.0,
      "end_time": 3.5,
      "duration": 3.5,
      "confidence": 0.95,
      "word_count": 7
    },
    {
      "speaker_id": "Speaker 1",
      "text": "Good morning!",
      "start_time": 3.6,
      "end_time": 4.2,
      "duration": 0.6,
      "confidence": 0.92,
      "word_count": 2
    }
  ],
  "speaker_count": 2,
  "speaker_stats": {
    "Speaker 0": {
      "total_duration": 45.3,
      "total_words": 156,
      "segment_count": 12
    },
    "Speaker 1": {
      "total_duration": 32.7,
      "total_words": 98,
      "segment_count": 8
    }
  },
  "total_segments": 20,
  "total_duration": 78.0,
  "generated_at": "2024-01-15T10:30:00Z"
}
```

**Usage Example:**

```bash
curl -X POST "http://localhost:8000/meeting/rooms/meeting123/diarize"
```

## Real-Time Diarization Flow

1. **Room Creation**
   - Room is created with unique ID
   - Recording starts automatically

2. **Participant Join**
   - Participant connects via WebSocket
   - Registered in room diarization service
   - Room-level Deepgram stream starts (if first participant)

3. **Audio Processing**
   - Audio from each participant is collected
   - Streams are mixed in real-time
   - Mixed audio sent to Deepgram with diarization enabled
   - Speaker labels returned from Deepgram

4. **Speaker Resolution**
   - Deepgram speaker IDs mapped to participant usernames
   - Transcripts broadcast with correct speaker attribution
   - Stored in transcript store with speaker metadata

5. **Cleanup**
   - Room diarization stops when last participant leaves
   - Audio buffers cleared
   - Recording saved

## Offline Diarization Flow

1. **Meeting Recording**
   - Audio from all participants recorded during meeting
   - Mixed into single WAV file

2. **Diarization Request**
   - POST request to `/meeting/rooms/{room_id}/diarize`
   - WAV file sent to Deepgram pre-recorded API

3. **Processing**
   - Deepgram analyzes audio for speaker changes
   - Returns segments with speaker labels and timestamps

4. **Results**
   - Diarized segments stored in transcript store
   - Speaker statistics calculated
   - Results returned as JSON

## Speaker Mapping

### Real-Time Mode

When `USE_ROOM_DIARIZATION=true`:

1. Each participant registers with their `user_id` and `username`
2. Deepgram identifies speakers as `Speaker 0`, `Speaker 1`, etc.
3. System attempts to map Deepgram speakers to actual participants
4. If mapping fails, generic speaker labels are used

### Offline Mode

Deepgram assigns speaker labels based on voice characteristics:
- `Speaker 0` - First distinct voice detected
- `Speaker 1` - Second distinct voice detected
- etc.

To map to actual participants, cross-reference with:
- Participant join times
- Speaking patterns
- Known participant list

## Best Practices

### For Real-Time Diarization

1. **Clear Audio Quality**
   - Use good quality microphones
   - Minimize background noise
   - Avoid audio echo/feedback

2. **Participant Management**
   - Ensure participants use distinct usernames
   - Limit to reasonable participant count (< 10 for best accuracy)

3. **Network Considerations**
   - Stable internet connection required
   - Low latency network preferred
   - Audio chunks sent every ~100ms

### For Offline Diarization

1. **Recording Quality**
   - Ensure recording captures all participants
   - Adequate audio levels for all speakers
   - Clean audio without excessive noise

2. **Meeting Duration**
   - Works best with meetings < 2 hours
   - Longer meetings may take more time to process

3. **Post-Processing**
   - Review speaker labels for accuracy
   - Manual correction may be needed for:
     - Similar voices
     - Overlapping speech
     - Poor audio quality segments

## Limitations

### Current Limitations

1. **Speaker Identification**
   - Accuracy depends on audio quality
   - Similar voices may be confused
   - Works best with 2-5 distinct speakers

2. **Overlapping Speech**
   - May not perfectly separate simultaneous speakers
   - Dominant speaker typically identified

3. **Voice Changes**
   - Emotional state changes may affect identification
   - Background noise can impact accuracy

4. **Language Support**
   - Currently optimized for English
   - Other languages supported but may have lower accuracy

## Troubleshooting

### Real-Time Diarization Issues

**Problem:** Speakers not identified correctly
- **Solution:** Check audio quality, reduce background noise
- **Solution:** Ensure `USE_ROOM_DIARIZATION=true` in config
- **Solution:** Verify Deepgram API key is valid

**Problem:** High latency in transcription
- **Solution:** Check network connection
- **Solution:** Reduce participant count
- **Solution:** Verify Deepgram service status

### Offline Diarization Issues

**Problem:** "No recording found" error
- **Solution:** Ensure meeting was recorded
- **Solution:** Check room_id is correct
- **Solution:** Verify recording didn't fail during meeting

**Problem:** Poor speaker separation
- **Solution:** Improve recording audio quality
- **Solution:** Ensure sufficient volume differences between speakers
- **Solution:** Minimize overlapping speech

## Advanced Configuration

### Customizing Audio Mixing

Edit `app/services/room_diarization_service.py`:

```python
# Adjust buffer size for different latency/quality tradeoff
# Current: 3 chunks (~300ms)
if len(self.room_buffers[room_id][pid]) > 3:
    self.room_buffers[room_id][pid].pop(0)
```

### Adjusting Diarization Parameters

Edit Deepgram options in the diarization service:

```python
options = PrerecordedOptions(
    model="nova-2",        # Use nova-2 for best accuracy
    smart_format=True,     # Enable smart formatting
    diarize=True,          # Enable diarization
    punctuate=True,        # Add punctuation
    paragraphs=True,       # Detect paragraph breaks
    utterances=True,       # Split into utterances
)
```

## API Integration Examples

### Python

```python
import requests

# Perform offline diarization
response = requests.post(
    "http://localhost:8000/meeting/rooms/meeting123/diarize"
)
result = response.json()

print(f"Found {result['speaker_count']} speakers")
for segment in result['segments']:
    print(f"{segment['speaker_id']}: {segment['text']}")
```

### JavaScript

```javascript
// Perform offline diarization
async function diarizeMeeting(roomId) {
  const response = await fetch(
    `http://localhost:8000/meeting/rooms/${roomId}/diarize`,
    { method: 'POST' }
  );
  const result = await response.json();
  
  console.log(`Found ${result.speaker_count} speakers`);
  result.segments.forEach(segment => {
    console.log(`${segment.speaker_id}: ${segment.text}`);
  });
}
```

## Support

For issues or questions:
1. Check Deepgram API status
2. Review application logs
3. Verify configuration settings
4. Check audio quality and network connection

For more help, refer to:
- Deepgram Documentation: https://developers.deepgram.com/
- EchoAI GitHub Issues
