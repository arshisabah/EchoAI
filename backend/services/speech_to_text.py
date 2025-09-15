"""
Real-time Speech-to-Text service for EchoAI.
Supports multiple ASR providers: OpenAI Whisper, Google Cloud STT, and Vosk (offline).
"""

import logging
import asyncio
import os
import json
import tempfile
import wave
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import uuid

import openai
import whisper
import vosk
import numpy as np
from google.cloud import speech
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

class ASRResult(BaseModel):
    """Speech recognition result"""
    text: str
    confidence: float
    language: Optional[str] = None
    words: Optional[List[Dict[str, Any]]] = None  # Word-level timestamps
    processing_time_ms: float = 0.0

class ASRProvider(ABC):
    """Abstract base class for ASR providers"""
    
    @abstractmethod
    async def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000) -> ASRResult:
        """Transcribe audio data to text"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is properly configured and available"""
        pass

class OpenAIWhisperProvider(ASRProvider):
    """OpenAI Whisper API provider"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "whisper-1"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = openai.AsyncOpenAI(api_key=self.api_key) if self.api_key else None
    
    def is_available(self) -> bool:
        return self.client is not None and self.api_key is not None
    
    async def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000) -> ASRResult:
        """Transcribe using OpenAI Whisper API"""
        if not self.is_available():
            raise ValueError("OpenAI Whisper not available - missing API key")
        
        start_time = datetime.now()
        
        try:
            # Save audio to temporary file (Whisper API requires file input)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                # Convert raw audio data to WAV format
                with wave.open(temp_file.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_data)
                
                # Transcribe using OpenAI API
                with open(temp_file.name, "rb") as audio_file:
                    transcript = await self.client.audio.transcriptions.create(
                        model=self.model,
                        file=audio_file,
                        response_format="verbose_json",
                        timestamp_granularities=["word"]
                    )
                
                # Clean up temp file
                os.unlink(temp_file.name)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Extract word-level timestamps if available
            words = []
            if hasattr(transcript, 'words') and transcript.words:
                words = [
                    {
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "confidence": getattr(word, 'confidence', 1.0)
                    }
                    for word in transcript.words
                ]
            
            return ASRResult(
                text=transcript.text.strip(),
                confidence=1.0,  # OpenAI doesn't provide confidence scores
                language=getattr(transcript, 'language', None),
                words=words,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            logger.error(f"OpenAI Whisper transcription error: {e}")
            raise

class GoogleCloudSTTProvider(ASRProvider):
    """Google Cloud Speech-to-Text provider"""
    
    def __init__(self, credentials_path: Optional[str] = None):
        self.credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.client = None
        
        if self.is_available():
            try:
                self.client = speech.SpeechClient()
            except Exception as e:
                logger.warning(f"Failed to initialize Google Cloud STT: {e}")
    
    def is_available(self) -> bool:
        return self.credentials_path is not None and os.path.exists(self.credentials_path)
    
    async def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000) -> ASRResult:
        """Transcribe using Google Cloud Speech-to-Text"""
        if not self.is_available() or not self.client:
            raise ValueError("Google Cloud STT not available - check credentials")
        
        start_time = datetime.now()
        
        try:
            # Configure recognition
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=sample_rate,
                language_code="en-US",
                enable_word_confidence=True,
                enable_word_time_offsets=True,
            )
            
            audio = speech.RecognitionAudio(content=audio_data)
            
            # Perform transcription
            response = self.client.recognize(config=config, audio=audio)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            if not response.results:
                return ASRResult(text="", confidence=0.0, processing_time_ms=processing_time)
            
            # Get best result
            result = response.results[0]
            alternative = result.alternatives[0]
            
            # Extract word-level information
            words = []
            if alternative.words:
                words = [
                    {
                        "word": word.word,
                        "start": word.start_time.total_seconds(),
                        "end": word.end_time.total_seconds(),
                        "confidence": word.confidence
                    }
                    for word in alternative.words
                ]
            
            return ASRResult(
                text=alternative.transcript.strip(),
                confidence=alternative.confidence,
                words=words,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            logger.error(f"Google Cloud STT error: {e}")
            raise

class VoskProvider(ASRProvider):
    """Vosk offline ASR provider"""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or os.getenv("VOSK_MODEL_PATH", "./models/vosk-model-en-us-0.22")
        self.model = None
        self.rec = None
        
        if self.is_available():
            try:
                self.model = vosk.Model(self.model_path)
            except Exception as e:
                logger.warning(f"Failed to load Vosk model: {e}")
    
    def is_available(self) -> bool:
        return os.path.exists(self.model_path) and self.model is not None
    
    async def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000) -> ASRResult:
        """Transcribe using Vosk offline recognition"""
        if not self.is_available():
            raise ValueError("Vosk not available - check model path")
        
        start_time = datetime.now()
        
        try:
            # Create recognizer for this session
            rec = vosk.KaldiRecognizer(self.model, sample_rate)
            rec.SetWords(True)  # Enable word-level results
            
            # Process audio data
            if rec.AcceptWaveform(audio_data):
                result_json = rec.Result()
            else:
                result_json = rec.PartialResult()
            
            result_data = json.loads(result_json)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Extract text and words
            text = result_data.get("text", "")
            words = []
            
            if "result" in result_data:
                words = [
                    {
                        "word": word["word"],
                        "start": word["start"],
                        "end": word["end"],
                        "confidence": word.get("conf", 1.0)
                    }
                    for word in result_data["result"]
                ]
            
            return ASRResult(
                text=text.strip(),
                confidence=result_data.get("confidence", 0.8),
                words=words,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            logger.error(f"Vosk transcription error: {e}")
            raise

class SpeechToTextService:
    """Main speech-to-text service with provider fallback"""
    
    def __init__(self):
        self.providers: Dict[str, ASRProvider] = {}
        self.primary_provider: Optional[str] = None
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available ASR providers"""
        # OpenAI Whisper
        whisper_provider = OpenAIWhisperProvider()
        if whisper_provider.is_available():
            self.providers["openai_whisper"] = whisper_provider
            if not self.primary_provider:
                self.primary_provider = "openai_whisper"
                logger.info("OpenAI Whisper initialized as primary provider")
        
        # Google Cloud STT
        google_provider = GoogleCloudSTTProvider()
        if google_provider.is_available():
            self.providers["google_stt"] = google_provider
            if not self.primary_provider:
                self.primary_provider = "google_stt"
                logger.info("Google Cloud STT initialized as primary provider")
        
        # Vosk (offline)
        vosk_provider = VoskProvider()
        if vosk_provider.is_available():
            self.providers["vosk"] = vosk_provider
            if not self.primary_provider:
                self.primary_provider = "vosk"
                logger.info("Vosk initialized as primary provider")
        
        if not self.providers:
            logger.warning("No ASR providers available!")
        else:
            logger.info(f"Available ASR providers: {list(self.providers.keys())}")
    
    async def transcribe(
        self, 
        audio_data: bytes, 
        sample_rate: int = 16000,
        preferred_provider: Optional[str] = None
    ) -> ASRResult:
        """
        Transcribe audio using available providers with fallback
        """
        if not self.providers:
            return ASRResult(text="No ASR providers available", confidence=0.0)
        
        # Determine provider to use
        provider_name = preferred_provider if preferred_provider in self.providers else self.primary_provider
        
        try:
            provider = self.providers[provider_name]
            result = await provider.transcribe_audio(audio_data, sample_rate)
            logger.info(f"Transcribed using {provider_name}: '{result.text[:50]}...'")
            return result
            
        except Exception as e:
            logger.error(f"Primary provider {provider_name} failed: {e}")
            
            # Try fallback providers
            for fallback_name, fallback_provider in self.providers.items():
                if fallback_name != provider_name:
                    try:
                        result = await fallback_provider.transcribe_audio(audio_data, sample_rate)
                        logger.info(f"Fallback transcription using {fallback_name}: '{result.text[:50]}...'")
                        return result
                    except Exception as fallback_error:
                        logger.error(f"Fallback provider {fallback_name} failed: {fallback_error}")
                        continue
            
            # All providers failed
            return ASRResult(text="Transcription failed", confidence=0.0)
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names"""
        return list(self.providers.keys())
    
    def set_primary_provider(self, provider_name: str) -> bool:
        """Set the primary ASR provider"""
        if provider_name in self.providers:
            self.primary_provider = provider_name
            logger.info(f"Primary ASR provider set to: {provider_name}")
            return True
        return False

# Global service instance
_stt_service = None

def get_stt_service() -> SpeechToTextService:
    """Get the global speech-to-text service instance"""
    global _stt_service
    if _stt_service is None:
        _stt_service = SpeechToTextService()
    return _stt_service

# Speaker identification utilities
def identify_speaker(audio_data: bytes, session_speakers: List[str]) -> str:
    """
    Basic speaker identification (placeholder for more advanced speaker diarization)
    In production, you'd use services like Amazon Transcribe, Google Cloud, or Pyannote
    """
    # Placeholder logic - in reality, you'd use speaker embeddings/diarization
    speaker_count = len(session_speakers)
    
    # Simple heuristic based on audio characteristics
    audio_hash = hash(audio_data) % 100
    
    if speaker_count == 0:
        return "Speaker_1"
    elif audio_hash > 70:  # New speaker detection heuristic
        return f"Speaker_{speaker_count + 1}"
    else:
        # Assign to existing speaker based on audio characteristics
        speaker_index = audio_hash % speaker_count
        return session_speakers[speaker_index]

async def process_audio_chunk(
    audio_data: bytes,
    session_id: str,
    sample_rate: int = 16000,
    session_speakers: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Process a single audio chunk and return transcript entry data
    """
    session_speakers = session_speakers or []
    
    try:
        # Get speech-to-text service
        stt_service = get_stt_service()
        
        # Transcribe audio
        asr_result = await stt_service.transcribe(audio_data, sample_rate)
        
        if not asr_result.text.strip():
            return None  # No speech detected
        
        # Identify speaker
        speaker = identify_speaker(audio_data, session_speakers)
        
        # Create transcript entry data
        entry_data = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "timestamp": datetime.now(),
            "text": asr_result.text,
            "speaker": speaker,
            "confidence": asr_result.confidence,
            "word_count": len(asr_result.text.split()),
            "processing_time_ms": asr_result.processing_time_ms,
            "words": asr_result.words
        }
        
        return entry_data
        
    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}")
        return None