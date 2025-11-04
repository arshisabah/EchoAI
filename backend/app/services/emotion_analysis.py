# backend/services/emotion_service.py
"""
Emotion Analysis Service for EchoAI.

Responsibilities:
- Analyze emotion from transcribed text using LLM
- Provide confidence scores for detected emotions
- Support both real-time and batch processing
- Return structured emotion data
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

# Supported emotion labels
SUPPORTED_EMOTIONS = [
    "happy",
    "sad", 
    "angry",
    "neutral",
    "excited",
    "frustrated",
    "confused",
    "surprised",
    "bored",
    "anxious",
    "confident",
    "disappointed"
]


class EmotionResult:
    """Container for emotion analysis results."""
    
    def __init__(self, emotion: str, confidence: float, scores: Dict[str, float] = None):
        self.emotion = emotion
        self.confidence = confidence
        self.scores = scores or {}


class EmotionService:
    """Service for analyzing emotions from text using OpenAI."""

    def __init__(self):
        self.supported_emotions = SUPPORTED_EMOTIONS
        logger.info("EmotionService initialized with OpenAI GPT-4o-mini")

    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze emotion from a chunk of transcribed text.

        Args:
            text (str): The transcribed text to analyze

        Returns:
            dict: Contains 'emotion', 'confidence', and 'scores'
        """
        if not text.strip():
            return {
                "emotion": "neutral",
                "confidence": 0.0,
                "scores": {emotion: 0.0 for emotion in self.supported_emotions}
            }

        try:
            # Create prompt for emotion classification
            emotions_str = ", ".join(self.supported_emotions)
            prompt = (
                "Analyze the emotion in the following text. "
                f"Choose from these emotions: {emotions_str}. "
                "Respond with a JSON object containing:\n"
                "- 'emotion': the primary emotion (string)\n"
                "- 'confidence': confidence score 0-1 (float)\n"
                "- 'scores': object with all emotions and their scores 0-1 (object)\n\n"
                f"Text to analyze: \"{text}\""
            )

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert emotion detection assistant. Always respond with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )

            content = response.choices[0].message.content.strip()
            
            # Parse the JSON response
            try:
                result = json.loads(content)
                emotion = result.get("emotion", "neutral").lower()
                confidence = float(result.get("confidence", 0.5))
                scores = result.get("scores", {})
                
                # Validate emotion is in supported list
                if emotion not in self.supported_emotions:
                    emotion = "neutral"
                    confidence = 0.3
                
                # Ensure all emotions have scores
                complete_scores = {emo: scores.get(emo, 0.0) for emo in self.supported_emotions}
                
                return {
                    "emotion": emotion,
                    "confidence": confidence,
                    "scores": complete_scores
                }
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse emotion JSON: {content}, error: {e}")
                return self._fallback_emotion_analysis(text, content)

        except Exception as e:
            logger.error(f"Emotion analysis failed: {e}")
            return {
                "emotion": "neutral",
                "confidence": 0.0,
                "scores": {emotion: 0.0 for emotion in self.supported_emotions}
            }

    def _fallback_emotion_analysis(self, text: str, response_content: str) -> Dict[str, Any]:
        """Fallback emotion detection using keyword matching."""
        text_lower = text.lower()
        response_lower = response_content.lower()
        
        # Simple keyword-based emotion detection
        emotion_keywords = {
            "happy": ["happy", "joy", "excited", "great", "awesome", "wonderful", "good"],
            "sad": ["sad", "down", "depressed", "unhappy", "disappointed"],
            "angry": ["angry", "mad", "furious", "upset", "irritated"],
            "frustrated": ["frustrated", "annoyed", "stressed"],
            "confused": ["confused", "unclear", "don't understand"],
            "surprised": ["surprised", "shocked", "wow", "unexpected"],
            "bored": ["bored", "tired", "uninterested"],
            "anxious": ["anxious", "worried", "nervous", "concerned"],
            "confident": ["confident", "sure", "certain", "strong"]
        }
        
        detected_emotion = "neutral"
        confidence = 0.3
        
        # Check for emotion keywords in text or response
        for emotion, keywords in emotion_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                detected_emotion = emotion
                confidence = 0.6
                break
            elif any(keyword in response_lower for keyword in keywords):
                detected_emotion = emotion
                confidence = 0.4
                break
        
        return {
            "emotion": detected_emotion,
            "confidence": confidence,
            "scores": {emotion: (0.6 if emotion == detected_emotion else 0.1) for emotion in self.supported_emotions}
        }

    async def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Analyze emotions for multiple text chunks.
        
        Args:
            texts: List of text strings to analyze
            
        Returns:
            List of emotion analysis results
        """
        results = []
        for text in texts:
            result = await self.analyze_text(text)
            results.append(result)
        return results

    async def analyze_session_emotions(self, transcript_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze emotions across an entire session.
        
        Args:
            transcript_entries: List of transcript dictionaries with 'text' field
            
        Returns:
            Dict with session emotion summary
        """
        if not transcript_entries:
            return {
                "overall_emotion": "neutral",
                "emotion_distribution": {emotion: 0.0 for emotion in self.supported_emotions},
                "emotion_timeline": []
            }
        
        emotions = []
        emotion_counts = {emotion: 0 for emotion in self.supported_emotions}
        
        for entry in transcript_entries:
            if not entry.get("text"):
                continue
                
            emotion_result = await self.analyze_text(entry["text"])
            emotions.append({
                "timestamp": entry.get("timestamp", datetime.utcnow().isoformat()),
                "speaker": entry.get("speaker", "Unknown"),
                "emotion": emotion_result["emotion"],
                "confidence": emotion_result["confidence"]
            })
            
            emotion_counts[emotion_result["emotion"]] += 1
        
        # Calculate overall emotion (most frequent)
        total_entries = len(emotions)
        overall_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0] if total_entries > 0 else "neutral"
        
        # Calculate distribution percentages
        emotion_distribution = {
            emotion: (count / total_entries * 100) if total_entries > 0 else 0.0
            for emotion, count in emotion_counts.items()
        }
        
        return {
            "overall_emotion": overall_emotion,
            "emotion_distribution": emotion_distribution,
            "emotion_timeline": emotions,
            "total_analyzed": total_entries
        }


# ---------------- Singleton accessor ---------------- #
_emotion_service: Optional[EmotionService] = None


def get_emotion_service() -> EmotionService:
    """Get the singleton emotion service instance."""
    global _emotion_service
    if _emotion_service is None:
        _emotion_service = EmotionService()
    return _emotion_service


# ---------------- Compatibility function ---------------- #
async def analyze_emotion(
    text: str,
    session_id: Optional[str] = None,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Legacy compatibility function for emotion analysis.
    
    Args:
        text: Text to analyze
        session_id: Optional session ID
        timestamp: Optional timestamp
        
    Returns:
        Dict with emotion analysis including metadata
    """
    service = get_emotion_service()
    result = await service.analyze_text(text)
    
    return {
        "id": f"emo_{uuid.uuid4()}",
        "session_id": session_id,
        "timestamp": timestamp or datetime.utcnow().isoformat(),
        "text": text,
        "emotion": result["emotion"],
        "confidence": result["confidence"],
        "scores": result["scores"]
    }