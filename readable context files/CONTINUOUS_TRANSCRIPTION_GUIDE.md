# Continuous Transcription & Parallel Emotion Detection - Implementation Guide

## Overview

EchoAI now supports **Google Meet-style continuous transcription** with **parallel emotion detection and guidance**. This system ensures real-time, uninterrupted transcription while emotion analysis runs asynchronously in the background.

## Key Features

### 1. Continuous Transcript Bars
- Words are **appended** to the same transcript bar while a speaker continues
- New bars are created only when:
  - **Speaker changes** (interruption)
  - **15 seconds of silence** detected
  - **30 seconds continuous speech** by same speaker (readability)

### 2. Parallel Emotion Processing
- Transcription **never blocks** for emotion analysis
- Emotion detection runs in background worker
- Transcript bars show processing state:
  - `active` - Currently receiving words
  - `processing_emotion` - Yellow state, emotion being analyzed
  - `finalized` - Green/neutral, emotion complete with guidance

## WebSocket Message Format

### 1. Transcript Bar Message (New Format)

```json
{
  "type": "transcript_bar",
  "action": "create" | "append",
  "bar": {
    "id": "unique-bar-id",
    "session_id": "room-123",
    "speaker": "user-456",
    "text": "Current transcript text...",
    "started_at": "2026-01-02T10:30:00Z",
    "updated_at": "2026-01-02T10:30:05Z",
    "confidence": 0.95,
    "word_count": 42,
    "status": "active" | "processing_emotion" | "finalized",
    "emotion": null | "happy" | "sad" | "frustrated" | ...,
    "emotion_confidence": null | 0.85,
    "emotion_scores": null | {"happy": 0.85, "sad": 0.10, ...},
    "emotion_guidance": null | "Great energy! Keep the positive momentum going."
  },
  "reason": "speaker_change" | "silence_threshold" | "duration_threshold" | "first_bar",
  "timestamp": "2026-01-02T10:30:05Z"
}
```

**Action Types:**
- `create`: New transcript bar created (display as new bubble/line)
- `append`: Text added to existing bar (update in-place)

### 2. Emotion Update Message (Async)

```json
{
  "type": "bar_emotion_update",
  "bar_id": "unique-bar-id",
  "emotion": "happy",
  "emotion_confidence": 0.87,
  "emotion_scores": {
    "happy": 0.87,
    "neutral": 0.10,
    "sad": 0.03
  },
  "emotion_guidance": "Great energy! Keep the positive momentum going.",
  "status": "finalized",
  "timestamp": "2026-01-02T10:30:08Z"
}
```

## Frontend Implementation Guide

### Step 1: Maintain Transcript Bar State

```javascript
// Store active bars by ID
const transcriptBars = new Map();

// Handle transcript_bar messages
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'transcript_bar') {
    const { action, bar } = message;
    
    if (action === 'create') {
      // Create new transcript bar UI element
      transcriptBars.set(bar.id, bar);
      renderNewTranscriptBar(bar);
    } else if (action === 'append') {
      // Update existing bar with new text
      const existingBar = transcriptBars.get(bar.id);
      if (existingBar) {
        existingBar.text = bar.text;
        existingBar.word_count = bar.word_count;
        existingBar.updated_at = bar.updated_at;
        updateTranscriptBarText(bar.id, bar.text);
      }
    }
  }
  
  if (message.type === 'bar_emotion_update') {
    // Update bar with emotion data (async)
    const bar = transcriptBars.get(message.bar_id);
    if (bar) {
      bar.emotion = message.emotion;
      bar.emotion_confidence = message.emotion_confidence;
      bar.emotion_guidance = message.emotion_guidance;
      bar.status = message.status;
      updateTranscriptBarEmotion(message.bar_id, message);
    }
  }
};
```

### Step 2: Visual State Management

```javascript
function renderNewTranscriptBar(bar) {
  const barElement = document.createElement('div');
  barElement.id = `bar-${bar.id}`;
  barElement.className = `transcript-bar ${bar.status}`;
  
  barElement.innerHTML = `
    <div class="speaker">${bar.speaker}</div>
    <div class="text">${bar.text}</div>
    <div class="emotion-indicator ${bar.status}"></div>
  `;
  
  transcriptContainer.appendChild(barElement);
  
  // Apply status-based styling
  updateBarStatus(barElement, bar.status);
}

function updateTranscriptBarText(barId, newText) {
  const barElement = document.getElementById(`bar-${barId}`);
  if (barElement) {
    const textElement = barElement.querySelector('.text');
    textElement.textContent = newText;
    
    // Optional: Smooth scroll to show new content
    textElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function updateTranscriptBarEmotion(barId, emotionData) {
  const barElement = document.getElementById(`bar-${barId}`);
  if (!barElement) return;
  
  // Update status indicator
  updateBarStatus(barElement, emotionData.status);
  
  // Add emotion badge/label
  const existingBadge = barElement.querySelector('.emotion-badge');
  if (existingBadge) existingBadge.remove();
  
  if (emotionData.emotion && emotionData.emotion !== 'neutral') {
    const badge = document.createElement('span');
    badge.className = `emotion-badge ${emotionData.emotion}`;
    badge.textContent = `${emotionData.emotion} (${(emotionData.emotion_confidence * 100).toFixed(0)}%)`;
    barElement.appendChild(badge);
  }
  
  // Show guidance tooltip or popup
  if (emotionData.emotion_guidance) {
    barElement.title = emotionData.emotion_guidance;
    // Or show in a separate guidance panel
    showEmotionGuidance(emotionData);
  }
}

function updateBarStatus(barElement, status) {
  // Remove all status classes
  barElement.classList.remove('active', 'processing_emotion', 'finalized');
  
  // Add current status
  barElement.classList.add(status);
  
  const indicator = barElement.querySelector('.emotion-indicator');
  if (indicator) {
    indicator.classList.remove('active', 'processing_emotion', 'finalized');
    indicator.classList.add(status);
  }
}
```

