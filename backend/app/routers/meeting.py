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
from starlette.websockets import WebSocketState

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
from app.services.room_diarization_service import get_room_diarization_service
from app.utils.timezone import get_ist_timestamp

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/meeting", tags=["Multi-User Meetings"])

# Constants
DEFAULT_CONFIDENCE_FALLBACK = 0.9  # Default confidence when not available from transcription

_room_audio_buffers = {}  # In-memory buffer for audio chunks per room
_room_diarization_active = {}  # Track which rooms have diarization active

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
        
        # Return as downloadable file with IST timestamp
        from app.utils.timezone import utc_to_ist
        ist_now = utc_to_ist(datetime.utcnow())
        
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename=transcript_{room_id}_{ist_now.strftime('%Y%m%d_%H%M%S')}_IST.{extension}"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading transcript: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _generate_txt_transcript(entries) -> str:
    """Generate plain text transcript with IST timestamps."""
    from app.utils.timezone import utc_to_ist
    
    lines = []
    lines.append("=" * 80)
    lines.append("MEETING TRANSCRIPT")
    lines.append("=" * 80)
    lines.append("")
    
    for entry in entries:
        # Convert to IST time
        if hasattr(entry.timestamp, 'strftime'):
            ist_time = utc_to_ist(entry.timestamp)
            timestamp = ist_time.strftime("%I:%M:%S %p IST")  # 12-hour format with AM/PM
        else:
            timestamp = str(entry.timestamp)
        
        # Speaker is already the username (we fixed the storage)
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


