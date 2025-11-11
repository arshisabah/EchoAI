# backend/modules/diarization.py
from app.core.config import settings
from app.models.diarization.loader import load_diarization_pipeline

from app.models.registry import model_registry

# NOTE: It's better to load the token from a central config or environment variables
HF_TOKEN = settings.HUGGING_FACE_TOKEN

print("Initializing diarization module...")
diarization_pipeline = model_registry.get_model("diarization")

def diarize_audio(audio_path: str):
    """
    Performs speaker diarization on an audio file using the
    globally loaded diarization pipeline.
    """
    try:
        diarization_pipeline = model_registry.get_model("diarization")
        if not diarization_pipeline:
            return {"status": "error", "message": "Diarization model not loaded."}

        result = diarization_pipeline(audio_path)

        segments = [
            {"speaker": speaker, "start": turn.start, "end": turn.end}
            for turn, _, speaker in result.itertracks(yield_label=True)
        ]

        return {"status": "success", "segments": segments}

    except Exception as e:
        print(f"❌ Error during diarization: {e}")
        return {"status": "error", "message": str(e)}