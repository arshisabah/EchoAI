import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends

from app.modules.realtime_store import realtime_store
from app.models.schemas import SummaryResponse
from .transcript import get_valid_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/summary", tags=["Summary"])

@router.get("/{meeting_id}", response_model=SummaryResponse)
async def get_meeting_summary(meeting_id: str, session=Depends(get_valid_session)):
    try:
        transcripts = await realtime_store.get_transcripts(meeting_id)
        session_info = await realtime_store.get_session(meeting_id)
        if not transcripts:
            raise HTTPException(status_code=404, detail="No transcript data available")
        
        total_words = sum(len(entry.text.split()) for entry in transcripts)
        participants = list(session_info.participants)
        duration = (datetime.now() - session_info.created_at).total_seconds() / 60

        summary_text = f"Meeting with {len(participants)} participants lasting {duration:.1f} minutes. " \
                       f"Total of {len(transcripts)} transcript entries with {total_words} words."

        key_points = []
        for entry in transcripts[-5:]:
            if len(entry.text) > 50:
                key_points.append(f"{entry.speaker}: {entry.text[:100]}...")

        result = SummaryResponse(
            meeting_id=meeting_id,
            summary=summary_text,
            key_points=key_points[:3],
            participants=participants,
            duration_minutes=duration,
            generated_at=datetime.now().isoformat()
        )

        logger.info(f"Generated summary for meeting: {meeting_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating summary for {meeting_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