@router.post("/rooms/{room_id}/diarize")
async def diarize_meeting_recording(room_id: str):
    """
    Perform offline diarization on the saved meeting recording.
    
    This endpoint:
    1. Gets the saved WAV recording from the audio recorder
    2. Sends it to Deepgram's pre-recorded API with diarization enabled
    3. Parses speaker labels and timestamps
    4. Stores results with speaker metadata
    5. Returns structured JSON with speaker segments
    
    Args:
        room_id: Room identifier
        
    Returns:
        Diarization results with speaker segments and timestamps
    """
    try:
        from app.core.config import settings
        
        # Check if Deepgram is available
        if not settings.DEEPGRAM_API_KEY:
            raise HTTPException(
                status_code=503, 
                detail="Deepgram API key not configured. Set DEEPGRAM_API_KEY environment variable."
            )
        
        # Get the recorder
        recorder = get_recorder(room_id)
        if not recorder:
            raise HTTPException(
                status_code=404, 
                detail=f"No recording found for room {room_id}"
            )
        
        # Stop recording if still active
        if recorder.is_recording:
            recorder.stop_recording()
        
        # Get WAV bytes
        wav_bytes = recorder.get_wav_bytes()
        if not wav_bytes or len(wav_bytes) < 100:
            raise HTTPException(
                status_code=404, 
                detail="No audio data available for diarization"
            )
        
        logger.info(f"🎙️ Starting offline diarization for room {room_id}, audio size: {len(wav_bytes)} bytes")
        
        # Use Deepgram pre-recorded API with diarization
        try:
            from deepgram import DeepgramClient, PrerecordedOptions, FileSource
            
            # Initialize Deepgram client
            deepgram = DeepgramClient(settings.DEEPGRAM_API_KEY)
            
            # Prepare audio payload
            payload: FileSource = {
                "buffer": wav_bytes,
            }
            
            # Configure options with diarization
            options = PrerecordedOptions(
                model="nova-2",
                smart_format=True,
                diarize=True,  # Enable speaker diarization
                punctuate=True,
                paragraphs=True,
                utterances=True,
            )
            
            # Make request to Deepgram
            logger.info(f"📤 Sending audio to Deepgram for diarization...")
            response = deepgram.listen.rest.v("1").transcribe_file(payload, options)
            
            logger.info(f"✅ Received diarization response from Deepgram")
            
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="Deepgram SDK not installed. Run: pip install deepgram-sdk"
            )
        except Exception as e:
            logger.error(f"❌ Deepgram API error: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Deepgram API error: {str(e)}"
            )
        
        # Parse diarization results
        diarized_segments = []
        speaker_stats = {}
        
        try:
            # Extract results
            if hasattr(response, 'results') and response.results:
                results = response.results
                
                # Process utterances (speaker-separated segments)
                if hasattr(results, 'utterances') and results.utterances:
                    for utterance in results.utterances:
                        speaker_id = utterance.speaker if hasattr(utterance, 'speaker') else 0
                        text = utterance.transcript if hasattr(utterance, 'transcript') else ""
                        start = utterance.start if hasattr(utterance, 'start') else 0
                        end = utterance.end if hasattr(utterance, 'end') else 0
                        confidence = utterance.confidence if hasattr(utterance, 'confidence') else 0
                        
                        segment = {
                            "speaker_id": f"Speaker {speaker_id}",
                            "text": text,
                            "start_time": start,
                            "end_time": end,
                            "duration": end - start,
                            "confidence": confidence,
                            "word_count": len(text.split())
                        }
                        
                        diarized_segments.append(segment)
                        
                        # Update speaker stats
                        speaker_key = f"Speaker {speaker_id}"
                        if speaker_key not in speaker_stats:
                            speaker_stats[speaker_key] = {
                                "total_duration": 0,
                                "total_words": 0,
                                "segment_count": 0
                            }
                        
                        speaker_stats[speaker_key]["total_duration"] += (end - start)
                        speaker_stats[speaker_key]["total_words"] += len(text.split())
                        speaker_stats[speaker_key]["segment_count"] += 1
                
                # If no utterances, fall back to words with speaker labels
                elif hasattr(results, 'channels') and len(results.channels) > 0:
                    channel = results.channels[0]
                    if hasattr(channel, 'alternatives') and len(channel.alternatives) > 0:
                        alternative = channel.alternatives[0]
                        
                        if hasattr(alternative, 'words'):
                            current_speaker = None
                            current_text = []
                            current_start = None
                            
                            for word in alternative.words:
                                word_speaker = word.speaker if hasattr(word, 'speaker') else 0
                                word_text = word.word if hasattr(word, 'word') else ""
                                word_start = word.start if hasattr(word, 'start') else 0
                                word_end = word.end if hasattr(word, 'end') else 0
                                
                                # If speaker changed, save previous segment
                                if current_speaker is not None and word_speaker != current_speaker:
                                    if current_text:
                                        segment = {
                                            "speaker_id": f"Speaker {current_speaker}",
                                            "text": " ".join(current_text),
                                            "start_time": current_start,
                                            "end_time": word_start,
                                            "duration": word_start - current_start,
                                            "confidence": DEFAULT_CONFIDENCE_FALLBACK,
                                            "word_count": len(current_text)
                                        }
                                        diarized_segments.append(segment)
                                        
                                        # Update stats
                                        speaker_key = f"Speaker {current_speaker}"
                                        if speaker_key not in speaker_stats:
                                            speaker_stats[speaker_key] = {
                                                "total_duration": 0,
                                                "total_words": 0,
                                                "segment_count": 0
                                            }
                                        speaker_stats[speaker_key]["total_duration"] += segment["duration"]
                                        speaker_stats[speaker_key]["total_words"] += len(current_text)
                                        speaker_stats[speaker_key]["segment_count"] += 1
                                    
                                    current_text = []
                                    current_start = word_start
                                
                                current_speaker = word_speaker
                                current_text.append(word_text)
                                if current_start is None:
                                    current_start = word_start
                            
                            # Save last segment
                            if current_text:
                                segment = {
                                    "speaker_id": f"Speaker {current_speaker}",
                                    "text": " ".join(current_text),
                                    "start_time": current_start,
                                    "end_time": word_end,
                                    "duration": word_end - current_start,
                                    "confidence": DEFAULT_CONFIDENCE_FALLBACK,
                                    "word_count": len(current_text)
                                }
                                diarized_segments.append(segment)
                                
                                speaker_key = f"Speaker {current_speaker}"
                                if speaker_key not in speaker_stats:
                                    speaker_stats[speaker_key] = {
                                        "total_duration": 0,
                                        "total_words": 0,
                                        "segment_count": 0
                                    }
                                speaker_stats[speaker_key]["total_duration"] += segment["duration"]
                                speaker_stats[speaker_key]["total_words"] += len(current_text)
                                speaker_stats[speaker_key]["segment_count"] += 1
            
        except Exception as e:
            logger.error(f"❌ Error parsing diarization results: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error parsing diarization results: {str(e)}"
            )
        
        # Store diarization results in transcript store
        try:
            store = get_transcript_store()
            
            for segment in diarized_segments:
                await store.add_transcript_entry(
                    meeting_id=room_id,
                    speaker=segment["speaker_id"],
                    text=segment["text"],
                    confidence=segment["confidence"]
                )
            
            logger.info(f"✅ Stored {len(diarized_segments)} diarized segments for room {room_id}")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to store diarization results: {e}")
        
        # Return results
        return {
            "room_id": room_id,
            "diarization_complete": True,
            "segments": diarized_segments,
            "speaker_count": len(speaker_stats),
            "speaker_stats": speaker_stats,
            "total_segments": len(diarized_segments),
            "total_duration": sum(s["duration"] for s in diarized_segments),
            "generated_at": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in offline diarization: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Offline diarization error: {str(e)}"
        )


