# backend/services/dependencies.py
"""
Initializes and provides single, shared instances of all application services.
This is the central point for managing service dependencies for FastAPI.
"""

from openai import AsyncOpenAI
from backend.core.config import settings

# 1. Import all the service CLASSES
from .transcription_service import TranscriptionService
from .emotion_service import EmotionService
from .summary_service import SummaryService
from .orchestrator_service import OrchestratorService

# 2. Create a single, shared OpenAI client
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# 3. Create single instances of the "specialist" services
transcription_service = TranscriptionService()
emotion_service = EmotionService(client=openai_client)
summary_service = SummaryService(client=openai_client)

# 4. Create the main orchestrator, giving it the other services it needs
orchestrator_instance = OrchestratorService(
    transcription_service=transcription_service,
    emotion_service=emotion_service,
    summary_service=summary_service
)

# --- Dependency Injection Functions ---
# These are the simple functions that your routers will call using `Depends`.

def get_orchestrator():
    return orchestrator_instance

def get_summary_service():
    return summary_service

def get_emotion_service():
    return emotion_service

def get_transcription_service():
    return transcription_service
