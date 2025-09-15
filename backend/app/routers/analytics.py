import logging
from fastapi import APIRouter, HTTPException, Depends

from app.modules.realtime_store import realtime_store
from app.models.schemas import AnalyticsResponse, ErrorResponse
from .transcript import get_valid_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/{meeting_id}", response_model=AnalyticsResponse)
async def get_meeting_analytics(meeting_id: str, session=Depends(get_valid_session)):
    try:
        analytics_data = await realtime_store.get_analytics_data(meeting_id)
        if not analytics_data:
            raise HTTPException(status_code=404, detail="No analytics data available")
        
        logger.info(f"Generated analytics for meeting: {meeting_id}")
        return AnalyticsResponse(**analytics_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating analytics for {meeting_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