# Test endpoint for WebSocket broadcast verification
@router.post("/rooms/{room_id}/test-broadcast")
async def test_broadcast(room_id: str):
    """
    Test endpoint to verify WebSocket broadcast is working.
    Sends a test transcript message to all participants in the room.
    """
    try:
        room_manager = get_meeting_room_manager()
        
        test_message = {
            "type": "live_transcript",
            "user_id": "test_user",
            "username": "Test User",
            "text": "This is a test transcript to verify WebSocket is working",
            "emotion": "neutral",
            "confidence": 1.0,
            "emotion_guidance": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await room_manager.broadcast_to_room(room_id, test_message)
        
        return {"status": "Test broadcast sent", "room_id": room_id, "message": test_message}
    except Exception as e:
        logger.error(f"❌ Test broadcast failed: {e}")
        raise HTTPException(status_code=500, detail=f"Test broadcast failed: {str(e)}")


# WebSocket for Real-Time Collaboration ---------------------------------------

async def safe_send(websocket: WebSocket, data: dict, context: str = "") -> bool:
    """
    Safely send data through WebSocket with proper state checking.
    
    Args:
        websocket: WebSocket connection
        data: Data to send
        context: Context for logging
        
    Returns:
        True if send succeeded, False otherwise
    """
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json(data)
            return True
        else:
            logger.debug(f"WebSocket not connected ({context}), skipping send")
            return False
    except Exception as e:
        logger.debug(f"Failed to send ({context}): {e}")
        return False


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
            await safe_send(websocket, {"type": "error", "message": f"Room {room_id} not found"}, "room_not_found")
            await websocket.close()
            return

        # If user already connected, remove from room first (prevent cleanup), then close socket
        if existing_room and user_id in existing_room.participants:
            old_participant = existing_room.participants.pop(user_id, None)
            logger.info(f"🔄 Replacing existing connection for {user_id} in {room_id}")
            if old_participant:
                try:
                    # Close old websocket gracefully with code 1000 (normal closure)
                    if old_participant.websocket.client_state == WebSocketState.CONNECTED:
                        await old_participant.websocket.close(code=1000, reason="Replaced by new connection")
                except Exception as e:
                    logger.debug(f"Error closing old websocket for {user_id}: {e}", exc_info=True)

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
            await safe_send(websocket, {"type": "error", "message": str(e)}, "join_error")
            await websocket.close()
            return

        logger.info(f"✅ {username} joined {room_id} as {participant.role.value}")
        # Initialize streaming transcription
        orchestrator = get_orchestrator_service()
        from app.core.config import settings
        logger.info(f"🔍 Configuration check:")
        logger.info(f"   - USE_STREAMING_TRANSCRIPTION: {settings.USE_STREAMING_TRANSCRIPTION}")
        logger.info(f"   - USE_ROOM_DIARIZATION: {getattr(settings, 'USE_ROOM_DIARIZATION', False)}")
        logger.info(f"   - DEEPGRAM_API_KEY exists: {bool(settings.DEEPGRAM_API_KEY)}")
        logger.info(f"   - orchestrator.use_streaming: {orchestrator.use_streaming}")
        logger.info(f"   - whisper_service exists: {getattr(orchestrator, 'whisper_service', None) is not None}")
        logger.info(f"   - deepgram_service exists: {getattr(orchestrator, 'deepgram_service', None) is not None}")


        # Check if we should use room-level diarization or per-user streaming
        use_room_diarization = settings.USE_ROOM_DIARIZATION
        
        
        # ✅ ADD THIS DEBUG BLOCK HERE:
        logger.info(f"🔍 Checking streaming mode...")
        logger.info(f"   - use_room_diarization: {use_room_diarization}")
        logger.info(f"   - orchestrator.use_streaming: {orchestrator.use_streaming}")

        # Safe checks for service attributes
        has_whisper = hasattr(orchestrator, 'whisper_service') and orchestrator.whisper_service
        has_deepgram = hasattr(orchestrator, 'deepgram_service') and orchestrator.deepgram_service

        if use_room_diarization and orchestrator.use_streaming:
            logger.info(f"🎙️ BRANCH: Room-level diarization mode")
        elif orchestrator.use_streaming and (has_whisper or has_deepgram):
            service_name = "Faster-Whisper" if has_whisper else "Deepgram"
            logger.info(f"🎙️ BRANCH: Per-user streaming mode ({service_name})")
            logger.info(f"   - About to initialize {service_name} for {username}")
        else:
            logger.info(f"🎙️ BRANCH: Legacy mode (no streaming)")
            logger.info(f"   - orchestrator.use_streaming = {orchestrator.use_streaming}")
            logger.info(f"   - has_whisper_service = {has_whisper}")
            logger.info(f"   - has_deepgram_service = {has_deepgram}")
        
        if use_room_diarization and orchestrator.use_streaming:
            # Room-level diarization mode (mixed stream with speaker identification)
            logger.info(f"🎙️ Using room-level diarization for {room_id}")
            
            # Get or create room diarization service
            room_diarization = get_room_diarization_service(settings.DEEPGRAM_API_KEY)
            
            if room_diarization:
                # Register participant for speaker mapping
                room_diarization.register_participant(room_id, user_id, username)
                
                # Start room diarization if not already active
                if room_id not in _room_diarization_active:
                    logger.info(f"🎤 Starting room-level diarization for {room_id}")
                    
                    # Capture variables for callback
                    current_room_id = room_id
                    
                    async def on_room_transcript(result: dict):
                        """Handle transcript results from room-level Deepgram streaming"""
                        try:
                            text = result.get('text', '').strip()
                            if not text:
                                return
                            
                            is_final = result.get('is_final', True)
                            confidence = result.get('confidence', 1.0)
                            deepgram_speaker = result.get('speaker')  # Deepgram speaker ID
                            
                            logger.info(f"📝 Room transcript: '{text[:50]}...' (speaker: {deepgram_speaker}, final: {is_final})")
                            
                            # Skip partial results
                            if not is_final:
                                return
                            
                            # Try to resolve speaker to participant
                            participant_id = room_diarization.resolve_speaker(current_room_id, deepgram_speaker)
                            
                            if not participant_id:
                                # Unknown speaker - uses Deepgram's speaker ID as fallback
                                # Speaker mapping could be enhanced with voice profile matching
                                participant_id = f"speaker_{deepgram_speaker}" if deepgram_speaker is not None else "unknown"
                                display_name = f"Speaker {deepgram_speaker}" if deepgram_speaker is not None else "Unknown"
                            else:
                                display_name = room_diarization.get_participant_name(current_room_id, participant_id)
                            
                            logger.info(f"👤 Resolved speaker: {deepgram_speaker} -> {participant_id} ({display_name})")
                            
                            # Emotion analysis (simplified for room-level) - FAST
                            emotion = {"emotion": "neutral", "confidence": 0.5, "scores": {}}
                            try:
                                emotion_service = get_emotion_service()
                                emotion_result = await asyncio.wait_for(
                                    emotion_service.analyze_text(text),
                                    timeout=0.3  # Very fast timeout
                                )
                                if emotion_result:
                                    emotion = emotion_result
                            except asyncio.TimeoutError:
                                logger.debug(f"⏱️ Emotion analysis timed out, using neutral")
                            except Exception as e:
                                logger.debug(f"⚠️ Emotion analysis failed: {e}")
                            
                            # Get emotion guidance - FAST, non-blocking
                            guidance = {}
                            try:
                                guidance_engine = get_emotion_guidance_engine()
                                guidance = await asyncio.wait_for(
                                    asyncio.to_thread(
                                        guidance_engine.get_guidance,
                                        emotion["emotion"], text, emotion.get("confidence", 0),
                                        context={"username": display_name, "room_id": current_room_id, "speaker": participant_id}
                                    ),
                                    timeout=0.5  # Fast timeout to avoid delays
                                )
                            except asyncio.TimeoutError:
                                logger.debug(f"⏱️ Guidance generation timed out (non-critical)")
                                guidance = {}  # Use empty guidance if too slow
                            except Exception as e:
                                logger.debug(f"⚠️ Guidance generation failed: {e}")
                                guidance = {}
                            
                            # Broadcast transcript
                            await room_manager.broadcast_transcript(
                                room_id=current_room_id,
                                user_id=participant_id,
                                username=display_name,
                                text=text,
                                emotion=emotion["emotion"],
                                confidence=emotion.get("confidence", 0),
                                emotion_guidance=guidance
                            )
                            
                            # Store transcript
                            store = get_transcript_store()
                            entry_obj = await store.add_transcript_entry(
                                meeting_id=current_room_id,
                                speaker=display_name,
                                text=text,
                                confidence=confidence
                            )
                            
                            if entry_obj:
                                entry_obj.emotions = {
                                    "emotion": emotion["emotion"],
                                    "confidence": emotion.get("confidence", 0),
                                    "scores": emotion.get("scores", {})
                                }
                            
                            logger.info(f"✅ Room transcript processed: '{text[:60]}' | Speaker: {display_name}")
                            
                        except Exception as e:
                            logger.error(f"❌ Error processing room transcript: {e}", exc_info=True)
                    
                    # Start room-level diarization
                    success = await room_diarization.start_room_diarization(
                        room_id=room_id,
                        on_transcript=on_room_transcript,
                        language="en",
                        model="nova-2"
                    )
                    
                    if success:
                        _room_diarization_active[room_id] = True
                        logger.info(f"✅ Room diarization started for {room_id}")
                    else:
                        logger.warning(f"⚠️ Failed to start room diarization for {room_id}")
                else:
                    logger.info(f"✅ Room diarization already active for {room_id}")
        
        elif orchestrator.use_streaming and (has_whisper or has_deepgram):
            # Per-user streaming mode (Faster-Whisper or Deepgram)
            service_name = "Faster-Whisper" if has_whisper else "Deepgram"
            stream_id = f"{room_id}_{user_id}"
            logger.info(f"🎙️ Initializing per-user {service_name} stream for {username} (stream: {stream_id})")
            
            # Initialize audio buffer for this user's stream
            if stream_id not in _room_audio_buffers:
                _room_audio_buffers[stream_id] = []
            
            # Define callback for transcript results FOR THIS USER
            # We need to capture these variables in the closure
            current_user_id = user_id
            current_username = username
            current_room_id = room_id
            current_stream_id = stream_id
            # Entry ID tracking for emotion updates
            current_entry_id = None
            
            async def on_deepgram_transcript(result: dict):
                """Handle transcript results from Deepgram streaming with continuous bars"""
                nonlocal current_entry_id
                try:
                    text = result.get('text', '').strip()
                    
                    logger.info(f"🔔 Callback received - text_len={len(text)}, is_final={result.get('is_final', False)}")
                    
                    if not text:
                        logger.warning(f"⚠️ Empty text in callback, skipping")
                        return
                    
                    is_final = result.get('is_final', False)
                    confidence = result.get('confidence', 1.0)
                    
                    # Generate or maintain entry_id
                    if current_entry_id is None:
                        import uuid
                        current_entry_id = f"{current_user_id}_{current_room_id}_{uuid.uuid4().hex[:8]}"
                        logger.info(f"🆕 New entry_id: {current_entry_id}")
                    
                    display_name = current_username
                    
                    logger.info(f"📝 Transcript for {display_name}: '{text[:50]}...' (is_final={is_final})")
                    
                    # ✅ Use continuous transcript manager
                    try:
                        # Get audio for emotion caching
                        audio_array = None
                        if current_stream_id in _room_audio_buffers and len(_room_audio_buffers[current_stream_id]) > 0:
                            try:
                                import numpy as np
                                recent_chunks = _room_audio_buffers[current_stream_id][-15:]
                                audio_array = np.concatenate(recent_chunks)
                            except Exception as e:
                                logger.warning(f"⚠️ Failed to get audio buffer: {e}")
                        
                        # Process through continuous transcript manager
                        transcript_result = await orchestrator.process_transcription_continuous(
                            session_id=current_room_id,
                            speaker=current_user_id,
                            text=text,
                            confidence=confidence,
                            audio_array=audio_array,
                            speaker_name=display_name,
                            is_final=is_final
                        )
                        
                        # Extract bar data
                        bar_data = transcript_result.get("bar", {})
                        action = transcript_result.get("action", "create")
                        
                        # Broadcast to room with new format
                        await room_manager.broadcast_to_room(current_room_id, {
                            "type": "transcript_bar",
                            "action": action,  # "append" or "create"
                            "bar": bar_data,
                            "timestamp": get_ist_timestamp()
                        })
                        
                        logger.info(f"✅ Broadcast continuous transcript: action={action}, bar_id={bar_data.get('id')}")
                        
                        # Store in transcript store if it's a finalized bar
                        if action == "create":
                            store = get_transcript_store()
                            await store.add_transcript_entry(
                                meeting_id=current_room_id,
                                speaker=display_name,
                                text=text,
                                confidence=confidence
                            )
                        
                    except Exception as e:
                        logger.error(f"❌ Error in continuous transcription: {e}", exc_info=True)
                        # Fallback to old format
                        await room_manager.broadcast_transcript(
                            room_id=current_room_id,
                            user_id=current_user_id,
                            username=display_name,
                            text=text,
                            emotion="neutral",
                            confidence=0.0,
                            emotion_guidance={},
                            is_final=True,
                            entry_id=current_entry_id
                        )
                    
                except Exception as e:
                    logger.error(f"❌ Error in transcript callback: {e}", exc_info=True)
            
            # Note: Emotion analysis is now handled automatically by AsyncEmotionProcessor
            # when transcript bars are finalized in the continuous transcript manager
            
            service_name = "Faster-Whisper" if has_whisper else "Deepgram"
            logger.info(f"🎙️ About to start {service_name} stream for {username} (stream: {stream_id})")

        try:
            if has_whisper:
                # Use Faster-Whisper (local, free, unlimited)
                success = await orchestrator.whisper_service.start_stream(
                    session_id=stream_id,
                    on_transcript=on_deepgram_transcript
                )
            elif has_deepgram:
                # Fallback to Deepgram
                success = await orchestrator.deepgram_service.start_stream(
                    session_id=stream_id,
                    on_transcript=on_deepgram_transcript,
                    language="en",
                    model="nova-2",
                    smart_format=True,
                    interim_results=True,
                    diarize=False
                )
            else:
                success = False
            
            logger.info(f"🔧 start_stream() returned: {success} for {username}")
            
            if success:
                logger.info(f"✅ {service_name} stream started for {username} (stream: {stream_id})")
            else:
                logger.error(f"❌ Failed to start {service_name} stream for {username}, falling back to legacy mode")
                
        except Exception as e:
            logger.error(f"❌ Exception starting streaming transcription for {username}: {e}", exc_info=True)
            success = False
                
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
        await safe_send(websocket, {
            "type": "welcome",
            "message": f"Welcome {username}!",
            "your_role": participant.role.value,
            "room_info": room_info
        }, "welcome")
        
        # Send ready_for_audio signal to indicate server is ready to receive audio
        await safe_send(websocket, {
            "type": "ready_for_audio",
            "streaming_enabled": orchestrator.use_streaming,
            "session_id": stream_id if (orchestrator.use_streaming and not use_room_diarization) else room_id,
            "message": "Server is ready to receive audio"
        }, "ready_for_audio")
        
        logger.info(f"📡 Sent ready_for_audio signal to {username}")

        await safe_send(websocket, {
            "type": "connection_ack",
            "message": f"Connected successfully as {username}",
            "timestamp": datetime.utcnow().isoformat()
        }, "connection_ack")

        # Send peer list (existing participants excluding self) so the client can initiate offers
        peers = []
        room_after_join = room_manager.rooms.get(room_id)
        if room_after_join:
            for uid, p in room_after_join.participants.items():
                if uid == user_id:
                    continue
                peers.append({"user_id": uid, "username": p.username})

        await safe_send(websocket, {
            "type": "peer_list",
            "peers": peers
        }, "peer_list")

        # Echo a new_participant to the new user (self = True) to make client-side logic uniform
        await safe_send(websocket, {
            "type": "new_participant",
            "user_id": user_id,
            "username": username,
            "timestamp": datetime.utcnow().isoformat(),
            "self": True
        }, "new_participant_self")

        # ✅ FIX: Send historical transcripts to newly joined participant
        # This ensures they can see what happened before they joined
        try:
            store = get_transcript_store()
            historical_transcripts = store.get_session_transcript(room_id)
            
            if historical_transcripts:
                logger.info(f"📜 Sending {len(historical_transcripts)} historical transcripts to {username}")
                
                # Get current room to map user_ids to usernames
                current_room = room_manager.rooms.get(room_id)
                
                # Send historical transcripts in batches to avoid overwhelming the connection
                batch_size = 10
                for i in range(0, len(historical_transcripts), batch_size):
                    batch = historical_transcripts[i:i + batch_size]
                    
                    for entry in batch:
                        # Try to get actual username from speaker ID
                        speaker_id = entry.speaker or "unknown"
                        speaker_name = speaker_id  # Default to speaker_id
                        
                        # Try to find the username from current participants
                        if current_room and speaker_id in current_room.participants:
                            speaker_name = current_room.participants[speaker_id].username
                        
                        # Format each transcript entry to match live_transcript format
                        transcript_message = {
                            "type": "live_transcript",
                            "user_id": speaker_id,
                            "username": speaker_name,
                            "text": entry.text,
                            "emotion": entry.emotions.get("emotion", "neutral") if entry.emotions else "neutral",
                            "confidence": entry.emotions.get("confidence", 0.0) if entry.emotions else 0.0,
                            "emotion_guidance": {},
                            "timestamp": entry.timestamp.isoformat() if hasattr(entry.timestamp, 'isoformat') else str(entry.timestamp),
                            "is_historical": True  # Mark as historical so frontend can handle differently if needed
                        }
                        await safe_send(websocket, transcript_message, "historical_transcript")
                    
                    # Small delay between batches to prevent overwhelming the connection
                    await asyncio.sleep(0.05)
                
                logger.info(f"✅ Historical transcripts sent to {username}")
        except Exception as e:
            logger.error(f"Failed to send historical transcripts to {username}: {e}", exc_info=True)

        # Main receive loop with extended timeout for long meetings
        # Timeout set to 3600 seconds (1 hour) to support long meetings
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=3600)
            except asyncio.TimeoutError:
                # send keep-alive ping after 1 hour of inactivity
                await safe_send(websocket, {
                    "type": "ping_timeout",
                    "message": "Keep-alive: No message received within 1 hour.",
                    "timestamp": datetime.utcnow().isoformat()
                }, "ping_timeout")
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
                    "timestamp": get_ist_timestamp()
                }
                await room_manager.broadcast_to_room(room_id, chat_message)
                await safe_send(websocket, {"type": "chat_ack", "message": chat_message["message"]}, "chat_ack")

            elif message_type == "media_state":
                # Handle video/audio toggle notifications
                is_video_on = message.get("is_video_on")
                is_audio_on = message.get("is_audio_on")
                
                logger.info(f"🎬 Media state update from {username}: video={is_video_on}, audio={is_audio_on}")
                
                # Update participant state
                await room_manager.update_participant_state(
                    room_id=room_id,
                    user_id=user_id,
                    is_video_on=is_video_on,
                    is_audio_on=is_audio_on
                )
                
                # Broadcast updated state to all participants in room
                if room_id in room_manager.rooms:
                    room = room_manager.rooms[room_id]
                    participant = room.participants.get(user_id)
                    if participant:
                        await room_manager.broadcast_to_room(
                            room_id,
                            {
                                "type": "participant_updated",
                                "user_id": user_id,
                                "username": username,
                                "is_video_on": participant.is_video_on,
                                "is_audio_on": participant.is_audio_on,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        )
                        logger.info(f"✅ Broadcast media state update for {username}")

            # WebRTC signaling routing: target_id must be present and will be forwarded
            elif message_type in {"webrtc_offer", "webrtc_answer", "ice_candidate"}:
                target_id = message.get("target_id")
                logger.info(f"📡 WebRTC signaling: {message_type} from {username} ({user_id}) to {target_id} in room {room_id}")
                
                if target_id and room_id in room_manager.rooms:
                    room = room_manager.rooms[room_id]
                    if target_id in room.participants:
                        target_ws = room.participants[target_id].websocket
                        # ✅ FIX: Use room_manager's safe_websocket_send for WebRTC signaling
                        success = await room_manager.safe_websocket_send(
                            target_ws,
                            {
                                **message,
                                "from_id": user_id,
                                "timestamp": datetime.utcnow().isoformat()
                            },
                            target_id
                        )
                        if success:
                            logger.info(f"✅ Forwarded {message_type} from {username} to {target_id}")
                        else:
                            logger.warning(f"⚠️ Failed to forward {message_type} to {target_id} (WebSocket not connected)")
                    else:
                        logger.warning(f"⚠️ Target {target_id} not found in room {room_id}. Available participants: {list(room.participants.keys())}")
                else:
                    logger.warning(f"⚠️ Signaling message without target_id or room {room_id} missing. Message: {message_type}")

            elif message_type == "ping":
                await safe_send(websocket, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }, "pong")

            else:
                # Unknown/other messages — log for debugging
                logger.debug(f"Unknown WS message from {username} in {room_id}: {message_type}")

    except WebSocketDisconnect:
        logger.info(f"❌ {username} disconnected from {room_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {username} in {room_id}: {e}", exc_info=True)
    finally:
        # Clean up streaming transcription (Faster-Whisper or Deepgram)
        try:
            orchestrator = get_orchestrator_service()
            stream_id = f"{room_id}_{user_id}"
            
            # Try Faster-Whisper first (preferred)
            if orchestrator.use_streaming and hasattr(orchestrator, 'whisper_service') and orchestrator.whisper_service:
                await orchestrator.whisper_service.stop_stream(stream_id)
                logger.info(f"🔌 Stopped Faster-Whisper stream for {username} in {room_id}")
            # Fallback to Deepgram
            elif orchestrator.use_streaming and hasattr(orchestrator, 'deepgram_service') and orchestrator.deepgram_service:
                await orchestrator.deepgram_service.stop_stream(stream_id)
                logger.info(f"🔌 Stopped Deepgram stream for {username} in {room_id}")
        except Exception as stream_err:
            logger.debug(f"Error stopping transcription stream: {stream_err}")
        
        # Clean up room diarization if this is the last participant
        try:
            from app.core.config import settings
            if settings.USE_ROOM_DIARIZATION and room_id in _room_diarization_active:
                room_diarization = get_room_diarization_service()
                if room_diarization:
                    # Unregister participant
                    room_diarization.unregister_participant(room_id, user_id)
                    
                    # Check if room is empty
                    room = room_manager.rooms.get(room_id)
                    if not room or len(room.participants) <= 1:  # <= 1 because we haven't removed this user yet
                        await room_diarization.stop_room_diarization(room_id)
                        if room_id in _room_diarization_active:
                            del _room_diarization_active[room_id]
                        logger.info(f"🔌 Stopped room diarization for {room_id}")
        except Exception as diar_err:
            logger.debug(f"Error stopping room diarization: {diar_err}")
        
        # 🔄 FIX: Only call leave_room if this is still the active connection (not replaced)
        try:
            room = room_manager.rooms.get(room_id)
            if room and user_id in room.participants:
                # Only leave if this is still the active connection for this user
                current_participant = room.participants.get(user_id)
                if current_participant and current_participant.websocket == websocket:
                    await room_manager.leave_room(room_id, user_id)
                    logger.info(f"👋 {username} left {room_id}")
                    
                    # ✅ Explicitly check if room is now empty and clean up immediately
                    room_after_leave = room_manager.rooms.get(room_id)
                    if room_after_leave and len(room_after_leave.participants) == 0:
                        logger.info(f"🧹 Room {room_id} is empty after {username} left - cleaning up immediately")
                        # Room status is already set to ENDED in leave_room, but ensure cleanup
                        await room_manager.broadcast_to_room(room_id, {
                            "type": "room_empty",
                            "room_id": room_id,
                            "message": "All participants have left",
                            "timestamp": get_ist_timestamp()
                        })
                else:
                    logger.info(f"🔄 {username}'s old connection closed (replaced by new connection)")
            else:
                logger.debug(f"User {user_id} already removed from room {room_id}")
        except Exception as leave_err:
            logger.debug(f"Error during leave_room cleanup: {leave_err}")


