# app/routers/meeting.py
"""
Complete multi-user meeting router with real-time collaboration.
Handles rooms, participants, live transcription, emotions, and task assignment.
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
    ParticipantRole,
    MeetingStatus
)
from app.services.orchestrator_service import get_orchestrator_service
from app.services.emotion_guidance import get_emotion_guidance_engine
from app.services.task_assignment import get_task_assignment_engine
from app.services.audio_utils import bytes_to_numpy
from app.services.transcription_service import get_transcription_service
from app.services.emotion_analysis import get_emotion_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/meeting", tags=["Multi-User Meetings"])


# Request/Response Models
class CreateRoomRequest(BaseModel):
    room_name: str
    created_by: str
    password: Optional[str] = None
    max_participants: int = 50


class JoinRoomRequest(BaseModel):
    user_id: str
    username: str
    password: Optional[str] = None
    role: ParticipantRole = ParticipantRole.PARTICIPANT


# REST Endpoints

@router.post("/rooms/create")
async def create_meeting_room(room_id: str, request: CreateRoomRequest):
    """Create a new meeting room."""
    try:
        room_manager = get_meeting_room_manager()
        
        # Start broadcasting if not started
        await room_manager.start_broadcasting()
        
        room = await room_manager.create_room(
            room_id=room_id,
            room_name=request.room_name,
            created_by=request.created_by,
            password=request.password,
            max_participants=request.max_participants
        )
        
        return {
            "success": True,
            "room": room.to_dict(),
            "websocket_url": f"/meeting/rooms/{room_id}/ws"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating room: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/rooms/{room_id}")
async def get_room_info(room_id: str):
    """Get room information and participants."""
    try:
        room_manager = get_meeting_room_manager()
        room_info = await room_manager.get_room_info(room_id)
        
        if not room_info:
            raise HTTPException(status_code=404, detail="Room not found")
        
        return room_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting room info: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/rooms")
async def list_rooms():
    """List all active meeting rooms."""
    try:
        room_manager = get_meeting_room_manager()
        rooms = await room_manager.list_rooms()
        
        return {
            "rooms": rooms,
            "total_count": len(rooms)
        }
        
    except Exception as e:
        logger.error(f"Error listing rooms: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/rooms/{room_id}/tasks")
async def get_meeting_tasks(room_id: str):
    """Get all tasks/action items from the meeting."""
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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/rooms/{room_id}/tasks/extract")
async def extract_tasks_from_meeting(room_id: str):
    """Extract tasks from meeting transcript using AI."""
    try:
        from app.modules.realtime_store import get_transcript_store
        
        # Get transcript
        store = get_transcript_store()
        transcript_entries = store.get_session_transcript(room_id)
        
        if not transcript_entries:
            raise HTTPException(status_code=404, detail="No transcript found")
        
        # Get participants
        room_manager = get_meeting_room_manager()
        participants = await room_manager.get_room_participants(room_id)
        
        # Extract tasks
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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/rooms/{room_id}/summary")
async def get_meeting_summary(room_id: str):
    """Get comprehensive meeting summary with tasks and emotions."""
    try:
        from app.modules.realtime_store import get_transcript_store
        
        # Get transcript
        store = get_transcript_store()
        transcript_entries = store.get_session_transcript(room_id)
        
        if not transcript_entries:
            raise HTTPException(status_code=404, detail="No transcript found")
        
        # Get orchestrator for summary
        orchestrator = get_orchestrator_service()
        insights = await orchestrator.generate_session_insights(room_id)
        
        # Get tasks
        task_engine = get_task_assignment_engine()
        task_summary = task_engine.get_task_summary(room_id)
        tasks = task_engine.get_meeting_tasks(room_id)
        
        # Get emotion guidance summary
        guidance_engine = get_emotion_guidance_engine()
        emotion_timeline = [
            {"emotion": e.emotions} for e in transcript_entries if e.emotions
        ]
        emotion_guidance = guidance_engine.get_meeting_summary_guidance(emotion_timeline)
        
        return {
            "room_id": room_id,
            "meeting_insights": insights,
            "task_summary": task_summary,
            "tasks": [task.to_dict() for task in tasks],
            "emotion_guidance": emotion_guidance,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# WebSocket Endpoint for Real-Time Collaboration

@router.websocket("/rooms/{room_id}/ws")
async def meeting_room_websocket(
    websocket: WebSocket,
    room_id: str,
    user_id: str = Query(...),
    username: str = Query(...),
    password: Optional[str] = Query(None),
    role: ParticipantRole = Query(ParticipantRole.PARTICIPANT)
):
    """
    WebSocket endpoint for real-time meeting collaboration.
    
    Messages from client:
    - {"type": "audio_chunk", "audio_data": "base64...", "sample_rate": 16000}
    - {"type": "chat", "message": "text message"}
    - {"type": "mute", "is_muted": true}
    - {"type": "ping"}
    
    Messages to client:
    - {"type": "live_transcript", "user_id": "...", "text": "...", "emotion": "...", "emotion_guidance": {...}}
    - {"type": "participant_joined", "user_id": "...", "username": "..."}
    - {"type": "participant_left", "user_id": "..."}
    - {"type": "chat_message", "from_user": "...", "message": "..."}
    - {"type": "pong"}
    """
    
    room_manager = get_meeting_room_manager()
    transcription_service = get_transcription_service()
    emotion_service = get_emotion_service()
    guidance_engine = get_emotion_guidance_engine()
    
    try:
        # Join room
        participant = await room_manager.join_room(
            room_id=room_id,
            user_id=user_id,
            username=username,
            websocket=websocket,
            password=password,
            role=role
        )
        
        logger.info(f"User {username} joined room {room_id}")
        
        # Send welcome message
        await websocket.send_json({
            "type": "welcome",
            "message": f"Welcome to {room_id}, {username}!",
            "your_role": role.value,
            "room_info": await room_manager.get_room_info(room_id)
        })
        
        # Main message loop
        while True:
            # Receive message
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get("type")
            
            if message_type == "audio_chunk":
                # Process audio chunk
                await handle_audio_chunk(
                    room_id,
                    user_id,
                    username,
                    message,
                    room_manager,
                    transcription_service,
                    emotion_service,
                    guidance_engine
                )
            
            elif message_type == "chat":
                # Broadcast chat message
                await room_manager.broadcast_to_room(room_id, {
                    "type": "chat_message",
                    "from_user_id": user_id,
                    "from_username": username,
                    "message": message.get("message", ""),
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            elif message_type == "mute":
                # Update mute status
                await room_manager.update_participant_state(
                    room_id,
                    user_id,
                    is_muted=message.get("is_muted", False)
                )
            
            elif message_type == "ping":
                # Respond to ping
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            else:
                logger.warning(f"Unknown message type: {message_type}")
        
    except WebSocketDisconnect:
        logger.info(f"User {username} disconnected from room {room_id}")
        await room_manager.leave_room(room_id, user_id)
    
    except Exception as e:
        logger.error(f"WebSocket error for {username} in {room_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
        finally:
            await room_manager.leave_room(room_id, user_id)


async def handle_audio_chunk(
    room_id: str,
    user_id: str,
    username: str,
    message: dict,
    room_manager,
    transcription_service,
    emotion_service,
    guidance_engine
):
    """Handle audio chunk processing and broadcasting."""
    try:
        # Decode audio
        audio_base64 = message.get("audio_data", "")
        sample_rate = message.get("sample_rate", 16000)
        
        if not audio_base64:
            return
        
        audio_bytes = base64.b64decode(audio_base64)
        audio_array, _ = bytes_to_numpy(audio_bytes, sample_rate)
        
        if len(audio_array) == 0:
            return
        
        # Transcribe
        segments = await transcription_service.transcribe_chunk(audio_array, room_id, sample_rate)
        
        for segment in segments:
            if not segment.text.strip():
                continue
            
            # Analyze emotion
            emotion_result = await emotion_service.analyze_text(segment.text)
            emotion = emotion_result.get("emotion", "neutral")
            confidence = emotion_result.get("confidence", 0.0)
            
            # Get emotion guidance
            guidance = guidance_engine.get_guidance(
                emotion,
                segment.text,
                confidence,
                context={"username": username, "room_id": room_id}
            )
            
            # Broadcast to all participants
            await room_manager.broadcast_transcript(
                room_id=room_id,
                user_id=user_id,
                username=username,
                text=segment.text,
                emotion=emotion,
                confidence=confidence,
                emotion_guidance=guidance
            )
            
            # Store in transcript store
            from app.modules.realtime_store import get_transcript_store
            store = get_transcript_store()
            
            await store.add_transcript_entry(
                meeting_id=room_id,
                speaker=username,
                text=segment.text,
                confidence=segment.confidence
            )
            
    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}")