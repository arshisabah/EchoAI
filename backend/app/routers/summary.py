"""
Updated summary router with real AI-powered summary generation.
Handles various types of summaries using multiple LLM providers.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncio
from collections import defaultdict
import csv
import io

from fastapi import APIRouter, HTTPException, Query, Body, BackgroundTasks
from pydantic import BaseModel, Field

# --- Placeholder for imports ---
# In a real application, these would be your actual service and model implementations.
# For this example to be self-contained, we will create dummy versions.

class SummaryType:
    BRIEF = "brief"
    DETAILED = "detailed"
    BULLET_POINTS = "bullet_points"
    ACTION_ITEMS = "action_items"
    KEY_TOPICS = "key_topics"

class SummaryRequest(BaseModel):
    session_id: str
    summary_type: SummaryType = Field(default="brief")
    max_length: Optional[int] = Field(default=None)
    include_speakers: bool = Field(default=True)
    preferred_provider: Optional[str] = Field(default=None)

class SummaryResponse(BaseModel):
    session_id: str
    summary: str
    summary_type: str
    word_count: int
    model_used: str
    processing_time_ms: int
    confidence_score: Optional[float] = None

class ErrorResponse(BaseModel):
    detail: str

class SuccessResponse(BaseModel):
    message: str

# Dummy services and store for demonstration purposes
class DummyAIService:
    async def generate_summary(self, transcript_text, summary_type, max_words=None):
        word_count = len(transcript_text.split())
        summary_text = f"This is a dummy '{summary_type}' summary for a transcript of {word_count} words."
        if max_words:
            summary_text = " ".join(summary_text.split()[:max_words])
        return SummaryResponse(
            session_id="dummy_session",
            summary=summary_text,
            summary_type=summary_type,
            word_count=len(summary_text.split()),
            model_used="dummy_provider",
            processing_time_ms=150,
            confidence_score=0.95
        )

class DummyReportService:
    def get_available_providers(self):
        return ["openai", "anthropic", "local"]

    def set_primary_provider(self, provider_name):
        if provider_name in self.get_available_providers():
            logger.info(f"Primary provider set to {provider_name}")
            return True
        return False

    async def generate_summary(self, session_id, summary_type, **kwargs):
        return {
            "session_id": session_id,
            "summary": f"Generated '{summary_type}' summary for session {session_id}.",
            "summary_type": summary_type,
            "word_count": 10,
            "model_used": kwargs.get('preferred_provider', 'default_provider'),
            "processing_time_ms": 250.5
        }

    async def generate_advanced_summary(self, session_id, **kwargs):
        return {
            "session_id": session_id,
            "summary": f"Generated advanced summary for session {session_id} with custom instructions.",
            "summary_type": kwargs.get('summary_type', 'brief'),
            "word_count": 25,
            "model_used": 'advanced_provider',
            "processing_time_ms": 450
        }

class DummyTranscriptStore:
    def __init__(self):
        self._sessions = {
            "session_001": [("Speaker A", "Hello everyone, let's start.", datetime.now()), ("Speaker B", "Agreed. The main topic is the Q3 forecast.", datetime.now())],
            "session_002": [("User 1", "I think we should pivot our strategy.", datetime.now()), ("User 2", "Can you elaborate on that?", datetime.now())],
            "session_003": [("Dev", "The bug is in the auth module.", datetime.now()), ("Manager", "What's the ETA for a fix?", datetime.now())],
        }

    def list_sessions(self):
        return list(self._sessions.keys())

    def get_session_transcript(self, session_id):
        class Entry:
            def __init__(self, speaker, text, timestamp):
                self.speaker = speaker
                self.text = text
                self.timestamp = timestamp
        return [Entry(s, t, ts) for s, t, ts in self._sessions.get(session_id, [])]

    def get_full_text(self, session_id, include_speakers=True):
        entries = self.get_session_transcript(session_id)
        if include_speakers:
            return "\n".join([f"{e.speaker}: {e.text}" for e in entries])
        return "\n".join([e.text for e in entries])

    def get_analytics(self, session_id):
        entries = self.get_session_transcript(session_id)
        speakers = list(set([e.speaker for e in entries]))
        word_count = sum(len(e.text.split()) for e in entries)
        return {
            "total_words": word_count,
            "speakers": speakers,
            "session_duration_seconds": 600,
            "overall_sentiment": "positive",
            "sentiment_score": 0.7,
            "speaker_word_counts": {s: word_count / len(speakers) for s in speakers}
        }
    def get_session_metadata(self, session_id):
        return {"created_at": datetime.now().isoformat(), "session_id": session_id}

# Singleton instances for the dummy services
_report_service = DummyReportService()
_ai_summary_service = DummyAIService()
_transcript_store = DummyTranscriptStore()

def get_report_service(): return _report_service
def get_ai_summary_service(): return _ai_summary_service
def get_transcript_store(): return _transcript_store
# --- End of Placeholder section ---


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/summary", tags=["summary"])

class BatchSummaryRequest(BaseModel):
    """Request model for batch summary generation"""
    session_ids: List[str] = Field(..., min_items=1, max_items=10)
    summary_type: SummaryType = Field(default="brief")
    max_length: Optional[int] = Field(default=None, ge=50, le=1000)
    include_speakers: bool = Field(default=True)
    preferred_provider: Optional[str] = Field(default=None)

class ComparativeSummaryRequest(BaseModel):
    """Request model for comparative summary between sessions"""
    session_ids: List[str] = Field(..., min_items=2, max_items=5)
    comparison_aspects: List[str] = Field(default=["topics", "sentiment", "decisions"])
    max_length: Optional[int] = Field(default=300, ge=100, le=1000)

class AdvancedSummaryRequest(BaseModel):
    """Advanced summary request with customization options"""
    session_id: str
    summary_type: SummaryType = Field(default="brief")
    focus_areas: Optional[List[str]] = Field(default=None, description="Specific areas to focus on")
    speaker_perspective: Optional[str] = Field(default=None, description="Summarize from specific speaker's perspective")
    time_range: Optional[Dict[str, Any]] = Field(default=None, description="Time range to summarize")
    custom_prompt: Optional[str] = Field(default=None, description="Custom instructions for summary")
    max_length: Optional[int] = Field(default=None, ge=50, le=2000)
    include_emotions: bool = Field(default=False, description="Include emotional analysis")
    include_decisions: bool = Field(default=True, description="Extract decisions and action items")

class SummaryAnalyticsRequest(BaseModel):
    """Request for summary analytics and insights"""
    session_ids: List[str] = Field(..., min_items=1, max_items=20)
    analytics_types: List[str] = Field(default=["topics", "sentiment", "participation", "decisions"])
    time_grouping: Optional[str] = Field(default=None, description="Group by time periods")

class ScheduledSummaryRequest(BaseModel):
    """Request for scheduled summary generation"""
    session_id: str
    summary_type: SummaryType = Field(default="brief")
    schedule_time: datetime = Field(description="When to generate the summary")
    webhook_url: Optional[str] = Field(default=None, description="URL to send results to")
    email_recipients: Optional[List[str]] = Field(default=None, description="Email addresses for results")

# In-memory store for scheduled summaries (in production, use Redis/database)
scheduled_summaries = {}

@router.post("/generate", response_model=SummaryResponse)
async def generate_summary(request: SummaryRequest):
    """
    Generate AI-powered summary for a transcript session.
    Supports multiple summary types and LLM providers.
    """
    try:
        report_service = get_report_service()
        
        # Validate session exists
        store = get_transcript_store()
        if request.session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Generate summary
        result = await report_service.generate_summary(
            session_id=request.session_id,
            summary_type=request.summary_type,
            max_length=request.max_length,
            include_speakers=request.include_speakers,
            preferred_provider=getattr(request, 'preferred_provider', None)
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=500, 
                detail=f"Summary generation failed: {result['error']}"
            )
        
        return SummaryResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summary generation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/generate/advanced")
async def generate_advanced_summary(request: AdvancedSummaryRequest):
    """
    Generate advanced customized summary with specific focus areas and perspectives.
    """
    try:
        report_service = get_report_service()
        store = get_transcript_store()
        
        # Validate session exists
        if request.session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get transcript data
        transcript_entries = store.get_session_transcript(request.session_id)
        
        # Apply time range filter if specified
        if request.time_range:
            transcript_entries = filter_by_time_range(transcript_entries, request.time_range)
        
        # Apply speaker perspective filter if specified
        if request.speaker_perspective:
            transcript_entries = filter_by_speaker_perspective(
                transcript_entries, request.speaker_perspective
            )
        
        # Build custom prompt based on advanced options
        custom_instructions = build_advanced_prompt(request, transcript_entries)
        
        # Generate advanced summary
        result = await report_service.generate_advanced_summary(
            session_id=request.session_id,
            summary_type=request.summary_type,
            max_length=request.max_length,
            custom_instructions=custom_instructions,
            focus_areas=request.focus_areas,
            include_emotions=request.include_emotions,
            include_decisions=request.include_decisions,
            filtered_entries=transcript_entries
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=500, 
                detail=f"Advanced summary generation failed: {result['error']}"
            )
        
        # Add advanced summary metadata
        result.update({
            "advanced_options": {
                "focus_areas": request.focus_areas,
                "speaker_perspective": request.speaker_perspective,
                "time_range_applied": request.time_range is not None,
                "custom_prompt_used": request.custom_prompt is not None,
                "emotions_included": request.include_emotions,
                "decisions_included": request.include_decisions
            },
            "filtered_entries_count": len(transcript_entries)
        })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Advanced summary generation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/session/{session_id}")
async def get_session_summary(
    session_id: str,
    summary_type: SummaryType = Query(default="brief"),
    max_length: Optional[int] = Query(default=None, ge=50, le=1000),
    include_speakers: bool = Query(default=True),
    preferred_provider: Optional[str] = Query(default=None)
):
    """
    Get summary for a specific session (convenience endpoint).
    """
    request = SummaryRequest(
        session_id=session_id,
        summary_type=summary_type,
        max_length=max_length,
        include_speakers=include_speakers
    )
    
    # Add preferred_provider if specified
    if preferred_provider:
        request.preferred_provider = preferred_provider
    
    return await generate_summary(request)

@router.post("/batch")
async def generate_batch_summaries(request: BatchSummaryRequest):
    """
    Generate summaries for multiple sessions in batch.
    """
    try:
        report_service = get_report_service()
        store = get_transcript_store()
        
        # Validate all sessions exist
        available_sessions = store.list_sessions()
        missing_sessions = [sid for sid in request.session_ids if sid not in available_sessions]
        
        if missing_sessions:
            raise HTTPException(
                status_code=404, 
                detail=f"Sessions not found: {missing_sessions}"
            )
        
        # Generate summaries for all sessions concurrently
        tasks = []
        for session_id in request.session_ids:
            task = report_service.generate_summary(
                session_id=session_id,
                summary_type=request.summary_type,
                max_length=request.max_length,
                include_speakers=request.include_speakers,
                preferred_provider=request.preferred_provider
            )
            tasks.append((session_id, task))
        
        # Wait for all summaries to complete
        results = []
        errors = []
        
        for session_id, task in tasks:
            try:
                result = await task
                if "error" in result:
                    errors.append({
                        "session_id": session_id,
                        "error": result["error"]
                    })
                else:
                    results.append(SummaryResponse(**result))
                    
            except Exception as e:
                logger.error(f"Batch summary error for {session_id}: {e}")
                errors.append({
                    "session_id": session_id,
                    "error": str(e)
                })
        
        return {
            "summaries": results,
            "successful_count": len(results),
            "failed_count": len(errors),
            "errors": errors,
            "generated_at": datetime.now().isoformat(),
            "batch_processing_time_ms": sum(s.processing_time_ms for s in results) if results else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch summary generation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/comparative")
async def generate_comparative_summary(request: ComparativeSummaryRequest):
    """
    Generate comparative summary between multiple sessions.
    Identifies common themes, differences, and patterns.
    """
    try:
        store = get_transcript_store()
        ai_service = get_ai_summary_service()
        
        # Validate sessions exist
        available_sessions = store.list_sessions()
        missing_sessions = [sid for sid in request.session_ids if sid not in available_sessions]
        
        if missing_sessions:
            raise HTTPException(
                status_code=404, 
                detail=f"Sessions not found: {missing_sessions}"
            )
        
        # Collect transcript data from all sessions
        session_data = {}
        total_words = 0
        
        for session_id in request.session_ids:
            transcript_text = store.get_full_text(session_id, include_speakers=True)
            analytics = store.get_analytics(session_id)
            
            session_data[session_id] = {
                "transcript": transcript_text,
                "analytics": analytics,
                "metadata": store.get_session_metadata(session_id)
            }
            total_words += analytics.get('total_words', 0)
        
        # Build comparative analysis prompt
        comparative_text = build_comparative_prompt(session_data, request.comparison_aspects)
        
        # Generate comparative summary
        summary_result = await ai_service.generate_summary(
            transcript_text=comparative_text,
            summary_type="detailed",
            max_words=request.max_length
        )
        
        return {
            "comparative_summary": summary_result.summary,
            "sessions_analyzed": request.session_ids,
            "comparison_aspects": request.comparison_aspects,
            "total_source_words": total_words,
            "summary_word_count": summary_result.word_count,
            "compression_ratio": summary_result.word_count / total_words if total_words > 0 else 0,
            "model_used": summary_result.model_used,
            "processing_time_ms": summary_result.processing_time_ms,
            "generated_at": datetime.now().isoformat(),
            
            # Individual session summaries for reference
            "session_overviews": {
                session_id: {
                    "word_count": data["analytics"].get("total_words", 0),
                    "speakers": data["analytics"].get("speakers", []),
                    "duration": data["analytics"].get("session_duration_seconds", 0)
                }
                for session_id, data in session_data.items()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comparative summary error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/analytics")
async def generate_summary_analytics(request: SummaryAnalyticsRequest):
    """
    Generate analytics and insights across multiple sessions.
    """
    try:
        store = get_transcript_store()
        
        # Validate sessions exist
        available_sessions = store.list_sessions()
        missing_sessions = [sid for sid in request.session_ids if sid not in available_sessions]
        
        if missing_sessions:
            raise HTTPException(
                status_code=404, 
                detail=f"Sessions not found: {missing_sessions}"
            )
        
        analytics_results = {}
        
        # Topic analysis
        if "topics" in request.analytics_types:
            analytics_results["topic_analysis"] = await analyze_topics_across_sessions(
                request.session_ids, store
            )
        
        # Sentiment analysis
        if "sentiment" in request.analytics_types:
            analytics_results["sentiment_analysis"] = await analyze_sentiment_across_sessions(
                request.session_ids, store
            )
        
        # Participation analysis
        if "participation" in request.analytics_types:
            analytics_results["participation_analysis"] = analyze_participation_across_sessions(
                request.session_ids, store
            )
        
        # Decision analysis
        if "decisions" in request.analytics_types:
            analytics_results["decision_analysis"] = await analyze_decisions_across_sessions(
                request.session_ids, store
            )
        
        # Time-based grouping if requested
        if request.time_grouping:
            analytics_results["time_grouped_analysis"] = group_analytics_by_time(
                analytics_results, request.session_ids, store, request.time_grouping
            )
        
        return {
            "analytics": analytics_results,
            "sessions_analyzed": request.session_ids,
            "analytics_types": request.analytics_types,
            "generated_at": datetime.now().isoformat(),
            "summary": generate_analytics_summary(analytics_results)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summary analytics error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/schedule")
async def schedule_summary(request: ScheduledSummaryRequest, background_tasks: BackgroundTasks):
    """
    Schedule a summary to be generated at a specific time.
    """
    try:
        store = get_transcript_store()
        
        # Validate session exists
        if request.session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Check if schedule time is in the future
        if request.schedule_time <= datetime.now():
            raise HTTPException(
                status_code=400, 
                detail="Schedule time must be in the future"
            )
        
        # Generate unique ID for scheduled task
        task_id = f"summary_{request.session_id}_{int(request.schedule_time.timestamp())}"
        
        # Store scheduled task
        scheduled_summaries[task_id] = {
            "request": request,
            "status": "scheduled",
            "created_at": datetime.now()
        }
        
        # Add background task
        delay_seconds = (request.schedule_time - datetime.now()).total_seconds()
        background_tasks.add_task(
            execute_scheduled_summary,
            task_id,
            request,
            delay_seconds
        )
        
        return {
            "task_id": task_id,
            "status": "scheduled",
            "schedule_time": request.schedule_time.isoformat(),
            "session_id": request.session_id,
            "summary_type": request.summary_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Schedule summary error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/schedule/{task_id}")
async def get_scheduled_summary_status(task_id: str):
    """
    Get status of a scheduled summary task.
    """
    if task_id not in scheduled_summaries:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    
    task_info = scheduled_summaries[task_id]
    
    return {
        "task_id": task_id,
        "status": task_info["status"],
        "created_at": task_info["created_at"].isoformat(),
        "schedule_time": task_info["request"].schedule_time.isoformat(),
        "session_id": task_info["request"].session_id,
        "result": task_info.get("result"),
        "error": task_info.get("error")
    }

@router.delete("/schedule/{task_id}")
async def cancel_scheduled_summary(task_id: str):
    """
    Cancel a scheduled summary task.
    """
    if task_id not in scheduled_summaries:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    
    task_info = scheduled_summaries[task_id]
    
    if task_info["status"] in ["completed", "failed"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel task with status: {task_info['status']}"
        )
    
    # Mark as cancelled
    scheduled_summaries[task_id]["status"] = "cancelled"
    scheduled_summaries[task_id]["cancelled_at"] = datetime.now()
    
    return SuccessResponse(message=f"Scheduled task {task_id} cancelled")

def build_comparative_prompt(session_data: dict, comparison_aspects: List[str]) -> str:
    """
    Build prompt for comparative analysis between sessions.
    """
    prompt_parts = [
        "COMPARATIVE ANALYSIS REQUEST:",
        f"Please analyze and compare the following {len(session_data)} conversation sessions.",
        f"Focus on these aspects: {', '.join(comparison_aspects)}",
        "",
        "Sessions to compare:",
        ""
    ]
    
    for session_id, data in session_data.items():
        analytics = data["analytics"]
        metadata = data.get("metadata", {})
        
        prompt_parts.extend([
            f"=== SESSION {session_id} ===",
            f"Duration: {analytics.get('session_duration_seconds', 0):.1f} seconds",
            f"Speakers: {', '.join(analytics.get('speakers', []))}",
            f"Total words: {analytics.get('total_words', 0)}",
            f"Created: {metadata.get('created_at', 'Unknown')}",
            "",
            "Transcript:",
            data["transcript"][:2000] + "..." if len(data["transcript"]) > 2000 else data["transcript"],
            "",
            "=" * 50,
            ""
        ])
    
    prompt_parts.extend([
        "ANALYSIS INSTRUCTIONS:",
        "1. Compare the sessions across the requested aspects",
        "2. Identify common themes and key differences",
        "3. Highlight significant patterns or insights",
        "4. Provide actionable conclusions where applicable",
        "5. Structure the response clearly with sections for each comparison aspect"
    ])
    
    return "\n".join(prompt_parts)

def build_advanced_prompt(request: AdvancedSummaryRequest, transcript_entries: List) -> str:
    """
    Build custom prompt for advanced summary generation.
    """
    prompt_parts = ["ADVANCED SUMMARY REQUEST:"]
    
    if request.focus_areas:
        prompt_parts.append(f"Focus specifically on: {', '.join(request.focus_areas)}")
    
    if request.speaker_perspective:
        prompt_parts.append(f"Summarize from {request.speaker_perspective}'s perspective")
    
    if request.include_emotions:
        prompt_parts.append("Include emotional context and sentiment analysis")
    
    if request.include_decisions:
        prompt_parts.append("Extract and highlight all decisions made and action items")
    
    if request.custom_prompt:
        prompt_parts.extend(["", "CUSTOM INSTRUCTIONS:", request.custom_prompt])
    
    prompt_parts.extend([
        "",
        f"Generate a {request.summary_type} summary with the above requirements."
    ])
    
    return "\n".join(prompt_parts)

def filter_by_time_range(transcript_entries: List, time_range: Dict[str, Any]) -> List:
    """
    Filter transcript entries by time range.
    """
    filtered_entries = []
    
    start_time = time_range.get('start_time')
    end_time = time_range.get('end_time')
    
    for entry in transcript_entries:
        entry_time = getattr(entry, 'timestamp', None)
        if entry_time is None:
            continue
            
        if start_time and entry_time < start_time:
            continue
        if end_time and entry_time > end_time:
            continue
            
        filtered_entries.append(entry)
    
    return filtered_entries

def filter_by_speaker_perspective(transcript_entries: List, speaker: str) -> List:
    """
    Filter to include entries relevant to a specific speaker's perspective.
    """
    # Include the speaker's own words plus responses/mentions
    relevant_entries = []
    
    for entry in transcript_entries:
        # Include speaker's own statements
        if getattr(entry, 'speaker', '') == speaker:
            relevant_entries.append(entry)
        # Include entries that mention the speaker
        elif speaker.lower() in entry.text.lower():
            relevant_entries.append(entry)
    
    return relevant_entries

async def analyze_topics_across_sessions(session_ids: List[str], store) -> Dict[str, Any]:
    """
    Analyze common topics across multiple sessions.
    """
    ai_service = get_ai_summary_service()
    
    all_transcripts = []
    for session_id in session_ids:
        transcript = store.get_full_text(session_id, include_speakers=False)
        all_transcripts.append(transcript)
    
    # Use AI to extract and categorize topics
    topics_prompt = f"""
    Analyze the following {len(all_transcripts)} conversation transcripts and identify:
    1. Common topics discussed across sessions
    2. Unique topics per session
    3. Topic frequency and importance
    4. Topic evolution patterns
    
    Transcripts:
    {' ### NEXT SESSION ### '.join(all_transcripts[:5000] for all_transcripts in all_transcripts)}
    """
    
    result = await ai_service.generate_summary(
        transcript_text=topics_prompt,
        summary_type="detailed",
        max_words=500
    )
    
    return {
        "topic_summary": result.summary,
        "sessions_analyzed": len(session_ids),
        "analysis_type": "cross_session_topics"
    }

async def analyze_sentiment_across_sessions(session_ids: List[str], store) -> Dict[str, Any]:
    """
    Analyze sentiment patterns across multiple sessions.
    """
    sentiment_data = {}
    
    for session_id in session_ids:
        analytics = store.get_analytics(session_id)
        sentiment_data[session_id] = {
            "overall_sentiment": analytics.get("overall_sentiment", "neutral"),
            "sentiment_score": analytics.get("sentiment_score", 0.0),
            "emotional_intensity": analytics.get("emotional_intensity", 0.0)
        }
    
    # Calculate aggregate metrics
    avg_sentiment = sum(data["sentiment_score"] for data in sentiment_data.values()) / len(sentiment_data)
    avg_intensity = sum(data["emotional_intensity"] for data in sentiment_data.values()) / len(sentiment_data)
    
    return {
        "session_sentiments": sentiment_data,
        "average_sentiment_score": avg_sentiment,
        "average_emotional_intensity": avg_intensity,
        "sentiment_trend": "positive" if avg_sentiment > 0.1 else "negative" if avg_sentiment < -0.1 else "neutral"
    }

def analyze_participation_across_sessions(session_ids: List[str], store) -> Dict[str, Any]:
    """
    Analyze speaker participation patterns across sessions.
    """
    speaker_stats = defaultdict(lambda: {
        "sessions_participated": 0,
        "total_words": 0,
        "avg_words_per_session": 0,
        "participation_percentage": 0
    })
    
    total_sessions = len(session_ids)
    
    for session_id in session_ids:
        analytics = store.get_analytics(session_id)
        speaker_word_counts = analytics.get("speaker_word_counts", {})
        total_words_in_session = sum(speaker_word_counts.values())
        
        for speaker, word_count in speaker_word_counts.items():
            speaker_stats[speaker]["sessions_participated"] += 1
            speaker_stats[speaker]["total_words"] += word_count
            
            if total_words_in_session > 0:
                speaker_stats[speaker]["participation_percentage"] += (word_count / total_words_in_session * 100)
    
    # Calculate averages
    for speaker, stats in speaker_stats.items():
        if stats["sessions_participated"] > 0:
            stats["avg_words_per_session"] = stats["total_words"] / stats["sessions_participated"]
            stats["participation_percentage"] = stats["participation_percentage"] / stats["sessions_participated"]
    
    return {
        "speaker_statistics": dict(speaker_stats),
        "most_active_speaker": max(speaker_stats.items(), key=lambda x: x[1]["total_words"])[0] if speaker_stats else None,
        "total_sessions_analyzed": total_sessions
    }

async def analyze_decisions_across_sessions(session_ids: List[str], store) -> Dict[str, Any]:
    """
    Extract and analyze decisions made across multiple sessions.
    """
    ai_service = get_ai_summary_service()
    
    decisions_prompt = f"""
    Analyze the following conversation sessions and extract:
    1. All decisions made
    2. Action items assigned
    3. Commitments and agreements
    4. Unresolved issues
    
    For each session, identify decision-making patterns and outcomes.
    """
    
    session_decisions = {}
    
    for session_id in session_ids:
        transcript = store.get_full_text(session_id, include_speakers=True)
        
        session_prompt = f"{decisions_prompt}\n\nSession {session_id}:\n{transcript[:3000]}"
        
        result = await ai_service.generate_summary(
            transcript_text=session_prompt,
            summary_type="bullet_points",
            max_words=200
        )
        
        session_decisions[session_id] = result.summary
    
    return {
        "session_decisions": session_decisions,
        "sessions_analyzed": len(session_ids)
    }

def group_analytics_by_time(analytics_results: Dict, session_ids: List[str], store, grouping: str) -> Dict[str, Any]:
    """
    Group analytics results by time periods.
    """
    time_groups = defaultdict(list)
    
    for session_id in session_ids:
        metadata = store.get_session_metadata(session_id)
        created_at = metadata.get("created_at", datetime.now())
        
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        # Group by different time periods
        if grouping == "daily":
            group_key = created_at.strftime("%Y-%m-%d")
        elif grouping == "weekly":
            week_start = created_at - timedelta(days=created_at.weekday())
            group_key = week_start.strftime("%Y-W%U")
        elif grouping == "monthly":
            group_key = created_at.strftime("%Y-%m")
        else:
            group_key = "all"
        
        time_groups[group_key].append(session_id)
    
    return {
        "groups": dict(time_groups),
        "grouping_method": grouping,
        "total_groups": len(time_groups)
    }

def generate_analytics_summary(analytics_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a high-level summary of analytics results.
    """
    summary = {}
    
    if "topic_analysis" in analytics_results:
        summary["topics"] = "Cross-session topic analysis completed"
    
    if "sentiment_analysis" in analytics_results:
        sentiment_data = analytics_results["sentiment_analysis"]
        trend = sentiment_data.get("sentiment_trend", "neutral")
        summary["sentiment"] = f"Overall sentiment trend: {trend}"
    
    if "participation_analysis" in analytics_results:
        participation_data = analytics_results["participation_analysis"]
        most_active = participation_data.get("most_active_speaker")
        summary["participation"] = f"Most active participant: {most_active}" if most_active else "Participation analysis completed"
    
    if "decision_analysis" in analytics_results:
        summary["decisions"] = "Decision and action item extraction completed"
    
    return summary