# Audio processing helper -----------------------------------------------------

async def process_audio(room_id, user_id, username, message, room_manager, websocket):
    """✅ FIXED: Process audio chunk with proper format handling for both streaming and legacy modes"""
    try:
        logger.info(f"🎵 process_audio called - room: {room_id}, user: {username} ({user_id})")
        
        # 1️⃣ Extract base64 audio from message
        audio_base64 = message.get("audio") or message.get("audio_data") or message.get("data", "")
        if not audio_base64:
            logger.warning(f"❌ No audio data found for user {username} in room {room_id}")
            return

        # 2️⃣ Decode base64 → bytes
        try:
            audio_bytes = base64.b64decode(audio_base64)
            logger.info(f"✅ Decoded audio chunk from {username}: {len(audio_bytes)} bytes")
        except Exception as decode_err:
            logger.error(f"❌ Base64 decode failed for {username}: {decode_err}")
            return
        
        # ✅ NEW: Buffer audio for emotion analysis in streaming mode
        try:
            audio_array_for_buffer, _ = bytes_to_numpy(audio_bytes, sample_rate=16000)
            
            # Check if streaming mode is active
            orchestrator = get_orchestrator_service()
            has_streaming = (hasattr(orchestrator, 'whisper_service') and orchestrator.whisper_service) or \
                           (hasattr(orchestrator, 'deepgram_service') and orchestrator.deepgram_service)
            if orchestrator.use_streaming and has_streaming:
                stream_id = f"{room_id}_{user_id}"
                # Initialize buffer if needed
                if stream_id not in _room_audio_buffers:
                    _room_audio_buffers[stream_id] = []
                
                # Add to buffer
                _room_audio_buffers[stream_id].append(audio_array_for_buffer)
                
                # Keep only last 20 chunks (about 2-3 seconds)
                if len(_room_audio_buffers[stream_id]) > 20:
                    _room_audio_buffers[stream_id].pop(0)
                
                logger.debug(f"🎤 Buffered audio for emotion: {len(_room_audio_buffers[stream_id])} chunks")
                
        except Exception as buffer_err:
            logger.warning(f"⚠️ Audio buffering failed: {buffer_err}")

        # 2.5️⃣ Add audio to recorder for meeting recording
        try:
            recorder = get_recorder(room_id)
            if recorder and recorder.is_recording:
                # Convert bytes to numpy array for recording
                audio_array, _ = bytes_to_numpy(audio_bytes, sample_rate=16000)
                recorder.add_audio_chunk(user_id, audio_array)
                logger.debug(f"📼 Audio added to recorder for room {room_id}")
        except Exception as rec_err:
            logger.warning(f"⚠️ Failed to add audio to recorder for room {room_id}: {rec_err}")
        
        # 2.6️⃣ Add audio to room diarization if active
        from app.core.config import settings
        if settings.USE_ROOM_DIARIZATION and room_id in _room_diarization_active:
            try:
                room_diarization = get_room_diarization_service()
                if room_diarization:
                    # Convert bytes to numpy array for mixing
                    audio_array, _ = bytes_to_numpy(audio_bytes, sample_rate=16000)
                    await room_diarization.add_audio_chunk(room_id, user_id, audio_array)
                    logger.debug(f"🎤 Audio added to room diarization for {username}")
            except Exception as diar_err:
                logger.warning(f"⚠️ Failed to add audio to room diarization: {diar_err}")

        # 3️⃣ Run unified AI pipeline via orchestrator
        stream_id = f"{room_id}_{user_id}"
        logger.info(f"🔧 Calling orchestrator for room {room_id}, user {username} with {len(audio_bytes)} bytes")
        orchestrator = get_orchestrator_service()
        result = await orchestrator.process_audio_chunk(
            audio_bytes=audio_bytes,
            session_id=stream_id,
            participant_id=user_id
        )
        logger.info(f"✅ Orchestrator returned result for room {room_id}: {type(result).__name__ if result else 'None'}")
        
        # 🔍 DEBUG - Add detailed logging of orchestrator result
        import json
        logger.info(f"🔍 DEBUG - Full result from orchestrator: {json.dumps(result, indent=2, default=str) if result else 'None'}")
        logger.info(f"🔍 DEBUG - Result keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")

        # 🔹 Handle streaming mode - transcripts come via callback
        if result and result.get("type") == "streaming":
            logger.debug(f"📡 Streaming mode - audio sent to Deepgram for {username}")
            return

        # 4️⃣ Skip empty result
        if not result:
            logger.debug(f"⚠️ No result from orchestrator for user {username} in {room_id}")
            return

        # 🔹 Handle lightweight "listening" heartbeats (legacy mode) - check AFTER empty check
        if result and result.get("type") == "listening":
            logger.debug(f"⏳ Buffering audio for {username} in {room_id}: {result.get('buffered_duration', 0):.2f}s")
            await safe_send(websocket, result, "listening_status")
            return

        # ✅ FIX: Handle both single and multi-speaker responses (legacy mode)
        entries = []
        if result.get("type") == "multi_speaker_chunk":
            entries = result.get("entries", [])
            logger.info(f"📋 Multi-speaker result with {len(entries)} entries")
        elif isinstance(result, dict) and result.get("text"):
            # Single entry - this is what we expect most of the time
            entries = [result]
            logger.info(f"📋 Single entry result: '{result.get('text', '')[:50]}...'")
        else:
            logger.warning(f"⚠️ Unexpected result structure: {result}")

        if not entries:
            logger.warning(f"❌ No valid entries extracted from orchestrator result for {username} in {room_id}")
            logger.warning(f"   Result was: {result}")
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
            logger.info(f"📢 Broadcasting transcript from {username} in {room_id}: '{text[:50]}...'")
            logger.info(f"🔊 ABOUT TO BROADCAST:")
            logger.info(f"   - room_id: {room_id}")
            logger.info(f"   - user_id: {user_id}")
            logger.info(f"   - username: {username}")
            logger.info(f"   - text: '{text[:100]}...'")
            logger.info(f"   - emotion: {emotion}")
            
            await room_manager.broadcast_transcript(
                room_id=room_id,
                user_id=user_id,
                username=username,
                text=text,
                emotion=emotion,
                confidence=confidence,
                emotion_guidance=guidance
            )
            
            logger.info(f"✅ BROADCAST COMPLETED for {username}")

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