# app/services/emotion_guidance.py
"""
Emotion Guidance Engine for EchoAI - Provides contextual guidance based on detected emotions.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class EmotionGuidanceEngine:
    """
    Provides contextual guidance and recommendations based on detected emotions.
    Helps users respond appropriately to emotional states in conversations.
    """

    def __init__(self):
        self.guidance_templates = {
            "happy": {
                "suggestion": "Great energy! Keep the positive momentum going.",
                "tips": [
                    "Build on this positive moment",
                    "Share your enthusiasm with others",
                    "Acknowledge what's working well"
                ],
                "tone": "encouraging"
            },
            "excited": {
                "suggestion": "Channel this excitement productively.",
                "tips": [
                    "Maintain enthusiasm while staying focused",
                    "Share your excitement to motivate others",
                    "Take action while energy is high"
                ],
                "tone": "energetic"
            },
            "confident": {
                "suggestion": "Your confidence is showing through.",
                "tips": [
                    "Use this confidence to lead discussions",
                    "Be decisive and clear in your points",
                    "Inspire confidence in others"
                ],
                "tone": "assertive"
            },
            "sad": {
                "suggestion": "It's okay to feel this way. Consider taking a moment.",
                "tips": [
                    "Take a brief pause if needed",
                    "Share your concerns openly",
                    "Ask for support from the team"
                ],
                "tone": "supportive"
            },
            "frustrated": {
                "suggestion": "Let's address what's causing frustration.",
                "tips": [
                    "Identify the specific issue clearly",
                    "Suggest constructive solutions",
                    "Take a short break if needed"
                ],
                "tone": "problem-solving"
            },
            "angry": {
                "suggestion": "Take a moment to cool down before responding.",
                "tips": [
                    "Pause before speaking",
                    "Focus on facts, not emotions",
                    "Consider taking a short break"
                ],
                "tone": "calming"
            },
            "confused": {
                "suggestion": "Don't hesitate to ask for clarification.",
                "tips": [
                    "Ask specific questions",
                    "Request examples or clarification",
                    "Summarize your understanding"
                ],
                "tone": "clarifying"
            },
            "anxious": {
                "suggestion": "Take a breath. You've got this.",
                "tips": [
                    "Break down concerns into smaller parts",
                    "Focus on what you can control",
                    "Ask for support if needed"
                ],
                "tone": "reassuring"
            },
            "disappointed": {
                "suggestion": "Acknowledge the disappointment and move forward.",
                "tips": [
                    "Express your concerns constructively",
                    "Focus on next steps",
                    "Learn from this experience"
                ],
                "tone": "constructive"
            },
            "surprised": {
                "suggestion": "Take a moment to process this new information.",
                "tips": [
                    "Ask follow-up questions",
                    "Consider implications carefully",
                    "Share your perspective"
                ],
                "tone": "inquisitive"
            },
            "bored": {
                "suggestion": "Re-engage with the conversation.",
                "tips": [
                    "Ask questions to increase engagement",
                    "Suggest new topics or approaches",
                    "Take an active role in discussion"
                ],
                "tone": "engaging"
            },
            "neutral": {
                "suggestion": "Keep the conversation flowing naturally.",
                "tips": [
                    "Stay engaged and attentive",
                    "Contribute your thoughts",
                    "Listen actively to others"
                ],
                "tone": "balanced"
            }
        }
        logger.info("✅ EmotionGuidanceEngine initialized")

    def get_guidance(
        self,
        emotion: str,
        text: str = "",
        confidence: float = 0.0,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get contextual guidance based on detected emotion.

        Args:
            emotion: The detected emotion label
            text: The text that was analyzed
            confidence: Confidence score of emotion detection (0-1)
            context: Additional context (username, room_id, speaker, etc.)

        Returns:
            dict: Guidance information including suggestion, tips, and tone
        """
        context = context or {}
        username = context.get("username", "User")
        
        logger.debug(f"🎯 Generating guidance for emotion: {emotion} (confidence: {confidence:.2f})")
        
        # Get base guidance template
        template = self.guidance_templates.get(emotion, self.guidance_templates["neutral"])
        
        # Adjust guidance based on confidence
        if confidence < 0.5:
            # Low confidence - provide general guidance
            suggestion = f"Emotion unclear. {template['suggestion']}"
        else:
            suggestion = template["suggestion"]
        
        # Add context-specific customization
        if emotion in ["frustrated", "angry"] and "problem" in text.lower():
            suggestion = "It seems there's a specific issue. Let's work through it together."
        elif emotion == "confused" and "?" in text:
            suggestion = "You have questions. Let's clarify things step by step."
        elif emotion == "excited" and confidence > 0.8:
            suggestion = "Your enthusiasm is contagious! Share your ideas."
        
        guidance = {
            "emotion": emotion,
            "confidence": confidence,
            "suggestion": suggestion,
            "primary_guidance": suggestion,  # ✅ Add field that frontend expects
            "recommended_phrases": template["tips"][:3],  # ✅ Frontend expects this field
            "response_strategies": template["tips"],  # ✅ Frontend expects this field
            "tips": template["tips"],
            "tone": template["tone"],
            "timestamp": datetime.utcnow().isoformat(),
            "context": {
                "username": username,
                "text_preview": text[:50] + "..." if len(text) > 50 else text
            }
        }
        
        logger.info(f"✅ Guidance generated: {suggestion}")
        return guidance

    def get_session_guidance(
        self,
        emotion_timeline: list,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze emotional trends over a session and provide overall guidance.

        Args:
            emotion_timeline: List of emotion detections with timestamps
            context: Additional context

        Returns:
            dict: Session-level guidance and recommendations
        """
        if not emotion_timeline:
            return {
                "overall_tone": "neutral",
                "trends": [],
                "recommendations": ["Continue engaging naturally"]
            }

        # Count emotion frequencies
        emotion_counts = {}
        for entry in emotion_timeline:
            emotion = entry.get("emotion", "neutral")
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

        # Determine dominant emotion
        dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0]
        
        # Identify trends
        trends = []
        if emotion_counts.get("frustrated", 0) > 2:
            trends.append("Multiple instances of frustration detected")
        if emotion_counts.get("confused", 0) > 2:
            trends.append("Confusion appears multiple times - may need clarification")
        if emotion_counts.get("happy", 0) + emotion_counts.get("excited", 0) > len(emotion_timeline) * 0.6:
            trends.append("Predominantly positive emotional state")

        # Generate recommendations
        recommendations = []
        if "frustrated" in emotion_counts:
            recommendations.append("Address sources of frustration proactively")
        if "confused" in emotion_counts:
            recommendations.append("Provide clear explanations and check for understanding")
        if dominant_emotion in ["happy", "excited", "confident"]:
            recommendations.append("Leverage positive energy for productive outcomes")
        
        return {
            "overall_tone": dominant_emotion,
            "emotion_distribution": emotion_counts,
            "trends": trends,
            "recommendations": recommendations,
            "total_entries": len(emotion_timeline)
        }


# Singleton instance
_emotion_guidance_engine: Optional[EmotionGuidanceEngine] = None


def get_emotion_guidance_engine() -> EmotionGuidanceEngine:
    """Get or create the emotion guidance engine singleton."""
    global _emotion_guidance_engine
    if _emotion_guidance_engine is None:
        _emotion_guidance_engine = EmotionGuidanceEngine()
    return _emotion_guidance_engine
