# # backend/app/routers/transcript.py
# from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
# from fastapi.responses import JSONResponse
# import json
# import logging
# import asyncio
# from typing import Dict, List
# import numpy as np

# # Import our real-time service
# from services.realtime_services import transcription_service, session_manager

# logger = logging.getLogger(__name__)
# router = APIRouter()

# class ConnectionManager:
#     def __init__(self):
#         self.active_connections: Dict[str, List[WebSocket]] = {}
    
#     async def connect(self, websocket: WebSocket, meeting_id: str):
#         await websocket.accept()
#         if meeting_id not in self.active_connections:
#             self.active_connections[meeting_id] = []
#         self.active_connections[meeting_id].append(websocket)
        
#         # Create session if it doesn't exist
#         if meeting_id not in session_manager.sessions:
#             session_manager.create_session(meeting_id)
        
#         logger.info(f"Client connected to meeting {meeting_id}")
    
#     def disconnect(self, websocket: WebSocket, meeting_id: str):
#         if meeting_id in self.active_connections:
#             self.active_connections[meeting_id].remove(websocket)
#             if not self.active_connections[meeting_id]:
#                 del self.active_connections[meeting_id]
#         logger.info(f"Client disconnected from meeting {meeting_id}")
    
#     async def broadcast_to_meeting(self, meeting_id: str, message: dict):
#         if meeting_id in self.active_connections:
#             dead_connections = []
#             for connection in self.active_connections[meeting_id]:
#                 try:
#                     await connection.send_json(message)
#                 except:
#                     dead_connections.append(connection)
            
#             # Remove dead connections
#             for dead_conn in dead_connections:
#                 self.active_connections[meeting_id].remove(dead_conn)

# manager = ConnectionManager()

# @router.websocket("/live/{meeting_id}")
# async def websocket_transcription(websocket: WebSocket, meeting_id: str):
#     """Real-time transcription WebSocket endpoint"""
#     await manager.connect(websocket, meeting_id)
    
#     try:
#         # Send initial connection confirmation
#         await websocket.send_json({
#             "type": "connection",
#             "status": "connected",
#             "meeting_id": meeting_id,
#             "message": "Real-time AI transcription started!"
#         })
        
#         audio_buffer = bytearray()
#         chunk_size = 4096  # Size of audio chunks to process
        
#         while True:
#             try:
#                 # Receive audio data
#                 data = await websocket.receive()
                
#                 if data["type"] == "websocket.disconnect":
#                     break
                
#                 # Handle different message types
#                 if "bytes" in data:
#                     # Audio data received
#                     audio_chunk = data["bytes"]
#                     audio_buffer.extend(audio_chunk)
                    
#                     # Process when we have enough data
#                     if len(audio_buffer) >= chunk_size * 4:  # ~0.5 seconds at 16kHz
#                         # Convert to numpy array for processing
#                         audio_array = np.frombuffer(bytes(audio_buffer), dtype=np.float32)
                        
#                         # Process with AI models
#                         result = await transcription_service.process_audio_chunk(audio_array)
                        
#                         if result["status"] == "success":
#                             # Add to session
#                             session_manager.add_transcription(meeting_id, result)
                            
#                             # Prepare response
#                             response = {
#                                 "type": "transcription",
#                                 "meeting_id": meeting_id,
#                                 "transcript": result["transcript"],
#                                 "emotion": result["emotion"],
#                                 "sentiment": result["sentiment"],
#                                 "timestamp": result["timestamp"],
#                                 "confidence": result["confidence"]
#                             }
                            
#                             # Send to all clients in this meeting
#                             await manager.broadcast_to_meeting(meeting_id, response)
                            
#                             logger.info(f"Processed audio for {meeting_id}: {result['transcript'][:50]}...")
                        
#                         # Clear buffer
#                         audio_buffer.clear()
                
#                 elif "text" in data:
#                     # Handle text commands
#                     try:
#                         command = json.loads(data["text"])
                        
#                         if command.get("action") == "get_summary":
#                             summary = session_manager.get_session_data(meeting_id)
#                             await websocket.send_json({
#                                 "type": "summary",
#                                 "data": summary
#                             })
                        
#                         elif command.get("action") == "clear_session":
#                             if meeting_id in session_manager.transcriptions:
#                                 session_manager.transcriptions[meeting_id].clear()
#                             await websocket.send_json({
#                                 "type": "info",
#                                 "message": "Session cleared"
#                             })
                    
#                     except json.JSONDecodeError:
#                         await websocket.send_json({
#                             "type": "error",
#                             "message": "Invalid command format"
#                         })
                
#             except Exception as e:
#                 logger.error(f"Error processing data: {e}")
#                 await websocket.send_json({
#                     "type": "error",
#                     "message": f"Processing error: {str(e)}"
#                 })
#                 continue
    
#     except WebSocketDisconnect:
#         manager.disconnect(websocket, meeting_id)
#         logger.info(f"WebSocket disconnected for meeting {meeting_id}")
    
#     except Exception as e:
#         logger.error(f"WebSocket error: {e}")
#         manager.disconnect(websocket, meeting_id)

