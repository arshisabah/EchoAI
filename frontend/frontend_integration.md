# 🎯 Frontend Integration Guide for Multi-User Meetings

## Overview

Your backend now supports **real-time multi-user meetings** with:
- ✅ Live transcription broadcast to all participants
- ✅ Real-time emotion detection with guidance
- ✅ AI-powered task extraction and assignment
- ✅ Meeting summaries and analytics

---

## 🚀 Quick Start

### 1. Create a Meeting Room

```javascript
// Create a new room
const response = await fetch('http://localhost:8000/meeting/rooms/create?room_id=meeting_123', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    room_name: "Weekly Team Sync",
    created_by: "user_alice",
    password: "optional_password",  // Optional
    max_participants: 10
  })
});

const data = await response.json();
console.log(data);
// {
//   "success": true,
//   "room": { ... },
//   "websocket_url": "/meeting/rooms/meeting_123/ws"
// }
```

### 2. Connect to Meeting via WebSocket

```javascript
const roomId = 'meeting_123';
const userId = 'user_bob';
const username = 'Bob Smith';

// Connect to WebSocket
const ws = new WebSocket(
  `ws://localhost:8000/meeting/rooms/${roomId}/ws?user_id=${userId}&username=${encodeURIComponent(username)}&role=participant`
);

ws.onopen = () => {
  console.log('✅ Connected to meeting room');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  handleMeetingMessage(message);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected from meeting');
};
```

### 3. Handle Incoming Messages

```javascript
function handleMeetingMessage(message) {
  switch (message.type) {
    case 'welcome':
      console.log('Welcome message:', message);
      displayRoomInfo(message.room_info);
      break;
    
    case 'live_transcript':
      // REAL-TIME TRANSCRIPT FROM ANY PARTICIPANT
      displayTranscript({
        username: message.username,
        text: message.text,
        emotion: message.emotion,
        timestamp: message.timestamp
      });
      
      // EMOTION GUIDANCE
      showEmotionGuidance(message.emotion_guidance);
      break;
    
    case 'participant_joined':
      console.log(`${message.username} joined the meeting`);
      updateParticipantList();
      break;
    
    case 'participant_left':
      console.log(`${message.username} left the meeting`);
      updateParticipantList();
      break;
    
    case 'participant_state_update':
      updateParticipantState(message);
      break;
    
    case 'chat_message':
      displayChatMessage(message);
      break;
    
    case 'room_ended':
      alert('Meeting has ended');
      ws.close();
      break;
    
    case 'pong':
      // Response to ping
      break;
  }
}
```

### 4. Send Audio from Microphone

```javascript
// Get microphone access
const stream = await navigator.mediaDevices.getUserMedia({ 
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    sampleRate: 16000
  } 
});

// Create media recorder
const mediaRecorder = new MediaRecorder(stream, {
  mimeType: 'audio/webm'
});

// Send audio chunks every 1 second
mediaRecorder.ondataavailable = async (event) => {
  if (event.data.size > 0 && ws.readyState === WebSocket.OPEN) {
    // Convert blob to base64
    const arrayBuffer = await event.data.arrayBuffer();
    const base64Audio = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
    
    // Send to backend
    ws.send(JSON.stringify({
      type: 'audio_chunk',
      audio_data: base64Audio,
      sample_rate: 16000
    }));
  }
};

// Start recording (send chunks every 1000ms)
mediaRecorder.start(1000);

// To stop
// mediaRecorder.stop();
```

---

## 📺 UI Components

### Live Transcript Display

```html
<div id="transcript-container">
  <!-- Transcripts will be added here -->
</div>

<script>
function displayTranscript(data) {
  const container = document.getElementById('transcript-container');
  
  const entry = document.createElement('div');
  entry.className = 'transcript-entry';
  entry.innerHTML = `
    <div class="transcript-header">
      <span class="username">${data.username}</span>
      <span class="emotion" style="color: ${getEmotionColor(data.emotion)}">
        ${getEmotionIcon(data.emotion)} ${data.emotion}
      </span>
      <span class="timestamp">${formatTime(data.timestamp)}</span>
    </div>
    <div class="transcript-text">${data.text}</div>
  `;
  
  container.appendChild(entry);
  
  // Auto-scroll to bottom
  container.scrollTop = container.scrollHeight;
}

function getEmotionIcon(emotion) {
  const icons = {
    'happy': '😊', 'excited': '🎉', 'sad': '😔',
    'angry': '😠', 'frustrated': '😤', 'anxious': '😰',
    'confused': '🤔', 'confident': '💪', 'neutral': '😐'
  };
  return icons[emotion] || '😐';
}

