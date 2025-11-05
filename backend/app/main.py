# backend/main.py
"""
Main FastAPI application with monitoring.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from app.core.config import settings
from app.core.logging_config import setup_logging

# Setup logging
setup_logging(log_level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    logger.info("🚀 Starting EchoAI Backend...")
    
    # Initialize monitoring
    try:
        from app.core.monitoring import get_metrics_collector
        metrics = get_metrics_collector()
        logger.info("✅ Monitoring initialized")
    except Exception as e:
        logger.warning(f"⚠️ Monitoring initialization warning: {e}")
    
    # Services will lazy-load on first use
    logger.info("✅ Services configured (lazy initialization)")
    
    yield
    
    logger.info("🛑 Shutting down EchoAI Backend...")


# Create FastAPI app
app = FastAPI(
    title="EchoAI Backend",
    description="Real-time meeting intelligence with AI",
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
    """Add processing time header and collect metrics."""
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
        logger.error(f"Request processing error: {e}")
        try:
            from app.core.monitoring import get_metrics_collector
            metrics = get_metrics_collector()
            metrics.increment("requests_failed")
        except:
            pass
        raise


# Include routers
try:
    from app.routers import transcript, summary, analytics, meeting
    
    app.include_router(meeting.router)  # Multi-user meetings (primary)
    app.include_router(transcript.router)  # Legacy single-user support
    app.include_router(summary.router)
    app.include_router(analytics.router)
    
    logger.info("✅ API routers loaded")
except Exception as e:
    logger.error(f"❌ Failed to load routers: {e}")


# Root endpoints
@app.get("/", tags=["Root"])
async def read_root():
    """Root endpoint."""
    return {
        "message": "EchoAI Backend - Real-time Meeting Intelligence",
        "version": "3.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "metrics": "/metrics"
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
    """Comprehensive health check with component status."""
    try:
        from app.core.monitoring import HealthChecker
        health = HealthChecker.get_comprehensive_health()
        return health
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """Get application metrics."""
    try:
        from app.core.monitoring import get_metrics_collector
        metrics = get_metrics_collector()
        
        return {
            "application_metrics": metrics.get_metrics(),
            "system_metrics": metrics.get_system_metrics(),
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Metrics retrieval failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/alerts", tags=["Monitoring"])
async def get_alerts(level: str = None):
    """Get system alerts."""
    try:
        from app.core.monitoring import get_alert_manager
        alert_manager = get_alert_manager()
        
        alerts = alert_manager.get_alerts(level)
        
        return {
            "alerts": alerts,
            "count": len(alerts),
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Alert retrieval failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    try:
        from app.core.monitoring import get_alert_manager
        alert_manager = get_alert_manager()
        alert_manager.add_alert(
            "error",
            f"Unhandled exception: {str(exc)}",
            {"path": request.url.path, "method": request.method}
        )
    except:
        pass
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An error occurred"
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