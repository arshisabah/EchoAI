# backend/services/emotion_analysis.py
"""
Emotion Analysis Service for EchoAI - Uses OpenAI GPT-4o-mini.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import json
from app.modules.audio_emotion_analyzer import analyze_audio_emotion

logger = logging.getLogger(__name__)

# Supported emotion labels
SUPPORTED_EMOTIONS = [
    "happy", "sad", "angry", "neutral", "excited",
    "frustrated", "confused", "surprised", "bored",
    "anxious", "confident", "disappointed"
]


class EmotionService:
    """Service for analyzing emotions from text using OpenAI."""

    def __init__(self):
        self.supported_emotions = SUPPORTED_EMOTIONS
        self._client = None  # Lazy initialization
        logger.info("EmotionService initialized (OpenAI client lazy-loaded)")

    def _get_client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI
            from app.core.config import settings
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze emotion from text.
        
        Returns dict with 'emotion', 'confidence', and 'scores'.
        """
        if not text.strip():
            return {
                "emotion": "neutral",
                "confidence": 0.0,
                "scores": {emotion: 0.0 for emotion in self.supported_emotions}
            }

        try:
            client = self._get_client()
            emotions_str = ", ".join(self.supported_emotions)
            
            prompt = (
                "Analyze the emotion in the following text. "
                f"Choose from: {emotions_str}. "
                "Respond with JSON: {'emotion': '...', 'confidence': 0-1, "
                "'scores': {emotion: score}}.\n\n"
                f"Text: \"{text}\""
            )

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an emotion detection expert. Respond only with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )

            content = response.choices[0].message.content.strip()
            
            try:
                # ✅ FIX: Remove markdown code blocks if present
                if content.startswith("```"):
                    # Extract JSON from markdown code block
                    lines = content.split("\n")
                    json_lines = []
                    in_code_block = False
                    
                    for line in lines:
                        if line.startswith("```"):
                            in_code_block = not in_code_block
                            continue
                        if in_code_block or (not line.startswith("```")):
                            json_lines.append(line)
                    
                    content = "\n".join(json_lines).strip()
                
                # ✅ FIX: Handle empty responses
                if not content:
                    logger.warning("Empty content from OpenAI, using fallback")
                    return self._fallback_emotion_analysis(text)
                
                result = json.loads(content)
                emotion = result.get("emotion", "neutral").lower()
                confidence = float(result.get("confidence", 0.5))
                scores = result.get("scores", {})
                
                if emotion not in self.supported_emotions:
                    emotion = "neutral"
                    confidence = 0.3
                
                complete_scores = {
                    emo: scores.get(emo, 0.0) 
                    for emo in self.supported_emotions
                }
                
                return {
                    "emotion": emotion,
                    "confidence": confidence,
                    "scores": complete_scores
                }
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error: {e}. Content: {content[:200]}")
                return self._fallback_emotion_analysis(text)

        except Exception as e:
            logger.error(f"Emotion analysis failed: {e}")
            return {
                "emotion": "neutral",
                "confidence": 0.0,
                "scores": {emotion: 0.0 for emotion in self.supported_emotions}
            }

    def _fallback_emotion_analysis(self, text: str) -> Dict[str, Any]:
        """Simple keyword-based fallback."""
        text_lower = text.lower()
        
        emotion_keywords = {
            "happy": ["happy", "joy", "excited", "great", "awesome"],
            "sad": ["sad", "down", "depressed", "unhappy"],
            "angry": ["angry", "mad", "furious", "upset"],
            "frustrated": ["frustrated", "annoyed", "stressed"],
            "confused": ["confused", "unclear", "don't understand"]
        }
        
        detected = "neutral"
        confidence = 0.3
        
        for emotion, keywords in emotion_keywords.items():
            if any(kw in text_lower for kw in keywords):
                detected = emotion
                confidence = 0.6
                break
        
        return {
            "emotion": detected,
            "confidence": confidence,
            "scores": {
                e: (0.6 if e == detected else 0.1) 
                for e in self.supported_emotions
            }
        }

    async def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Analyze multiple texts."""
        return [await self.analyze_text(text) for text in texts]

    async def analyze_session_emotions(
        self, 
        transcript_entries: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze emotions for an entire session."""
        if not transcript_entries:
            return {
                "overall_emotion": "neutral",
                "emotion_distribution": {e: 0.0 for e in self.supported_emotions},
                "emotion_timeline": []
            }
        
        emotions = []
        emotion_counts = {e: 0 for e in self.supported_emotions}
        
        for entry in transcript_entries:
            text = entry.get("text", "")
            if not text:
                continue
                
            result = await self.analyze_text(text)
            emotions.append({
                "timestamp": entry.get("timestamp", datetime.utcnow().isoformat()),
                "speaker": entry.get("speaker", "Unknown"),
                "emotion": result["emotion"],
                "confidence": result["confidence"]
            })
            
            emotion_counts[result["emotion"]] += 1
        
        total = len(emotions)
        overall = max(emotion_counts.items(), key=lambda x: x[1])[0] if total > 0 else "neutral"
        
        distribution = {
            e: (count / total * 100) if total > 0 else 0.0
            for e, count in emotion_counts.items()
        }
        
        return {
            "overall_emotion": overall,
            "emotion_distribution": distribution,
            "emotion_timeline": emotions,
            "total_analyzed": total
        }


