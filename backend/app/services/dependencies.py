# backend/services/dependencies.py
"""
Dependency injection for FastAPI.
Provides singleton instances of all services.
"""

from typing import Optional
from openai import AsyncOpenAI
from app.core.config import settings

# Import service classes
from app.services.transcription_service import TranscriptionService
from app.services.emotion_analysis import EmotionService
from app.services.summary_service import SummaryService
from app.services.speaker_identification_service import SpeakerIdentificationService

# --- Singleton instances ---
_openai_client: Optional[AsyncOpenAI] = None
_transcription_service: Optional[TranscriptionService] = None
_emotion_service: Optional[EmotionService] = None
_summary_service: Optional[SummaryService] = None
_speaker_service: Optional[SpeakerIdentificationService] = None


def get_openai_client() -> AsyncOpenAI:
    """Get shared OpenAI client."""
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def get_transcription_service() -> TranscriptionService:
    """Get transcription service singleton."""
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = TranscriptionService()
    return _transcription_service


def get_emotion_service() -> EmotionService:
    """Get emotion analysis service singleton."""
    global _emotion_service
    if _emotion_service is None:
        _emotion_service = EmotionService()
    return _emotion_service


def get_summary_service() -> SummaryService:
    """Get summary service singleton."""
    global _summary_service
    if _summary_service is None:
        _summary_service = SummaryService()
    return _summary_service


def get_speaker_service() -> SpeakerIdentificationService:
    """Get speaker identification service singleton."""
    global _speaker_service
    if _speaker_service is None:
        _speaker_service = SpeakerIdentificationService()
    return _speaker_service