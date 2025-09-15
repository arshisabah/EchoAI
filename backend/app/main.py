# # app/main.py
"""
Updated main FastAPI application with production-ready features.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Import logging configuration
from app.core.logging_config import setup_logging, RequestLoggingMiddleware

# Import routers
from app.routers import transcript, analytics, summary

# Setup logging before creating app
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
setup_logging(log_level=LOG_LEVEL)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("🚀 Starting Transcript API server...")
    logger.info(f"Log level: {LOG_LEVEL}")
    logger.info("All systems ready!")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Transcript API server...")
    logger.info("Cleanup completed!")

# Create FastAPI app
app = FastAPI(
    title="Real-time Transcript API",
    description="Production-ready API for real-time meeting transcription and analytics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Handle validation errors with detailed messages."""
    logger.warning(f"Validation error for {request.url.path}: {exc}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "detail": str(exc),
            "errors": exc.errors()
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with consistent format."""
    logger.error(f"HTTP error {exc.status_code} for {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url.path)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected exceptions."""
    logger.exception(f"Unexpected error for {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred. Please try again later.",
            "path": str(request.url.path)
        }
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "message": "Transcript API is running"
    }

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Real-time Transcript API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "transcript": "/transcript",
            "analytics": "/analytics",
            "summary": "/summary"
        }
    }

# Include routers
app.include_router(transcript.router)
app.include_router(analytics.router)
app.include_router(summary.router)

if __name__ == "__main__":
    import uvicorn
    
    # Run with uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )