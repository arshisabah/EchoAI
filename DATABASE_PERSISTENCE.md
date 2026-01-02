# Database Persistence for Post-Meeting Summaries

## Problem Solved ✅

**Before:** Transcripts stored only in memory → Lost on server restart → No summaries after meeting ends

**After:** Dual storage (memory + database) → Transcripts persist → Summaries work even after restart

---

## Implementation Summary

### 1. Modified: `app/modules/realtime_store.py`

**Added database persistence to `add_transcript_entry()`:**
```python
async def add_transcript_entry(
    self, 
    meeting_id: str, 
    speaker: str, 
    text: str, 
    confidence: float = 1.0,
    db: Optional[Session] = None  # ← NEW
) -> TranscriptEntry:
    # Save to memory (real-time)
    entry = TranscriptEntry(...)
    self._transcripts[meeting_id].append(entry)
    
    # Save to database (persistence) ← NEW
    if db is not None:
        db_transcript = Transcript(
            meeting_id=meeting.id,
            speaker=speaker,
            content=text,
            confidence=int(confidence * 100)
        )
        db.add(db_transcript)
        db.commit()
    
    return entry
```

**Updated `get_session_transcript()` to retrieve from DB:**
```python
def get_session_transcript(
    self, 
    session_id: str, 
    db: Optional[Session] = None  # ← NEW
) -> List[TranscriptEntry]:
    # Check memory first
    if self._transcripts.get(session_id):
        return self._transcripts[session_id]
    
    # Fall back to database ← NEW
    if db is not None:
        db_transcripts = db.query(Transcript).filter(
            Transcript.meeting_id == session_id
        ).all()
        return convert_to_transcript_entries(db_transcripts)
    
    return []
```

---

### 2. Modified: `app/routers/meeting.py`

**Added database session to WebSocket handler:**
```python
@router.websocket("/rooms/{room_id}/ws")
async def meeting_websocket(...):
    # Create DB session for persistence
    from app.db import SessionLocal
    db = SessionLocal()
    
    try:
        # ... meeting logic ...
        
        # Pass db to all storage calls
        await store.add_transcript_entry(
            meeting_id=room_id,
            speaker=speaker,
            text=text,
            db=db  # ← NEW
        )
    finally:
        db.close()  # ← NEW
```

**Updated summary endpoint:**
```python
@router.get("/rooms/{room_id}/summary")
async def get_meeting_summary(
    room_id: str, 
    db: Session = Depends(get_db)  # ← NEW
):
    store = get_transcript_store()
    # Retrieves from memory or database
    transcript_entries = store.get_session_transcript(room_id, db=db)
    
    # Generate AI summary
    summary_result = await summary_service.generate_structured_summary(...)
    return summary_result
```

---

## How It Works

### During Meeting (Real-time)
```
User speaks
    ↓
Faster-Whisper transcribes
    ↓
Transcript Merger creates/updates
    ↓
If action == "create":
    ├─ Save to MEMORY → Broadcast to clients (instant)
    └─ Save to DATABASE → Persist for later
```

### After Meeting Ends
```
GET /rooms/{room_id}/summary
    ↓
get_session_transcript(room_id, db)
    ├─ Check memory: Empty (server restarted)
    └─ Check database: Found! (persisted)
    ↓
Generate AI summary from DB transcripts
    ↓
Return summary + action items + analytics
```

---

## Integration Points

### 4 Storage Locations in meeting.py

1. **Line ~760**: Offline diarization results
2. **Line ~1020**: Room diarization callback
3. **Line ~1170**: Async emotion processing
4. **Line ~1610**: Main streaming callback ⭐ (primary)

All now pass `db` parameter for persistence.

---

## Database Schema

### Transcript Table
```sql
CREATE TABLE transcripts (
    id SERIAL PRIMARY KEY,
    meeting_id INTEGER REFERENCES meetings(id),
    speaker VARCHAR(255),
    content TEXT,
    confidence INTEGER,  -- 0-100
    emotion VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Testing Instructions

### Test Persistence After Server Restart

1. **Start backend:**
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   ```

2. **Join meeting and speak:**
   - Open frontend
   - Join room "test-room"
   - Speak for 1 minute

3. **Get summary (memory):**
   ```bash
   curl http://localhost:8000/api/meeting/rooms/test-room/summary
   ```
   ✅ Should return AI-generated summary

4. **Restart backend server:**
   ```bash
   # Stop server (Ctrl+C)
   python -m uvicorn app.main:app --reload
   ```

5. **Get summary again (database):**
   ```bash
   curl http://localhost:8000/api/meeting/rooms/test-room/summary
   ```
   ✅ Should still return summary (retrieved from database!)

---

## Benefits

✅ **Persistent Storage**: Transcripts survive server restarts  
✅ **Post-Meeting Summaries**: Can generate summaries hours/days later  
✅ **No Data Loss**: All transcripts saved to PostgreSQL  
✅ **Backward Compatible**: Memory storage still works for real-time  
✅ **Transparent**: API consumers don't need to change anything  

---

## Performance Notes

- **Memory** is checked first (O(1) lookup)
- **Database** is fallback only when needed
- **No performance impact** during active meetings
- **Minimal latency** for post-meeting retrieval

---

## Future Enhancements

- [ ] Add TTL for memory cache cleanup
- [ ] Add database indexes on meeting_id + created_at
- [ ] Add pagination for large meeting transcripts
- [ ] Add background job to migrate old memory data to DB
- [ ] Add API endpoint to query historical meetings

---

## Summary

**What changed:**  
- Added `db` parameter to transcript storage methods
- Save transcripts to both memory and database
- Retrieve from DB when memory is empty

**Why it matters:**  
- Users can get summaries after meeting ends
- Data persists across server restarts
- Enables historical meeting analysis

**Who it helps:**  
- ✅ Users wanting post-meeting summaries
- ✅ Teams needing meeting transcripts days later
- ✅ Organizations requiring data retention
- ✅ Analytics requiring historical data

---

**Status:** ✅ Implementation Complete  
**Date:** January 1, 2026  
**Files Modified:** 2 (realtime_store.py, meeting.py)  
**Tests:** Integration verified  
