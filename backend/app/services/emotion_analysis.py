# backend/services/emotion_analysis.py
"""
Emotion Analysis Service for EchoAI - Uses OpenAI GPT-4o-mini.
"""

import logging
import uuid
import re  # For word boundary matching in keyword fallback
from datetime import datetime
from app.utils.timezone import get_ist_timestamp
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
        logger.debug(f"Supported emotions: {', '.join(SUPPORTED_EMOTIONS)}")

    def _get_client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI
            from app.core.config import settings
            
            # Validate API key
            if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_openai_key_here":
                logger.error("❌ OpenAI API key is missing or not configured!")
                logger.error("Please set OPENAI_API_KEY environment variable")
                raise ValueError("OpenAI API key not configured")
            
            logger.debug(f"✅ Initializing OpenAI client (API key: ...{settings.OPENAI_API_KEY[-4:]})")
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("✅ OpenAI client initialized successfully")
        return self._client

    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze emotion from text.
        
        Returns dict with 'emotion', 'confidence', and 'scores'.
        """
        logger.info(f"🎭 [EMOTION] Starting analysis for: '{text[:80]}...'")
        
        if not text.strip():
            logger.debug("⚠️ Empty text provided, returning neutral emotion")
            return {
                "emotion": "neutral",
                "confidence": 0.0,
                "scores": {emotion: 0.0 for emotion in self.supported_emotions}
            }

        try:
            logger.info("📡 [EMOTION] Getting OpenAI client...")
            client = self._get_client()
            logger.info("✅ [EMOTION] OpenAI client ready, making API call...")
            
            emotions_str = ", ".join(self.supported_emotions)
            
            prompt = (
                "Analyze the emotion in the following text. "
                f"Choose from: {emotions_str}. "
                "Respond with JSON: {'emotion': '...', 'confidence': 0-1, "
                "'scores': {emotion: score}}.\n\n"
                f"Text: \"{text}\""
            )
            
            logger.debug(f"📤 Sending request to OpenAI GPT-4o-mini...")

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
            
            logger.info(f"✅ [EMOTION] Got OpenAI response successfully")

            content = response.choices[0].message.content.strip()
            logger.debug(f"📥 OpenAI response content: {content[:200]}")
            
            # ✅ FIX: Remove markdown code blocks if present
            if "```json" in content:
                content = content.replace("```json", "").replace("```", "").strip()
            elif "```" in content:
                content = content.replace("```", "").strip()

            result = json.loads(content)
            logger.info(f"✅ [EMOTION] Parsed emotion result: {result.get('emotion', 'unknown')} (confidence: {result.get('confidence', 0):.2f})")
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Failed to parse OpenAI response as JSON: {e}")
            logger.warning(f"   Response content: {content[:200]}")
            # Fallback with keyword matching
            return self._fallback_emotion_detection(text)
        except Exception as e:
            logger.error(f"❌ [EMOTION] Error during OpenAI analysis: {e}", exc_info=True)
            return self._fallback_emotion_detection(text)
            
            try:
                # ✅ FIX: Remove markdown code blocks if present
                if content.startswith("```"):
                    logger.debug("🔧 Removing markdown code blocks from response")
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
                    logger.debug(f"🔧 Cleaned content: {content[:200]}")
                
                # ✅ FIX: Handle empty responses
                if not content:
                    logger.warning("⚠️ Empty content from OpenAI, using fallback")
                    return self._fallback_emotion_analysis(text)
                
                result = json.loads(content)
                emotion = result.get("emotion", "neutral").lower()
                confidence = float(result.get("confidence", 0.5))
                scores = result.get("scores", {})
                
                logger.info(f"✅ Detected emotion: {emotion} (confidence: {confidence:.2f})")
                
                if emotion not in self.supported_emotions:
                    logger.warning(f"⚠️ Unsupported emotion '{emotion}' returned, defaulting to neutral")
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
                logger.warning(f"❌ JSON parse error: {e}. Content: {content[:200]}")
                logger.warning("🔄 Falling back to keyword-based analysis")
                return self._fallback_emotion_analysis(text)

        except ValueError as e:
            logger.error(f"❌ Configuration error: {e}")
            logger.warning("🔄 Using keyword-based fallback due to configuration error")
            return self._fallback_emotion_analysis(text)
        except Exception as e:
            logger.error(f"❌ Emotion analysis failed: {e}", exc_info=True)
            logger.warning("🔄 Falling back to neutral emotion")
            return {
                "emotion": "neutral",
                "confidence": 0.0,
                "scores": {emotion: 0.0 for emotion in self.supported_emotions}
            }

    def _fallback_emotion_analysis(self, text: str) -> Dict[str, Any]:
        """
        Enhanced keyword-based fallback with expanded vocabulary.
        This is used when OpenAI is unavailable or returns invalid results.
        Uses word boundary matching to prevent false positives.
        """
        logger.info(f"🔄 Using keyword-based fallback analysis for: '{text[:50]}...'")
        text_lower = text.lower()
        
        # Expanded emotion keywords with stronger patterns
        emotion_keywords = {
            "happy": {
                "keywords": ["happy", "joy", "joyful", "excited", "great", "awesome", "wonderful", 
                           "fantastic", "excellent", "amazing", "delighted", "pleased", "glad",
                           "thrilled", "love", "loving", "brilliant", "perfect", "yay", "yes!"],
                "weight": 0.7
            },
            "sad": {
                "keywords": ["sad", "down", "depressed", "miserable", "gloomy", 
                           "disappointed", "heartbroken", "sorrowful", "melancholy", "unfortunate",
                           "terrible", "awful", "bad news", "sorry to hear"],
                "weight": 0.7
            },
            "angry": {
                "keywords": ["angry", "mad", "furious", "upset", "rage", "outraged", "irritated",
                           "pissed", "annoyed", "infuriated", "disgusted", "hate", "hateful",
                           "ridiculous", "unacceptable", "damn", "fuck", "fucking", "shit", "bullshit",
                           "bastard", "hell", "wtf", "dammit", "crap", "piss off", "screw",
                           "stupid", "idiot", "moron", "dumb", "asshole", "bitch"],
                "weight": 0.85
            },
            "frustrated": {
                "keywords": ["frustrated", "frustrating", "annoyed", "annoying", "stressed", 
                           "stress", "struggling", "struggle", "difficult", "can't figure",
                           "not working", "broken", "fail", "failing", "why won't", "keeps breaking"],
                "weight": 0.7
            },
            "confused": {
                "keywords": ["confused", "confusing", "unclear", "don't understand", "not sure",
                           "uncertain", "puzzled", "bewildered", "lost", "what do you mean",
                           "how does", "why does", "help me understand", "clarify"],
                "weight": 0.6
            },
            "excited": {
                "keywords": ["excited", "exciting", "can't wait", "looking forward", "pumped",
                           "enthusiastic", "eager", "anticipated", "stoked", "hyped"],
                "weight": 0.7
            },
            "anxious": {
                "keywords": ["anxious", "worried", "nervous", "concerned", "afraid", "scared",
                           "fearful", "apprehensive", "uneasy", "worried about", "what if",
                           "hope it works", "hopefully", "crossing fingers"],
                "weight": 0.65
            },
            "confident": {
                "keywords": ["confident", "sure", "certain", "definitely", "absolutely", 
                           "no doubt", "guaranteed", "convinced", "assured", "positive"],
                "weight": 0.6
            },
            "surprised": {
                "keywords": ["surprised", "shocking", "wow", "unexpected", "didn't expect",
                           "can't believe", "unbelievable", "astonishing"],
                "weight": 0.6
            },
            "bored": {
                "keywords": ["bored", "boring", "dull", "monotonous", "tedious", "uninteresting",
                           "yawn", "whatever", "meh"],
                "weight": 0.6
            },
            "disappointed": {
                "keywords": ["disappointed", "disappointing", "let down", "expected more",
                           "hoped for", "not what I", "underwhelming"],
                "weight": 0.65
            }
        }
        
        detected = "neutral"
        max_confidence = 0.3
        matched_keywords = []
        
        # Check for emotion keywords with word boundaries
        for emotion, config in emotion_keywords.items():
            keywords = config["keywords"]
            base_weight = config["weight"]
            
            matches = []
            for kw in keywords:
                # Use word boundaries for single words, phrase matching for multi-word keywords
                if ' ' in kw:
                    # Multi-word phrase - check for exact substring match
                    if kw in text_lower:
                        matches.append(kw)
                else:
                    # Single word - use word boundary regex to avoid false positives
                    pattern = r'\b' + re.escape(kw) + r'\b'
                    if re.search(pattern, text_lower):
                        matches.append(kw)
            
            if matches:
                # Calculate confidence based on number and strength of matches
                match_count = len(matches)
                confidence = min(base_weight + (match_count - 1) * 0.05, 0.95)
                
                if confidence > max_confidence:
                    max_confidence = confidence
                    detected = emotion
                    matched_keywords = matches
        
        logger.info(f"✅ Fallback detected: {detected} (confidence: {max_confidence:.2f})")
        if matched_keywords:
            logger.debug(f"   Matched keywords: {', '.join(matched_keywords)}")
        
        # Build scores dictionary
        scores = {e: 0.1 for e in self.supported_emotions}
        scores[detected] = max_confidence
        
        return {
            "emotion": detected,
            "confidence": max_confidence,
            "scores": scores
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
                "timestamp": entry.get("timestamp", get_ist_timestamp()),
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
    logger.debug(f"🔀 analyze_text_and_audio_combined called")
    logger.debug(f"   Text: '{text[:100]}...' (length: {len(text)})")
    logger.debug(f"   Audio: {'provided' if audio_array is not None else 'not provided'}")
    logger.debug(f"   Weights: text={text_weight}, audio={audio_weight}")
    
    from app.services.dependencies import get_emotion_service
    service = get_emotion_service()

    # --- Analyze text-based emotion ---
    logger.debug("📝 Analyzing text-based emotion...")
    text_result = await service.analyze_text(text)
    if not text_result:
        logger.warning("⚠️ Text analysis returned None, using neutral")
        text_result = {"emotion": "neutral", "confidence": 0.0}
    logger.info(f"✅ Text emotion: {text_result.get('emotion', 'neutral')} (confidence: {text_result.get('confidence', 0):.2f})")

    # --- Analyze audio-based emotion (optional) ---
    audio_result = None
    if audio_array is not None:
        logger.debug(f"🎤 Analyzing audio-based emotion (array length: {len(audio_array)})...")
        try:
            from app.modules.audio_emotion_analyzer import analyze_audio_emotion
            import asyncio
            audio_result = await asyncio.to_thread(analyze_audio_emotion, audio_array, sample_rate)
            logger.info(f"✅ Audio emotion: {audio_result.get('emotion', 'neutral')} (confidence: {audio_result.get('confidence', 0):.2f})")
        except Exception as e:
            logger.error(f"❌ Audio emotion analysis failed: {e}", exc_info=True)
            audio_result = {"emotion": "neutral", "confidence": 0.0}
    else:
        logger.debug("ℹ️ No audio provided for emotion analysis")

    # --- If no audio available, fallback to text only ---
    if audio_result is None:
        logger.info(f"➡️ Using text-only emotion: {text_result['emotion']}")
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

    logger.debug(f"🔀 Combining emotions:")
    logger.debug(f"   Text: {t_emo} ({t_conf:.2f}) × {text_weight} = {t_conf * text_weight:.2f}")
    logger.debug(f"   Audio: {a_emo} ({a_conf:.2f}) × {audio_weight} = {a_conf * audio_weight:.2f}")

    # Choose dominant emotion
    if t_emo == a_emo:
        final_emotion = t_emo
        logger.debug(f"✅ Both sources agree: {final_emotion}")
    else:
        final_emotion = a_emo if a_conf * audio_weight > t_conf * text_weight else t_emo
        logger.debug(f"⚖️ Weighted selection: {final_emotion} (text: {t_emo}, audio: {a_emo})")

    # Weighted confidence
    final_confidence = round(t_conf * text_weight + a_conf * audio_weight, 3)
    
    logger.info(f"✅ Combined emotion result: {final_emotion} (confidence: {final_confidence:.2f})")

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

