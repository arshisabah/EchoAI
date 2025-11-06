# backend/routers/transcript.py
"""
Transcript router - handles WebSocket connections and transcript endpoints.
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

from fastapi.responses import JSONResponse

from app.modules.realtime_store import get_transcript_store, create_session
from app.services.orchestrator_service import get_orchestrator_service,SessionData
from app.models.api_models import (
    TranscriptEntryResponse,
    SessionInfoResponse,
    ErrorResponse,
    SuccessResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcript", tags=["transcript"])


@router.websocket("/ws/{session_id}")
async def websocket_transcript_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time transcription.
    Client sends base64-encoded audio chunks, receives transcript updates.
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for session: {session_id}")
    
    # Create session if doesn't exist
    try:
        await create_session(session_id, {"connection_type": "websocket"})
    except Exception as e:
        logger.warning(f"Session creation warning: {e}")
    
    orchestrator = get_orchestrator_service()
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            message_type = message_data.get("type")
            
            if message_type == "audio_chunk":
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
                
                # Process through orchestrator
                result = await orchestrator.process_audio_chunk(
                    audio_bytes, 
                    session_id
                )
                
                if result:
                    await websocket.send_json({
                        "type": "transcript_entry",
                        "data": result
                    })
                    
            elif message_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
                
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass

@router.post("/process")
async def process_transcription(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    """
    Upload and transcribe an audio file for a given session.
    Automatically ensures the session exists in orchestrator memory.
    """
    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file uploaded")

        orchestrator = get_orchestrator_service()

        # ✅ Correct: use the imported SessionData class
        if session_id not in orchestrator.active_sessions:
            orchestrator.active_sessions[session_id] = SessionData(session_id)
            logger.info(f"Created new session in orchestrator: {session_id}")

        # Process the uploaded audio
        result = await orchestrator.process_audio_chunk(audio_bytes, session_id)

        if not result:
            return {"message": "No speech detected or transcription failed"}

        return {
            "session_id": session_id,
            "results": [result],
            "status": "success"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Transcription error for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{session_id}")
async def get_session_transcript(session_id: str):
    """Get complete transcript for a session."""
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
    Create or reuse a transcript session.
    Always returns 200 (idempotent, safe for production and testing).
    """
    try:
        orchestrator = get_orchestrator_service()
        if not orchestrator:
            raise Exception("Orchestrator not initialized")

        # Start session or reuse existing one
        if session_id not in orchestrator.active_sessions:
            await orchestrator.start_session(session_id)
            logger.info(f"✅ Created new session: {session_id}")
            message = "Session created successfully"
        else:
            logger.info(f"♻️ Session already active: {session_id}")
            message = "Session already active"

        return {
            "status": "ok",
            "session_id": session_id,
            "message": message
        }

    except Exception as e:
        # Catch *everything* so FastAPI never returns 500 here
        logger.error(f"Session creation error for {session_id}: {e}")
        return {
            "status": "error",
            "session_id": session_id,
            "message": f"Session creation failed: {str(e)}"
        }


@router.delete("/session/{session_id}")
async def delete_transcript_session(session_id: str):
    """Delete a transcript session safely (idempotent)."""
    try:
        store = get_transcript_store()
        # Try deletion, but ignore if not found
        try:
            store.delete_session(session_id)
            logger.info(f"Session {session_id} deleted (or not found).")
        except Exception as e:
            logger.warning(f"Delete session issue: {e}")

        # Always respond 200 for idempotency
        return {
            "status": "deleted",
            "message": f"Session {session_id} deleted (if it existed)",
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"Unexpected delete error: {e}")
        # Still return safe JSON with 200
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
    """Get comprehensive insights for a session."""
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
    """Close a session and generate final summary."""
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