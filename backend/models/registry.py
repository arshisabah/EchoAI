#backend/models/registry.py
"""
Central Model Registry for the EchoAI Application.

This module is responsible for:
1.  Loading all required AI models at application startup.
2.  Storing the loaded models in a central, easily accessible location.
3.  Handling model loading errors gracefully to prevent application crashes.
"""

import logging
from typing import Dict, Any

# Import the central configuration
from backend.core.config import settings

# Import the individual model loader functions
from .whisper_loader import load_whisper_model
from .diarization_loader import load_diarization_pipeline
from .emotion_loader import load_emotion_model
from .summarizer_loader import load_summarizer_model
from .bias_loader import load_bias_model

logger = logging.getLogger(__name__)

class ModelRegistry:
    """
    A central singleton class to load, manage, and provide access to all AI models.
    """
    def __init__(self):
        self.models: Dict[str, Any] = {}

    def load_all_models(self):
        """
        Orchestrates the loading of all AI models required for the application.
        This method is designed to be called once at application startup.
        """
        logger.info("Initializing Model Registry: Loading all AI models...")

        # --- 1. Whisper Model (for Transcription) ---
        try:
            whisper_model = load_whisper_model(model_name="base")
            if whisper_model:
                self.models["whisper"] = whisper_model
            else:
                raise RuntimeError("Whisper model failed to load.")
        except Exception as e:
            logger.error(f"❌ Critical error loading Whisper model: {e}", exc_info=True)
            # You might decide to exit the app if a critical model fails
            # raise SystemExit("Critical model 'Whisper' failed to load. Exiting.")

        # --- 2. Diarization Pipeline (for Speaker Identification) ---
        try:
            # The auth token is fetched from our central settings
            diarization_pipeline = load_diarization_pipeline(
                auth_token=settings.HUGGING_FACE_TOKEN
            )
            if diarization_pipeline:
                self.models["diarization"] = diarization_pipeline
            else:
                # This is not critical, so we'll just log a warning
                logger.warning("Diarization pipeline is not available.")
        except Exception as e:
            logger.error(f"Error loading Diarization pipeline: {e}", exc_info=True)

        # --- 3. Emotion Model (Wav2Vec2 for Audio Emotion) ---
        try:
            emotion_processor, emotion_model = load_emotion_model()
            if emotion_processor and emotion_model:
                self.models["emotion"] = {
                    "processor": emotion_processor,
                    "model": emotion_model
                }
            else:
                logger.warning("Emotion detection model is not available.")
        except Exception as e:
            logger.error(f"Error loading Emotion Detection model: {e}", exc_info=True)

        # --- 4. Summarizer Model (BART for Text Summarization) ---
        try:
            summarizer_pipeline = load_summarizer_model()
            if summarizer_pipeline:
                self.models["summarizer"] = summarizer_pipeline
            else:
                logger.warning("Summarization model is not available.")
        except Exception as e:
            logger.error(f"Error loading Summarization model: {e}", exc_info=True)

        # --- 5. Bias Model (BERT for Bias Detection) ---
        try:
            bias_tokenizer, bias_model = load_bias_model()
            if bias_tokenizer and bias_model:
                self.models["bias"] = {
                    "tokenizer": bias_tokenizer,
                    "model": bias_model
                }
            else:
                logger.warning("Bias detection model is not available.")
        except Exception as e:
            logger.error(f"Error loading Bias Detection model: {e}", exc_info=True)

        logger.info("✅ Model Registry initialization complete.")

    def get_model(self, name: str) -> Any:
        """
        Retrieves a loaded model from the registry.

        Args:
            name (str): The key name of the model (e.g., 'whisper', 'emotion').

        Returns:
            The loaded model object(s), or None if not found.
        """
        model = self.models.get(name)
        if model is None:
            logger.error(f"Model '{name}' not found in registry. It may have failed to load.")
        return model

# Create a single, global instance of the registry.
# This ensures that models are loaded only once for the entire application.
model_registry = ModelRegistry()