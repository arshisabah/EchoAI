# app/services/transcription_service.py
"""
Fixed production-ready transcription service with multiple backends.
"""

import asyncio
import uuid
import logging
import time
import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import torch
import numpy as np

logger = logging.getLogger(__name__)


class ASRResult:
    """Normalized ASR result."""
    def __init__(self, text="", confidence=1.0, words=None, processing_time_ms=0.0, speaker="Speaker_1"):
        self.text = text
        self.confidence = confidence
        self.words = words or []
        self.processing_time_ms = processing_time_ms
        self.speaker = speaker


class TranscriptionService:
    """Production transcription service with multiple backends."""

    def __init__(self, device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.model_type = "none"
        
        self._initialize_models()

    def _initialize_models(self):
        """Initialize available transcription models."""
        # Try OpenAI Whisper API first (most reliable)
        if os.getenv("OPENAI_API_KEY"):
            self.model_type = "openai_api"
            logger.info("✅ Using OpenAI Whisper API")
            return
        
        # Try WhisperX
        try:
            import whisperx
            logger.info("Loading WhisperX model...")
            self.model = whisperx.load_model(
                "base", 
                device=self.device, 
                compute_type="float32" if self.device == "cpu" else "float16"
            )
            self.model_type = "whisperx"
            logger.info(f"✅ WhisperX loaded on {self.device}")
            return
        except Exception as e:
            logger.warning(f"WhisperX not available: {e}")

        # Fallback to standard Whisper
        try:
            import whisper
            logger.info("Loading standard Whisper model...")
            self.model = whisper.load_model("base", device=self.device)
            self.model_type = "whisper"
            logger.info(f"✅ Standard Whisper loaded on {self.device}")
            return
        except Exception as e:
            logger.warning(f"Standard Whisper not available: {e}")

        logger.error("❌ No transcription models available!")

    async def transcribe_chunk(
        self, 
        audio_array: np.ndarray, 
        session_id: str,
        sample_rate: int = 16000
    ) -> List[ASRResult]:
        """Transcribe audio chunk and return results."""
        
        if len(audio_array) == 0:
            return []

        start_time = time.time()

        # Route to appropriate method
        if self.model_type == "openai_api":
            return await self._transcribe_openai_api(audio_array, sample_rate, start_time)
        elif self.model_type == "whisperx":
            return await self._transcribe_whisperx(audio_array, start_time)
        elif self.model_type == "whisper":
            return await self._transcribe_whisper(audio_array, start_time)
        else:
            logger.error("No transcription backend available")
            return []

    async def _transcribe_openai_api(
        self, 
        audio_array: np.ndarray, 
        sample_rate: int,
        start_time: float
    ) -> List[ASRResult]:
        """Transcribe using OpenAI Whisper API."""
        try:
            from openai import AsyncOpenAI
            from app.core.config import settings
            import io
            import soundfile as sf

            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            # Convert numpy array to audio file bytes
            audio_io = io.BytesIO()
            sf.write(audio_io, audio_array, sample_rate, format='WAV')
            audio_io.seek(0)
            audio_io.name = "audio.wav"

            # Call OpenAI API
            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_io,
                response_format="verbose_json",
                language="en"
            )

            text = response.text.strip()

            if not text:
                return []

            # Extract words with timestamps if available
            words = []
            if hasattr(response, 'words') and response.words:
                words = [
                    {
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "confidence": 1.0
                    }
                    for word in response.words
                ]

            return [ASRResult(
                text=text,
                confidence=1.0,
                words=words,
                processing_time_ms=(time.time() - start_time) * 1000,
                speaker="Speaker_1"
            )]
        except Exception as e:
            logger.error(f"OpenAI API transcription failed: {e}")
            return []

    async def _transcribe_whisperx(
        self, 
        audio_array: np.ndarray, 
        start_time: float
    ) -> List[ASRResult]:
        """Transcribe using WhisperX."""
        def _sync_transcribe():
            result = self.model.transcribe(audio_array)
            return result.get("segments", [])

        try:
            segments = await asyncio.to_thread(_sync_transcribe)
            results = []
            
            for seg in segments:
                text = seg.get("text", "").strip()
                if not text:
                    continue
                    
                results.append(ASRResult(
                    text=text,
                    confidence=seg.get("confidence", 1.0),
                    words=seg.get("words"),
                    processing_time_ms=(time.time() - start_time) * 1000,
                    speaker=seg.get("speaker", "Speaker_1")
                ))
            
            return results
        except Exception as e:
            logger.error(f"WhisperX transcription failed: {e}")
            return []

    async def _transcribe_whisper(
        self, 
        audio_array: np.ndarray, 
        start_time: float
    ) -> List[ASRResult]:
        """Transcribe using standard Whisper."""
        def _sync_transcribe():
            result = self.model.transcribe(
                audio_array,
                fp16=(self.device == "cuda"),
                language="en"
            )
            return result

        try:
            result = await asyncio.to_thread(_sync_transcribe)
            text = result.get("text", "").strip()
            
            if not text:
                return []

            return [ASRResult(
                text=text,
                confidence=1.0,
                words=[],
                processing_time_ms=(time.time() - start_time) * 1000,
                speaker="Speaker_1"
            )]
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return []


# Singleton
_transcription_service: Optional[TranscriptionService] = None


def get_transcription_service() -> TranscriptionService:
    """Get singleton transcription service."""
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = TranscriptionService()
    return _transcription_service


async def process_audio_chunk(
    audio_bytes: bytes,
    session_id: str,
    sample_rate: int = 16000
) -> List[Dict[str, Any]]:
    """
    High-level function to process audio chunk.
    Returns list of transcript entries.
    """
    from app.services.audio_utils import bytes_to_numpy
    
    try:
        # Convert bytes to numpy
        audio_array, actual_sr = bytes_to_numpy(audio_bytes, sample_rate)
        
        if len(audio_array) == 0:
            return []

        # Transcribe
        service = get_transcription_service()
        segments = await service.transcribe_chunk(audio_array, session_id, actual_sr)

        # Convert to dict format
        processed_entries = []
        for seg in segments:
            if not seg.text.strip():
                continue

            processed_entries.append({
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "text": seg.text,
                "speaker": seg.speaker,
                "confidence": float(seg.confidence),
                "word_count": len(seg.text.split()),
                "processing_time_ms": float(seg.processing_time_ms),
                "words": seg.words
            })

        return processed_entries

    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}")
        return []