# @router.get("/session/{meeting_id}")
# async def get_session_info(meeting_id: str):
#     """Get session information and transcriptions"""
#     try:
#         session_data = session_manager.get_session_data(meeting_id)
#         if "error" in session_data:
#             raise HTTPException(status_code=404, detail="Session not found")
        
#         return session_data
#     except Exception as e:
#         logger.error(f"Error getting session info: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/session/{meeting_id}/create")
# async def create_session(meeting_id: str):
#     """Create a new meeting session"""
#     try:
#         result = session_manager.create_session(meeting_id)
#         return result
#     except Exception as e:
#         logger.error(f"Error creating session: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.delete("/session/{meeting_id}")
# async def delete_session(meeting_id: str):
#     """Delete a meeting session"""
#     try:
#         if meeting_id in session_manager.sessions:
#             del session_manager.sessions[meeting_id]
#         if meeting_id in session_manager.transcriptions:
#             del session_manager.transcriptions[meeting_id]
        
#         return {"status": "deleted", "meeting_id": meeting_id}
#     except Exception as e:
#         logger.error(f"Error deleting session: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/session/{meeting_id}/export")
# async def export_session(meeting_id: str, format: str = "json"):
#     """Export session data"""
#     try:
#         session_data = session_manager.get_session_data(meeting_id)
#         if "error" in session_data:
#             raise HTTPException(status_code=404, detail="Session not found")
        
#         if format.lower() == "json":
#             return JSONResponse(content=session_data)
#         elif format.lower() == "text":
#             # Convert to readable text format
#             transcriptions = session_data.get("transcriptions", [])
#             text_content = f"Meeting ID: {meeting_id}\n"
#             text_content += f"Date: {session_data['session_info']['created_at']}\n"
#             text_content += "=" * 50 + "\n\n"
            
#             for i, trans in enumerate(transcriptions, 1):
#                 text_content += f"[{i}] {trans['timestamp']}\n"
#                 text_content += f"Text: {trans['transcript']}\n"
#                 text_content += f"Emotion: {trans['emotion']['emotion']} ({trans['emotion']['confidence']:.2f})\n"
#                 text_content += f"Sentiment: {trans['sentiment']['sentiment']} ({trans['sentiment']['confidence']:.2f})\n"
#                 text_content += "-" * 30 + "\n"
            
#             return JSONResponse(content={"text": text_content})
#         else:
#             raise HTTPException(status_code=400, detail="Unsupported format")
    
#     except Exception as e:
#         logger.error(f"Error exporting session: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/sessions")
# async def list_sessions():
#     """List all active sessions"""
#     try:
#         sessions = []
#         for meeting_id, session_info in session_manager.sessions.items():
#             sessions.append({
#                 "meeting_id": meeting_id,
#                 "created_at": session_info["created_at"],
#                 "status": session_info["status"],
#                 "total_chunks": session_info["total_chunks"]
#             })
        
#         return {"sessions": sessions}
#     except Exception as e:
#         logger.error(f"Error listing sessions: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# app/routers/transcript.py
"""
Updated transcript router with centralized store and proper error handling.
"""