function getEmotionColor(emotion) {
  const colors = {
    'happy': '#44ff88', 'excited': '#ffaa44', 'sad': '#4488ff',
    'angry': '#ff4444', 'frustrated': '#ff8844', 'anxious': '#aa88ff',
    'confused': '#8888ff', 'confident': '#ff88ff', 'neutral': '#888888'
  };
  return colors[emotion] || '#888888';
}
</script>
```

### Emotion Guidance Panel

```html
<div id="emotion-guidance-panel" style="display: none;">
  <div class="guidance-header">
    <span id="guidance-icon"></span>
    <h3 id="guidance-title"></h3>
  </div>
  <div class="guidance-content">
    <p id="guidance-primary"></p>
    <div class="guidance-strategies">
      <h4>Response Strategies:</h4>
      <ul id="guidance-strategies-list"></ul>
    </div>
    <div class="guidance-phrases">
      <h4>Recommended Phrases:</h4>
      <ul id="guidance-phrases-list"></ul>
    </div>
    <div class="ai-suggestion">
      <h4>💡 AI Suggested Response:</h4>
      <p id="ai-response"></p>
    </div>
  </div>
</div>

<script>
function showEmotionGuidance(guidance) {
  const panel = document.getElementById('emotion-guidance-panel');
  
  // Update content
  document.getElementById('guidance-icon').textContent = guidance.visual.icon;
  document.getElementById('guidance-title').textContent = 
    `How to respond to ${guidance.emotion}`;
  document.getElementById('guidance-primary').textContent = 
    guidance.primary_guidance;
  
  // Strategies
  const strategiesList = document.getElementById('guidance-strategies-list');
  strategiesList.innerHTML = '';
  guidance.response_strategies.forEach(strategy => {
    const li = document.createElement('li');
    li.textContent = strategy;
    strategiesList.appendChild(li);
  });
  
  // Phrases
  const phrasesList = document.getElementById('guidance-phrases-list');
  phrasesList.innerHTML = '';
  guidance.recommended_phrases.forEach(phrase => {
    const li = document.createElement('li');
    li.textContent = phrase;
    phrasesList.appendChild(li);
  });
  
  // AI suggestion
  document.getElementById('ai-response').textContent = 
    guidance.ai_suggested_response;
  
  // Show panel
  panel.style.display = 'block';
  panel.style.borderColor = guidance.visual.color;
  
  // Auto-hide after 10 seconds
  setTimeout(() => {
    panel.style.display = 'none';
  }, 10000);
}
</script>
```

### Participant List

```html
<div id="participants-panel">
  <h3>Participants (<span id="participant-count">0</span>)</h3>
  <ul id="participants-list"></ul>
</div>

<script>
async function updateParticipantList() {
  const response = await fetch(`http://localhost:8000/meeting/rooms/${roomId}`);
  const data = await response.json();
  
  const list = document.getElementById('participants-list');
  const count = document.getElementById('participant-count');
  
  list.innerHTML = '';
  count.textContent = data.participants.length;
  
  data.participants.forEach(participant => {
    const li = document.createElement('li');
    li.className = 'participant-item';
    li.innerHTML = `
      <span class="participant-name">${participant.username}</span>
      <span class="participant-status">
        ${participant.is_speaking ? '🎤' : ''}
        ${participant.is_muted ? '🔇' : '🔊'}
        ${participant.emotion_state}
      </span>
    `;
    list.appendChild(li);
  });
}
</script>
```

---

## 📋 Task Management

### Get Meeting Tasks

```javascript
async function getTasksForMeeting() {
  const response = await fetch(`http://localhost:8000/meeting/rooms/${roomId}/tasks`);
  const data = await response.json();
  
  displayTasks(data.tasks);
}

