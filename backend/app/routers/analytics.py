from fastapi import APIRouter
from database.session_store import SessionStore

router = APIRouter()
session_store = SessionStore()

@router.get("/{meeting_id}")
def get_analytics(meeting_id: str):
    transcript = session_store.get_transcript(meeting_id)
    if not transcript:
        return {"error": "No transcript found"}

    total_words = sum(len(turn["text"].split()) for turn in transcript)
    speakers = {turn["speaker"] for turn in transcript}

    return {
        "meeting_id": meeting_id,
        "speakers": list(speakers),
        "total_words": total_words,
        "turns": len(transcript),
    }