# Singleton
_emotion_service: Optional[EmotionService] = None


def get_emotion_service() -> EmotionService:
    """Get singleton emotion service."""
    global _emotion_service
    if _emotion_service is None:
        _emotion_service = EmotionService()
    return _emotion_service

# ------------------------------------------------------------------------
# 🔹 Combined Emotion Analysis (Text + Audio) — Real-Time Fusion Function
# ------------------------------------------------------------------------

async def analyze_text_and_audio_combined(
    text: str,
    audio_array=None,
    sample_rate: int = 16000,
    text_weight: float = 0.6,
    audio_weight: float = 0.4
) -> Dict[str, Any]:
    """
    Combines text-based and audio-based emotion analysis for more realistic results.

    Args:
        text (str): Transcribed text from the user's speech.
        audio_array (np.ndarray, optional): Numpy array of audio samples.
        sample_rate (int): Sampling rate of audio (default 16kHz).
        text_weight (float): Weight given to text model confidence.
        audio_weight (float): Weight given to audio model confidence.

    Returns:
        dict: {
            'emotion': final_emotion,
            'confidence': float,
            'sources': {
                'text': {...},
                'audio': {...}
            }
        }
    """
    from app.services.dependencies import get_emotion_service
    service = get_emotion_service()

    # --- Analyze text-based emotion ---
    text_result = await service.analyze_text(text)
    if not text_result:
        text_result = {"emotion": "neutral", "confidence": 0.0}

    # --- Analyze audio-based emotion (optional) ---
    audio_result = None
    if audio_array is not None:
        try:
            from app.modules.audio_emotion_analyzer import analyze_audio_emotion
            import asyncio
            audio_result = await asyncio.to_thread(analyze_audio_emotion, audio_array, sample_rate)
        except Exception as e:
            logger.error(f"Audio emotion analysis failed: {e}")
            audio_result = {"emotion": "neutral", "confidence": 0.0}

    # --- If no audio available, fallback to text only ---
    if audio_result is None:
        return {
            "emotion": text_result["emotion"],
            "confidence": text_result["confidence"],
            "sources": {"text": text_result, "audio": None}
        }

    # --- Normalize and combine ---
    t_emo = text_result.get("emotion", "neutral")
    t_conf = float(text_result.get("confidence", 0.0))
    a_emo = audio_result.get("emotion", "neutral")
    a_conf = float(audio_result.get("confidence", 0.0))

    # Choose dominant emotion
    if t_emo == a_emo:
        final_emotion = t_emo
    else:
        final_emotion = a_emo if a_conf * audio_weight > t_conf * text_weight else t_emo

    # Weighted confidence
    final_confidence = round(t_conf * text_weight + a_conf * audio_weight, 3)

    return {
        "emotion": final_emotion,
        "confidence": final_confidence,
        "sources": {
            "text": text_result,
            "audio": audio_result
        }
    }
# Compatibility function
async def analyze_transcript_emotions(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze emotions for transcript entries."""
    service = get_emotion_service()
    
    # Analyze each entry
    individual_results = []
    for entry in entries:
        emotion_result = await service.analyze_text(entry.get("text", ""))
        individual_results.append({
            "entry_id": entry.get("id"),
            "speaker": entry.get("speaker"),
            "emotion_analysis": {
                "primary_emotion": emotion_result["emotion"],
                "confidence": emotion_result["confidence"],
                "sentiment_polarity": "positive" if emotion_result["emotion"] in ["happy", "excited", "confident"] else "negative" if emotion_result["emotion"] in ["sad", "angry", "frustrated"] else "neutral",
                "sentiment_score": emotion_result["confidence"] if emotion_result["emotion"] in ["happy", "excited"] else -emotion_result["confidence"] if emotion_result["emotion"] in ["sad", "angry"] else 0.0
            }
        })
    
    # Session summary
    session_summary = await service.analyze_session_emotions(entries)
    
    # Add additional fields for compatibility
    emotion_counts = {}
    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
    
    for result in individual_results:
        emotion = result["emotion_analysis"]["primary_emotion"]
        sentiment = result["emotion_analysis"]["sentiment_polarity"]
        
        emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        sentiment_counts[sentiment] += 1
    
    avg_sentiment = sum(
        r["emotion_analysis"]["sentiment_score"] 
        for r in individual_results
    ) / len(individual_results) if individual_results else 0.0
    
    session_summary["emotion_distribution"] = emotion_counts
    session_summary["sentiment_distribution"] = sentiment_counts
    session_summary["average_sentiment_score"] = avg_sentiment
    session_summary["dominant_emotion"] = session_summary.get("overall_emotion", "neutral")
    session_summary["dominant_sentiment"] = max(sentiment_counts.items(), key=lambda x: x[1])[0] if sentiment_counts else "neutral"
    
    return {
        "individual_results": individual_results,
        "session_summary": session_summary
    }