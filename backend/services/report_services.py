from database.session_store import SessionStore

class ReportService:
    def __init__(self):
        self.session_store = SessionStore()

    def generate_summary(self, meeting_id: str):
        transcript = self.session_store.get_transcript(meeting_id)
        if not transcript:
            return {"error": "No transcript found"}

        # TODO: Replace with real summarizer model
        summary = "This is a dummy meeting summary."
        action_items = ["Follow up with client", "Send project proposal"]

        return {
            "meeting_id": meeting_id,
            "summary": summary,
            "action_items": action_items,
            "transcript_length": len(transcript)
        }
