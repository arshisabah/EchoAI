# app/models/schemas.py
"""
Pydantic models for request/response validation and documentation.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class SessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"

class TranscriptEntryRequest(BaseModel):
    """Request model for adding transcript entries."""
    speaker: str = Field(..., min_length=1, max_length=100, description="Speaker name")
    text: str = Field(..., min_length=1, max_length=5000, description="Transcript text")
    confidence: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Confidence score")
    
    @validator('speaker')
    def validate_speaker(cls, v):
        return v.strip()
    
    @validator('text')
    def validate_text(cls, v):
        return v.strip()

class TranscriptEntryResponse(BaseModel):
    """Response model for transcript entries."""
    id: str
    speaker: str
    text: str
    timestamp: str
    confidence: float
    
    class Config:
        schema_extra = {
            "example": {
                "id": "meeting123_0",
                "speaker": "John Doe",
                "text": "Welcome to today's meeting.",
                "timestamp": "2025-09-11T10:30:00",
                "confidence": 0.95
            }
        }

class SessionInfoResponse(BaseModel):
    """Response model for session information."""
    meeting_id: str
    status: SessionStatus
    created_at: str
    participants: List[str]
    total_entries: int
    
    class Config:
        schema_extra = {
            "example": {
                "meeting_id": "meeting123",
                "status": "active",
                "created_at": "2025-09-11T10:00:00",
                "participants": ["John Doe", "Jane Smith"],
                "total_entries": 25
            }
        }

class TranscriptsResponse(BaseModel):
    """Response model for transcript list."""
    meeting_id: str
    transcripts: List[TranscriptEntryResponse]
    total_count: int
    
    class Config:
        schema_extra = {
            "example": {
                "meeting_id": "meeting123",
                "transcripts": [
                    {
                        "id": "meeting123_0",
                        "speaker": "John Doe",
                        "text": "Welcome to today's meeting.",
                        "timestamp": "2025-09-11T10:30:00",
                        "confidence": 0.95
                    }
                ],
                "total_count": 1
            }
        }

class AnalyticsResponse(BaseModel):
    """Response model for meeting analytics."""
    meeting_id: str
    session_info: SessionInfoResponse
    total_transcripts: int
    total_words: int
    speaker_statistics: Dict[str, Dict[str, int]]
    average_confidence: float
    duration_minutes: float
    
    class Config:
        schema_extra = {
            "example": {
                "meeting_id": "meeting123",
                "session_info": {
                    "meeting_id": "meeting123",
                    "status": "active",
                    "created_at": "2025-09-11T10:00:00",
                    "participants": ["John", "Jane"],
                    "total_entries": 10
                },
                "total_transcripts": 10,
                "total_words": 150,
                "speaker_statistics": {
                    "John": {"words": 80, "entries": 6},
                    "Jane": {"words": 70, "entries": 4}
                },
                "average_confidence": 0.92,
                "duration_minutes": 30.5
            }
        }

class SummaryResponse(BaseModel):
    """Response model for meeting summary."""
    meeting_id: str
    summary: str
    key_points: List[str]
    participants: List[str]
    duration_minutes: float
    generated_at: str
    
    class Config:
        schema_extra = {
            "example": {
                "meeting_id": "meeting123",
                "summary": "The team discussed quarterly goals and project timelines.",
                "key_points": [
                    "Q4 targets set at 150% growth",
                    "New project timeline approved",
                    "Budget allocation finalized"
                ],
                "participants": ["John Doe", "Jane Smith"],
                "duration_minutes": 45.0,
                "generated_at": "2025-09-11T11:30:00"
            }
        }

class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    detail: Optional[str] = None
    meeting_id: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "error": "Meeting not found",
                "detail": "No active session found for meeting ID: meeting123",
                "meeting_id": "meeting123"
            }
        }

class WebSocketMessage(BaseModel):
    """WebSocket message model."""
    type: str = Field(..., description="Message type")
    data: Dict[str, Any] = Field(..., description="Message data")
    timestamp: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "type": "transcript_entry",
                "data": {
                    "id": "meeting123_0",
                    "speaker": "John",
                    "text": "Hello everyone",
                    "confidence": 0.95
                },
                "timestamp": "2025-09-11T10:30:00"
            }
        }