# main.py
"""
EchoAI Backend - Production Ready Multi-User Meeting Platform
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import time
import psutil
import os
import warnings

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.db import init_db

# Setup logging
setup_logging(log_level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Initialize database
try:
    init_db()
except Exception as e:
    logger.warning(f"Database initialization failed: {e}. App will continue without database.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    logger.info("🚀 Starting EchoAI Backend...")
    
    # Log device information
    import torch
    if torch.cuda.is_available():
        logger.info(f"🎮 CUDA available: {torch.cuda.get_device_name(0)}")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        logger.info("🍎 Apple MPS (Metal) available - GPU acceleration enabled")
    else:
        logger.info("💻 Using CPU (no GPU acceleration)")
    
    # Initialize monitoring
    try:
        from app.core.monitoring import get_metrics_collector
        metrics = get_metrics_collector()
        logger.info("✅ Monitoring initialized")
    except Exception as e:
        logger.warning(f"⚠️ Monitoring initialization warning: {e}")
    
    # Start meeting room broadcasting
    try:
        from app.services.meeting_room_manager import get_meeting_room_manager
        room_manager = get_meeting_room_manager()
        await room_manager.start_broadcasting()
        logger.info("✅ Meeting room manager started")
    except Exception as e:
        logger.error(f"❌ Meeting room manager failed: {e}")
    
    # Start async emotion processor
    try:
        from app.services.async_emotion_processor import get_async_emotion_processor
        emotion_processor = get_async_emotion_processor()
        await emotion_processor.start()
        logger.info("✅ Async emotion processor started")
    except Exception as e:
        logger.error(f"❌ Async emotion processor failed: {e}")
    
    logger.info("✅ EchoAI Backend ready!")
    
    yield
    
    # Cleanup
    try:
        from app.services.async_emotion_processor import get_async_emotion_processor
        emotion_processor = get_async_emotion_processor()
        await emotion_processor.stop()
        logger.info("✅ Async emotion processor stopped")
    except:
        pass
    
    try:
        from app.services.meeting_room_manager import get_meeting_room_manager
        room_manager = get_meeting_room_manager()
        await room_manager.stop_broadcasting()
        logger.info("✅ Meeting room manager stopped")
    except:
        pass
    
    logger.info("🛑 EchoAI Backend shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="EchoAI Backend",
    description="Multi-User Meeting Platform with Real-Time AI Intelligence",
    version="3.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header."""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        response.headers["X-Process-Time-Ms"] = str(round(process_time, 2))
        
        # Record metrics
        try:
            from app.core.monitoring import get_metrics_collector
            metrics = get_metrics_collector()
            metrics.increment("requests_total")
            metrics.record_request_time(process_time)
        except:
            pass
        
        return response
    except Exception as e:
        logger.error(f"Request error: {e}")
        try:
            from app.core.monitoring import get_metrics_collector
            get_metrics_collector().increment("requests_failed")
        except:
            pass
        raise


# Include routers
from app.routers import meeting, transcript, summary, analytics, debug

app.include_router(meeting.router)       # Multi-user meetings (PRIMARY)
app.include_router(transcript.router)    # Legacy single-user support
app.include_router(summary.router)       # AI summaries
app.include_router(analytics.router)     # Meeting analytics
app.include_router(debug.router)         # Debug endpoints

logger.info("✅ All API routers loaded")


# Root endpoints
@app.get("/", tags=["Root"])
async def read_root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to EchoAI Backend API",
        "name": "EchoAI Backend",
        "version": "3.0.0",
        "status": "running",
        "description": "Multi-User Meeting Platform with Real-Time AI Intelligence",
        "features": [
            "Multi-user real-time meetings",
            "Live transcription with speaker identification",
            "Real-time emotion analysis with guidance",
            "AI-powered task extraction and assignment",
            "Meeting summaries and analytics",
            "Local data export"
        ],
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "metrics": "/metrics",
            "create_room": "POST /meeting/rooms/create?room_id={id}",
            "join_room": "WS /meeting/rooms/{room_id}/ws",
            "get_summary": "GET /meeting/rooms/{room_id}/summary",
            "get_tasks": "GET /meeting/rooms/{room_id}/tasks"
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "version": "3.0.0",
        "timestamp": time.time()
    }


@app.get("/health/detailed", tags=["Health"])
async def detailed_health_check():
    """Comprehensive health check (production-safe)."""
    components = {}
    status = "ok"

    # Database check
    try:
        from app.db import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        components["database"] = "connected"
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        components["database"] = f"error: {e}"
        status = "unhealthy"

    # OpenAI API check
    try:
        import openai
        if settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
            components["openai"] = "configured"
        else:
            components["openai"] = "missing"
    except Exception as e:
        components["openai"] = f"error: {e}"
        status = "unhealthy"

    # Version info
    components["version"] = getattr(settings, "APP_VERSION", "unknown")

    return {
        "status": status,
        "components": components,
        "timestamp": time.time(),
    }

@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """Return live app + system metrics (safe in production)."""
    app_metrics = {}
    system_metrics = {}

    try:
        # Real app metrics if collector available
        from app.core.monitoring import get_metrics_collector
        metrics = get_metrics_collector()
        app_metrics = metrics.get_metrics()
        system_metrics = metrics.get_system_metrics()
    except Exception:
        # Fallback to psutil system metrics
        app_metrics = {
            "status": "ok",
            "requests_total": 0,
            "requests_failed": 0,
        }
        system_metrics = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_used_mb": round(psutil.virtual_memory().used / (1024 * 1024), 2),
            "memory_percent": psutil.virtual_memory().percent,
        }

    return {
        "application_metrics": app_metrics,
        "system_metrics": system_metrics,
        "timestamp": time.time(),
    }

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An error occurred",
            "path": str(request.url.path)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting EchoAI Backend server...")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )


# 🔹 Add this new route
# Line 265-269 in app/main.py
@app.get("/test")
def serve_test():
    file_path = os.path.join(os.path.dirname(__file__), "../test.html")
    # ✅ Add no-cache headers
    return FileResponse(
        file_path,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )