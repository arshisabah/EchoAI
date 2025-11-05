# app/routers/meeting.py
"""
Complete Multi-User Meeting Router
Handles: rooms, real-time transcription, emotions, guidance, tasks
"""

import logging
import json
import base64
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from pydantic import BaseModel

from app.services.meeting_room_manager import (
    get_meeting_room_manager,
    ParticipantRole
)
from app.services.transcription_service import get_transcription_service
from app.services.emotion_analysis import get_emotion_service
from app.services.emotion_guidance import get_emotion_guidance_engine
from app.services.task_assignment import get_task_assignment_engine
from app.services.summary_service import get_summary_service
from app.services.audio_utils import bytes_to_numpy
from app.modules.realtime_store import get_transcript_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/meeting", tags=["Multi-User Meetings"])


# Request Models
class CreateRoomRequest(BaseModel):
    room_name: str
    created_by: str
    password: Optional[str] = None
    max_participants: int = 50


# REST Endpoints

@router.post("/rooms/create")
async def create_meeting_room(room_id: str, request: CreateRoomRequest):
    """Create a new meeting room."""
    try:
        room_manager = get_meeting_room_manager()
        await room_manager.start_broadcasting()
        
        room = await room_manager.create_room(
            room_id=room_id,
            room_name=request.room_name,
            created_by=request.created_by,
            password=request.password,
            max_participants=request.max_participants
        )
        
        # Create session in transcript store
        store = get_transcript_store()
        await store.create_session(room_id, {
            "room_name": request.room_name,
            "created_by": request.created_by
        })
        
        return {
            "success": True,
            "room": room.to_dict(),
            "websocket_url": f"ws://localhost:8000/meeting/rooms/{room_id}/ws"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating room: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}")
async def get_room_info(room_id: str):
    """Get room information."""
    try:
        room_manager = get_meeting_room_manager()
        room_info = await room_manager.get_room_info(room_id)
        
        if not room_info:
            raise HTTPException(status_code=404, detail="Room not found")
        
        return room_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting room: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms")
async def list_rooms():
    """List all active rooms."""
    try:
        room_manager = get_meeting_room_manager()
        rooms = await room_manager.list_rooms()
        
        return {
            "rooms": rooms,
            "total_count": len(rooms)
        }
        
    except Exception as e:
        logger.error(f"Error listing rooms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rooms/{room_id}")
async def end_meeting_room(room_id: str, ended_by: str = Query(...)):
    """End a meeting room."""
    try:
        room_manager = get_meeting_room_manager()
        await room_manager.end_room(room_id, ended_by)
        
        return {
            "success": True,
            "message": f"Room {room_id} ended"
        }
        
    except Exception as e:
        logger.error(f"Error ending room: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/transcript")
async def get_room_transcript(room_id: str):
    """Get complete meeting transcript."""
    try:
        store = get_transcript_store()
        entries = store.get_session_transcript(room_id)
        
        return {
            "room_id": room_id,
            "transcript": [e.to_dict() for e in entries],
            "total_entries": len(entries)
        }
        
    except Exception as e:
        logger.error(f"Error getting transcript: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/tasks")
