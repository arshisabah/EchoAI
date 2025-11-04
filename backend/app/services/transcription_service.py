"""
Real-time transcription service using WhisperX for multi-speaker meetings.
Handles overlapping speech, diarization, and word-level timestamps.
"""

import asyncio
import uuid
import logging
import time
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import torch
import numpy as np
import whisperx

from pyannote.audio import Pipeline
from app.models.registry import model_registry

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
        self.hf_token = os.getenv("HUGGINGFACE_TOKEN")

        # ✅ Load Whisper model safely (float32 for CPU compatibility)
        logger.info(f"Loading WhisperX model on {self.device} (float32 mode)...")
        self.whisper_model = whisperx.load_model("medium", device=self.device, compute_type="float32")

        # ✅ Load diarization pipeline (with fallback)
        self.diar_model = None
        try:
            from whisperx.diarize import DiarizationPipeline
            if self.hf_token:
                logger.info("Loading diarization with Hugging Face token...")
                self.diar_model = DiarizationPipeline.from_pretrained(
                    "pyannote/speaker-diarization",
                    use_auth_token=self.hf_token,
                    device=self.device
                )
            else:
                logger.warning("No HUGGINGFACE_TOKEN found — attempting diarization without authentication.")
                self.diar_model = DiarizationPipeline.from_pretrained(
                    "pyannote/speaker-diarization",
                    device=self.device
                )
        except Exception as e:
            logger.warning(f"Falling back to direct PyAnnote diarization: {e}")
            try:
                if self.hf_token:
                    self.diar_model = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization@2.1",
                        use_auth_token=self.hf_token
                    ).to(self.device)
                else:
                    logger.warning("No HUGGINGFACE_TOKEN — loading PyAnnote without authentication.")
                    self.diar_model = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization@2.1"
                    ).to(self.device)
            except Exception as e2:
                logger.error(f"⚠️ Diarization completely disabled: {e2}")
                self.diar_model = None

        logger.info(f"WhisperX loaded successfully on {self.device}")

    async def transcribe_chunk(self, audio_array: np.ndarray, session_id: str) -> List[ASRResult]:
        """
        Transcribe in-memory audio chunk (numpy array) and return ASRResult per speaker segment.
        """
        start_time = time.time()

        def _sync_transcribe():
            # Step 1: ASR
            result = self.whisper_model.transcribe(audio_array)

            # Step 2: Optional diarization
            if self.diar_model:
                try:
                    diarization = self.diar_model(audio_array)
                    aligned_result = whisperx.align(result["segments"], diarization, audio_array, device=self.device)
                    segments = aligned_result["segments"]
                except Exception as e:
                    logger.warning(f"Diarization alignment failed, using ASR only: {e}")
                    segments = result["segments"]
            else:
                segments = result["segments"]

            return segments

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
