# app/routers/analytics.py
"""
Analytics router with comprehensive meeting insights.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from collections import Counter

from fastapi import APIRouter, HTTPException, Query

from app.modules.realtime_store import get_transcript_store
from app.services.emotion_analysis import get_emotion_service, analyze_transcript_emotions
from app.services.speaker_identification_service import get_speaker_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/session/{session_id}")
async def get_session_analytics(session_id: str):
    """Get comprehensive analytics for a session."""
    try:
        store = get_transcript_store()
        
        # Check if session exists
        sessions = store.list_sessions()
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get basic analytics
        analytics = store.get_analytics(session_id)
        
        if not analytics:
            raise HTTPException(status_code=404, detail="No analytics data available")
        
        return {
            "session_id": session_id,
            **analytics,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analytics error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/session/{session_id}/detailed")
async def get_detailed_analytics(session_id: str):
    """Get detailed analytics including emotions and patterns."""
    try:
        store = get_transcript_store()
        
        if session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get transcript entries
        transcript_entries = store.get_session_transcript(session_id)
        
        if not transcript_entries:
            return {
                "session_id": session_id,
                "message": "No transcript data available",
                "total_entries": 0
            }
        
        # Get basic analytics
        basic_analytics = store.get_analytics(session_id)
        
        # Get emotion analysis
        entries_dict = [entry.to_dict() for entry in transcript_entries]
        emotion_results = await analyze_transcript_emotions(entries_dict)
        
        # Get speaker patterns
        speaker_service = get_speaker_service()
        speaker_patterns = await speaker_service.analyze_speaker_patterns(session_id)
        
        # Calculate conversation metrics
        conversation_metrics = calculate_conversation_metrics(transcript_entries)
        
        return {
            "session_id": session_id,
            "basic_analytics": basic_analytics,
            "emotion_analysis": emotion_results["session_summary"],
            "speaker_patterns": speaker_patterns,
            "conversation_metrics": conversation_metrics,
            "total_entries": len(transcript_entries),
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Detailed analytics error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/session/{session_id}/emotions")
async def get_emotion_analytics(session_id: str):
    """Get emotion analysis for a session."""
    try:
        store = get_transcript_store()
        
        if session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        transcript_entries = store.get_session_transcript(session_id)
        
        if not transcript_entries:
            return {
                "session_id": session_id,
                "message": "No transcript data for emotion analysis",
                "emotion_distribution": {}
            }
        
        # Analyze emotions
        entries_dict = [entry.to_dict() for entry in transcript_entries]
        emotion_results = await analyze_transcript_emotions(entries_dict)
        
        return {
            "session_id": session_id,
            "emotion_analysis": emotion_results,
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Emotion analytics error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/session/{session_id}/speakers")
async def get_speaker_analytics(session_id: str):
    """Get speaker-specific analytics."""
    try:
        speaker_service = get_speaker_service()
        
        speakers = await speaker_service.get_session_speakers(session_id)
        patterns = await speaker_service.analyze_speaker_patterns(session_id)
        
        return {
            "session_id": session_id,
            "speakers": speakers,
            "patterns": patterns,
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Speaker analytics error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/session/{session_id}/timeline")
async def get_conversation_timeline(session_id: str, limit: int = Query(default=100, ge=1, le=500)):
    """Get chronological timeline of conversation events."""
    try:
        store = get_transcript_store()
        
        if session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        transcript_entries = store.get_session_transcript(session_id)
        
        # Limit entries
        if len(transcript_entries) > limit:
            transcript_entries = transcript_entries[-limit:]
        
        timeline = []
        for entry in transcript_entries:
            timeline.append({
                "timestamp": entry.timestamp.isoformat(),
                "speaker": entry.speaker,
                "text": entry.text,
                "confidence": entry.confidence,
                "word_count": len(entry.text.split())
            })
        
        return {
            "session_id": session_id,
            "timeline": timeline,
            "total_events": len(timeline),
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Timeline error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/session/{session_id}/summary")
async def get_analytics_summary(session_id: str):
    """Get quick analytics summary."""
    try:
        store = get_transcript_store()
        
        if session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        analytics = store.get_analytics(session_id)
        session = await store.get_session(session_id)
        
        summary = {
            "session_id": session_id,
            "status": session.status.value if session else "unknown",
            "duration_minutes": analytics.get("duration_minutes", 0),
            "total_words": analytics.get("total_words", 0),
            "total_turns": len(analytics.get("speaker_statistics", {})),
            "speakers": analytics.get("speakers", []),
            "average_confidence": analytics.get("average_confidence", 0),
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summary error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sessions/compare")
async def compare_sessions(session_ids: List[str] = Query(...)):
    """Compare analytics across multiple sessions."""
    try:
        store = get_transcript_store()
        
        # Validate sessions
        available = store.list_sessions()
        missing = [sid for sid in session_ids if sid not in available]
        
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Sessions not found: {missing}"
            )
        
        # Collect analytics for each session
        comparison = []
        
        for session_id in session_ids:
            analytics = store.get_analytics(session_id)
            
            comparison.append({
                "session_id": session_id,
                "total_words": analytics.get("total_words", 0),
                "duration_minutes": analytics.get("duration_minutes", 0),
                "speakers": len(analytics.get("speakers", [])),
                "avg_confidence": analytics.get("average_confidence", 0)
            })
        
        # Calculate aggregate stats
        total_words = sum(s["total_words"] for s in comparison)
        total_duration = sum(s["duration_minutes"] for s in comparison)
        avg_speakers = sum(s["speakers"] for s in comparison) / len(comparison) if comparison else 0
        
        return {
            "sessions": comparison,
            "aggregate": {
                "total_sessions": len(comparison),
                "total_words": total_words,
                "total_duration_minutes": total_duration,
                "average_speakers_per_session": round(avg_speakers, 2)
            },
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session comparison error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sessions")
async def list_all_sessions():
    """List all available sessions with basic stats."""
    try:
        store = get_transcript_store()
        sessions = store.list_sessions()
        
        session_list = []
        for session_id in sessions:
            analytics = store.get_analytics(session_id)
            session_list.append({
                "session_id": session_id,
                "total_entries": analytics.get("total_transcripts", 0),
                "speakers": analytics.get("speakers", []),
                "duration_minutes": analytics.get("duration_minutes", 0)
            })
        
        return {
            "sessions": session_list,
            "total_count": len(session_list),
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"List sessions error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sessions/list")
async def list_sessions_alias():
    """Alias for /sessions endpoint to support legacy API calls."""
    return await list_all_sessions()

@router.get("/{session_id}")
async def get_basic_or_detailed_analytics(session_id: str):
    """Alias route for frontend analytics dashboard"""
    return await get_detailed_analytics(session_id)

def calculate_conversation_metrics(transcript_entries: List) -> Dict[str, Any]:
    """Calculate conversation flow metrics."""
    if not transcript_entries:
        return {}
    
    # Calculate turn-taking patterns
    speaker_transitions = []
    previous_speaker = None
    
    for entry in transcript_entries:
        if previous_speaker and previous_speaker != entry.speaker:
            speaker_transitions.append({
                "from": previous_speaker,
                "to": entry.speaker
            })
        previous_speaker = entry.speaker
    
    # Calculate speaking pace
    total_words = sum(len(entry.text.split()) for entry in transcript_entries)
    duration = (transcript_entries[-1].timestamp - transcript_entries[0].timestamp).total_seconds() / 60
    words_per_minute = total_words / duration if duration > 0 else 0
    
    # Vocabulary richness
    all_words = []
    for entry in transcript_entries:
        words = [w.lower().strip('.,!?;:"()[]{}') for w in entry.text.split()]
        all_words.extend(words)
    
    unique_words = len(set(all_words))
    vocabulary_diversity = unique_words / len(all_words) if all_words else 0
    
    return {
        "total_turns": len(transcript_entries),
        "speaker_transitions": len(speaker_transitions),
        "words_per_minute": round(words_per_minute, 2),
        "vocabulary_diversity": round(vocabulary_diversity, 3),
        "unique_words": unique_words,
        "total_words": len(all_words)
    }