function displayTasks(tasks) {
  const container = document.getElementById('tasks-container');
  container.innerHTML = '<h3>Action Items</h3>';
  
  tasks.forEach(task => {
    const taskEl = document.createElement('div');
    taskEl.className = `task task-${task.priority}`;
    taskEl.innerHTML = `
      <div class="task-header">
        <span class="task-title">${task.title}</span>
        <span class="task-priority">${task.priority}</span>
      </div>
      <div class="task-description">${task.description}</div>
      <div class="task-footer">
        <span class="task-assignee">👤 ${task.assigned_to}</span>
        <span class="task-due">📅 ${formatDueDate(task.due_date)}</span>
        <span class="task-status">${task.status}</span>
      </div>
    `;
    container.appendChild(taskEl);
  });
}
```

### Extract Tasks from Meeting

```javascript
async function extractTasksFromMeeting() {
  const response = await fetch(
    `http://localhost:8000/meeting/rooms/${roomId}/tasks/extract`,
    { method: 'POST' }
  );
  
  const data = await response.json();
  
  if (data.success) {
    console.log(`✅ Extracted ${data.task_count} tasks`);
    displayTasks(data.extracted_tasks);
  }
}
```

---

## 📊 Meeting Summary

### Get Complete Meeting Summary

```javascript
async function getMeetingSummary() {
  const response = await fetch(`http://localhost:8000/meeting/rooms/${roomId}/summary`);
  const data = await response.json();
  
  // Meeting insights
  console.log('Meeting Summary:', data.meeting_insights.meeting_summary);
  console.log('Total Duration:', data.meeting_insights.session_duration_minutes, 'minutes');
  
  // Tasks
  console.log('Tasks:', data.tasks);
  console.log('Task Summary:', data.task_summary);
  
  // Emotion analysis
  console.log('Emotion Guidance:', data.emotion_guidance);
}
```

---

## 🎨 Complete React Example

```jsx
import React, { useState, useEffect, useRef } from 'react';

function MeetingRoom({ roomId, userId, username }) {
  const [ws, setWs] = useState(null);
  const [transcripts, setTranscripts] = useState([]);
  const [participants, setParticipants] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef(null);
  
  // Connect to meeting
  useEffect(() => {
    const websocket = new WebSocket(
      `ws://localhost:8000/meeting/rooms/${roomId}/ws?user_id=${userId}&username=${username}`
    );
    
    websocket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'live_transcript') {
        setTranscripts(prev => [...prev, message]);
      } else if (message.type === 'participant_joined' || message.type === 'participant_left') {
        fetchParticipants();
      }
    };
    
    setWs(websocket);
    
    return () => websocket.close();
  }, [roomId, userId, username]);
  
  // Start/stop recording
  const toggleRecording = async () => {
    if (!isRecording) {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      
      recorder.ondataavailable = async (event) => {
        const arrayBuffer = await event.data.arrayBuffer();
        const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
        
        ws.send(JSON.stringify({
          type: 'audio_chunk',
          audio_data: base64,
          sample_rate: 16000
        }));
      };
      
      recorder.start(1000);
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } else {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
    }
  };
  
  return (
    <div className="meeting-room">
      <div className="meeting-header">
        <h2>Meeting Room: {roomId}</h2>
        <button onClick={toggleRecording}>
          {isRecording ? '🛑 Stop' : '🎤 Start Recording'}
        </button>
      </div>
      
      <div className="meeting-content">
        <div className="transcript-panel">
          <h3>Live Transcript</h3>
          {transcripts.map((t, i) => (
            <div key={i} className="transcript-entry">
              <strong>{t.username}:</strong> {t.text}
              <span className="emotion">{t.emotion}</span>
            </div>
          ))}
        </div>
        
        <div className="participants-panel">
          <h3>Participants ({participants.length})</h3>
          {participants.map(p => (
            <div key={p.user_id}>{p.username}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default MeetingRoom;
```

---

## ✅ Your Backend Now Supports

✅ **Multi-user real-time meetings**  
✅ **Live transcript broadcasting to all participants**  
✅ **Real-time emotion detection with AI guidance**  
✅ **Automatic task extraction and assignment**  
✅ **Meeting summaries with emotion analysis**  
✅ **Speaker identification**  
✅ **Participant management**  
✅ **WebSocket real-time communication**

---

## 🚀 Production Deployment

```bash
# Start the backend
docker-compose up -d

# Backend will be available at:
# http://localhost:8000

# WebSocket endpoint:
# ws://localhost:8000/meeting/rooms/{room_id}/ws
```

---

## 📝 Summary

Your backend is **PRODUCTION READY** for multi-user meetings with:
1. Real-time collaboration
2. Live transcription broadcast
3. Emotion guidance
4. Task management
5. Meeting analytics

**All files work together seamlessly!** 🎉

# Terminal 1: Start Backend
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Update IP in .env, then start Frontend
cd frontend
# Edit .env: VITE_BACKEND_URL=http://192.168.0.106:8000
npm run dev:network

# Access from any device: http://192.168.0.106:5173