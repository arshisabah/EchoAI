# backend/services/summary_service.py
"""
Summary Service for EchoAI.

Responsibilities:
- Generate real-time and final summaries of meeting transcripts
- Extract key discussion points, decisions, and action items
- Provide different summary modes (brief, detailed, action-focused)
- Track conversation topics and themes
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import json
from app.core.config import settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Summary modes
SUMMARY_MODES = {
    "realtime": "brief real-time update",
    "final": "comprehensive final summary",
    "action_items": "focus on decisions and action items",
    "topics": "extract main topics and themes"
}


class SummaryService:
    """Service for generating meeting summaries using OpenAI."""

    def __init__(self):
        self.modes = SUMMARY_MODES
        logger.info("SummaryService initialized with OpenAI GPT-4o-mini")

    async def generate_summary(
        self, 
        text: str, 
        mode: str = "final",
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a summary of the provided text.

        Args:
            text (str): The text to summarize
            mode (str): Summary mode ('realtime', 'final', 'action_items', 'topics')
            context (dict): Additional context like speaker info, previous summaries

        Returns:
            str: Generated summary text
        """
        if not text.strip():
            return ""

        context = context or {}
        
        try:
            system_prompt = self._get_system_prompt(mode)
            user_prompt = self._build_user_prompt(text, mode, context)

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=self._get_max_tokens(mode)
            )

            summary = response.choices[0].message.content.strip()
            return summary

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return ""

    def _get_system_prompt(self, mode: str) -> str:
        """Get appropriate system prompt based on summary mode."""
        base_prompt = "You are an expert meeting summarizer and note-taker."
        
        prompts = {
            "realtime": (
                f"{base_prompt} Generate very brief, concise updates (1-2 bullet points maximum) "
                "highlighting the most recent key points discussed. Focus on immediate insights."
            ),
            "final": (
                f"{base_prompt} Create a comprehensive, well-structured meeting summary with "
                "clear sections for key discussion points, decisions made, and next steps. "
                "Be thorough but organized."
            ),
            "action_items": (
                f"{base_prompt} Focus specifically on extracting concrete action items, "
                "decisions made, deadlines mentioned, and responsibilities assigned. "
                "Present as clear, actionable bullet points."
            ),
            "topics": (
                f"{base_prompt} Identify and extract the main topics, themes, and subjects "
                "discussed. Organize by topic with brief descriptions of what was covered."
            )
        }
        
        return prompts.get(mode, prompts["final"])

    def _build_user_prompt(self, text: str, mode: str, context: Dict[str, Any]) -> str:
        """Build user prompt with text and context."""
        prompt_parts = []
        
        # Add context if available
        if context.get("speakers"):
            prompt_parts.append(f"Participants: {', '.join(context['speakers'])}")
        
        if context.get("previous_summary"):
            prompt_parts.append(f"Previous summary context: {context['previous_summary']}")
        
        if context.get("session_duration"):
            prompt_parts.append(f"Session duration: {context['session_duration']} minutes")

        # Add mode-specific instructions
        mode_instructions = {
            "realtime": "Provide a quick update on the latest discussion:",
            "final": "Please summarize this meeting transcript:",
            "action_items": "Extract all action items, decisions, and next steps from:",
            "topics": "Identify the main topics and themes discussed in:"
        }
        
        prompt_parts.append(mode_instructions.get(mode, mode_instructions["final"]))
        prompt_parts.append(f"\nTranscript:\n{text}")
        
        return "\n".join(prompt_parts)

    def _get_max_tokens(self, mode: str) -> int:
        """Get appropriate token limit based on mode."""
        token_limits = {
            "realtime": 150,
            "final": 800,
            "action_items": 400,
            "topics": 300
        }
        return token_limits.get(mode, 500)

    async def generate_structured_summary(
        self, 
        transcript_chunks: List[str],
        session_id: Optional[str] = None,
        mode: str = "final"
    ) -> Dict[str, Any]:
        """
        Generate a structured summary with metadata.

        Args:
            transcript_chunks (List[str]): List of transcript text chunks
            session_id (str): Optional session/meeting ID
            mode (str): Summary mode

        Returns:
            Dict: Structured summary with metadata
        """
        if not transcript_chunks:
            return {
                "id": f"sum_{uuid.uuid4()}",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "mode": mode,
                "summary": "",
                "word_count": 0,
                "chunk_count": 0
            }

        try:
            # Combine all chunks
            full_text = "\n".join(chunk for chunk in transcript_chunks if chunk.strip())
            
            # Generate summary
            summary_text = await self.generate_summary(full_text, mode)
            
            return {
                "id": f"sum_{uuid.uuid4()}",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "mode": mode,
                "summary": summary_text,
                "word_count": len(full_text.split()),
                "chunk_count": len(transcript_chunks)
            }

        except Exception as e:
            logger.error(f"Structured summary generation failed: {e}")
            return {
                "id": f"sum_{uuid.uuid4()}",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "mode": mode,
                "summary": "",
                "word_count": 0,
                "chunk_count": len(transcript_chunks) if transcript_chunks else 0
            }

    async def extract_action_items(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract specific action items from text.

        Args:
            text (str): Text to analyze for action items

        Returns:
            List of action item dictionaries
        """
        if not text.strip():
            return []

        try:
            prompt = (
                "Extract all action items, tasks, and decisions from the following text. "
                "For each item, identify:\n"
                "- The action/task description\n"
                "- Who is responsible (if mentioned)\n"
                "- Any deadline or timeframe (if mentioned)\n"
                "- Priority level (high/medium/low if indicated)\n\n"
                "Respond with a JSON array of objects with fields: 'action', 'assignee', 'deadline', 'priority'.\n\n"
                f"Text: {text}"
            )

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert at extracting action items from meetings. Always respond with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=600
            )

            content = response.choices[0].message.content.strip()
            
            try:
                action_items = json.loads(content)
                # Ensure it's a list
                if isinstance(action_items, dict):
                    action_items = [action_items]
                
                # Add IDs and timestamps
                for item in action_items:
                    item["id"] = str(uuid.uuid4())
                    item["extracted_at"] = datetime.utcnow().isoformat()
                    # Ensure required fields exist
                    item.setdefault("action", "")
                    item.setdefault("assignee", "Unassigned")
                    item.setdefault("deadline", "No deadline")
                    item.setdefault("priority", "medium")
                
                return action_items
                
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse action items JSON: {content}")
                return []

        except Exception as e:
            logger.error(f"Action item extraction failed: {e}")
            return []

    async def generate_meeting_insights(
        self, 
        transcript_entries: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate comprehensive insights from a meeting session.

        Args:
            transcript_entries: List of transcript dictionaries

        Returns:
            Dict with various meeting insights
        """
        if not transcript_entries:
            return {
                "total_entries": 0,
                "summary": "",
                "action_items": [],
                "key_topics": [],
                "participants": [],
                "duration_analysis": {}
            }

        try:
            # Extract basic info
            participants = list(set(entry.get("speaker", "Unknown") for entry in transcript_entries))
            full_text = " ".join(entry.get("text", "") for entry in transcript_entries if entry.get("text"))
            
            # Generate different types of summaries
            final_summary = await self.generate_summary(full_text, mode="final")
            action_items = await self.extract_action_items(full_text)
            topics_summary = await self.generate_summary(full_text, mode="topics")
            
            # Calculate speaking statistics
            speaker_stats = {}
            for entry in transcript_entries:
                speaker = entry.get("speaker", "Unknown")
                if speaker not in speaker_stats:
                    speaker_stats[speaker] = {"word_count": 0, "turn_count": 0}
                speaker_stats[speaker]["word_count"] += len(entry.get("text", "").split())
                speaker_stats[speaker]["turn_count"] += 1
            
            return {
                "total_entries": len(transcript_entries),
                "participants": participants,
                "summary": final_summary,
                "action_items": action_items,
                "key_topics": topics_summary,
                "speaker_statistics": speaker_stats,
                "total_words": len(full_text.split()),
                "generated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Meeting insights generation failed: {e}")
            return {
                "total_entries": len(transcript_entries),
                "summary": "",
                "action_items": [],
                "key_topics": [],
                "participants": [],
                "error": str(e)
            }


# ---------------- Singleton accessor ---------------- #
_summary_service: Optional[SummaryService] = None


def get_summary_service() -> SummaryService:
    """Get the singleton summary service instance."""
    global _summary_service
    if _summary_service is None:
        _summary_service = SummaryService()
    return _summary_service


# ---------------- Compatibility function ---------------- #
async def generate_summary(
    transcript_chunks: List[str],
    session_id: Optional[str] = None,
    mode: str = "realtime"
) -> Dict[str, Any]:
    """
    Legacy compatibility function for summary generation.
    
    Args:
        transcript_chunks: List of transcript text chunks
        session_id: Optional session ID
        mode: Summary mode
        
    Returns:
        Dict with summary and metadata
    """
    service = get_summary_service()
    return await service.generate_structured_summary(transcript_chunks, session_id, mode)