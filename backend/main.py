# backend/main.py
"""
Main application entry point for the EchoAI Backend.

This file initializes the FastAPI application, sets up the application lifecycle
(startup and shutdown events), configures logging, loads AI models,
initializes the database, and includes all API routers.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- 1. Import all centralized components ---
from backend.core.config import settings
from backend.core.logging_config import setup_logging
from backend.models.registry import model_registry
from backend.database.session_store import get_session_store

# --- 2. Import all your API routers ---
from backend.routers import transcript, summary, analytics

# --- 3. Setup Logging ---
# This should be the very first thing to run so that all subsequent
# steps are properly logged.
setup_logging()
logger = logging.getLogger(__name__)


# --- 4. Define the Application Lifecycle (Startup & Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's startup and shutdown events.
    This is the modern replacement for @app.on_event("startup").
    """
    # --- Code to run on server startup ---
    logger.info("🚀 Starting EchoAI Backend...")
    
    # 1. Load all AI models into the central registry. This is a slow
    #    process that should only happen once.
    model_registry.load_all_models()
    
    # 2. Initialize the database connection pool and store it in the app's
    #    state, making it accessible to other parts of the application.
    app.state.db_store = await get_session_store()
    logger.info(f"✅ Database ({settings.SESSION_STORE_TYPE}) and AI models loaded successfully.")
    
    yield # The application is now running and ready to accept requests
    
    # --- Code to run on server shutdown ---
    logger.info("🛑 Shutting down EchoAI Backend...")
    # (You can add cleanup logic here, like gracefully closing database pools)


# --- 5. Create the FastAPI Application Instance ---
app = FastAPI(
    title="EchoAI Backend",
    description="Real-time meeting intelligence with transcription, emotion, and analysis.",
    version="3.0.0",
    lifespan=lifespan # Use the new lifespan manager
)


# --- 6. Add Middleware ---
# (CORS middleware allows your frontend to communicate with this backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, change "*" to your frontend's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 7. Include API Routers ---
# This connects all the endpoints from your router files to the main application.
app.include_router(transcript.router)
app.include_router(summary.router)
app.include_router(analytics.router)


# --- 8. Define a Root Endpoint ---
@app.get("/", tags=["Root"])
async def read_root():
    """A simple root endpoint to confirm the API is running."""
    return {"message": "Welcome to the EchoAI Backend. Go to /docs for the API documentation."}