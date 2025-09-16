# backend/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import logging
import uvicorn
import os
from pathlib import Path

# Import your routers
from app.routers import transcript, summary, analytics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="EchoAI Real-time Backend",
    description="AI-powered meeting intelligence with real-time transcription, emotion detection, and sentiment analysis",
    version="2.0.0"
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(
    transcript.router, 
    prefix="/transcript", 
    tags=["Real-time Transcription"]
)
app.include_router(
    summary.router, 
    prefix="/summary", 
    tags=["AI Summary"]
)
app.include_router(
    analytics.router, 
    prefix="/analytics", 
    tags=["Meeting Analytics"]
)

# Health check and info endpoints
@app.get("/")
async def root():
    """Root endpoint with system info"""
    return {
        "message": "🚀 EchoAI Real-time Backend is running!",
        "version": "2.0.0",
        "features": [
            "Real-time speech transcription (Whisper)",
            "Emotion detection (Wav2Vec2)",
            "Sentiment analysis (RoBERTa)", 
            "Live WebSocket streaming",
            "Session management",
            "Export functionality"
        ],
        "endpoints": {
            "websocket": "/transcript/live/{meeting_id}",
            "session_info": "/transcript/session/{meeting_id}",
            "export": "/transcript/session/{meeting_id}/export",
            "health": "/health",
            "test_client": "/test"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # You can add model health checks here
        from services.realtime_services import transcription_service
        
        model_status = {
            "whisper": transcription_service.whisper_model is not None,
            "emotion": transcription_service.emotion_model is not None,
            "sentiment": transcription_service.sentiment_model is not None,
        }
        
        all_healthy = all(model_status.values())
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "models": model_status,
            "timestamp": "2024-01-01T00:00:00Z"  # You can use actual timestamp
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.get("/models/status")
async def models_status():
    """Get detailed model status"""
    try:
        from services.realtime_services import transcription_service
        import torch
        
        status = {
            "device": transcription_service.device,
            "cuda_available": torch.cuda.is_available(),
            "models": {
                "whisper": {
                    "loaded": transcription_service.whisper_model is not None,
                    "model_name": "base"
                },
                "emotion": {
                    "loaded": transcription_service.emotion_model is not None,
                    "model_name": "harshit345/xlsr-wav2vec-speech-emotion-recognition"
                },
                "sentiment": {
                    "loaded": transcription_service.sentiment_model is not None,
                    "model_name": "cardiffnlp/twitter-roberta-base-sentiment-latest"
                }
            }
        }
        return status
    except Exception as e:
        logger.error(f"Model status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Serve the test client
@app.get("/test", response_class=HTMLResponse)
async def get_test_client():
    """Serve the test client HTML"""
    # You can either read from file or embed the HTML
    test_client_path = Path(__file__).parent / "test_client.html"
    
    if test_client_path.exists():
        with open(test_client_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    else:
        # Embedded version for quick testing
        return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>EchoAI Test Client</title>
    <style>
        body { font-family: Arial; max-width: 800px; margin: 0 auto; padding: 20px; }
        .controls { margin: 20px 0; }
        button { padding: 10px 20px; margin: 5px; }
        .status { padding: 15px; margin: 10px 0; border-radius: 5px; }
        .connected { background: #d4edda; }
        .disconnected { background: #f8d7da; }
        #transcripts { border: 1px solid #ccc; min-height: 200px; padding: 10px; }
        .transcript { margin: 10px 0; padding: 10px; background: #f8f9fa; border-left: 3px solid #007bff; }
    </style>
</head>
<body>
    <h1>🚀 EchoAI Test Client</h1>
    <div class="controls">
        <input type="text" id="meetingId" placeholder="Meeting ID" value="test-001">
        <button onclick="startRecording()">Start Recording</button>
        <button onclick="stopRecording()">Stop Recording</button>
        <button onclick="clearSession()">Clear</button>
    </div>
    <div id="status" class="status disconnected">Disconnected</div>
    <div id="transcripts"></div>
    
    <script>
        let ws = null;
        let mediaRecorder = null;
        
        async function startRecording() {
            const meetingId = document.getElementById('meetingId').value;
            ws = new WebSocket(`ws://localhost:8000/transcript/live/${meetingId}`);
            
            ws.onopen = () => {
                document.getElementById('status').innerHTML = '✅ Connected';
                document.getElementById('status').className = 'status connected';
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'transcription') {
                    addTranscript(data);
                }
            };
            
            // Get microphone
            const stream = await navigator.mediaDevices.getUserMedia({audio: true});
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = (event) => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(event.data);
                }
            };
            
            mediaRecorder.start(1000);
        }
        
        function stopRecording() {
            if (mediaRecorder) mediaRecorder.stop();
            if (ws) ws.close();
            document.getElementById('status').innerHTML = '❌ Disconnected';
            document.getElementById('status').className = 'status disconnected';
        }
        
        function addTranscript(data) {
            const div = document.createElement('div');
            div.className = 'transcript';
            div.innerHTML = `
                <strong>${data.transcript}</strong><br>
                <small>Emotion: ${data.emotion.emotion} | Sentiment: ${data.sentiment.sentiment}</small>
            `;
            document.getElementById('transcripts').insertBefore(div, document.getElementById('transcripts').firstChild);
        }
        
        function clearSession() {
            document.getElementById('transcripts').innerHTML = '';
        }
    </script>
</body>
</html>
        """)

# Exception handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return {"error": "Internal server error", "detail": str(exc)}

if __name__ == "__main__":
    # Initialize models on startup
    logger.info("🚀 Starting EchoAI Backend...")
    
    try:
        # Import to trigger model loading
        from services.realtime_services import transcription_service
        logger.info("✅ AI models loaded successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to load models: {e}")
        logger.error("⚠️ Server will start but AI features may not work")
    
    # Run the server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )