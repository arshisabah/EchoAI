# app/routers/meeting.py
"""
Fixed Multi-User Meeting Router with proper error handling
"""

import asyncio
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
from app.services.orchestrator_service import get_orchestrator_service
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
        password = request.password
        if password in ("", " ", None, "null", "undefined"):
            password = None
        room = await room_manager.create_room(
            room_id=room_id,
            room_name=request.room_name,
            created_by=request.created_by,
            password=password,
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
            "websocket_url": f"/meeting/rooms/{room_id}/ws"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating room: {e}", exc_info=True)
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
        logger.error(f"Error getting room: {e}", exc_info=True)
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
        logger.error(f"Error listing rooms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rooms/{room_id}")
async def end_meeting_room(room_id: str, ended_by: str = Query(...)):
    """End a meeting room."""
    try:
        room_manager = get_meeting_room_manager()
        room = room_manager.rooms.get(room_id)
        
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        
        await room_manager.end_room(room_id, ended_by)
        
        # Also delete from store
        store = get_transcript_store()
        # Also delete from store (if exists)
        store = get_transcript_store()
        try:
            # if async:
            maybe = store.delete_session(room_id)
            if asyncio.iscoroutine(maybe):
                await maybe
        except Exception as e:
            logger.debug(f"Warning: delete_session failed (maybe missing): {e}", exc_info=True)
        
        return {
            "success": True,
            "message": f"Room {room_id} ended successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending room: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/transcript")
async def get_room_transcript(room_id: str):
    """Get complete meeting transcript."""
    try:
        store = get_transcript_store()
        entries = store.get_session_transcript(room_id)
        
        return {
            "room_id": room_id,
            "transcript": json.loads(json.dumps([e.to_dict() for e in entries], default=str)),
            "total_entries": len(entries)
        }
        
    except Exception as e:
        logger.error(f"Error getting transcript: {e}", exc_info=True)
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
        logger.error(f"Error getting tasks: {e}", exc_info=True)
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
        room = room_manager.rooms.get(room_id)
        
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        
        participants = [p.to_dict() for p in room.participants.values()]
        
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
        logger.error(f"Error extracting tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/summary")
async def get_meeting_summary(room_id: str):
    """Get comprehensive meeting summary."""
    try:
        store = get_transcript_store()
        transcript_entries = store.get_session_transcript(room_id)
        
        if not transcript_entries:
            return {
                "room_id": room_id,
                "summary": "No transcript available yet",
                "tasks": [],
                "analytics": {}
            }
        
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
        
        # Get analytics
        analytics = store.get_analytics(room_id)
        
        return {
            "room_id": room_id,
            "summary": summary_result,
            "task_summary": task_summary,
            "tasks": [task.to_dict() for task in tasks],
            "analytics": analytics,
            "total_participants": len(set(e.speaker for e in transcript_entries)),
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/export")
async def export_meeting_data(room_id: str, format: str = Query("json")):
    """Export all meeting data."""
    try:
        summary_data = await get_meeting_summary(room_id)
        store = get_transcript_store()
        full_transcript = store.get_session_transcript(room_id)
        
        export_data = {
            "room_id": room_id,
            "export_timestamp": datetime.utcnow().isoformat(),
            "transcript": [e.to_dict() for e in full_transcript],
            "summary": summary_data.get("summary"),
            "tasks": summary_data.get("tasks", []),
            "analytics": summary_data.get("analytics", {})
        }
        
        return export_data
        
    except Exception as e:
        logger.error(f"Error exporting data: {e}", exc_info=True)
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
    """Real-time meeting WebSocket."""
    room_manager = get_meeting_room_manager()
    try:
        # Accept first, but guard join with try/except so we can close on failures
        await websocket.accept()

        # Ensure room exists before attempting join (avoid creating implicit room)
        existing_room = room_manager.rooms.get(room_id)
        if not existing_room:
            # send clear error then close
            await websocket.send_json({"type": "error", "message": f"Room {room_id} not found"})
            await websocket.close()
            return

        # If user already has a connection, close that connection first (safer than leave_room which broadcasts)
        if existing_room and user_id in existing_room.participants:
            old_participant = existing_room.participants[user_id]
            try:
                # close old websocket quietly
                await old_participant.websocket.close()
            except Exception:
                logger.debug(f"Failed to close old websocket for {user_id}", exc_info=True)
            # remove old record
            existing_room.participants.pop(user_id, None)

        # Now join room
        participant_role = ParticipantRole(role)
        try:
            participant = await room_manager.join_room(
                room_id=room_id,
                user_id=user_id,
                username=username,
                websocket=websocket,
                password=password,
                role=participant_role
            )
        except Exception as e:
            logger.error(f"Failed to join room {room_id} for user {user_id}: {e}", exc_info=True)
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
            return
        logger.info(f"✅ {username} joined {room_id}")
        # Notify all others that a new participant joined (for WebRTC handshake)
        await room_manager.broadcast_to_room(room_id, {
            "type": "new_participant",
            "user_id": user_id,
            "username": username,
            "timestamp": datetime.utcnow().isoformat()
        }, exclude_user_id=user_id)
        
        # Send welcome with room info
        room_info = await room_manager.get_room_info(room_id)
        await websocket.send_json({
            "type": "welcome",
            "message": f"Welcome {username}!",
            "your_role": role,
            "room_info": room_info
        })

         # 6️⃣ (✨ NEW) Send a connection acknowledgement to frontend
        await websocket.send_json({
            "type": "connection_ack",
            "message": f"Connected successfully as {username}",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Message loop
        while True:
            try:
                # Wait for client message with a 30-second timeout
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                # If no message within 30 seconds, send heartbeat ping
                await websocket.send_json({
                    "type": "ping_timeout",
                    "message": "No message received within 30 seconds. Sending keep-alive ping.",
                    "timestamp": datetime.utcnow().isoformat()
                })
                continue  # Go back to waiting for next message
            except Exception as e:
                logger.error(f"WebSocket receive error in {room_id}: {e}", exc_info=True)
                break  # Exit loop on fatal receive errors

            # Normal message handling
            message = json.loads(data)
            message_type = message.get("type")
            
            if message_type == "audio_chunk":
                await process_audio(
                    room_id, user_id, username, message, room_manager, websocket
                )
            
            elif message_type == "chat":
                chat_message = {
                    "type": "chat_message",
                    "from_user": username,
                    "message": message.get("message"),
                    "timestamp": datetime.utcnow().isoformat()
                }
                await room_manager.broadcast_to_room(room_id, chat_message)
                await websocket.send_json({"type": "chat_ack", "message": chat_message["message"]})

            # --- WebRTC Signaling ---
            elif message_type in {"webrtc_offer", "webrtc_answer", "ice_candidate"}:
                target_id = message.get("target_id")
                if target_id and room_id in room_manager.rooms:
                    room = room_manager.rooms[room_id]
                    if target_id in room.participants:
                        target_ws = room.participants[target_id].websocket
                        await target_ws.send_json({
                            **message,
                            "from_id": user_id,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    else:
                        logger.warning(f"⚠️ Target {target_id} not found in {room_id}") 


            elif message_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
        
    except WebSocketDisconnect:
        logger.info(f"❌ {username} left {room_id}")
        await room_manager.leave_room(room_id, user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await room_manager.leave_room(room_id, user_id)
        except:
            pass

    finally:
        # 8️⃣ (✨ NEW) Always ensure cleanup even if socket closes unexpectedly
        if websocket.client_state.name != "CONNECTED":
            try:
                await room_manager.leave_room(room_id, user_id)
            except Exception:
                pass



async def process_audio(room_id, user_id, username, message, room_manager, websocket):
    """Process audio chunk using unified Orchestrator pipeline."""
    try:
        # 1️⃣ Extract base64 audio from message
        audio_base64 = message.get("audio_data") or message.get("data", "")
        if not audio_base64:
            logger.warning(f"No audio data found for user {username} in room {room_id}")
            return

        # 2️⃣ Decode base64 → bytes
        audio_bytes = base64.b64decode(audio_base64)

        # 3️⃣ Run unified AI pipeline via orchestrator
        orchestrator = get_orchestrator_service()
        result = await orchestrator.process_audio_chunk(
            audio_bytes=audio_bytes,
            session_id=room_id,
            participant_id=user_id
        )

        # 🔹 Handle lightweight "listening" heartbeats
        if result and result.get("type") == "listening":
            await websocket.send_json(result)  # send only to this user (not broadcast)
            return
        # 4️⃣ Skip empty result
        if not result:
            logger.debug(f"No result from orchestrator for user {username} in {room_id}")
            return

        # If orchestrator returned a multi-speaker chunk, handle each entry
        if result.get("type") == "multi_speaker_chunk":
            entries = result.get("entries", [])
        else:
            # single entry expected to have 'text'
            entries = [result] if result.get("text") else []

        if not entries:
            logger.debug(f"No valid transcription entries for {username} in {room_id}")
            return

        # Iterate entries (may contain different speaker ids)
        for entry in entries:
            text = entry.get("text", "")
            if not text.strip():
                continue

            speaker = entry.get("speaker") or user_id  # prefer orchestrator speaker, fallback to user_id
            confidence = entry.get("emotion_confidence", entry.get("confidence", 0.0))
            emotion = entry.get("emotion", "neutral")

            # Emotion guidance
            guidance_engine = get_emotion_guidance_engine()
            guidance = guidance_engine.get_guidance(emotion, text, confidence,
                                                   context={"username": username, "room_id": room_id, "speaker": speaker})

            # Broadcast
            await room_manager.broadcast_transcript(
                room_id=room_id,
                user_id=user_id,
                username=username,
                text=text,
                emotion=emotion,
                confidence=confidence,
                emotion_guidance=guidance
            )

            # Store transcript
            store = get_transcript_store()
            # store.add_transcript_entry might be async — use await if it's defined async
            entry_obj = await store.add_transcript_entry(
                meeting_id=room_id,
                speaker=speaker,
                text=text,
                confidence=entry.get("confidence", 1.0)
            )

            if entry_obj:
                entry_obj.emotions = {
                    "emotion": emotion,
                    "confidence": confidence,
                    "scores": entry.get("emotion_scores", {})
                }

            logger.debug(f"🗣️ [{speaker}] '{text[:60]}' | Emotion={emotion} ({confidence:.2f})")

    except Exception as e:
        logger.error(f"Audio processing error in room {room_id}: {e}", exc_info=True)