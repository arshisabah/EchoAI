from fastapi import APIRouter
from services.report_services import ReportService

router = APIRouter()
report_service = ReportService()

@router.get("/{meeting_id}")
def get_summary(meeting_id: str):
    return report_service.generate_summary(meeting_id)
