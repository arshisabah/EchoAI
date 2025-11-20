# app/services/emotion_guidance.py
"""
Emotion guidance system - provides real-time suggestions on how to respond
to detected emotions in conversations.
"""

import logging
import time
from typing import Dict, Any, List
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# Fallback guidance templates when OpenAI is unavailable
FALLBACK_GUIDANCE_TEMPLATES = {
    "angry": {
        "severity": "high",
        "suggestions": [
            "Stay calm and acknowledge their frustration",
            "Listen without interrupting",
            "Avoid being defensive"
        ]
    },
    "frustrated": {
        "severity": "medium",
        "suggestions": [
            "Show empathy and help them find solutions",
            "Ask what specific help they need",
            "Offer concrete assistance"
        ]
    },
    "sad": {
        "severity": "medium",
        "suggestions": [
            "Show compassion and provide emotional support",
            "Listen actively without trying to 'fix' immediately",
            "Validate their feelings"
        ]
    },
    "happy": {
        "severity": "low",
        "suggestions": [
            "Share in their joy",
            "Show genuine enthusiasm",
            "Celebrate their success"
        ]
    },
    "excited": {
        "severity": "low",
        "suggestions": [
            "Match their enthusiasm",
            "Ask engaging questions",
            "Encourage their passion"
        ]
    },
    "anxious": {
        "severity": "medium",
        "suggestions": [
            "Provide reassurance",
            "Help them feel secure",
            "Offer concrete next steps"
        ]
    },
    "confused": {
        "severity": "low",
        "suggestions": [
            "Clarify and explain patiently",
            "Use examples and analogies",
            "Check understanding frequently"
        ]
    },
    "confident": {
        "severity": "low",
        "suggestions": [
            "Support their confidence",
            "Ask thoughtful questions",
            "Ensure all factors are considered"
        ]
    },
    "neutral": {
        "severity": "none",
        "suggestions": [
            "Maintain professional engagement",
            "Stay focused on the topic",
            "Be clear and direct"
        ]
    }
}