async def get_meeting_tasks(room_id: str):
    """Get all tasks from the meeting."""
    try:
        task_engine = get_task_assignment_engine()
        
        tasks = task_engine.get_meeting_tasks(room_id)
        summary = task_engine.get_task_summary(room_id)
        
        return {
            "room_id": room_id,
            "tasks": [task.to_dict() for task in tasks],
            "summary": summary,
            "total_tasks": len(tasks)
        }
        
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/tasks/extract")
async def extract_tasks(room_id: str):
    """AI-powered task extraction from transcript."""
    try:
        store = get_transcript_store()
        transcript_entries = store.get_session_transcript(room_id)
        
        if not transcript_entries:
            raise HTTPException(status_code=404, detail="No transcript found")
        
        room_manager = get_meeting_room_manager()
        participants = await room_manager.get_room_participants(room_id)
        
        task_engine = get_task_assignment_engine()
        tasks = await task_engine.extract_tasks_from_transcript(
            [e.to_dict() for e in transcript_entries],
            room_id,
            participants
        )
        
        return {
            "success": True,
            "extracted_tasks": [task.to_dict() for task in tasks],
            "task_count": len(tasks)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/summary")
async def get_meeting_summary(room_id: str):
    """Get comprehensive meeting summary."""
    try:
        store = get_transcript_store()
        transcript_entries = store.get_session_transcript(room_id)
        
        if not transcript_entries:
            raise HTTPException(status_code=404, detail="No transcript found")
        
        # Generate AI summary
        summary_service = get_summary_service()
        transcript_texts = [e.text for e in transcript_entries]
        summary_result = await summary_service.generate_structured_summary(
            transcript_texts,
            room_id,
            mode="final"
        )
        
        # Get tasks
        task_engine = get_task_assignment_engine()
        task_summary = task_engine.get_task_summary(room_id)
        tasks = task_engine.get_meeting_tasks(room_id)
        
        # Get emotion analysis
        emotion_service = get_emotion_service()
        emotion_analysis = await emotion_service.analyze_session_emotions(
            [e.to_dict() for e in transcript_entries]
        )
        
        # Get emotion guidance summary
        guidance_engine = get_emotion_guidance_engine()
        emotion_timeline = [
            {
                "emotion": e.emotions.get("emotion", "neutral") if e.emotions else "neutral",
                "timestamp": e.timestamp.isoformat(),
                "speaker": e.speaker
            }
            for e in transcript_entries
        ]
        emotion_guidance = guidance_engine.get_meeting_summary_guidance(emotion_timeline)
        
        return {
            "room_id": room_id,
            "summary": summary_result,
            "task_summary": task_summary,
            "tasks": [task.to_dict() for task in tasks],
            "emotion_analysis": emotion_analysis,
            "emotion_guidance": emotion_guidance,
            "total_participants": len(set(e.speaker for e in transcript_entries)),
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/export")
async def export_meeting_data(room_id: str, format: str = Query("json")):
    """Export all meeting data locally."""
    try:
        import json as json_lib
        
        # Get all data
        summary_data = await get_meeting_summary(room_id)
        
        store = get_transcript_store()
        full_transcript = store.get_session_transcript(room_id)
        
        export_data = {
            "room_id": room_id,
            "export_timestamp": datetime.utcnow().isoformat(),
            "transcript": [e.to_dict() for e in full_transcript],
            "summary": summary_data["summary"],
            "tasks": summary_data["tasks"],
            "emotion_analysis": summary_data["emotion_analysis"],
            "emotion_guidance": summary_data["emotion_guidance"],
            "task_summary": summary_data["task_summary"]
        }
        
        if format == "json":
            # Save to file
            filename = f"meeting_{room_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(f"data/{filename}", "w") as f:
                json_lib.dump(export_data, f, indent=2)
            
            return {
                "success": True,
                "filename": filename,
                "data": export_data
            }
        
        return export_data
        
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket for Real-Time Collaboration

@router.websocket("/rooms/{room_id}/ws")
async def meeting_websocket(
    websocket: WebSocket,
    room_id: str,
    user_id: str = Query(...),
    username: str = Query(...),
    password: Optional[str] = Query(None),
    role: str = Query("participant")
):
    """
    Real-time meeting WebSocket.
    
    Client sends:
    - {"type": "audio_chunk", "audio_data": "base64...", "sample_rate": 16000}
    - {"type": "chat", "message": "..."}
    - {"type": "ping"}
    
    Client receives:
    - {"type": "live_transcript", ...}
    - {"type": "participant_joined", ...}
    - {"type": "pong"}
    """
    
    room_manager = get_meeting_room_manager()
    
    try:
        # Join room
        participant_role = ParticipantRole(role)
        participant = await room_manager.join_room(
            room_id=room_id,
            user_id=user_id,
            username=username,
            websocket=websocket,
            password=password,
            role=participant_role
        )
        
        logger.info(f"✅ {username} joined {room_id}")
        
        # Send welcome
        await websocket.send_json({
            "type": "welcome",
            "message": f"Welcome {username}!",
            "your_role": role,
            "room_info": await room_manager.get_room_info(room_id)
        })
        
        # Message loop
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            message_type = message.get("type")
            
            if message_type == "audio_chunk":
                await process_audio(
                    room_id, user_id, username, message, room_manager
                )
            
            elif message_type == "chat":
                await room_manager.broadcast_to_room(room_id, {
                    "type": "chat_message",
                    "from_user": username,
                    "message": message.get("message"),
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            elif message_type == "ping":
                await websocket.send_json({"type": "pong"})
        
    except WebSocketDisconnect:
        logger.info(f"❌ {username} left {room_id}")
        await room_manager.leave_room(room_id, user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await room_manager.leave_room(room_id, user_id)


async def process_audio(room_id, user_id, username, message, room_manager):
    """Process audio chunk with full AI pipeline."""
    try:
        audio_base64 = message.get("audio_data", "")
        if not audio_base64:
            return
        
        audio_bytes = base64.b64decode(audio_base64)
        audio_array, sample_rate = bytes_to_numpy(audio_bytes, 16000)
        
        if len(audio_array) == 0:
            return
        
        # Transcribe
        transcription_service = get_transcription_service()
        segments = await transcription_service.transcribe_chunk(
            audio_array, room_id, sample_rate
        )
        
        for segment in segments:
            if not segment.text.strip():
                continue
            
            # Emotion analysis
            emotion_service = get_emotion_service()
            emotion_result = await emotion_service.analyze_text(segment.text)
            emotion = emotion_result.get("emotion", "neutral")
            confidence = emotion_result.get("confidence", 0.0)
            
            # Emotion guidance
            guidance_engine = get_emotion_guidance_engine()
            guidance = guidance_engine.get_guidance(
                emotion, segment.text, confidence,
                context={"username": username, "room_id": room_id}
            )
            
            # Broadcast to all
            await room_manager.broadcast_transcript(
                room_id=room_id,
                user_id=user_id,
                username=username,
                text=segment.text,
                emotion=emotion,
                confidence=confidence,
                emotion_guidance=guidance
            )
            
            # Store transcript
            store = get_transcript_store()
            entry = await store.add_transcript_entry(
                meeting_id=room_id,
                speaker=username,
                text=segment.text,
                confidence=segment.confidence
            )
            
            # Store emotion data
            if entry:
                entry.emotions = {
                    "emotion": emotion,
                    "confidence": confidence,
                    "scores": emotion_result.get("scores", {})
                }
            
    except Exception as e:
        logger.error(f"Audio processing error: {e}")