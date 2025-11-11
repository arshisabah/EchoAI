# app/modules/audio_emotion_analyzer.py
"""
Audio-based emotion analysis using a pretrained Wav2Vec2-based classifier.
This uses a feature extractor (no tokenizer/vocab dependency) to avoid
'vocab_file = None' TypeError when loading audio-only models.
"""

import logging
from typing import Dict, Any

import numpy as np
import torch
from transformers import (
    Wav2Vec2ForSequenceClassification,
    Wav2Vec2FeatureExtractor,
    Wav2Vec2Processor,
    AutoConfig,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Model name (change if you have a different checkpoint)
_MODEL_NAME = "superb/wav2vec2-base-superb-er"

# device
_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f"Loading audio emotion model {_MODEL_NAME} on device {_DEVICE}")

# Try to load a feature extractor (preferred for audio-only models)
_feature_extractor = None
_processor = None
_model = None

try:
    _feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(_MODEL_NAME)
    logger.info("Loaded Wav2Vec2FeatureExtractor.")
except Exception as exc:
    logger.warning(f"Could not load Wav2Vec2FeatureExtractor: {exc}. Trying Wav2Vec2Processor...")
    try:
        _processor = Wav2Vec2Processor.from_pretrained(_MODEL_NAME)
        logger.info("Loaded Wav2Vec2Processor.")
    except Exception as exc2:
        logger.error(f"Failed to load processor/feature_extractor for {_MODEL_NAME}: {exc2}")
        raise

# Load model
try:
    _model = Wav2Vec2ForSequenceClassification.from_pretrained(_MODEL_NAME)
    _model.to(_DEVICE)
    _model.eval()
    logger.info("Loaded Wav2Vec2ForSequenceClassification model.")
except Exception as exc:
    logger.exception(f"Error loading model {_MODEL_NAME}: {exc}")
    raise

# id2label mapping
_EMOTION_LABELS = {int(k): v for k, v in _model.config.id2label.items()}

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
    # Basic validations & conversions
    if audio_array is None or len(audio_array) == 0:
        return {"emotion": "neutral", "confidence": 0.0, "scores": {}}

    # Ensure numpy array and float32 values in [-1, 1] ideally
    audio = np.asarray(audio_array)

    # If audio dtype is integer (e.g., int16), convert to float32 in [-1,1]
    if np.issubdtype(audio.dtype, np.integer):
        max_val = np.iinfo(audio.dtype).max
        audio = audio.astype("float32") / float(max_val)
    else:
        audio = audio.astype("float32")

    # If audio has multiple channels, average to mono
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    # Prepare inputs using feature_extractor or processor
    if _feature_extractor is not None:
        inputs = _feature_extractor(audio, sampling_rate=sample_rate, return_tensors="pt", padding=True)
    else:
        # processor contains feature extractor internally; use it as fallback
        inputs = _processor(audio, sampling_rate=sample_rate, return_tensors="pt", padding=True)

    # Move tensors to device
    inputs = {k: v.to(_DEVICE) for k, v in inputs.items()}

    # Forward pass
    outputs = _model(**inputs)
    logits = outputs.logits
    probs = torch.softmax(logits, dim=-1)[0].cpu().numpy()

    pred_id = int(probs.argmax())
    emotion_label = _EMOTION_LABELS.get(pred_id, "unknown").lower().replace("_", " ")
    confidence = float(probs[pred_id])

    # Map labels to scores (make them human-friendly)
    scores = { _EMOTION_LABELS[i].lower().replace("_", " "): float(probs[i]) for i in range(len(probs)) }

    return {"emotion": emotion_label, "confidence": confidence, "scores": scores}
