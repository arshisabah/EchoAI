"""
Central Model Registry for the EchoAI Application.

This module is responsible for:
1.  Loading all required AI models at application startup.
2.  Storing the loaded models in a central, easily accessible location.
3.  Tracking model load status and providing safe access to models.
4.  Handling model loading errors gracefully to prevent application crashes.
"""

import logging
from typing import Dict, Any, Optional
from app.core.config import settings

# Import model loaders
from .whisper.loader import load_whisper_model
from .diarization.loader import load_diarization_pipeline
from .wav2vec.emotion_loader import load_emotion_model
from .summarizer.loader import load_summarizer_model
from .bias.loader import load_bias_model

logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Central class to manage all AI models.
    Loads models once at startup and provides safe access throughout the app.
    """

    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.status: Dict[str, str] = {}

    # ----------------------------------------------------------------------
    # 🚀 MAIN LOADER
    # ----------------------------------------------------------------------
    def load_all_models(self):
        """
        Loads all critical AI models at application startup.
        Tracks success or failure for each model.
        """
        logger.info("🧠 Initializing Model Registry — Loading all AI models...")

        loaders = {
            "whisper": lambda: load_whisper_model(model_name=settings.WHISPER_MODEL or "base"),
            "diarization": lambda: load_diarization_pipeline(auth_token=settings.HUGGING_FACE_TOKEN),
            "emotion": load_emotion_model,
            "summarizer": load_summarizer_model,
            "bias": load_bias_model,
        }

        for name, loader in loaders.items():
            try:
                logger.info(f"⏳ Loading {name.capitalize()} model...")
                result = loader()

                if not result:
                    raise RuntimeError(f"{name.capitalize()} model returned None")

                # Handle complex returns (like tuples)
                if isinstance(result, tuple) and all(r is None for r in result):
                    raise RuntimeError(f"{name.capitalize()} model failed to initialize.")

                self.models[name] = result
                self.status[name] = "✅ Loaded"
                logger.info(f"✅ {name.capitalize()} model loaded successfully.")

            except Exception as e:
                self.models[name] = None
                self.status[name] = f"❌ Failed: {str(e)}"
                logger.error(f"❌ Error loading {name.capitalize()} model: {e}", exc_info=True)

        logger.info("✅ Model Registry initialization complete.")
        logger.info(f"📊 Model load summary: {self.status}")

    # ----------------------------------------------------------------------
    # 🔍 MODEL ACCESSOR
    # ----------------------------------------------------------------------
    def get_model(self, name: str) -> Any:
        """
        Safely retrieves a loaded model from the registry.

        Args:
            name (str): The key name of the model (e.g., 'whisper', 'emotion').

        Returns:
            The loaded model object(s).
        
        Raises:
            RuntimeError: If the model is not found or failed to load.
        """
        model = self.models.get(name)
        if model is None:
            msg = f"Model '{name}' not available or failed to load."
            logger.error(msg)
            raise RuntimeError(msg)
        return model

    # ----------------------------------------------------------------------
    # 🔁 MODEL RELOADER
    # ----------------------------------------------------------------------
    def reload_model(self, name: str):
        """
        Reloads a single model dynamically without restarting the application.
        Useful if a model crashes or needs to be updated.
        """
        loaders = {
            "whisper": lambda: load_whisper_model(model_name=settings.WHISPER_MODEL or "base"),
            "diarization": lambda: load_diarization_pipeline(auth_token=settings.HUGGING_FACE_TOKEN),
            "emotion": load_emotion_model,
            "summarizer": load_summarizer_model,
            "bias": load_bias_model,
        }

        if name not in loaders:
            logger.warning(f"Unknown model '{name}' — cannot reload.")
            return

        logger.info(f"♻️ Reloading {name} model...")
        try:
            result = loaders[name]()
            if not result:
                raise RuntimeError("Reload returned None")

            self.models[name] = result
            self.status[name] = "✅ Reloaded"
            logger.info(f"✅ Model '{name}' reloaded successfully.")

        except Exception as e:
            logger.error(f"❌ Failed to reload model '{name}': {e}", exc_info=True)
            self.status[name] = f"❌ Reload failed: {str(e)}"

    # ----------------------------------------------------------------------
    # 🩺 STATUS REPORT
    # ----------------------------------------------------------------------
    def get_status_report(self) -> Dict[str, str]:
        """
        Returns a summary of all models and their load status.
        Can be exposed via an API endpoint for monitoring.
        """
        return self.status

    # ----------------------------------------------------------------------
    # 🧹 CLEANUP
    # ----------------------------------------------------------------------
    def unload_all_models(self):
        """
        Unloads all models and clears memory. Useful during shutdown or redeploy.
        """
        logger.info("🧹 Unloading all models from memory...")
        self.models.clear()
        self.status.clear()

        if torch.cuda.is_available():
            import torch
            torch.cuda.empty_cache()

        logger.info("✅ All models unloaded and GPU cache cleared.")


# ----------------------------------------------------------------------
# 🌐 Create a global, singleton instance
# ----------------------------------------------------------------------
model_registry = ModelRegistry()
