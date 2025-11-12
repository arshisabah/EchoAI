from starlette.websockets import WebSocketState
# app/routers/transcript.py
"""
Fixed transcript router with real-time WebSocket processing.
"""
import uuid
import logging
import json
import base64
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    UploadFile,
    File,
    Form,
)

from app.modules.realtime_store import get_transcript_store
from app.services.orchestrator_service import get_orchestrator_service, SessionData

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcript", tags=["transcript"])


@router.websocket("/ws/{session_id}")
async def websocket_transcript_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time transcription with emotion analysis."""
    await websocket.accept()
    logger.info(f"✅ WebSocket connected for session: {session_id}")

    try:
        store = get_transcript_store()
        await store.create_session(session_id, {"connection_type": "websocket"})
        for _ in range(3):
            if hasattr(store, "session_exists") and await store.session_exists(session_id):
                break
            await asyncio.sleep(0.2)
    except Exception as e:
        logger.warning(f"Session creation warning: {e}")

    orchestrator = get_orchestrator_service()
    
    if not hasattr(orchestrator, "last_ping"):
        orchestrator.last_ping = {}
    
    orchestrator.last_ping[session_id] = datetime.utcnow()

    if session_id not in orchestrator.active_sessions:
        await orchestrator.start_session(session_id)

    try:
        while True:
            # ✅ FIX: Increased timeout to 90 seconds for slow transcription
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=90.0)
            except asyncio.TimeoutError:
                time_since_last_ping = (datetime.utcnow() - orchestrator.last_ping[session_id]).seconds
                if time_since_last_ping > 70:
                    logger.warning(f"⏳ Heartbeat timeout for {session_id} ({time_since_last_ping}s)")
                    await orchestrator.close_session(session_id)
                    await websocket.close()
                    break
                logger.debug(f"📡 Sending keep-alive ping to {session_id}")
                try:
                    await websocket.send_json({"type": "ping", "timestamp": datetime.utcnow().isoformat()})
                except:
                    logger.warning(f"Failed to send ping, connection may be closed")
                    break
                continue

            try:
                message_data = json.loads(data)
                message_type = message_data.get("type")
            except Exception:
                message_type = data.strip().lower()
                message_data = {"type": message_type}

            orchestrator.last_ping[session_id] = datetime.utcnow()
            logger.debug(f"📨 Received {message_type} from {session_id}")

            if message_type == "ping":
                try:
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except:
                    logger.warning("Failed to send pong, connection closed")
                    break

            elif message_type == "audio_chunk":
                audio_base64 = message_data.get("audio_data", "")
                sample_rate = message_data.get("sample_rate", 16000)
                
                if not audio_base64:
                    await safe_send(websocket, {"type": "error", "message": "No audio data"})
                    continue

                if len(audio_base64) > 5_000_000:
                    await safe_send(websocket, {"type": "error", "message": "Audio too large"})
                    continue

                try:
                    await safe_send(websocket, {
                        "type": "audio_received",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    audio_bytes = base64.b64decode(audio_base64)
                    
                    if len(audio_bytes) == 0:
                        await safe_send(websocket, {"type": "error", "message": "Empty audio"})
                        continue
                        
                    logger.info(f"📥 Processing {len(audio_bytes)} bytes from {session_id}")
                    
                except Exception as e:
                    logger.error(f"Audio decode error: {e}")
                    await safe_send(websocket, {"type": "error", "message": f"Decode error: {e}"})
                    continue

                try:
                    if not hasattr(orchestrator, "processing_locks"):
                        orchestrator.processing_locks = {}
                    if session_id not in orchestrator.processing_locks:
                        orchestrator.processing_locks[session_id] = asyncio.Lock()

                    async with orchestrator.processing_locks[session_id]:
                        result = await orchestrator.process_audio_chunk(audio_bytes, session_id)

                    if result:
                        await safe_send(websocket, {
                            "type": "transcript_entry",
                            "data": result,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        logger.info(f"📝 Transcript (full): '{result.get('text', '')}'")
                    else:
                        await safe_send(websocket, {
                            "type": "no_speech",
                            "message": "No speech detected",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        
                except Exception as e:
                    logger.error(f"Audio processing error: {e}", exc_info=True)
                    await safe_send(websocket, {"type": "error", "message": f"Processing failed: {e}"})

            elif message_type == "get_summary":
                last_n = message_data.get("last_n_entries", 10)
                summary = await orchestrator.generate_realtime_summary(session_id, last_n)
                await safe_send(websocket, {
                    "type": "summary",
                    "data": summary,
                    "timestamp": datetime.utcnow().isoformat()
                })

            else:
                logger.warning(f"Unknown message type: {message_type}")
                await safe_send(websocket, {"type": "error", "message": f"Unknown type: {message_type}"})

    except WebSocketDisconnect:
        logger.info(f"❌ WebSocket disconnected: {session_id}")
        if session_id in orchestrator.active_sessions:
            try:
                await asyncio.sleep(0.1)
                await orchestrator.close_session(session_id)
            except Exception as e:
                logger.warning(f"Cleanup error: {e}")

    except Exception as e:
        logger.error(f"WebSocket error for {session_id}: {e}")
        try:
            await safe_send(websocket, {"type": "error", "message": str(e)})
        except:
            pass


# ✅ NEW: Safe send function that checks connection state
async def safe_send(websocket: WebSocket, data: dict):
    """Send JSON data to WebSocket, handling closed connections gracefully."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json(data)
        else:
            logger.debug(f"WebSocket not connected, skipping send: {data.get('type')}")
    except Exception as e:
        logger.debug(f"Failed to send WebSocket message: {e}")

