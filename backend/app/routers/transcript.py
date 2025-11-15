from starlette.websockets import WebSocketState
import uuid
import logging
import json
import base64
import asyncio
from datetime import datetime
from fastapi import (
    APIRouter, WebSocket, WebSocketDisconnect,
    HTTPException, UploadFile, File, Form
)

from app.modules.realtime_store import get_transcript_store
from app.services.orchestrator_service import get_orchestrator_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcript", tags=["transcript"])


# ======================================================
# MAIN WEBSOCKET ENDPOINT
# ======================================================
@router.websocket("/ws/{session_id}")
async def websocket_transcript_endpoint(websocket: WebSocket, session_id: str):

    await websocket.accept()
    logger.info(f"🔌 WebSocket connected → {session_id}")

    store = get_transcript_store()
    orchestrator = get_orchestrator_service()

    # Register session
    try:
        await store.create_session(session_id, {"connection_type": "websocket"})
    except Exception as e:
        logger.warning(f"Store create failed: {e}")

    # Ensure ping map exists
    if not hasattr(orchestrator, "last_ping"):
        orchestrator.last_ping = {}

    orchestrator.last_ping[session_id] = datetime.utcnow()

    # Per-session audio lock
    if not hasattr(orchestrator, "processing_locks"):
        orchestrator.processing_locks = {}

    if session_id not in orchestrator.processing_locks:
        orchestrator.processing_locks[session_id] = asyncio.Lock()

    # Ensure session active
    if session_id not in orchestrator.active_sessions:
        await orchestrator.start_session(session_id)

    # ======================================================
    # WEBSOCKET LOOP
    # ======================================================
    try:
        while True:
            # -------- TIMEOUT HANDLING --------
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=90)
            except asyncio.TimeoutError:
                delta = (datetime.utcnow() - orchestrator.last_ping[session_id]).seconds
                if delta > 300:
                    logger.warning(f"⏳ Timeout {delta}s → closing session {session_id}")
                    await orchestrator.close_session(session_id)
                    await websocket.close()
                    break

                # send heartbeat ping
                try:
                    await websocket.send_json({"type": "ping"})
                except:
                    break
                continue

            # ---------------------------------------------------
            # 1️⃣  HANDLE BINARY PCM AUDIO (raw bytes)
            # ---------------------------------------------------
            if message.get("bytes") is not None:

                audio_bytes = message["bytes"]
                if not audio_bytes:
                    continue

                logger.debug(f"📥 Binary {len(audio_bytes)} bytes received")

                async with orchestrator.processing_locks[session_id]:
                    result = await orchestrator.process_audio_chunk(audio_bytes, session_id)

                # ------------------------
                # HANDLE RESULT CLEANLY
                # ------------------------
                await _handle_orchestrator_result(websocket, result, session_id)
                continue

            # ---------------------------------------------------
            # 2️⃣  HANDLE TEXT MESSAGE
            # ---------------------------------------------------
            text_data = message.get("text")
            if text_data is None:
                continue

            try:
                msg = json.loads(text_data)
                msg_type = msg.get("type")
            except:
                msg_type = text_data.strip().lower()
                msg = {"type": msg_type}

            orchestrator.last_ping[session_id] = datetime.utcnow()

            # HEARTBEAT
            if msg_type == "ping":
                try:
                    await websocket.send_json({"type": "pong"})
                except:
                    break
                continue

            # ---------------------------------------------------
            # 3️⃣  HANDLE BASE64 AUDIO
            # ---------------------------------------------------
            if msg_type == "audio_chunk":

                b64audio = msg.get("audio_data")
                if not b64audio:
                    await safe_send(websocket, {"type": "error", "message": "No audio data"})
                    continue

                try:
                    audio_bytes = base64.b64decode(b64audio)
                except Exception as e:
                    await safe_send(websocket, {"type": "error", "message": "Base64 decode failed"})
                    continue

                await safe_send(websocket, {"type": "audio_received"})

                async with orchestrator.processing_locks[session_id]:
                    result = await orchestrator.process_audio_chunk(audio_bytes, session_id)

                await _handle_orchestrator_result(websocket, result, session_id)
                continue

            # SUMMARY REQUEST
            if msg_type == "get_summary":
                summary = await orchestrator.generate_realtime_summary(session_id)
                await safe_send(websocket, {"type": "summary", "data": summary})
                continue

            # UNKNOWN TYPE
            logger.warning(f"Unknown WS message type: {msg_type}")
            await safe_send(websocket, {"type": "error", "message": f"Unknown type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info(f"❌ Disconnected → {session_id}")

    except Exception as e:
        logger.error(f"WebSocket crashed → {session_id} → {e}")

    finally:
        try:
            await orchestrator.close_session(session_id)
        except:
            pass


# ======================================================
# HELPER: SEND RESULT SAFELY
# ======================================================
async def _handle_orchestrator_result(websocket: WebSocket, result, session_id: str):

    # Listening / partial
    if isinstance(result, dict) and result.get("type") == "listening":
        await safe_send(websocket, {
            "type": "listening",
            "buffered": result.get("buffered_duration", 0)
        })
        return

    # No data
    if result is None:
        await safe_send(websocket, {"type": "no_speech"})
        return

    # MULTI ENTRY
    if isinstance(result, dict) and result.get("type") == "multi_speaker":
        await safe_send(websocket, {
            "type": "transcript_entry",
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        })
        return

    # SINGLE ENTRY (correct)
    if isinstance(result, dict) and result.get("text"):
        await safe_send(websocket, {
            "type": "transcript_entry",
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        })
        return

    # Unknown structure
    logger.debug(f"⚠️ Unknown orchestrator output → {result}")


# ======================================================
# SAFE SEND WRAPPER
# ======================================================
async def safe_send(websocket: WebSocket, data: dict):
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json(data)
    except:
        logger.debug("WebSocket send failed")


# ======================================================
# REST ENDPOINTS (UNCHANGED)
# ======================================================

@router.post("/process")
async def process_transcription(file: UploadFile = File(...), session_id: str = Form(...)):
    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(400, "Empty audio file")

        orchestrator = get_orchestrator_service()

        if session_id not in orchestrator.active_sessions:
            await orchestrator.start_session(session_id)

        result = await orchestrator.process_audio_chunk(audio_bytes, session_id)
        if not result:
            return {"status": "no_speech", "session_id": session_id}

        return {"status": "success", "session_id": session_id, "results": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/session/{session_id}")
async def get_transcript(session_id: str):
    orchestrator = get_orchestrator_service()
    result = await orchestrator.get_session_transcript(session_id)
    if not result:
        raise HTTPException(404, "Session not found")
    return result
