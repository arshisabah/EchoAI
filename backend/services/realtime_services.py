# backend/services/realtime_services.py
import asyncio
import io
import numpy as np
import whisper
import librosa
from transformers import (
    Wav2Vec2Processor, Wav2Vec2ForSequenceClassification,
    AutoTokenizer, AutoModelForSequenceClassification
)
import torch
import json
from typing import Dict, List, Optional
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealTimeTranscriptionService:
    def __init__(self):
        self.whisper_model = None
        self.emotion_processor = None
        self.emotion_model = None
        self.sentiment_tokenizer = None
        self.sentiment_model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.audio_buffer = []
        self.sample_rate = 16000
        self.chunk_duration = 3  # seconds
        self.load_models()
    
    def load_models(self):
        """Load all AI models"""
        try:
            logger.info("Loading Whisper model...")
            self.whisper_model = whisper.load_model("base")
            
            logger.info("Loading emotion detection model...")
            self.emotion_processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base")
            self.emotion_model = Wav2Vec2ForSequenceClassification.from_pretrained(
                "harshit345/xlsr-wav2vec-speech-emotion-recognition"
            )
            self.emotion_model.to(self.device)
            
            logger.info("Loading sentiment analysis model...")
            self.sentiment_tokenizer = AutoTokenizer.from_pretrained(
                "cardiffnlp/twitter-roberta-base-sentiment-latest"
            )
            self.sentiment_model = AutoModelForSequenceClassification.from_pretrained(
                "cardiffnlp/twitter-roberta-base-sentiment-latest"
            )
            self.sentiment_model.to(self.device)
            
            logger.info("All models loaded successfully!")
            
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            raise e
    
    async def process_audio_chunk(self, audio_data: bytes) -> Dict:
        """Process audio chunk and return transcription with analysis"""
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            
            # Ensure minimum length for processing
            if len(audio_array) < self.sample_rate * 0.5:  # Less than 0.5 seconds
                return {"status": "too_short"}
            
            # Transcription
            transcript = await self.transcribe_audio(audio_array)
            if not transcript or transcript.strip() == "":
                return {"status": "no_speech"}
            
            # Emotion detection
            emotion = await self.detect_emotion(audio_array)
            
            # Sentiment analysis
            sentiment = await self.analyze_sentiment(transcript)
            
            result = {
                "status": "success",
                "transcript": transcript,
                "emotion": emotion,
                "sentiment": sentiment,
                "timestamp": datetime.now().isoformat(),
                "confidence": 0.85  # You can implement actual confidence scoring
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            return {"status": "error", "message": str(e)}
    
    async def transcribe_audio(self, audio_array: np.ndarray) -> str:
        """Transcribe audio using Whisper"""
        try:
            # Whisper expects audio at 16kHz
            if len(audio_array) > 0:
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    lambda: self.whisper_model.transcribe(audio_array)
                )
                return result["text"].strip()
            return ""
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
    
    async def detect_emotion(self, audio_array: np.ndarray) -> Dict:
        """Detect emotion from audio"""
        try:
            # Resample if needed
            if len(audio_array) > 0:
                # Process with Wav2Vec2
                inputs = self.emotion_processor(
                    audio_array, 
                    sampling_rate=self.sample_rate, 
                    return_tensors="pt",
                    padding=True
                )
                
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    outputs = self.emotion_model(**inputs)
                    predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
                
                # Emotion labels (adjust based on your model)
                emotions = ["angry", "calm", "disgust", "fearful", "happy", "neutral", "sad", "surprised"]
                
                # Get top emotion
                emotion_id = predictions.argmax().item()
                confidence = predictions[0][emotion_id].item()
                
                return {
                    "emotion": emotions[emotion_id] if emotion_id < len(emotions) else "neutral",
                    "confidence": float(confidence),
                    "all_emotions": {emotions[i]: float(predictions[0][i]) for i in range(len(emotions[:len(predictions[0])]))}
                }
        except Exception as e:
            logger.error(f"Emotion detection error: {e}")
            return {"emotion": "neutral", "confidence": 0.0}
    
    async def analyze_sentiment(self, text: str) -> Dict:
        """Analyze sentiment from text"""
        try:
            if not text.strip():
                return {"sentiment": "neutral", "confidence": 0.0}
            
            inputs = self.sentiment_tokenizer(
                text, 
                return_tensors="pt", 
                truncation=True, 
                padding=True,
                max_length=512
            )
            
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.sentiment_model(**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            
            # Sentiment labels
            sentiments = ["NEGATIVE", "NEUTRAL", "POSITIVE"]
            
            sentiment_id = predictions.argmax().item()
            confidence = predictions[0][sentiment_id].item()
            
            return {
                "sentiment": sentiments[sentiment_id],
                "confidence": float(confidence),
                "scores": {
                    "negative": float(predictions[0][0]),
                    "neutral": float(predictions[0][1]),
                    "positive": float(predictions[0][2])
                }
            }
            
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {"sentiment": "neutral", "confidence": 0.0}

class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.transcriptions = {}
    
    def create_session(self, meeting_id: str) -> Dict:
        """Create a new meeting session"""
        self.sessions[meeting_id] = {
            "created_at": datetime.now(),
            "status": "active",
            "participants": [],
            "total_chunks": 0
        }
        self.transcriptions[meeting_id] = []
        return {"status": "created", "meeting_id": meeting_id}
    
    def add_transcription(self, meeting_id: str, transcription_data: Dict):
        """Add transcription to session"""
        if meeting_id not in self.transcriptions:
            self.transcriptions[meeting_id] = []
        
        self.transcriptions[meeting_id].append(transcription_data)
        self.sessions[meeting_id]["total_chunks"] += 1
    
    def get_session_data(self, meeting_id: str) -> Dict:
        """Get complete session data"""
        if meeting_id not in self.sessions:
            return {"error": "Session not found"}
        
        return {
            "session_info": self.sessions[meeting_id],
            "transcriptions": self.transcriptions.get(meeting_id, []),
            "summary": self.generate_quick_summary(meeting_id)
        }
    
    def generate_quick_summary(self, meeting_id: str) -> Dict:
        """Generate quick summary of the session"""
        if meeting_id not in self.transcriptions:
            return {}
        
        transcripts = self.transcriptions[meeting_id]
        if not transcripts:
            return {}
        
        # Basic analytics
        total_words = sum(len(t.get("transcript", "").split()) for t in transcripts)
        emotions = [t.get("emotion", {}).get("emotion", "neutral") for t in transcripts]
        sentiments = [t.get("sentiment", {}).get("sentiment", "neutral") for t in transcripts]
        
        # Count occurrences
        emotion_counts = {}
        for emotion in emotions:
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        sentiment_counts = {}
        for sentiment in sentiments:
            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
        
        return {
            "total_words": total_words,
            "total_segments": len(transcripts),
            "dominant_emotion": max(emotion_counts, key=emotion_counts.get) if emotion_counts else "neutral",
            "dominant_sentiment": max(sentiment_counts, key=sentiment_counts.get) if sentiment_counts else "neutral",
            "emotion_distribution": emotion_counts,
            "sentiment_distribution": sentiment_counts
        }

# Global instances
transcription_service = RealTimeTranscriptionService()
session_manager = SessionManager()