import asyncio
import logging
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.modules.realtime_store import realtime_store
from app.models.schemas import (
    TranscriptEntryRequest,
    TranscriptEntryResponse,
    TranscriptsResponse,
    SessionInfoResponse,
    ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcript", tags=["Transcript"])

async def get_valid_session(meeting_id: str):
    """Dependency to validate meeting session exists."""
    session = await realtime_store.get_session(meeting_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"No active session found for meeting ID: {meeting_id}"
        )
    return session

@router.websocket("/live/{meeting_id}")
async def websocket_endpoint(websocket: WebSocket, meeting_id: str):
    """
    WebSocket endpoint for real-time transcript streaming.
    
    Clients connect here to receive live transcript updates.
    """
    await websocket.accept()
    queue = asyncio.Queue()
    
    try:
        # Ensure session exists
        await realtime_store.create_session(meeting_id)
        
        # Add connection to store
        await realtime_store.add_connection(meeting_id, queue)
        
        # Send initial session info
        session = await realtime_store.get_session(meeting_id)
        await websocket.send_json({
            "type": "session_connected",
            "data": session.to_dict() if session else {}
        })
        
        logger.info(f"WebSocket connected for meeting: {meeting_id}")
        
        # Listen for messages to broadcast
        while True:
            try:
                # Wait for new data from the queue
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json({
                    "type": "transcript_entry",
                    "data": data
                })
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                await websocket.send_json({
                    "type": "heartbeat",
                    "data": {"timestamp": "now"}
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for meeting: {meeting_id}")
    except Exception as e:
        logger.error(f"WebSocket error for meeting {meeting_id}: {e}")
    finally:
        # Clean up connection
        await realtime_store.remove_connection(meeting_id, queue)

@router.post("/{meeting_id}/add", response_model=TranscriptEntryResponse)
async def add_transcript_entry(
    meeting_id: str,
    entry_request: TranscriptEntryRequest
):
    """
    Add a new transcript entry to the meeting.
    
    This will automatically broadcast to all connected WebSocket clients.
    """
    try:
        entry = await realtime_store.add_transcript_entry(
            meeting_id=meeting_id,
            speaker=entry_request.speaker,
            text=entry_request.text,
            confidence=entry_request.confidence
        )
        
        logger.info(f"Added transcript entry for {meeting_id}: {entry_request.speaker}")
        return TranscriptEntryResponse(**entry.to_dict())
        
    except Exception as e:
        logger.error(f"Error adding transcript entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{meeting_id}", response_model=TranscriptsResponse)
async def get_transcripts(
    meeting_id: str,
    limit: int = 100,
    session = Depends(get_valid_session)
):
    """
    Get all transcript entries for a meeting.
    
    Args:
        meeting_id: The meeting identifier
        limit: Maximum number of entries to return (default: 100)
    """
    try:
        if limit > 1000:
            raise HTTPException(status_code=400, detail="Limit cannot exceed 1000")
            
        entries = await realtime_store.get_recent_transcripts(meeting_id, limit)
        
        return TranscriptsResponse(
            meeting_id=meeting_id,
            transcripts=[TranscriptEntryResponse(**entry.to_dict()) for entry in entries],
            total_count=len(entries)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transcripts for {meeting_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{meeting_id}/session", response_model=SessionInfoResponse)
async def get_session_info(meeting_id: str, session = Depends(get_valid_session)):
    """Get session information for a meeting."""
    return SessionInfoResponse(**session.to_dict())

@router.post("/{meeting_id}/start", response_model=SessionInfoResponse)
async def start_session(meeting_id: str):
    """Start a new transcript session for a meeting."""
    try:
        session = await realtime_store.create_session(meeting_id)
        logger.info(f"Started new session: {meeting_id}")
        return SessionInfoResponse(**session.to_dict())
    except Exception as e:
        logger.error(f"Error starting session {meeting_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{meeting_id}/end")
async def end_session(meeting_id: str, session = Depends(get_valid_session)):
    """End a transcript session and clean up resources."""
    try:
        await realtime_store.end_session(meeting_id)
        logger.info(f"Ended session: {meeting_id}")
        return {"message": f"Session {meeting_id} ended successfully"}
    except Exception as e:
        logger.error(f"Error ending session {meeting_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# app/routers/analytics.py
"""
Updated analytics router using centralized store.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends

from app.modules.realtime_store import realtime_store
from app.models.schemas import AnalyticsResponse, ErrorResponse
from .transcript import get_valid_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/{meeting_id}", response_model=AnalyticsResponse)
async def get_meeting_analytics(
    meeting_id: str,
    session = Depends(get_valid_session)
):
    """
    Get comprehensive analytics for a meeting session.
    
    Includes speaker statistics, word counts, confidence scores, and more.
    """
    try:
        analytics_data = await realtime_store.get_analytics_data(meeting_id)
        
        if not analytics_data:
            raise HTTPException(
                status_code=404,
                detail=f"No analytics data available for meeting: {meeting_id}"
            )
        
        logger.info(f"Generated analytics for meeting: {meeting_id}")
        return AnalyticsResponse(**analytics_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating analytics for {meeting_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# app/routers/summary.py
"""
Updated summary router using centralized store.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends

from app.modules.realtime_store import realtime_store
from app.models.schemas import SummaryResponse
from .transcript import get_valid_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/summary", tags=["Summary"])

@router.get("/{meeting_id}", response_model=SummaryResponse)
async def get_meeting_summary(
    meeting_id: str,
    session = Depends(get_valid_session)
):
    """
    Generate a meeting summary with key points and insights.
    
    In production, this would integrate with LLM services for intelligent summarization.
    """
    try:
        # Get transcript data
        transcripts = await realtime_store.get_transcripts(meeting_id)
        session_info = await realtime_store.get_session(meeting_id)
        
        if not transcripts:
            raise HTTPException(
                status_code=404,
                detail=f"No transcript data available for meeting: {meeting_id}"
            )
        
        # Generate summary (placeholder - replace with LLM integration)
        total_words = sum(len(entry.text.split()) for entry in transcripts)
        participants = list(session_info.participants)
        duration = (datetime.now() - session_info.created_at).total_seconds() / 60
        
        # Simple summary generation (replace with AI/LLM)
        summary = f"Meeting with {len(participants)} participants lasting {duration:.1f} minutes. " \
                 f"Total of {len(transcripts)} transcript entries with {total_words} words discussed."
        
        # Extract key points (placeholder logic)
        key_points = []
        for entry in transcripts[-5:]:  # Last 5 entries as "key points"
            if len(entry.text) > 50:  # Only longer statements
                key_points.append(f"{entry.speaker}: {entry.text[:100]}...")
        
        result = SummaryResponse(
            meeting_id=meeting_id,
            summary=summary,
            key_points=key_points[:3],  # Top 3 key points
            participants=participants,
            duration_minutes=duration,
            generated_at=datetime.now().isoformat()
        )
        
        logger.info(f"Generated summary for meeting: {meeting_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating summary for {meeting_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))