### Step 3: CSS Styling

```css
.transcript-bar {
  margin: 10px 0;
  padding: 15px;
  border-radius: 8px;
  border-left: 4px solid #ccc;
  background: #f9f9f9;
  transition: all 0.3s ease;
}

.transcript-bar.active {
  border-left-color: #2196F3; /* Blue for active */
  background: #E3F2FD;
}

.transcript-bar.processing_emotion {
  border-left-color: #FFC107; /* Yellow for processing */
  background: #FFF8E1;
}

.transcript-bar.finalized {
  border-left-color: #4CAF50; /* Green for finalized */
  background: #ffffff;
}

.emotion-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
  margin-left: 8px;
}

.emotion-indicator.active {
  background: #2196F3;
  animation: pulse 1.5s infinite;
}

.emotion-indicator.processing_emotion {
  background: #FFC107;
  animation: pulse 1.5s infinite;
}

.emotion-indicator.finalized {
  background: #4CAF50;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.emotion-badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  margin-left: 10px;
}

.emotion-badge.happy { background: #C8E6C9; color: #2E7D32; }
.emotion-badge.sad { background: #BBDEFB; color: #1565C0; }
.emotion-badge.frustrated { background: #FFCCBC; color: #D84315; }
.emotion-badge.confused { background: #F0F4C3; color: #827717; }
```

## Backend Architecture

### Components

1. **ContinuousTranscriptManager** (`app/services/continuous_transcript_manager.py`)
   - Manages transcript bar lifecycle
   - Implements bar creation rules (speaker change, silence, duration)
   - Queues bars for emotion processing

2. **AsyncEmotionProcessor** (`app/services/async_emotion_processor.py`)
   - Background worker for emotion analysis
   - Processes bars from queue without blocking
   - Broadcasts emotion updates via WebSocket

3. **OrchestratorService** (updated)
   - `process_transcription_continuous()` method
   - Integrates with continuous transcript manager
   - Caches audio for emotion analysis

4. **Meeting WebSocket** (updated)
   - Uses new continuous transcription format
   - Broadcasts transcript_bar messages
   - Forwards emotion updates to clients

### Flow Diagram

```
Audio Input → Transcription Service → Continuous Manager
                                              ↓
                                    Check Bar Rules
                                    ├─ Same speaker → APPEND
                                    └─ New conditions → CREATE
                                              ↓
                                    Broadcast to clients (immediate)
                                              ↓
                                    Finalized bar → Queue
                                              ↓
                                    Async Emotion Worker
                                    ├─ Text + Audio Analysis
                                    ├─ Generate Guidance
                                    └─ Broadcast Update
```

## Testing

### Manual Test Scenario

1. **Single Speaker Continuous**:
   - Speak for 10 seconds continuously
   - Should see: ONE bar with text appending
   - After 30s: New bar created (duration threshold)

2. **Speaker Interruption**:
   - User A starts speaking
   - User B interrupts
   - Should see: Bar A finalizes, Bar B created

3. **Silence Detection**:
   - Speak for 5 seconds
   - Wait 16 seconds
   - Speak again
   - Should see: New bar after silence

4. **Emotion Processing**:
   - Watch bar turn yellow (processing_emotion)
   - 2-3 seconds later: Turn green with emotion label
   - Verify guidance appears

## Configuration

### Thresholds (Adjustable)

```python
# In continuous_transcript_manager.py
SILENCE_THRESHOLD_SECONDS = 15  # New bar after silence
MAX_DURATION_SECONDS = 30       # New bar after duration
```

### Enable/Disable

```python
# In orchestrator_service.py __init__
self.use_continuous_transcription = True  # Set to False to disable
```

## Migration from Old Format

If your frontend currently uses the old `live_transcript` format:

### Old Format (Deprecated)
```json
{
  "type": "live_transcript",
  "user_id": "user-123",
  "username": "John",
  "text": "Hello world",
  "emotion": "neutral",
  "is_final": true
}
```

### New Format
```json
{
  "type": "transcript_bar",
  "action": "create",
  "bar": {
    "id": "bar-abc123",
    "speaker": "user-123",
    "text": "Hello world",
    "status": "active",
    ...
  }
}
```

Update your message handlers to support both formats during transition.

## Troubleshooting

### Issue: Bars not appending
- Check that speaker IDs match exactly
- Verify silence detection isn't too sensitive
- Check logs for "New bar needed" reasons

### Issue: Emotion updates not appearing
- Verify AsyncEmotionProcessor is started
- Check emotion queue for backlog
- Ensure WebSocket broadcast is working

### Issue: Too many bars created
- Adjust `SILENCE_THRESHOLD_SECONDS` (increase)
- Check speaker identification accuracy
- Review duration threshold setting

## Future Enhancements

- [ ] Partial transcript support (interim results)
- [ ] Configurable thresholds per meeting
- [ ] Speaker voice profile matching
- [ ] Multi-language emotion detection
- [ ] Emotion trend visualization
- [ ] Export with emotion timeline

---

**Implementation Date**: January 2, 2026  
**Status**: ✅ Fully Implemented