async def execute_scheduled_summary(task_id: str, request: ScheduledSummaryRequest, delay_seconds: float):
    """
    Execute a scheduled summary generation.
    """
    # Wait for the scheduled time
    await asyncio.sleep(delay_seconds)
    
    if task_id not in scheduled_summaries:
        return  # Task was cancelled
    
    if scheduled_summaries[task_id]["status"] == "cancelled":
        return
    
    # Update status
    scheduled_summaries[task_id]["status"] = "processing"
    
    try:
        # Generate the summary
        report_service = get_report_service()
        
        result = await report_service.generate_summary(
            session_id=request.session_id,
            summary_type=request.summary_type,
            max_length=None,
            include_speakers=True,
            preferred_provider=None
        )
        
        # Update with results
        scheduled_summaries[task_id]["status"] = "completed"
        scheduled_summaries[task_id]["result"] = result
        scheduled_summaries[task_id]["completed_at"] = datetime.now()
        
        # Send to webhook if provided
        if request.webhook_url:
            await send_webhook_notification(request.webhook_url, result)
        
        # Send email if provided
        if request.email_recipients:
            await send_email_notification(request.email_recipients, result)
        
    except Exception as e:
        logger.error(f"Scheduled summary execution error for {task_id}: {e}")
        scheduled_summaries[task_id]["status"] = "failed"
        scheduled_summaries[task_id]["error"] = str(e)
        scheduled_summaries[task_id]["failed_at"] = datetime.now()

