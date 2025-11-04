# app/models/api_models.py
"""
Pydantic models for API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class TranscriptEntryResponse(BaseModel):
    """Response model for transcript entries."""
    id: str
    speaker: str
    text: str
    timestamp: str
    confidence: float
    emotion: Optional[str] = None
    emotion_confidence: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "entry_123",
                "speaker": "Speaker_1",
                "text": "Hello everyone",
                "timestamp": "2025-01-01T10:00:00",
                "confidence": 0.95,
                "emotion": "neutral",
                "emotion_confidence": 0.85
            }
        }


class SessionInfoResponse(BaseModel):
    """Response model for session information."""
    meeting_id: str
    status: SessionStatus
    created_at: str
    participants: List[str]
    total_entries: int


class AnalyticsResponse(BaseModel):
    """Response model for analytics data."""
    meeting_id: str
    session_info: Optional[SessionInfoResponse] = None
    total_transcripts: int
    total_words: int
    speaker_statistics: Dict[str, Dict[str, int]]
    average_confidence: float
    duration_minutes: float


class WebSocketMessage(BaseModel):
    """WebSocket message model."""
    type: str
    session_id: str
    data: Dict[str, Any]
    timestamp: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    session_id: Optional[str] = None


class SuccessResponse(BaseModel):
    """Standard success response."""
    message: str
    session_id: Optional[str] = None