class EmotionGuidanceEngine:
    """
    Provides intelligent guidance on how to respond to emotions.
    Helps users maintain empathetic and effective communication.
    """
    
    def __init__(self):
        self.guidance_rules = self._load_guidance_rules()
        self.use_fallback = self._check_openai_availability()
        if self.use_fallback:
            logger.warning("⚠️ OpenAI API not available, using fallback guidance templates")
        else:
            logger.info("✅ EmotionGuidanceEngine initialized with OpenAI support")
    
    def _check_openai_availability(self) -> bool:
        """Check if OpenAI API is available."""
        try:
            from app.core.config import settings
            if not settings.OPENAI_API_KEY:
                return True  # Use fallback if no API key
            # Could add additional checks here (e.g., test API call)
            return False  # API key exists, don't use fallback by default
        except Exception as e:
            logger.warning(f"Error checking OpenAI availability: {e}")
            return True  # Use fallback on error
    
    def _load_guidance_rules(self) -> Dict[str, Dict[str, Any]]:
        """Load emotion-specific guidance rules."""
        return {
            "angry": {
                "severity": "high",
                "color": "#ff4444",
                "icon": "⚠️",
                "primary_guidance": "Stay calm and acknowledge their frustration",
                "response_strategies": [
                    "Listen without interrupting",
                    "Acknowledge their feelings: 'I understand this is frustrating'",
                    "Ask clarifying questions calmly",
                    "Avoid being defensive",
                    "Focus on solutions, not blame"
                ],
                "phrases_to_use": [
                    "I hear your concern...",
                    "Let's work together to resolve this...",
                    "I understand why you feel that way...",
                    "What would help make this better?"
                ],
                "phrases_to_avoid": [
                    "Calm down",
                    "You're overreacting",
                    "It's not a big deal",
                    "That's not true"
                ],
                "tone_guidance": "Keep voice calm and steady. Lower volume slightly. Speak slower than usual.",
                "body_language": "Maintain open posture. Avoid crossing arms. Keep steady eye contact."
            },
            
            "frustrated": {
                "severity": "medium",
                "color": "#ff8844",
                "icon": "😤",
                "primary_guidance": "Show empathy and help them find solutions",
                "response_strategies": [
                    "Validate their frustration",
                    "Ask what specific help they need",
                    "Break down the problem into smaller parts",
                    "Offer concrete assistance",
                    "Share similar experiences if relevant"
                ],
                "phrases_to_use": [
                    "That sounds challenging...",
                    "What can I do to help?",
                    "Let's tackle this together...",
                    "I've felt similar frustration when..."
                ],
                "phrases_to_avoid": [
                    "Just try harder",
                    "It's easy if you...",
                    "I don't see the problem"
                ],
                "tone_guidance": "Supportive and encouraging. Show energy and willingness to help.",
                "body_language": "Lean in slightly. Nod to show understanding."
            },
            
            "sad": {
                "severity": "medium",
                "color": "#4488ff",
                "icon": "😔",
                "primary_guidance": "Show compassion and provide emotional support",
                "response_strategies": [
                    "Express genuine concern",
                    "Listen actively without trying to 'fix' immediately",
                    "Validate their feelings",
                    "Offer presence and support",
                    "Ask if they want to talk about it"
                ],
                "phrases_to_use": [
                    "I'm here for you...",
                    "That must be really hard...",
                    "How are you holding up?",
                    "Is there anything I can do?"
                ],
                "phrases_to_avoid": [
                    "Look on the bright side",
                    "It could be worse",
                    "You'll get over it",
                    "Don't cry"
                ],
                "tone_guidance": "Soft and gentle. Slower pace. Warm and caring.",
                "body_language": "Gentle demeanor. Offer comfort if appropriate."
            },
            
            "happy": {
                "severity": "low",
                "color": "#44ff88",
                "icon": "😊",
                "primary_guidance": "Share in their joy and maintain positive energy",
                "response_strategies": [
                    "Show genuine enthusiasm",
                    "Ask them to share more",
                    "Celebrate their success",
                    "Build on the positive momentum",
                    "Express happiness for them"
                ],
                "phrases_to_use": [
                    "That's wonderful!",
                    "Tell me more about it!",
                    "I'm so happy for you!",
                    "You must be thrilled!"
                ],
                "phrases_to_avoid": [
                    "Don't get too excited",
                    "It's not that big a deal",
                    "Let's not celebrate yet"
                ],
                "tone_guidance": "Upbeat and enthusiastic. Match their energy level.",
                "body_language": "Smile genuinely. Open and animated gestures."
            },
            
            "excited": {
                "severity": "low",
                "color": "#ffaa44",
                "icon": "🎉",
                "primary_guidance": "Match their enthusiasm and encourage their passion",
                "response_strategies": [
                    "Show equal excitement",
                    "Ask engaging questions",
                    "Encourage them to continue",
                    "Share in their vision",
                    "Be an active listener"
                ],
                "phrases_to_use": [
                    "That's amazing!",
                    "I love your enthusiasm!",
                    "Tell me everything!",
                    "This sounds incredible!"
                ],
                "phrases_to_avoid": [
                    "Slow down",
                    "That's unrealistic",
                    "Let's be practical"
                ],
                "tone_guidance": "High energy. Quick pace. Animated voice.",
                "body_language": "Animated gestures. Forward-leaning posture."
            },
            
            "anxious": {
                "severity": "medium",
                "color": "#aa88ff",
                "icon": "😰",
                "primary_guidance": "Provide reassurance and help them feel secure",
                "response_strategies": [
                    "Acknowledge their concerns",
                    "Provide reassurance based on facts",
                    "Help them identify specific worries",
                    "Offer concrete next steps",
                    "Be patient and supportive"
                ],
                "phrases_to_use": [
                    "It's okay to feel anxious...",
                    "Let's work through this together...",
                    "What specifically worries you?",
                    "We'll figure this out..."
                ],
                "phrases_to_avoid": [
                    "There's nothing to worry about",
                    "Just relax",
                    "Stop overthinking"
                ],
                "tone_guidance": "Calm and steady. Reassuring. Not rushed.",
                "body_language": "Calm demeanor. Steady presence."
            },
            
            "confused": {
                "severity": "low",
                "color": "#8888ff",
                "icon": "🤔",
                "primary_guidance": "Clarify and explain patiently",
                "response_strategies": [
                    "Ask what they're unclear about",
                    "Explain step by step",
                    "Use examples and analogies",
                    "Check understanding frequently",
                    "Encourage questions"
                ],
                "phrases_to_use": [
                    "Let me clarify that...",
                    "Does this make sense?",
                    "Think of it like...",
                    "What part is unclear?"
                ],
                "phrases_to_avoid": [
                    "It's obvious",
                    "Everyone knows that",
                    "Pay attention"
                ],
                "tone_guidance": "Patient and clear. Slower pace. Emphasis on key points.",
                "body_language": "Open and approachable. Use visual aids if possible."
            },
            
            "confident": {
                "severity": "low",
                "color": "#ff88ff",
                "icon": "💪",
                "primary_guidance": "Support their confidence while staying grounded",
                "response_strategies": [
                    "Acknowledge their confidence",
                    "Ask thoughtful questions",
                    "Ensure they've considered all factors",
                    "Offer constructive perspectives",
                    "Support their decisions"
                ],
                "phrases_to_use": [
                    "You seem confident about this...",
                    "Have you considered...?",
                    "I appreciate your conviction...",
                    "What gives you this confidence?"
                ],
                "phrases_to_avoid": [
                    "You're being overconfident",
                    "That won't work",
                    "You'll fail"
                ],
                "tone_guidance": "Respectful and engaged. Professional.",
                "body_language": "Attentive. Respectful distance."
            },
            
            "neutral": {
                "severity": "none",
                "color": "#888888",
                "icon": "😐",
                "primary_guidance": "Maintain professional engagement",
                "response_strategies": [
                    "Stay focused on the topic",
                    "Ask clarifying questions",
                    "Provide relevant information",
                    "Maintain professional tone",
                    "Be clear and direct"
                ],
                "phrases_to_use": [
                    "To clarify...",
                    "Moving forward...",
                    "What are your thoughts on...?",
                    "Let's discuss..."
                ],
                "phrases_to_avoid": [],
                "tone_guidance": "Professional and clear. Moderate pace.",
                "body_language": "Professional posture. Appropriate eye contact."
            }
        }
    
    def _calculate_severity(self, emotion: str) -> str:
        """Calculate severity level for an emotion."""
        rules = self.guidance_rules.get(emotion, self.guidance_rules.get("neutral", {}))
        return rules.get("severity", "none")
    
    def _extract_suggestions(self, rules: Dict[str, Any]) -> List[str]:
        """Extract key suggestions from guidance rules."""
        suggestions = []
        if "primary_guidance" in rules:
            suggestions.append(rules["primary_guidance"])
        if "response_strategies" in rules:
            suggestions.extend(rules["response_strategies"][:2])  # Top 2 strategies
        return suggestions
    
    def _get_fallback_suggestions(self, emotion: str) -> Dict[str, Any]:
        """Get fallback guidance when OpenAI is unavailable or rate-limited."""
        emotion = emotion.lower()
        template = FALLBACK_GUIDANCE_TEMPLATES.get(emotion, FALLBACK_GUIDANCE_TEMPLATES["neutral"])
        
        return {
            "emotion": emotion,
            "severity": template["severity"],
            "suggestions": template["suggestions"],
            "source": "fallback_template",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_guidance(
        self,
        emotion: str,
        text: str,
        confidence: float,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Get real-time guidance for responding to a detected emotion.
        
        Args:
            emotion: Detected emotion
            text: The text that was spoken
            confidence: Confidence of emotion detection
            context: Additional context (speaker history, meeting topic, etc.)
            
        Returns:
            Comprehensive guidance dictionary
        """
        emotion = emotion.lower()
        context = context or {}
        
        # If fallback mode is enabled or OpenAI fails, use fallback templates
        if self.use_fallback:
            return self._get_fallback_suggestions(emotion)
        
        # Try to get guidance with retry logic
        from app.core.config import settings
        max_retries = settings.OPENAI_MAX_RETRIES
        retry_delay = settings.OPENAI_RETRY_DELAY
        
        for attempt in range(max_retries + 1):
            try:
                rules = self.guidance_rules.get(emotion, self.guidance_rules["neutral"])
                
                # Build guidance response
                guidance = {
                    "emotion": emotion,
                    "confidence": confidence,
                    "severity": rules["severity"],
                    "visual": {
                        "color": rules["color"],
                        "icon": rules["icon"]
                    },
                    "primary_guidance": rules["primary_guidance"],
                    "response_strategies": rules["response_strategies"],
                    "recommended_phrases": rules["phrases_to_use"],
                    "avoid_phrases": rules["phrases_to_avoid"],
                    "tone_guidance": rules["tone_guidance"],
                    "body_language": rules["body_language"],
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Add contextual enhancements
                if confidence < 0.5:
                    guidance["note"] = "Low confidence - use general supportive communication"
                
                if rules["severity"] == "high":
                    guidance["alert"] = True
                    guidance["alert_message"] = f"⚠️ High emotion detected. Proceed with extra care and empathy."
                
                # Add AI-generated specific response
                guidance["ai_suggested_response"] = self._generate_ai_response(
                    emotion, text, context
                )
                
                return guidance
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}")
                
                # On rate limit errors (429) or last attempt, use fallback
                if "429" in str(e) or attempt >= max_retries:
                    logger.warning(f"Using fallback guidance for {emotion}")
                    return self._get_fallback_suggestions(emotion)
                
                # Exponential backoff
                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
        
        # Final fallback
        return self._get_fallback_suggestions(emotion)
    
    def _generate_ai_response(
        self,
        emotion: str,
        text: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Generate a specific AI-powered response suggestion.
        In production, this could use GPT for more contextual responses.
        """
        # Simple template-based responses for now
        templates = {
            "angry": f"I understand this situation is frustrating. Let's work together to find a solution.",
            "frustrated": f"I can see this is challenging. How can I best support you right now?",
            "sad": f"I'm sorry you're going through this. I'm here to listen if you'd like to talk.",
            "happy": f"That's wonderful news! I'd love to hear more about it.",
            "excited": f"Your enthusiasm is contagious! Tell me more about this.",
            "anxious": f"I understand your concern. Let's go through this step by step together.",
            "confused": f"Let me help clarify that for you. Which part would you like me to explain?",
            "confident": f"I appreciate your confidence. Let's make sure we've covered all the bases.",
            "neutral": f"Thank you for sharing. What are your thoughts on the next steps?"
        }
        
        return templates.get(emotion, "I understand. Please continue.")
    
    def get_meeting_summary_guidance(
        self,
        emotion_timeline: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze emotion patterns throughout the meeting and provide summary guidance.
        
        Args:
            emotion_timeline: List of emotion events throughout meeting
            
        Returns:
            Summary guidance for the meeting
        """
        if not emotion_timeline:
            return {
                "status": "neutral",
                "message": "No significant emotional patterns detected",
                "recommendations": []
            }
        
        # Count emotions
        emotion_counts = {}
        high_severity_count = 0
        
        for event in emotion_timeline:
            emotion = event.get("emotion", "neutral")
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
            
            rules = self.guidance_rules.get(emotion, self.guidance_rules["neutral"])
            if rules["severity"] == "high":
                high_severity_count += 1
        
        # Determine overall meeting tone
        dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0] if emotion_counts else "neutral"
        
        # Build summary
        summary = {
            "dominant_emotion": dominant_emotion,
            "emotion_distribution": emotion_counts,
            "high_severity_moments": high_severity_count,
            "total_events": len(emotion_timeline)
        }
        
        # Generate recommendations
        recommendations = []
        
        if high_severity_count > len(emotion_timeline) * 0.2:  # >20% high severity
            recommendations.append({
                "level": "important",
                "message": "Multiple high-emotion moments detected. Consider follow-up conversations.",
                "action": "Schedule individual check-ins with participants"
            })
        
        if emotion_counts.get("frustrated", 0) > 3:
            recommendations.append({
                "level": "moderate",
                "message": "Frustration was expressed multiple times",
                "action": "Review blockers and provide additional support"
            })
        
        if emotion_counts.get("confused", 0) > 2:
            recommendations.append({
                "level": "moderate",
                "message": "Confusion detected multiple times",
                "action": "Send follow-up clarification and documentation"
            })
        
        summary["recommendations"] = recommendations
        summary["overall_assessment"] = self._assess_meeting_tone(emotion_counts, high_severity_count)
        
        return summary
    
    def _assess_meeting_tone(self, emotion_counts: Dict[str, int], high_severity: int) -> str:
        """Assess overall meeting tone."""
        total = sum(emotion_counts.values())
        
        if total == 0:
            return "Meeting had minimal emotional engagement"
        
        positive_emotions = emotion_counts.get("happy", 0) + emotion_counts.get("excited", 0) + emotion_counts.get("confident", 0)
        negative_emotions = emotion_counts.get("angry", 0) + emotion_counts.get("frustrated", 0) + emotion_counts.get("sad", 0)
        
        positive_ratio = positive_emotions / total
        negative_ratio = negative_emotions / total
        
        if high_severity > total * 0.3:
            return "Meeting had significant emotional challenges. Follow-up recommended."
        elif positive_ratio > 0.5:
            return "Meeting had predominantly positive tone. Good engagement."
        elif negative_ratio > 0.3:
            return "Meeting had some challenging moments. Monitor team morale."
        else:
            return "Meeting maintained balanced emotional tone."


# Singleton
_emotion_guidance_engine: Optional[EmotionGuidanceEngine] = None


def get_emotion_guidance_engine() -> EmotionGuidanceEngine:
    """Get singleton emotion guidance engine."""
    global _emotion_guidance_engine
    if _emotion_guidance_engine is None:
        _emotion_guidance_engine = EmotionGuidanceEngine()
    return _emotion_guidance_engine