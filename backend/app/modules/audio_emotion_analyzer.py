# app/modules/audio_emotion_analyzer.py
"""
Audio-based emotion analysis using Wav2Vec2 or any pretrained model.
"""

import torch
import numpy as np
from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2Processor

# Load model once at import (fast and memory-safe)
_MODEL_NAME = "superb/wav2vec2-base-superb-er"
_processor = Wav2Vec2Processor.from_pretrained(_MODEL_NAME)
_model = Wav2Vec2ForSequenceClassification.from_pretrained(_MODEL_NAME)
_model.eval()

_EMOTION_LABELS = _model.config.id2label


@torch.no_grad()
def analyze_audio_emotion(audio_array: np.ndarray, sample_rate: int = 16000):
    """
    Predict dominant emotion from audio.
    Returns: {'emotion': str, 'confidence': float}
    """
    if len(audio_array) == 0:
        return {"emotion": "neutral", "confidence": 0.0}

    # Convert to tensor
    inputs = _processor(audio_array, sampling_rate=sample_rate, return_tensors="pt", padding=True)
    logits = _model(**inputs).logits
    probs = torch.softmax(logits, dim=-1)[0]
    pred_id = int(torch.argmax(probs))
    emotion = _EMOTION_LABELS[pred_id].lower().replace("_", " ")
    confidence = float(probs[pred_id])

    return {"emotion": emotion, "confidence": confidence, "scores": { _EMOTION_LABELS[i]: float(p) for i, p in enumerate(probs) }}