@router.post("/process")
async def process_transcription(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    """
    Upload and transcribe an audio file.
    Returns transcription with emotion analysis for each speaker.
    """
    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file uploaded")

        orchestrator = get_orchestrator_service()

        # Ensure session exists
        if session_id not in orchestrator.active_sessions:
            await orchestrator.start_session(session_id)

        # Process the uploaded audio
        unique_id = f"{session_id}_{uuid.uuid4().hex[:6]}"
        result = await orchestrator.process_audio_chunk(audio_bytes, unique_id)
        if not result:
            return {
                "message": "No speech detected or transcription failed",
                "session_id": session_id,
                "status": "no_speech"
            }

        return {
            "session_id": session_id,
            "results": [result] if isinstance(result, dict) else result,
            "status": "success"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Transcription error for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_session_transcript(session_id: str):
    """Get complete transcript for a session with emotions."""
    try:
        orchestrator = get_orchestrator_service()
        result = await orchestrator.get_session_transcript(session_id)
        
        if not result or (isinstance(result, dict) and "error" in result):
            raise HTTPException(status_code=404, detail="Session not found or empty")

        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session transcript {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/session/{session_id}/create")
async def create_transcript_session(session_id: str):
    """
    Create or reuse a transcript session (idempotent).
    """
    try:
        orchestrator = get_orchestrator_service()

        # Start session or reuse existing one
        result = await orchestrator.start_session(session_id)

        return {
            "status": "ok",
            "session_id": session_id,
            "message": "Session ready",
            **result
        }

    except Exception as e:
        logger.error(f"Session creation error for {session_id}: {e}")
        return {
            "status": "error",
            "session_id": session_id,
            "message": f"Session creation failed: {str(e)}"
        }


@router.delete("/session/{session_id}")
async def delete_transcript_session(session_id: str):
    """Delete a transcript session (idempotent)."""
    try:
        store = get_transcript_store()
        orchestrator = get_orchestrator_service()

        # Delete from store
        try:
            store.delete_session(session_id)
        except Exception as e:
            logger.warning(f"Delete from store failed: {e}")
        
        # Delete from orchestrator
        if session_id in orchestrator.active_sessions:
            del orchestrator.active_sessions[session_id]

        return {
            "status": "deleted",
            "message": f"Session {session_id} deleted",
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"Unexpected delete error: {e}")
        return {
            "status": "error",
            "message": f"Error deleting session: {str(e)}",
            "session_id": session_id
        }


@router.get("/sessions")
async def list_sessions():
    """List all active sessions."""
    try:
        orchestrator = get_orchestrator_service()
        
        sessions = orchestrator.list_active_sessions()
        
        return {
            "sessions": sessions,
            "total_sessions": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/session/{session_id}/summary")
async def get_session_summary(session_id: str, last_n_entries: int = 10):
    """Get real-time summary of recent conversation."""
    try:
        orchestrator = get_orchestrator_service()
        summary = await orchestrator.generate_realtime_summary(
            session_id, 
            last_n_entries
        )
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating summary for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/session/{session_id}/insights")
async def get_session_insights(session_id: str):
    """Get comprehensive insights including emotion analysis."""
    try:
        orchestrator = get_orchestrator_service()
        insights = await orchestrator.generate_session_insights(session_id)
        
        if "error" in insights:
            raise HTTPException(status_code=404, detail=insights["error"])
        
        return insights
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating insights for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/session/{session_id}/close")
async def close_session(session_id: str):
    """Close a session and generate final summary with emotion analysis."""
    try:
        orchestrator = get_orchestrator_service()
        result = await orchestrator.close_session(session_id)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/session/{session_id}/emotions")
async def get_session_emotions(session_id: str):
    """Get emotion analysis for the entire session."""
    try:
        orchestrator = get_orchestrator_service()
        
        session = orchestrator.active_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        emotion_service = orchestrator.emotion_service
        emotion_results = await emotion_service.analyze_session_emotions(
            session.transcript_entries
        )
        
        return {
            "session_id": session_id,
            "emotion_analysis": emotion_results,
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting emotions for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")