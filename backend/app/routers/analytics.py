"""
Enhanced analytics router with real-time insights, emotion analysis, and advanced metrics.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import Counter

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Import our services
from modules.realtime_store import get_transcript_store
from app.services.emotion_analysis import (
    get_emotion_service, 
    analyze_transcript_emotions
)
from app.models.api_models import AnalyticsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

class DetailedAnalyticsResponse(BaseModel):
    """Comprehensive analytics response with emotion insights"""
    session_id: str
    
    # Basic metrics
    total_words: int = Field(ge=0)
    total_turns: int = Field(ge=0)
    speakers: List[str]
    turns_by_speaker: Dict[str, int]
    words_by_speaker: Dict[str, int]
    avg_words_per_turn: float = Field(ge=0.0)
    session_duration_seconds: float = Field(ge=0.0)
    avg_confidence: float = Field(ge=0.0, le=1.0)
    
    # Time-based analytics
    speaking_time_distribution: Dict[str, float]
    conversation_pace: Dict[str, float]  # Words per minute by speaker
    turn_frequency: Dict[str, float]  # Turns per minute by speaker
    
    # Emotion analytics
    emotion_distribution: Dict[str, int]
    sentiment_distribution: Dict[str, int]
    average_sentiment_score: float
    dominant_emotion: str
    dominant_sentiment: str
    emotion_timeline: List[Dict[str, Any]]
    
    # Advanced insights
    speaker_engagement: Dict[str, float]  # Engagement score per speaker
    conversation_flow: List[Dict[str, Any]]  # Turn transitions
    key_moments: List[Dict[str, Any]]  # High emotion/important moments
    vocabulary_richness: Dict[str, Any]  # Unique words, complexity
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.now)
    analysis_duration_ms: float
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TrendAnalyticsRequest(BaseModel):
    """Request for trend analysis across multiple sessions"""
    session_ids: List[str] = Field(..., min_items=1, max_items=20)
    time_range_hours: Optional[int] = Field(default=24, ge=1, le=168)  # Max 1 week
    metrics: List[str] = Field(default=["sentiment", "engagement", "emotion"])

@router.get("/session/{session_id}", response_model=AnalyticsResponse)
async def get_basic_analytics(session_id: str):
    """
    Get basic analytics for a session (backward compatibility).
    """
    try:
        store = get_transcript_store()
        
        if session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        analytics = store.get_analytics(session_id)
        
        return AnalyticsResponse(
            session_id=session_id,
            **analytics
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Basic analytics error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/session/{session_id}/detailed", response_model=DetailedAnalyticsResponse)
async def get_detailed_analytics(session_id: str):
    """
    Get comprehensive analytics including emotion analysis and advanced insights.
    """
    start_time = datetime.now()
    
    try:
        store = get_transcript_store()
        
        if session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get basic analytics
        basic_analytics = store.get_analytics(session_id)
        transcript_entries = store.get_session_transcript(session_id)
        
        if not transcript_entries:
            raise HTTPException(status_code=404, detail="No transcript data found")
        
        # Get emotion analysis
        entries_dict = [entry.to_dict() for entry in transcript_entries]
        emotion_results = await analyze_transcript_emotions(entries_dict)
        
        # Calculate advanced metrics
        advanced_metrics = calculate_advanced_analytics(transcript_entries)
        
        # Calculate time-based metrics
        time_metrics = calculate_time_based_metrics(transcript_entries)
        
        # Build comprehensive response
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        response = DetailedAnalyticsResponse(
            session_id=session_id,
            
            # Basic metrics from store
            total_words=basic_analytics.get('total_words', 0),
            total_turns=basic_analytics.get('total_turns', 0),
            speakers=basic_analytics.get('speakers', []),
            turns_by_speaker=basic_analytics.get('turns_by_speaker', {}),
            avg_words_per_turn=basic_analytics.get('avg_words_per_turn', 0.0),
            session_duration_seconds=basic_analytics.get('session_duration_seconds', 0.0),
            avg_confidence=basic_analytics.get('avg_confidence', 0.0),
            
            # Advanced calculated metrics
            words_by_speaker=advanced_metrics['words_by_speaker'],
            speaking_time_distribution=time_metrics['speaking_time_distribution'],
            conversation_pace=time_metrics['conversation_pace'],
            turn_frequency=time_metrics['turn_frequency'],
            
            # Emotion analytics
            emotion_distribution=emotion_results['session_summary']['emotion_distribution'],
            sentiment_distribution=emotion_results['session_summary']['sentiment_distribution'],
            average_sentiment_score=emotion_results['session_summary']['average_sentiment_score'],
            dominant_emotion=emotion_results['session_summary']['dominant_emotion'],
            dominant_sentiment=emotion_results['session_summary']['dominant_sentiment'],
            emotion_timeline=build_emotion_timeline(emotion_results['individual_results']),
            
            # Advanced insights
            speaker_engagement=advanced_metrics['speaker_engagement'],
            conversation_flow=advanced_metrics['conversation_flow'],
            key_moments=identify_key_moments(entries_dict, emotion_results),
            vocabulary_richness=advanced_metrics['vocabulary_richness'],
            
            analysis_duration_ms=processing_time
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Detailed analytics error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

def calculate_advanced_analytics(transcript_entries) -> Dict[str, Any]:
    """Calculate advanced analytics metrics"""
    
    words_by_speaker = {}
    speaker_turns = {}
    all_words = []
    conversation_flow = []
    previous_speaker = None
    
    for entry in transcript_entries:
        speaker = entry.speaker
        words = entry.text.split()
        word_count = len(words)
        
        # Words by speaker
        words_by_speaker[speaker] = words_by_speaker.get(speaker, 0) + word_count
        
        # Speaker turns
        speaker_turns[speaker] = speaker_turns.get(speaker, 0) + 1
        
        # All words for vocabulary analysis
        all_words.extend([word.lower().strip('.,!?;:"()[]{}') for word in words])
        
        # Conversation flow (speaker transitions)
        if previous_speaker and previous_speaker != speaker:
            conversation_flow.append({
                "from_speaker": previous_speaker,
                "to_speaker": speaker,
                "timestamp": entry.timestamp.isoformat()
            })
        
        previous_speaker = speaker
    
    # Calculate speaker engagement (based on words and turn frequency)
    total_words = sum(words_by_speaker.values())
    total_turns = sum(speaker_turns.values())
    
    speaker_engagement = {}
    for speaker in words_by_speaker.keys():
        word_share = words_by_speaker[speaker] / total_words if total_words > 0 else 0
        turn_share = speaker_turns[speaker] / total_turns if total_turns > 0 else 0
        
        # Engagement score combines word contribution and turn frequency
        engagement_score = (word_share * 0.6 + turn_share * 0.4) * 100
        speaker_engagement[speaker] = round(engagement_score, 2)
    
    # Vocabulary richness analysis
    unique_words = set(all_words)
    word_frequency = Counter(all_words)
    
    vocabulary_richness = {
        "total_words": len(all_words),
        "unique_words": len(unique_words),
        "vocabulary_diversity": len(unique_words) / len(all_words) if all_words else 0,
        "most_common_words": [
            {"word": word, "count": count} 
            for word, count in word_frequency.most_common(10)
        ],
        "average_word_length": sum(len(word) for word in all_words) / len(all_words) if all_words else 0
    }
    
    return {
        "words_by_speaker": words_by_speaker,
        "speaker_engagement": speaker_engagement,
        "conversation_flow": conversation_flow[-20:],  # Last 20 transitions
        "vocabulary_richness": vocabulary_richness
    }

def calculate_time_based_metrics(transcript_entries) -> Dict[str, Any]:
    """Calculate time-based conversation metrics"""
    
    if len(transcript_entries) < 2:
        return {
            "speaking_time_distribution": {},
            "conversation_pace": {},
            "turn_frequency": {}
        }
    
    # Calculate session duration
    start_time = transcript_entries[0].timestamp
    end_time = transcript_entries[-1].timestamp
    total_duration = (end_time - start_time).total_seconds() / 60  # Minutes
    
    if total_duration <= 0:
        total_duration = 1  # Avoid division by zero
    
    # Time distribution and pace by speaker
    speaker_stats = {}
    
    for i, entry in enumerate(transcript_entries):
        speaker = entry.speaker
        words = len(entry.text.split())
        
        if speaker not in speaker_stats:
            speaker_stats[speaker] = {
                "total_words": 0,
                "total_turns": 0,
                "speaking_time": 0  # We'll estimate this
            }
        
        speaker_stats[speaker]["total_words"] += words
        speaker_stats[speaker]["total_turns"] += 1
        
        # Estimate speaking time (rough approximation)
        # Assume average speaking rate of 150 words per minute
        estimated_speaking_time = words / 150  # Minutes
        speaker_stats[speaker]["speaking_time"] += estimated_speaking_time
    
    # Calculate final metrics
    speaking_time_distribution = {}
    conversation_pace = {}
    turn_frequency = {}
    
    total_speaking_time = sum(stats["speaking_time"] for stats in speaker_stats.values())
    
    for speaker, stats in speaker_stats.items():
        # Speaking time distribution (percentage)
        speaking_time_distribution[speaker] = round(
            (stats["speaking_time"] / total_speaking_time * 100) if total_speaking_time > 0 else 0, 2
        )
        
        # Conversation pace (words per minute)
        conversation_pace[speaker] = round(
            stats["total_words"] / total_duration, 2
        )
        
        # Turn frequency (turns per minute)
        turn_frequency[speaker] = round(
            stats["total_turns"] / total_duration, 2
        )
    
    return {
        "speaking_time_distribution": speaking_time_distribution,
        "conversation_pace": conversation_pace,
        "turn_frequency": turn_frequency
    }

def build_emotion_timeline(emotion_results: List[Dict]) -> List[Dict[str, Any]]:
    """Build timeline of emotions throughout the conversation"""
    timeline = []
    
    for result in emotion_results:
        if 'emotion_analysis' in result:
            emotion_data = result['emotion_analysis']
            timeline.append({
                "entry_id": result.get('entry_id'),
                "speaker": result.get('speaker'),
                "emotion": emotion_data.get('primary_emotion'),
                "confidence": emotion_data.get('confidence', 0),
                "sentiment": emotion_data.get('sentiment_polarity'),
                "sentiment_score": emotion_data.get('sentiment_score', 0)
            })
    
    return timeline

def identify_key_moments(entries_dict: List[Dict], emotion_results: Dict) -> List[Dict[str, Any]]:
    """Identify key moments in the conversation based on emotion intensity and content"""
    key_moments = []
    
    individual_results = emotion_results.get('individual_results', [])
    
    for i, result in enumerate(individual_results):
        if 'emotion_analysis' not in result:
            continue
            
        emotion_data = result['emotion_analysis']
        confidence = emotion_data.get('confidence', 0)
        emotional_intensity = emotion_data.get('emotional_intensity', 0)
        sentiment_score = abs(emotion_data.get('sentiment_score', 0))
        
        # Identify high-intensity moments
        intensity_threshold = 0.7
        if (confidence > intensity_threshold or 
            emotional_intensity > intensity_threshold or 
            sentiment_score > intensity_threshold):
            
            # Find corresponding transcript entry
            entry_id = result.get('entry_id')
            matching_entry = next(
                (entry for entry in entries_dict if entry.get('id') == entry_id), 
                None
            )
            
            if matching_entry:
                key_moments.append({
                    "timestamp": matching_entry.get('timestamp'),
                    "speaker": result.get('speaker'),
                    "text_snippet": matching_entry.get('text', '')[:100] + "...",
                    "emotion": emotion_data.get('primary_emotion'),
                    "sentiment": emotion_data.get('sentiment_polarity'),
                    "intensity_score": max(confidence, emotional_intensity, sentiment_score),
                    "reason": determine_moment_reason(emotion_data)
                })
    
    # Sort by intensity and return top moments
    key_moments.sort(key=lambda x: x['intensity_score'], reverse=True)
    return key_moments[:10]  # Top 10 key moments

def determine_moment_reason(emotion_data: Dict) -> str:
    """Determine why this moment is considered key"""
    emotion = emotion_data.get('primary_emotion', 'neutral')
    confidence = emotion_data.get('confidence', 0)
    sentiment_score = emotion_data.get('sentiment_score', 0)
    
    if emotion in ['anger', 'frustration'] and confidence > 0.7:
        return "High tension/conflict detected"
    elif emotion in ['joy', 'excitement'] and confidence > 0.7:
        return "Positive breakthrough/agreement"
    elif abs(sentiment_score) > 0.8:
        return f"Strong {'positive' if sentiment_score > 0 else 'negative'} sentiment"
    elif emotion == 'surprise' and confidence > 0.6:
        return "Unexpected development"
    else:
        return "High emotional intensity"

@router.get("/sessions/trends")
async def get_trend_analytics(
    session_ids: List[str] = Query(...),
    time_range_hours: int = Query(default=24, ge=1, le=168),
    metrics: List[str] = Query(default=["sentiment", "engagement", "emotion"])
):
    """
    Analyze trends across multiple sessions.
    """
    try:
        store = get_transcript_store()
        
        # Validate sessions
        available_sessions = store.list_sessions()
        missing_sessions = [sid for sid in session_ids if sid not in available_sessions]
        
        if missing_sessions:
            raise HTTPException(
                status_code=404, 
                detail=f"Sessions not found: {missing_sessions}"
            )
        
        # Collect data from all sessions
        session_analytics = {}
        cutoff_time = datetime.now() - timedelta(hours=time_range_hours)
        
        for session_id in session_ids:
            metadata = store.get_session_metadata(session_id)
            
            # Check if session is within time range
            if metadata and 'created_at' in metadata:
                created_at = datetime.fromisoformat(metadata['created_at'].replace('Z', '+00:00'))
                if created_at < cutoff_time:
                    continue
            
            basic_analytics = store.get_analytics(session_id)
            transcript_entries = store.get_session_transcript(session_id)
            
            if transcript_entries:
                # Get emotion analysis if requested
                emotion_analysis = None
                if 'emotion' in metrics or 'sentiment' in metrics:
                    entries_dict = [entry.to_dict() for entry in transcript_entries]
                    emotion_analysis = await analyze_transcript_emotions(entries_dict)
                
                session_analytics[session_id] = {
                    'basic': basic_analytics,
                    'emotion': emotion_analysis,
                    'metadata': metadata,
                    'entry_count': len(transcript_entries)
                }
        
        # Generate trend insights
        trends = analyze_trends(session_analytics, metrics)
        
        return {
            "sessions_analyzed": len(session_analytics),
            "time_range_hours": time_range_hours,
            "requested_metrics": metrics,
            "trends": trends,
            "generated_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trend analytics error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

def analyze_trends(session_analytics: Dict, requested_metrics: List[str]) -> Dict[str, Any]:
    """Analyze trends across session data"""
    trends = {}
    
    if not session_analytics:
        return trends
    
    # Sentiment trends
    if 'sentiment' in requested_metrics:
        sentiment_scores = []
        for session_data in session_analytics.values():
            if session_data['emotion']:
                avg_sentiment = session_data['emotion']['session_summary']['average_sentiment_score']
                sentiment_scores.append(avg_sentiment)
        
        if sentiment_scores:
            trends['sentiment'] = {
                'average_score': sum(sentiment_scores) / len(sentiment_scores),
                'trend_direction': 'improving' if sentiment_scores[-1] > sentiment_scores[0] else 'declining',
                'volatility': max(sentiment_scores) - min(sentiment_scores),
                'session_scores': sentiment_scores
            }
    
    # Engagement trends  
    if 'engagement' in requested_metrics:
        engagement_data = []
        for session_data in session_analytics.values():
            basic = session_data['basic']
            engagement_score = basic.get('avg_words_per_turn', 0) * len(basic.get('speakers', []))
            engagement_data.append(engagement_score)
        
        if engagement_data:
            trends['engagement'] = {
                'average_engagement': sum(engagement_data) / len(engagement_data),
                'trend_direction': 'increasing' if engagement_data[-1] > engagement_data[0] else 'decreasing',
                'peak_engagement': max(engagement_data),
                'session_engagement': engagement_data
            }
    
    # Emotion trends
    if 'emotion' in requested_metrics:
        all_emotions = []
        for session_data in session_analytics.values():
            if session_data['emotion']:
                dominant = session_data['emotion']['session_summary']['dominant_emotion']
                all_emotions.append(dominant)
        
        if all_emotions:
            emotion_distribution = Counter(all_emotions)
            trends['emotion'] = {
                'most_common_emotion': emotion_distribution.most_common(1)[0][0],
                'emotion_distribution': dict(emotion_distribution),
                'emotional_consistency': len(set(all_emotions)) / len(all_emotions) if all_emotions else 1
            }
    
    return trends

@router.get("/session/{session_id}/export")
async def export_session_analytics(
    session_id: str,
    include_raw_data: bool = Query(default=False),
    format_type: str = Query(default="json", regex="^(json|csv)$")
):
    """
    Export comprehensive session analytics data.
    """
    try:
        store = get_transcript_store()
        
        if session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get comprehensive session data
        export_data = store.export_session(session_id)
        
        if include_raw_data:
            # Add detailed analytics
            detailed_analytics = await get_detailed_analytics(session_id)
            export_data['detailed_analytics'] = detailed_analytics.dict()
        
        export_data['export_timestamp'] = datetime.now().isoformat()
        export_data['export_format'] = format_type
        
        if format_type == "csv":
            # Convert to CSV format (simplified)
            return {
                "message": "CSV export not yet implemented",
                "available_formats": ["json"],
                "data": export_data
            }
        
        return export_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export analytics error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")