async def send_webhook_notification(webhook_url: str, result: Dict[str, Any]):
    """
    Send summary results to webhook URL.
    """
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=result) as response:
                if response.status != 200:
                    logger.warning(f"Webhook notification failed: {response.status}")
    except Exception as e:
        logger.error(f"Webhook notification error: {e}")

async def send_email_notification(recipients: List[str], result: Dict[str, Any]):
    """
    Send summary results via email.
    """
    # Implementation depends on your email service
    # This is a placeholder for email functionality
    logger.info(f"Email notification sent to {len(recipients)} recipients")
    pass

@router.get("/types")
async def get_summary_types():
    """Get available summary types and their descriptions"""
    return {
        "summary_types": {
            "brief": "Concise overview of main points and outcomes",
            "detailed": "Comprehensive summary with all major topics and context",
            "bullet_points": "Key points organized as bullet list",
            "action_items": "Specific tasks and next steps extracted from conversation",
            "key_topics": "Major themes and subjects discussed, grouped logically"
        },
        "default_type": "brief",
        "supported_formats": ["text", "structured"]
    }

@router.get("/providers")
async def get_summary_providers():
    """Get available AI summary providers"""
    try:
        report_service = get_report_service()
        providers = report_service.get_available_providers()
        
        return {
            "available_providers": providers,
            "provider_info": {
                "openai": {
                    "name": "OpenAI GPT",
                    "description": "High-quality summaries using GPT models",
                    "strengths": ["Natural language", "Context understanding", "Multiple formats"]
                },
                "anthropic": {
                    "name": "Anthropic Claude",
                    "description": "Thoughtful analysis with Claude models",
                    "strengths": ["Detailed analysis", "Safety", "Reasoning"]
                },
                "local": {
                    "name": "Local Transformer",
                    "description": "Privacy-focused local processing",
                    "strengths": ["Privacy", "No API costs", "Offline capable"]
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting summary providers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/providers/{provider_name}")
async def set_primary_summary_provider(provider_name: str):
    """Set the primary summary provider"""
    try:
        report_service = get_report_service()
        success = report_service.set_primary_provider(provider_name)
        
        if success:
            return SuccessResponse(
                message=f"Primary summary provider set to {provider_name}"
            )
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Provider {provider_name} not available"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting summary provider: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/session/{session_id}/preview")
async def get_summary_preview(
    session_id: str,
    max_words: int = Query(default=50, ge=20, le=100)
):
    """
    Get a quick preview/snippet of what the summary would contain.
    Useful for UI previews before generating full summaries.
    """
    try:
        store = get_transcript_store()
        
        if session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get basic session info
        transcript_entries = store.get_session_transcript(session_id)
        analytics = store.get_analytics(session_id)
        
        if not transcript_entries:
            return {
                "preview": "No transcript content available for preview",
                "session_id": session_id,
                "entry_count": 0
            }
        
        # Create a brief preview from first and last few entries
        preview_entries = []
        if len(transcript_entries) <= 6:
            preview_entries = transcript_entries
        else:
            preview_entries = transcript_entries[:3] + transcript_entries[-3:]
        
        preview_text = " ... ".join([entry.text for entry in preview_entries])
        
        # Truncate to word limit
        words = preview_text.split()
        if len(words) > max_words:
            preview_text = " ".join(words[:max_words]) + "..."
        
        return {
            "preview": preview_text,
            "session_id": session_id,
            "entry_count": len(transcript_entries),
            "total_words": analytics.get('total_words', 0),
            "speakers": analytics.get('speakers', []),
            "duration_seconds": analytics.get('session_duration_seconds', 0),
            "estimated_summary_length": {
                "brief": min(analytics.get('total_words', 0) // 10, 150),
                "detailed": min(analytics.get('total_words', 0) // 5, 400),
                "bullet_points": min(analytics.get('total_words', 0) // 8, 200)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting summary preview for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/session/{session_id}/history")
async def get_session_summary_history(session_id: str):
    """
    Get history of summaries generated for a session.
    """
    try:
        store = get_transcript_store()
        
        if session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get summary history from store (implement this method in your store)
        history = store.get_summary_history(session_id) if hasattr(store, 'get_summary_history') else []
        
        return {
            "session_id": session_id,
            "summary_history": history,
            "total_summaries": len(history)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting summary history for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/session/{session_id}/summaries")
async def delete_session_summaries(session_id: str):
    """
    Delete all summaries for a session.
    """
    try:
        store = get_transcript_store()
        
        if session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Delete summaries (implement this method in your store)
        if hasattr(store, 'delete_summaries'):
            deleted_count = store.delete_summaries(session_id)
        else:
            deleted_count = 0
        
        return SuccessResponse(
            message=f"Deleted {deleted_count} summaries for session {session_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting summaries for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/templates")
async def get_summary_templates():
    """
    Get available summary templates for different use cases.
    """
    return {
        "templates": {
            "meeting": {
                "name": "Meeting Summary",
                "description": "Standard meeting summary with agenda, decisions, and action items",
                "focus_areas": ["agenda_items", "decisions", "action_items", "next_steps"],
                "summary_type": "detailed",
                "include_speakers": True,
                "include_decisions": True
            },
            "interview": {
                "name": "Interview Summary",
                "description": "Interview summary focusing on responses and insights",
                "focus_areas": ["key_responses", "insights", "qualifications", "concerns"],
                "summary_type": "detailed",
                "include_speakers": True,
                "include_emotions": True
            },
            "brainstorm": {
                "name": "Brainstorming Summary",
                "description": "Creative session summary with ideas and concepts",
                "focus_areas": ["ideas", "concepts", "creativity", "innovation"],
                "summary_type": "bullet_points",
                "include_speakers": False,
                "include_decisions": False
            },
            "training": {
                "name": "Training Summary",
                "description": "Training session summary with key learnings",
                "focus_areas": ["learning_objectives", "key_concepts", "questions", "understanding"],
                "summary_type": "detailed",
                "include_speakers": True,
                "include_emotions": False
            },
            "customer_call": {
                "name": "Customer Call Summary",
                "description": "Customer interaction summary with requirements and follow-up",
                "focus_areas": ["customer_needs", "requirements", "concerns", "follow_up"],
                "summary_type": "detailed",
                "include_speakers": True,
                "include_decisions": True
            }
        }
    }

@router.post("/template/{template_name}")
async def generate_template_summary(
    template_name: str,
    session_id: str = Body(...),
    custom_focus: Optional[List[str]] = Body(default=None)
):
    """
    Generate summary using a predefined template.
    """
    try:
        # Get template configuration
        templates_response = await get_summary_templates()
        templates = templates_response["templates"]
        
        if template_name not in templates:
            raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")
        
        template = templates[template_name]
        
        # Build advanced summary request from template
        request = AdvancedSummaryRequest(
            session_id=session_id,
            summary_type=template["summary_type"],
            focus_areas=custom_focus or template["focus_areas"],
            include_emotions=template.get("include_emotions", False),
            include_decisions=template.get("include_decisions", True),
            custom_prompt=f"Generate a {template['name'].lower()} following this description: {template['description']}"
        )
        
        # Generate the summary
        result = await generate_advanced_summary(request)
        
        # Add template metadata
        result["template_used"] = {
            "name": template_name,
            "description": template["description"],
            "focus_areas": request.focus_areas
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Template summary generation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/export")
async def export_summaries(
    session_ids: List[str] = Body(..., min_items=1, max_items=50),
    export_format: str = Body(default="json", pattern="^(json|csv|pdf|markdown)$"),
    include_metadata: bool = Body(default=True),
    summary_type: SummaryType = Body(default="brief")
):
    """
    Export summaries for multiple sessions in various formats.
    """
    try:
        store = get_transcript_store()
        report_service = get_report_service()
        
        # Validate sessions exist
        available_sessions = store.list_sessions()
        missing_sessions = [sid for sid in session_ids if sid not in available_sessions]
        
        if missing_sessions:
            raise HTTPException(
                status_code=404, 
                detail=f"Sessions not found: {missing_sessions}"
            )
        
        # Generate summaries for all sessions
        export_data = []
        
        for session_id in session_ids:
            try:
                # Generate summary
                summary_result = await report_service.generate_summary(
                    session_id=session_id,
                    summary_type=summary_type,
                    include_speakers=True
                )
                
                export_entry = {
                    "session_id": session_id,
                    "summary": summary_result.get("summary", ""),
                    "summary_type": summary_type,
                    "generated_at": datetime.now().isoformat()
                }
                
                if include_metadata:
                    analytics = store.get_analytics(session_id)
                    metadata = store.get_session_metadata(session_id)
                    
                    export_entry.update({
                        "metadata": metadata,
                        "analytics": {
                            "total_words": analytics.get("total_words", 0),
                            "speakers": analytics.get("speakers", []),
                            "duration_seconds": analytics.get("session_duration_seconds", 0)
                        },
                        "processing_time_ms": summary_result.get("processing_time_ms", 0),
                        "model_used": summary_result.get("model_used", "unknown")
                    })
                
                export_data.append(export_entry)
                
            except Exception as e:
                logger.error(f"Export error for session {session_id}: {e}")
                export_data.append({
                    "session_id": session_id,
                    "error": str(e),
                    "generated_at": datetime.now().isoformat()
                })
        
        # Format the export data based on requested format
        if export_format == "json":
            return {
                "export_format": "json",
                "exported_at": datetime.now().isoformat(),
                "sessions_count": len(session_ids),
                "data": export_data
            }
        
        elif export_format == "csv":
            output = io.StringIO()
            if export_data:
                # Dynamically get fieldnames from the first non-error row
                first_data_row = next((row for row in export_data if "error" not in row), None)
                if first_data_row:
                    fieldnames = flatten_dict(first_data_row).keys()
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for row in export_data:
                        flat_row = flatten_dict(row)
                        # Ensure all keys are present, fill with empty string if not
                        filtered_row = {key: flat_row.get(key, "") for key in fieldnames}
                        writer.writerow(filtered_row)
            
            csv_content = output.getvalue()
            output.close()
            
            return {
                "export_format": "csv",
                "exported_at": datetime.now().isoformat(),
                "sessions_count": len(session_ids),
                "content": csv_content
            }
        
        elif export_format == "markdown":
            markdown_content = generate_markdown_export(export_data)
            
            return {
                "export_format": "markdown",
                "exported_at": datetime.now().isoformat(),
                "sessions_count": len(session_ids),
                "content": markdown_content
            }
        
        elif export_format == "pdf":
            # PDF generation would require additional dependencies
            # This is a placeholder implementation
            return {
                "export_format": "pdf",
                "exported_at": datetime.now().isoformat(),
                "sessions_count": len(session_ids),
                "message": "PDF export not yet implemented",
                "data": export_data
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/health")
async def check_summary_health():
    """
    Check health of summary services and providers.
    """
    try:
        report_service = get_report_service()
        ai_service = get_ai_summary_service()
        
        # Check provider availability
        providers = report_service.get_available_providers()
        provider_status = {}
        
        for provider in providers:
            try:
                # Test with a simple summary request
                test_result = await ai_service.generate_summary(
                    transcript_text="This is a test message.",
                    summary_type="brief",
                    max_words=20
                )
                provider_status[provider] = {
                    "status": "healthy",
                    "response_time_ms": test_result.processing_time_ms
                }
            except Exception as e:
                provider_status[provider] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        # Check scheduled tasks
        active_scheduled = len([
            task for task in scheduled_summaries.values() 
            if task["status"] in ["scheduled", "processing"]
        ])
        
        overall_status = "healthy" if any(
            status["status"] == "healthy" for status in provider_status.values()
        ) else "degraded"
        
        return {
            "overall_status": overall_status,
            "providers": provider_status,
            "scheduled_summaries": {
                "active": active_scheduled,
                "total": len(scheduled_summaries)
            },
            "checked_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "overall_status": "unhealthy",
            "error": str(e),
            "checked_at": datetime.now().isoformat()
        }

def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
    """
    Flatten nested dictionary for CSV export.
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            items.append((new_key, ', '.join(map(str, v))))
        else:
            items.append((new_key, v))
    return dict(items)

def generate_markdown_export(export_data: List[Dict[str, Any]]) -> str:
    """
    Generate markdown format export.
    """
    markdown_lines = [
        "# Summary Export Report",
        f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Sessions: {len(export_data)}",
        "",
        "---",
        ""
    ]
    
    for i, entry in enumerate(export_data, 1):
        session_id = entry.get("session_id", "Unknown")
        summary = entry.get("summary", "No summary available")
        
        markdown_lines.extend([
            f"## Session {i}: {session_id}",
            "",
            f"**Summary Type:** {entry.get('summary_type', 'Unknown')}",
            f"**Generated At:** {entry.get('generated_at', 'Unknown')}",
            ""
        ])
        
        if "error" in entry:
            markdown_lines.extend([
                f"**Error:** {entry['error']}",
                ""
            ])
        else:
            markdown_lines.extend([
                "### Summary",
                summary,
                ""
            ])
            
            if "analytics" in entry:
                analytics = entry["analytics"]
                markdown_lines.extend([
                    "### Session Analytics",
                    f"- **Duration:** {analytics.get('duration_seconds', 0):.1f} seconds",
                    f"- **Total Words:** {analytics.get('total_words', 0)}",
                    f"- **Speakers:** {', '.join(analytics.get('speakers', []))}",
                    ""
                ])
        
        markdown_lines.extend(["---", ""])
    
    return "\n".join(markdown_lines)

# Additional utility endpoints for debugging and monitoring
@router.get("/debug/scheduled")
async def debug_scheduled_summaries():
    """
    Debug endpoint to view all scheduled summaries.
    """
    return {
        "scheduled_summaries": {
            task_id: {
                **task_info,
                "created_at": task_info["created_at"].isoformat(),
                "request": {
                    "session_id": task_info["request"].session_id,
                    "summary_type": task_info["request"].summary_type,
                    "schedule_time": task_info["request"].schedule_time.isoformat()
                }
            }
            for task_id, task_info in scheduled_summaries.items()
        },
        "total_scheduled": len(scheduled_summaries)
    }

@router.post("/debug/clear-scheduled")
async def clear_all_scheduled_summaries():
    """
    Clear all scheduled summaries (debug/admin endpoint).
    """
    cleared_count = len(scheduled_summaries)
    scheduled_summaries.clear()
    
    return SuccessResponse(
        message=f"Cleared {cleared_count} scheduled summaries"
    )

@router.get("/stats")
async def get_summary_statistics():
    """
    Get comprehensive statistics about summary usage and performance.
    """
    try:
        store = get_transcript_store()
        
        # Get all sessions for statistics
        all_sessions = store.list_sessions()
        
        # Calculate basic statistics
        total_sessions = len(all_sessions)
        sessions_with_summaries = 0
        total_summary_count = 0
        
        # Summary type distribution
        summary_type_stats = defaultdict(int)
        
        # Provider usage statistics  
        provider_usage_stats = defaultdict(int)
        
        # Processing time statistics
        processing_times = []
        
        for session_id in all_sessions:
            if hasattr(store, 'get_summary_history'):
                session_summaries = store.get_summary_history(session_id)
                if session_summaries:
                    sessions_with_summaries += 1
                    total_summary_count += len(session_summaries)
                    
                    for summary in session_summaries:
                        summary_type_stats[summary.get('summary_type', 'unknown')] += 1
                        provider_usage_stats[summary.get('model_used', 'unknown')] += 1
                        
                        if 'processing_time_ms' in summary:
                            processing_times.append(summary['processing_time_ms'])
        
        # Calculate performance metrics
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        min_processing_time = min(processing_times) if processing_times else 0
        max_processing_time = max(processing_times) if processing_times else 0
        
        # Scheduled summary statistics
        scheduled_stats = {
            "total_scheduled": len(scheduled_summaries),
            "pending": len([t for t in scheduled_summaries.values() if t["status"] == "scheduled"]),
            "processing": len([t for t in scheduled_summaries.values() if t["status"] == "processing"]),
            "completed": len([t for t in scheduled_summaries.values() if t["status"] == "completed"]),
            "failed": len([t for t in scheduled_summaries.values() if t["status"] == "failed"]),
            "cancelled": len([t for t in scheduled_summaries.values() if t["status"] == "cancelled"])
        }
        
        return {
            "summary_statistics": {
                "total_sessions": total_sessions,
                "sessions_with_summaries": sessions_with_summaries,
                "total_summaries_generated": total_summary_count,
                "average_summaries_per_session": total_summary_count / sessions_with_summaries if sessions_with_summaries > 0 else 0,
                "summary_coverage_percentage": (sessions_with_summaries / total_sessions * 100) if total_sessions > 0 else 0
            },
            "summary_type_distribution": dict(summary_type_stats),
            "provider_usage": dict(provider_usage_stats),
            "performance_metrics": {
                "average_processing_time_ms": avg_processing_time,
                "min_processing_time_ms": min_processing_time,
                "max_processing_time_ms": max_processing_time,
                "total_samples": len(processing_times)
            },
            "scheduled_summaries": scheduled_stats,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating summary statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/regenerate/{session_id}")
async def regenerate_summary(
    session_id: str,
    summary_type: SummaryType = Body(default="brief"),
    force_new_analysis: bool = Body(default=False),
    preferred_provider: Optional[str] = Body(default=None)
):
    """
    Regenerate summary for a session, optionally with different parameters.
    """
    try:
        store = get_transcript_store()
        
        if session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        report_service = get_report_service()
        
        # Clear any cached summaries if force_new_analysis is True
        if force_new_analysis and hasattr(store, 'clear_summary_cache'):
            store.clear_summary_cache(session_id)
        
        # Generate new summary
        result = await report_service.generate_summary(
            session_id=session_id,
            summary_type=summary_type,
            include_speakers=True,
            preferred_provider=preferred_provider
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=500, 
                detail=f"Summary regeneration failed: {result['error']}"
            )
        
        # Add regeneration metadata
        result["regeneration_info"] = {
            "regenerated_at": datetime.now().isoformat(),
            "forced_new_analysis": force_new_analysis,
            "provider_used": preferred_provider or "default"
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summary regeneration error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/compare-versions")
async def compare_summary_versions(
    session_id: str = Body(...),
    summary_types: List[SummaryType] = Body(..., min_items=2, max_items=5),
    providers: Optional[List[str]] = Body(default=None)
):
    """
    Generate multiple summary versions for comparison.
    """
    try:
        store = get_transcript_store()
        
        if session_id not in store.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        
        report_service = get_report_service()
        available_providers = providers or report_service.get_available_providers()
        
        # Generate summaries with different types and providers
        comparison_results = []
        
        for summary_type in summary_types:
            for provider in available_providers[:2]:  # Limit to 2 providers to avoid excessive calls
                try:
                    result = await report_service.generate_summary(
                        session_id=session_id,
                        summary_type=summary_type,
                        include_speakers=True,
                        preferred_provider=provider
                    )
                    
                    if "error" not in result:
                        comparison_results.append({
                            "summary_type": summary_type,
                            "provider": provider,
                            "summary": result.get("summary", ""),
                            "word_count": result.get("word_count", 0),
                            "processing_time_ms": result.get("processing_time_ms", 0),
                            "confidence_score": result.get("confidence_score", 0.0)
                        })
                        
                except Exception as e:
                    logger.error(f"Comparison error for {summary_type} with {provider}: {e}")
                    comparison_results.append({
                        "summary_type": summary_type,
                        "provider": provider,
                        "error": str(e)
                    })
        
        # Generate comparison analysis
        comparison_analysis = analyze_summary_differences(comparison_results)
        
        return {
            "session_id": session_id,
            "comparison_results": comparison_results,
            "analysis": comparison_analysis,
            "generated_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summary comparison error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

def analyze_summary_differences(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze differences between summary versions.
    """
    successful_results = [r for r in results if "error" not in r]
    
    if len(successful_results) < 2:
        return {"error": "Insufficient successful results for comparison"}
    
    # Word count analysis
    word_counts = [r["word_count"] for r in successful_results]
    
    # Processing time analysis
    processing_times = [r["processing_time_ms"] for r in successful_results]
    
    # Summary type distribution
    type_distribution = defaultdict(int)
    provider_distribution = defaultdict(int)
    
    for result in successful_results:
        type_distribution[result["summary_type"]] += 1
        provider_distribution[result["provider"]] += 1
    
    return {
        "total_versions": len(successful_results),
        "word_count_stats": {
            "min": min(word_counts),
            "max": max(word_counts),
            "average": sum(word_counts) / len(word_counts),
            "range": max(word_counts) - min(word_counts)
        },
        "processing_time_stats": {
            "min": min(processing_times),
            "max": max(processing_times),
            "average": sum(processing_times) / len(processing_times),
            "fastest_provider": successful_results[processing_times.index(min(processing_times))]["provider"],
            "slowest_provider": successful_results[processing_times.index(max(processing_times))]["provider"]
        },
        "type_distribution": dict(type_distribution),
        "provider_distribution": dict(provider_distribution),
        "recommendations": generate_comparison_recommendations(successful_results)
    }

def generate_comparison_recommendations(results: List[Dict[str, Any]]) -> List[str]:
    """
    Generate recommendations based on summary comparison.
    """
    recommendations = []
    
    # Find fastest provider
    fastest = min(results, key=lambda x: x["processing_time_ms"])
    recommendations.append(f"Fastest processing: {fastest['provider']} ({fastest['processing_time_ms']:.1f}ms)")
    
    # Find most comprehensive (highest word count)
    most_detailed = max(results, key=lambda x: x["word_count"])
    recommendations.append(f"Most detailed: {most_detailed['summary_type']} type with {most_detailed['provider']} ({most_detailed['word_count']} words)")
    
    # Processing time vs quality trade-off
    avg_processing_time = sum(r["processing_time_ms"] for r in results) / len(results)
    fast_results = [r for r in results if r["processing_time_ms"] < avg_processing_time]
    
    if fast_results:
        best_fast_result = max(fast_results, key=lambda x: x.get("confidence_score", 0))
        recommendations.append(f"Best speed/quality trade-off: {best_fast_result['provider']} with {best_fast_result['summary_type']} type")
    
    return recommendations

# Rate limiting and caching endpoints
@router.get("/cache/stats")
async def get_cache_statistics():
    """
    Get summary cache statistics and performance metrics.
    """
    try:
        report_service = get_report_service()
        
        # Get cache statistics from service if available
        cache_stats = {}
        if hasattr(report_service, 'get_cache_stats'):
            cache_stats = report_service.get_cache_stats()
        
        return {
            "cache_statistics": cache_stats,
            "cache_enabled": hasattr(report_service, 'get_cache_stats'),
            "retrieved_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting cache statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/cache/clear")
async def clear_summary_cache():
    """
    Clear all cached summaries.
    """
    try:
        report_service = get_report_service()
        
        if hasattr(report_service, 'clear_cache'):
            cleared_count = report_service.clear_cache()
            return SuccessResponse(
                message=f"Cleared {cleared_count} cached summaries"
            )
        else:
            return SuccessResponse(
                message="Cache clearing not supported by current provider"
            )
            
    except Exception as e:
        logger.error(f"Error clearing summary cache: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/limits")
async def get_rate_limits():
    """
    Get current rate limiting information.
    """
    return {
        "rate_limits": {
            "summary_generation": {
                "requests_per_minute": 30,
                "requests_per_hour": 500,
                "concurrent_requests": 10
            },
            "batch_operations": {
                "max_sessions_per_batch": 10,
                "requests_per_hour": 50
            },
            "scheduled_summaries": {
                "max_active_schedules": 100,
                "max_schedules_per_user": 20
            }
        },
        "current_usage": {
            "active_requests": 0,  # Would be tracked in production
            "scheduled_tasks": len(scheduled_summaries)
        }
    }

# Webhook management for scheduled summaries
@router.get("/webhooks")
async def list_webhook_configurations():
    """
    List configured webhooks for summary notifications.
    """
    # In production, this would be stored in a database
    webhook_configs = {}
    
    for task_id, task_info in scheduled_summaries.items():
        webhook_url = task_info["request"].webhook_url
        if webhook_url:
            if webhook_url not in webhook_configs:
                webhook_configs[webhook_url] = {
                    "url": webhook_url,
                    "active_tasks": 0,
                    "total_tasks": 0
                }
            
            webhook_configs[webhook_url]["total_tasks"] += 1
            if task_info["status"] in ["scheduled", "processing"]:
                webhook_configs[webhook_url]["active_tasks"] += 1
    
    return {
        "webhook_configurations": list(webhook_configs.values()),
        "total_webhooks": len(webhook_configs)
    }

@router.post("/webhooks/test")
async def test_webhook(webhook_url: str = Body(...)):
    """
    Test webhook endpoint with sample data.
    """
    try:
        test_payload = {
            "test": True,
            "message": "This is a test webhook notification",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "session_id": "test-session",
                "summary": "This is a test summary",
                "summary_type": "brief"
            }
        }
        
        # Send test webhook
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=test_payload) as response:
                return {
                    "webhook_url": webhook_url,
                    "status_code": response.status,
                    "success": 200 <= response.status < 300,
                    "response_text": await response.text(),
                    "tested_at": datetime.now().isoformat()
                }
                
    except Exception as e:
        logger.error(f"Webhook test error: {e}")
        return {
            "webhook_url": webhook_url,
            "success": False,
            "error": str(e),
            "tested_at": datetime.now().isoformat()
        }