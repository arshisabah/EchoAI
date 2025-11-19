# app/routers/meeting.py
"""
✅ FIXED: Transcription processing and room creation
✅ Proper handling of orchestrator responses
✅ Speaker diarization working
✅ Room name search endpoint added
"""

import asyncio
import logging
import json
import base64
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import Response
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
from app.modules.audio_recorder import get_or_create_recorder, get_recorder, delete_recorder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/meeting", tags=["Multi-User Meetings"])


# Request Models
class CreateRoomRequest(BaseModel):
    room_name: str
    created_by: str
    password: Optional[str] = None
    max_participants: int = 50


# REST Endpoints --------------------------------------------------------------

@router.post("/rooms/create")
async def create_meeting_room(request: CreateRoomRequest):
    """✅ FIXED: Create room using room_name as room_id"""
    try:
        room_manager = get_meeting_room_manager()
        await room_manager.start_broadcasting()
        
        # ✅ FIX: Use room_name as room_id so users can join by name
        room_id = request.room_name
        
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
        maybe = store.create_session(room_id, {
            "room_name": request.room_name,
            "created_by": request.created_by
        })
        if asyncio.iscoroutine(maybe):
            await maybe

        return {
            "success": True,
            "room": room.to_dict(),
            "room_id": room_id,
            "websocket_url": f"/meeting/rooms/{room_id}/ws"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating room: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/search")
async def search_room_by_name(room_name: str = Query(...)):
    """✅ NEW: Search for room by name"""
    try:
        room_manager = get_meeting_room_manager()
        room_info = await room_manager.get_room_info(room_name)
        
        if not room_info:
            raise HTTPException(status_code=404, detail="Room not found")
        
        return room_info
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching room: {e}", exc_info=True)
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

        # Stop recording if active
        recorder = get_recorder(room_id)
        if recorder and recorder.is_recording:
            recorder.stop_recording()
            logger.info(f"Stopped recording for room {room_id}")

        await room_manager.end_room(room_id, ended_by)

        # Also delete from store (if exists)
        store = get_transcript_store()
        try:
            maybe = store.delete_session(room_id)
            if asyncio.iscoroutine(maybe):
                await maybe
        except Exception as e:
            logger.debug(f"Warning: delete_session failed (maybe missing): {e}", exc_info=True)

        return {
            "success": True,
            "message": f"Room {room_id} ended successfully",
            "recording_available": recorder is not None
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


@router.get("/rooms/{room_id}/recording/download")
async def download_meeting_recording(room_id: str):
    """Download the meeting recording as WAV file."""
    try:
        recorder = get_recorder(room_id)
        
        if not recorder:
            raise HTTPException(status_code=404, detail="No recording found for this room")
        
        # Stop recording if still active
        if recorder.is_recording:
            recorder.stop_recording()
        
        # Get WAV bytes
        wav_bytes = recorder.get_wav_bytes()
        
        if not wav_bytes:
            raise HTTPException(status_code=404, detail="No audio data available")
        
        # Return as downloadable file
        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename=meeting_{room_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.wav"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading recording: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/recording/metadata")
async def get_recording_metadata(room_id: str):
    """Get metadata about the meeting recording."""
    try:
        recorder = get_recorder(room_id)
        
        if not recorder:
            raise HTTPException(status_code=404, detail="No recording found for this room")
        
        return recorder.get_metadata()
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recording metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/transcript/download")
async def download_meeting_transcript(room_id: str, format: str = Query("txt", regex="^(txt|json|srt)$")):
    """
    Download the meeting transcript in various formats.
    
    Args:
        room_id: Room identifier
        format: Output format (txt, json, srt)
    """
    try:
        store = get_transcript_store()
        transcript_entries = store.get_session_transcript(room_id)
        
        if not transcript_entries:
            raise HTTPException(status_code=404, detail="No transcript found for this room")
        
        # Generate content based on format
        if format == "txt":
            content = _generate_txt_transcript(transcript_entries)
            media_type = "text/plain"
            extension = "txt"
        elif format == "json":
            content = _generate_json_transcript(transcript_entries)
            media_type = "application/json"
            extension = "json"
        elif format == "srt":
            content = _generate_srt_transcript(transcript_entries)
            media_type = "text/plain"
            extension = "srt"
        else:
            raise HTTPException(status_code=400, detail="Invalid format. Use txt, json, or srt")
        
        # Return as downloadable file
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename=transcript_{room_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{extension}"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading transcript: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _generate_txt_transcript(entries) -> str:
    """Generate plain text transcript."""
    lines = []
    lines.append("=" * 80)
    lines.append("MEETING TRANSCRIPT")
    lines.append("=" * 80)
    lines.append("")
    
    for entry in entries:
        timestamp = entry.timestamp.strftime("%H:%M:%S") if hasattr(entry.timestamp, 'strftime') else str(entry.timestamp)
        speaker = entry.speaker or "Unknown"
        text = entry.text
        
        # Add emotion info if available
        emotion_str = ""
        if hasattr(entry, 'emotions') and entry.emotions:
            emotion = entry.emotions.get('emotion', 'neutral')
            confidence = entry.emotions.get('confidence', 0)
            emotion_str = f" [{emotion.upper()} {confidence:.0%}]"
        
        lines.append(f"[{timestamp}] {speaker}{emotion_str}:")
        lines.append(f"  {text}")
        lines.append("")
    
    return "\n".join(lines)


def _generate_json_transcript(entries) -> str:
    """Generate JSON transcript."""
    transcript_data = {
        "transcript": [
            {
                "timestamp": entry.timestamp.isoformat() if hasattr(entry.timestamp, 'isoformat') else str(entry.timestamp),
                "speaker": entry.speaker or "Unknown",
                "text": entry.text,
                "confidence": getattr(entry, 'confidence', 1.0),
                "emotions": getattr(entry, 'emotions', {}) or {}
            }
            for entry in entries
        ],
        "total_entries": len(entries),
        "generated_at": datetime.utcnow().isoformat()
    }
    
    return json.dumps(transcript_data, indent=2)


def _generate_srt_transcript(entries) -> str:
    """Generate SRT subtitle format transcript."""
    lines = []
    
    for idx, entry in enumerate(entries, 1):
        # SRT format:
        # 1
        # 00:00:00,000 --> 00:00:05,000
        # Speaker: Text
        
        timestamp = entry.timestamp
        
        # Calculate approximate duration (assume 3 seconds per entry if no duration info)
        duration_seconds = 3
        
        # Format timestamps for SRT
        if hasattr(timestamp, 'strftime'):
            start_time = timestamp.strftime("%H:%M:%S,000")
            # Add duration
            end_timestamp = timestamp
            try:
                from datetime import timedelta
                end_timestamp = timestamp + timedelta(seconds=duration_seconds)
            except:
                pass
            end_time = end_timestamp.strftime("%H:%M:%S,000")
        else:
            start_time = "00:00:00,000"
            end_time = "00:00:03,000"
        
        speaker = entry.speaker or "Unknown"
        text = entry.text
        
        lines.append(str(idx))
        lines.append(f"{start_time} --> {end_time}")
        lines.append(f"{speaker}: {text}")
        lines.append("")
    
    return "\n".join(lines)


# WebSocket for Real-Time Collaboration ---------------------------------------

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
        # Accept socket
        await websocket.accept()

        # Ensure room exists
        existing_room = room_manager.rooms.get(room_id)
        if not existing_room:
            await websocket.send_json({"type": "error", "message": f"Room {room_id} not found"})
            await websocket.close()
            return

        # If user already connected, close old socket and remove record
        if existing_room and user_id in existing_room.participants:
            old_participant = existing_room.participants[user_id]
            try:
                await old_participant.websocket.close()
            except Exception:
                logger.debug(f"Failed to close old websocket for {user_id}", exc_info=True)
            existing_room.participants.pop(user_id, None)

        # Determine actual role server-side (trust created_by)
        room_for_role_check = room_manager.rooms.get(room_id)
        actual_role = ParticipantRole.HOST if (room_for_role_check and room_for_role_check.created_by == username) else ParticipantRole.PARTICIPANT

        # Try to join the room
        try:
            participant = await room_manager.join_room(
                room_id=room_id,
                user_id=user_id,
                username=username,
                websocket=websocket,
                password=password,
                role=actual_role
            )
        except Exception as e:
            logger.error(f"Failed to join room {room_id} for user {user_id}: {e}", exc_info=True)
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
            return

        logger.info(f"✅ {username} joined {room_id} as {participant.role.value}")

        # Start recording if this is the first participant
        recorder = get_or_create_recorder(room_id)
        if not recorder.is_recording:
            recorder.start_recording()
            logger.info(f"Started recording for room {room_id}")

        # Broadcast a lightweight "new_participant" event to others so they start WebRTC handshake
        # (exclude the newly-joined user)
        await room_manager.broadcast_to_room(room_id, {
            "type": "new_participant",
            "user_id": user_id,
            "username": username,
            "timestamp": datetime.utcnow().isoformat()
        }, exclude_user_id=user_id)

        # Send welcome + ack to the new user
        room_info = await room_manager.get_room_info(room_id)
        await websocket.send_json({
            "type": "welcome",
            "message": f"Welcome {username}!",
            "your_role": participant.role.value,
            "room_info": room_info
        })

        await websocket.send_json({
            "type": "connection_ack",
            "message": f"Connected successfully as {username}",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Send peer list (existing participants excluding self) so the client can initiate offers
        peers = []
        room_after_join = room_manager.rooms.get(room_id)
        if room_after_join:
            for uid, p in room_after_join.participants.items():
                if uid == user_id:
                    continue
                peers.append({"user_id": uid, "username": p.username})

        await websocket.send_json({
            "type": "peer_list",
            "peers": peers
        })

        # Echo a new_participant to the new user (self = True) to make client-side logic uniform
        await websocket.send_json({
            "type": "new_participant",
            "user_id": user_id,
            "username": username,
            "timestamp": datetime.utcnow().isoformat(),
            "self": True
        })

        # ✅ FIX: Send historical transcripts to newly joined participant
        # This ensures they can see what happened before they joined
        try:
            store = get_transcript_store()
            historical_transcripts = store.get_session_transcript(room_id)
            
            if historical_transcripts:
                logger.info(f"📜 Sending {len(historical_transcripts)} historical transcripts to {username}")
                
                # Send historical transcripts in batches to avoid overwhelming the connection
                batch_size = 10
                for i in range(0, len(historical_transcripts), batch_size):
                    batch = historical_transcripts[i:i + batch_size]
                    
                    for entry in batch:
                        # Format each transcript entry to match live_transcript format
                        transcript_message = {
                            "type": "live_transcript",
                            "user_id": entry.speaker or "unknown",
                            "username": entry.speaker or "Unknown Speaker",
                            "text": entry.text,
                            "emotion": entry.emotions.get("emotion", "neutral") if entry.emotions else "neutral",
                            "confidence": entry.emotions.get("confidence", 0.0) if entry.emotions else 0.0,
                            "emotion_guidance": {},
                            "timestamp": entry.timestamp.isoformat() if hasattr(entry.timestamp, 'isoformat') else str(entry.timestamp),
                            "is_historical": True  # Mark as historical so frontend can handle differently if needed
                        }
                        await websocket.send_json(transcript_message)
                    
                    # Small delay between batches to prevent overwhelming the connection
                    await asyncio.sleep(0.05)
                
                logger.info(f"✅ Historical transcripts sent to {username}")
        except Exception as e:
            logger.error(f"Failed to send historical transcripts to {username}: {e}", exc_info=True)

        # Main receive loop with extended timeout for long meetings
        # Timeout extended to 180 seconds (3 minutes) to support 30+ minute meetings
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=180)
            except asyncio.TimeoutError:
                # send keep-alive ping after 3 minutes of inactivity
                try:
                    await websocket.send_json({
                        "type": "ping_timeout",
                        "message": "Keep-alive: No message received within 180 seconds.",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception:
                    pass
                continue
            except WebSocketDisconnect:
                logger.info(f"WebSocketDisconnect for {username} in {room_id}")
                break
            except Exception as e:
                logger.error(f"WebSocket receive error in {room_id}: {e}", exc_info=True)
                break

            # Handle incoming message
            try:
                message = json.loads(data)
            except Exception:
                logger.warning("Invalid JSON received, skipping")
                continue

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
                try:
                    await websocket.send_json({"type": "chat_ack", "message": chat_message["message"]})
                except Exception:
                    pass

            # WebRTC signaling routing: target_id must be present and will be forwarded
            elif message_type in {"webrtc_offer", "webrtc_answer", "ice_candidate"}:
                target_id = message.get("target_id")
                if target_id and room_id in room_manager.rooms:
                    room = room_manager.rooms[room_id]
                    if target_id in room.participants:
                        target_ws = room.participants[target_id].websocket
                        try:
                            await target_ws.send_json({
                                **message,
                                "from_id": user_id,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                        except Exception as e:
                            logger.warning(f"Failed to forward signaling to {target_id}: {e}", exc_info=True)
                    else:
                        logger.warning(f"⚠️ Target {target_id} not found in {room_id}")
                else:
                    logger.warning("Signaling message without target_id or room missing")

            elif message_type == "ping":
                try:
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception:
                    pass

            else:
                # Unknown/other messages — log for debugging
                logger.debug(f"Unknown WS message from {username} in {room_id}: {message_type}")

    except WebSocketDisconnect:
        logger.info(f"❌ {username} disconnected from {room_id}")
        try:
            await room_manager.leave_room(room_id, user_id)
        except Exception:
            logger.exception("Error during leave_room on WebSocketDisconnect")
    except Exception as e:
        logger.error(f"WebSocket error for {username} in {room_id}: {e}", exc_info=True)
        try:
            await room_manager.leave_room(room_id, user_id)
        except Exception:
            logger.exception("Error during leave_room on exception")
    finally:
        # final cleanup: ensure the participant is removed
        try:
            await room_manager.leave_room(room_id, user_id)
        except Exception:
            pass


# Audio processing helper -----------------------------------------------------

async def process_audio(room_id, user_id, username, message, room_manager, websocket):
    """✅ FIXED: Process audio chunk with proper format handling"""
    try:
        # 1️⃣ Extract base64 audio from message
        audio_base64 = message.get("audio") or message.get("audio_data") or message.get("data", "")
        if not audio_base64:
            logger.warning(f"No audio data found for user {username} in room {room_id}")
            return

        # 2️⃣ Decode base64 → bytes
        audio_bytes = base64.b64decode(audio_base64)

        # 2.5️⃣ Add audio to recorder for meeting recording
        try:
            recorder = get_recorder(room_id)
            if recorder and recorder.is_recording:
                # Convert bytes to numpy array for recording
                audio_array = bytes_to_numpy(audio_bytes, sample_rate=16000)
                recorder.add_audio_chunk(user_id, audio_array)
        except Exception as rec_err:
            logger.warning(f"Failed to add audio to recorder: {rec_err}")

        # 3️⃣ Run unified AI pipeline via orchestrator
        orchestrator = get_orchestrator_service()
        result = await orchestrator.process_audio_chunk(
            audio_bytes=audio_bytes,
            session_id=room_id,
            participant_id=user_id
        )

        # 🔹 Handle lightweight "listening" heartbeats
        if result and result.get("type") == "listening":
            try:
                await websocket.send_json(result)  # send only to this user (not broadcast)
            except Exception:
                pass
            return

        # 4️⃣ Skip empty result
        if not result:
            logger.debug(f"No result from orchestrator for user {username} in {room_id}")
            return

        # ✅ FIX: Handle both single and multi-speaker responses
        entries = []
        if result.get("type") == "multi_speaker_chunk":
            entries = result.get("entries", [])
        elif isinstance(result, dict) and result.get("text"):
            # Single entry
            entries = [result]

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

            # Broadcast transcript + emotion -> uses manager's broadcast_transcript
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

            logger.info(f"🗣️ [{speaker}] '{text[:60]}' | Emotion={emotion} ({confidence:.2f})")

    except Exception as e:
        logger.error(f"Audio processing error in room {room_id}: {e}", exc_info=True)