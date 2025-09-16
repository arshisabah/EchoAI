# backend/services/transcription_service.py
"""
Real-time transcription service using WhisperX for multi-speaker meetings.
Handles overlapping speech, diarization, and word-level timestamps.
"""

import asyncio
import uuid
import logging
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
import torch
import numpy as np

import whisperx

from backend.models.registry import model_registry

logger = logging.getLogger(__name__)
logging.getLogger("asyncio").setLevel(logging.WARNING)


class ASRResult:
    """Normalized ASR result container."""
    def __init__(self, text="", confidence=1.0, words=None, processing_time_ms=0.0, speaker="Speaker_1"):
        self.text = text
        self.confidence = confidence
        self.words = words
        self.processing_time_ms = processing_time_ms
        self.speaker = speaker


class TranscriptionService:
    """Real-time multi-speaker transcription using WhisperX."""

    def __init__(self, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        self.device = device
        self.whisper_model = whisperx.load_model("medium", device=self.device)
        self.diar_model = whisperx.DiarizationPipeline(device=self.device)
        logger.info(f"WhisperX loaded on {self.device}")

    async def transcribe_chunk(self, audio_array: np.ndarray, session_id: str) -> List[ASRResult]:
        """
        Transcribe in-memory audio chunk (numpy array) and return ASRResult per speaker segment.
        """
        start_time = time.time()

        def _sync_transcribe():
            result = self.whisper_model.transcribe(audio_array)
            aligned_result = whisperx.align(result["segments"], self.diar_model, audio_array, device=self.device)
            return aligned_result["segments"]

        try:
            segments = await asyncio.to_thread(_sync_transcribe)
            results = []
            for seg in segments:
                results.append(
                    ASRResult(
                        text=seg.get("text", ""),
                        confidence=seg.get("confidence", 1.0),
                        words=seg.get("words"),
                        processing_time_ms=(time.time() - start_time) * 1000,
                        speaker=seg.get("speaker", "Speaker_1")
                    )
                )
            return results
        except Exception as e:
            logger.exception("WhisperX transcription failed: %s", e)
            return []


# ---------------- Singleton accessor ---------------- #
_transcription_service: Optional[TranscriptionService] = None


def get_transcription_service() -> TranscriptionService:
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = TranscriptionService()
    return _transcription_service


# ---------------- High-level helper for orchestrator ---------------- #
async def process_audio_chunk_whisperx(audio_array: np.ndarray, session_id: str) -> List[Dict[str, Any]]:
    """
    Returns list of dicts containing speaker-wise transcription data
    compatible with orchestrator_service.
    """
    service = get_transcription_service()
    segments = await service.transcribe_chunk(audio_array, session_id)

    processed_entries = []
    for seg in segments:
        if not seg.text.strip():
            continue
        processed_entries.append({
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "timestamp": datetime.utcnow(),
            "text": seg.text,
            "speaker": seg.speaker,
            "confidence": float(seg.confidence),
            "word_count": len(seg.text.split()),
            "processing_time_ms": float(seg.processing_time_ms),
            "words": seg.words
        })
    return processed_entries
