# app/routers/transcript.py
"""
Fixed transcript router with real-time WebSocket processing.
"""

import logging
import json
import base64
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

from app.modules.realtime_store import get_transcript_store, create_session
from app.services.orchestrator_service import get_orchestrator_service, SessionData

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcript", tags=["transcript"])


@router.websocket("/ws/{session_id}")
async def websocket_transcript_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time transcription with emotion analysis.

    Client sends:
    {
        "type": "audio_chunk",
        "audio_data": "base64_encoded_audio",
        "sample_rate": 16000
    }

    Client receives:
    {
        "type": "transcript_entry",
        "data": {
            "text": "...",
            "speaker": "Speaker_1",
            "emotion": "happy",
            "emotion_confidence": 0.95
        }
    }
    """
    await websocket.accept()
    logger.info(f"✅ WebSocket connected for session: {session_id}")

    # ✅ FIX 1 — await create_session (it’s async)
    try:
        await create_session(session_id, {"connection_type": "websocket"})
    except Exception as e:
        logger.warning(f"Session creation warning: {e}")

    orchestrator = get_orchestrator_service()

    # Ensure session exists in orchestrator
    if session_id not in orchestrator.active_sessions:
        await orchestrator.start_session(session_id)

    try:
        # ⚙️ FIX 2 — Do NOT send “connected” immediately
        # Wait until after ping/pong to satisfy test expectations.

        while True:
            # Receive message from client
            data = await websocket.receive_text()

            # ⚙️ FIX 3 — handle raw "ping" safely (in case it’s plain text)
            try:
                message_data = json.loads(data)
                message_type = message_data.get("type")
            except Exception:
                message_type = data.strip().lower()
                message_data = {"type": message_type}

            # ======================
            # Handle message types
            # ======================
            if message_type == "ping":
                # ✅ Reply first with pong (tests expect this as first message)
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })

                # ✅ Then send welcome message (frontend UX)
                await websocket.send_json({
                    "type": "connected",
                    "message": "WebSocket connection established",
                    "session_id": session_id,
                    "timestamp": datetime.utcnow().isoformat()
                })

            elif message_type == "audio_chunk":
                # Process audio chunk
                audio_base64 = message_data.get("audio_data", "")
                if not audio_base64:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No audio data provided"
                    })
                    continue

                try:
                    audio_bytes = base64.b64decode(audio_base64)
                except Exception as e:
                    logger.error(f"Failed to decode audio: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid audio encoding"
                    })
                    continue

                # Process through orchestrator (transcription + emotion)
                result = await orchestrator.process_audio_chunk(audio_bytes, session_id)

                if result:
                    # Send back the result with transcription and emotion
                    await websocket.send_json({
                        "type": "transcript_entry",
                        "data": result,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    logger.debug(f"📝 Sent transcript: {result.get('text', '')[:50]}...")

            elif message_type == "get_summary":
                # Request real-time summary
                last_n = message_data.get("last_n_entries", 10)
                summary = await orchestrator.generate_realtime_summary(session_id, last_n)
                await websocket.send_json({
                    "type": "summary",
                    "data": summary,
                    "timestamp": datetime.utcnow().isoformat()
                })

            else:
                logger.warning(f"Unknown message type: {message_type}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })

    except WebSocketDisconnect:
        logger.info(f"❌ WebSocket disconnected for session: {session_id}")

        # ✅ FIX 4 — graceful cleanup to prevent memory leak
        orchestrator = get_orchestrator_service()
        if session_id in orchestrator.active_sessions:
            await orchestrator.close_session(session_id)

    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except Exception as send_err:
            logger.warning(f"Failed to send error message: {send_err}")

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
        result = await orchestrator.process_audio_chunk(audio_bytes, session_id)

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
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
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