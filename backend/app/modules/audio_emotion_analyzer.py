# app/modules/audio_emotion_analyzer.py
"""
Audio-based emotion analysis using a pretrained Wav2Vec2-based classifier.
This uses a feature extractor (no tokenizer/vocab dependency) to avoid
'vocab_file = None' TypeError when loading audio-only models.
"""

import logging
import os
from typing import Dict, Any

import numpy as np
import torch

# Set HuggingFace to offline mode to avoid network errors when models aren't available
os.environ['HF_HUB_OFFLINE'] = '0'
os.environ['TRANSFORMERS_OFFLINE'] = '0'

from transformers import (
    Wav2Vec2ForSequenceClassification,
    Wav2Vec2FeatureExtractor,
    Wav2Vec2Processor,
    AutoConfig,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Enable debug logging for emotion analysis

# Model name (change if you have a different checkpoint)
_MODEL_NAME = "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"

# Detect device: MPS (Apple Silicon) > CUDA (NVIDIA) > CPU
if torch.cuda.is_available():
    _DEVICE = torch.device("cuda")
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    _DEVICE = torch.device("mps")
else:
    _DEVICE = torch.device("cpu")

logger.info(f"🎭 Loading emotion model on {_DEVICE}")

# Try to load a feature extractor (preferred for audio-only models)
_feature_extractor = None
_processor = None
_model = None
_MODEL_AVAILABLE = False

logger.debug(f"🔧 Attempting to load feature extractor for {_MODEL_NAME}")
try:
    _feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(_MODEL_NAME)
    logger.info("✅ Loaded Wav2Vec2FeatureExtractor.")
except Exception as exc:
    logger.warning(f"⚠️ Could not load Wav2Vec2FeatureExtractor: {exc}. Trying Wav2Vec2Processor...")
    try:
        _processor = Wav2Vec2Processor.from_pretrained(_MODEL_NAME)
        logger.info("✅ Loaded Wav2Vec2Processor.")
    except Exception as exc2:
        logger.warning(f"❌ Failed to load processor/feature_extractor for {_MODEL_NAME}: {exc2}. Emotion analysis will use fallback.")
        _feature_extractor = None
        _processor = None

# Load model only if processor/extractor was loaded
if _feature_extractor or _processor:
    logger.debug("🔧 Feature extractor/processor loaded, now loading model...")
    try:
        _model = Wav2Vec2ForSequenceClassification.from_pretrained(_MODEL_NAME)
        _model.to(_DEVICE)
        _model.eval()
        _MODEL_AVAILABLE = True
        logger.info("✅ Loaded Wav2Vec2ForSequenceClassification model successfully.")
        logger.info(f"✅ Audio emotion model is ready on {_DEVICE}")
    except Exception as exc:
        logger.warning(f"❌ Error loading model {_MODEL_NAME}: {exc}. Emotion analysis will use fallback.")
        _model = None
        _MODEL_AVAILABLE = False
else:
    logger.warning("⚠️ Audio emotion model not available. Using fallback emotion detection.")
    logger.warning("To enable audio emotion: pip install transformers torch")

# id2label mapping (only if model loaded)
_EMOTION_LABELS = {}
if _model and _MODEL_AVAILABLE:
    try:
        _EMOTION_LABELS = {int(k): v for k, v in _model.config.id2label.items()}
    except:
        _EMOTION_LABELS = {}

@torch.no_grad()
def analyze_audio_emotion(audio_array: np.ndarray, sample_rate: int = 16000) -> Dict[str, Any]:
    """
    Predict dominant emotion from audio.
    Args:
      audio_array: 1-D numpy array, float32 or int16. Mono audio expected.
      sample_rate: sampling rate of audio_array (default 16000)

    Returns:
      dict: {
        "emotion": str,
        "confidence": float,
        "scores": {label: score, ...}
      }
    """
    logger.debug(f"🎤 analyze_audio_emotion called - array shape: {audio_array.shape if audio_array is not None else 'None'}, sample_rate: {sample_rate}")
    
    # Basic validations & conversions
    if audio_array is None or len(audio_array) == 0:
        logger.debug("⚠️ Empty audio array, returning neutral")
        return {"emotion": "neutral", "confidence": 0.0, "scores": {}}

    # If model is not available, return fallback response
    if not _MODEL_AVAILABLE or _model is None:
        logger.debug("⚠️ Audio emotion model not available, using fallback.")
        return {
            "emotion": "neutral",
            "confidence": 0.5,
            "scores": {"neutral": 0.5, "happy": 0.2, "sad": 0.15, "angry": 0.1, "fearful": 0.05}
        }

    # Ensure numpy array and float32 values in [-1, 1] ideally
    audio = np.asarray(audio_array)

    # If audio dtype is integer (e.g., int16), convert to float32 in [-1,1]
    if np.issubdtype(audio.dtype, np.integer):
        max_val = np.iinfo(audio.dtype).max
        audio = audio.astype("float32") / float(max_val)
        logger.debug(f"🔧 Converted integer audio to float32")
    else:
        audio = audio.astype("float32")

    # If audio has multiple channels, average to mono
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
        logger.debug(f"🔧 Converted multi-channel audio to mono")

    try:
        logger.debug(f"🔧 Processing audio: {len(audio)} samples at {sample_rate}Hz")
        
        # Prepare inputs using feature_extractor or processor
        if _feature_extractor is not None:
            inputs = _feature_extractor(audio, sampling_rate=sample_rate, return_tensors="pt", padding=True)
            logger.debug("✅ Used feature_extractor for audio preprocessing")
        else:
            # processor contains feature extractor internally; use it as fallback
            inputs = _processor(audio, sampling_rate=sample_rate, return_tensors="pt", padding=True)
            logger.debug("✅ Used processor for audio preprocessing")

        # Move tensors to device
        inputs = {k: v.to(_DEVICE) for k, v in inputs.items()}

        # Forward pass
        logger.debug(f"🔧 Running model inference on {_DEVICE}")
        outputs = _model(**inputs)
        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)[0].cpu().numpy()

        pred_id = int(probs.argmax())
        emotion_label = _EMOTION_LABELS.get(pred_id, "unknown").lower().replace("_", " ")
        confidence = float(probs[pred_id])

        # Map labels to scores (make them human-friendly)
        scores = { _EMOTION_LABELS[i].lower().replace("_", " "): float(probs[i]) for i in range(len(probs)) }

        logger.info(f"✅ Audio emotion detected: {emotion_label} (confidence: {confidence:.2f})")
        logger.debug(f"   All scores: {scores}")
        
        return {"emotion": emotion_label, "confidence": confidence, "scores": scores}
    except Exception as e:
        logger.warning(f"❌ Error during emotion analysis: {e}. Using fallback.", exc_info=True)
        return {
            "emotion": "neutral",
            "confidence": 0.5,
            "scores": {"neutral": 0.5, "happy": 0.2, "sad": 0.15, "angry": 0.1, "fearful": 0.05}
        }

import atexit

def cleanup_emotion_model():
    """Clean up emotion model resources on shutdown."""
    global _model, _feature_extractor, _processor
    try:
        if _model is not None:
            del _model
        if _feature_extractor is not None:
            del _feature_extractor
        if _processor is not None:
            del _processor
        
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            torch.mps.empty_cache()
        logger.info("✅ Emotion model resources cleaned up")
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")

# Register cleanup
atexit.register(cleanup_emotion_model)