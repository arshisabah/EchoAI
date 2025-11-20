import os
from typing import List, Optional
from pydantic_settings import BaseSettings

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables and `.env` file.
    This ensures consistency across environments (dev, staging, prod).
    """

    # -------------------------------------------------------------------
    # APP CONFIG
    # -------------------------------------------------------------------
    APP_NAME: str = "EchoAI Backend"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = True
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # -------------------------------------------------------------------
    # API KEYS
    # -------------------------------------------------------------------
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    HUGGING_FACE_TOKEN: Optional[str] = os.getenv("HUGGING_FACE_TOKEN")
    DEEPGRAM_API_KEY: Optional[str] = os.getenv("DEEPGRAM_API_KEY")

    # -------------------------------------------------------------------
    # DATABASE
    # -------------------------------------------------------------------
    SESSION_STORE_TYPE: str = os.getenv("SESSION_STORE_TYPE", "file")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"postgresql://{os.getenv('USER', 'postgres')}@localhost:5432/echoai"
    )

    # -------------------------------------------------------------------
    # AI MODELS
    # -------------------------------------------------------------------
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")
    MODEL_CACHE_DIR: str = os.getenv("MODEL_CACHE_DIR", "./models_cache")
    API_TIMEOUT_SECONDS: int = int(os.getenv("API_TIMEOUT_SECONDS", "60"))
    USE_STREAMING_TRANSCRIPTION: bool = os.getenv("USE_STREAMING_TRANSCRIPTION", "true").lower() == "true"

    # -------------------------------------------------------------------
    # OPENAI RATE LIMITING
    # -------------------------------------------------------------------
    OPENAI_MAX_RETRIES: int = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
    OPENAI_RETRY_DELAY: float = float(os.getenv("OPENAI_RETRY_DELAY", "1.0"))
    OPENAI_REQUEST_TIMEOUT: float = float(os.getenv("OPENAI_REQUEST_TIMEOUT", "2.0"))

    # -------------------------------------------------------------------
    # FRONTEND CORS CONFIG
    # -------------------------------------------------------------------
    # Format in .env: ALLOWED_ORIGINS=["*"] or ["http://localhost:5173"]
    ALLOWED_ORIGINS: List[str] = ["*"]

    # -------------------------------------------------------------------
    # INTERNAL CONFIG
    # -------------------------------------------------------------------
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Allow extra fields in .env without crashing
        extra = "allow"


# Instantiate global settings
settings = Settings()
