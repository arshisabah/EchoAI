# backend/modules/diarization.py

from app.models.diarization.loader import load_diarization_pipeline
import os

# NOTE: It's better to load the token from a central config or environment variables
HF_TOKEN = os.environ.get("HF_TOKEN")

print("Initializing diarization module...")
diarization_pipeline = load_diarization_pipeline(auth_token=HF_TOKEN)

def diarize_audio(audio_path: str):
    """
    Performs speaker diarization on an audio file.

    Args:
        audio_path (str): The path to the audio file.

    Returns:
        A list of dictionaries, where each dictionary contains
        'speaker', 'start', and 'end' time for a segment.
    """
    if not diarization_pipeline:
        return [{"error": "Diarization pipeline not loaded."}]
        
    try:
        diarization_result = diarization_pipeline(audio_path)
        
        segments = []
        for turn, _, speaker in diarization_result.itertracks(yield_label=True):
            segments.append({
                "speaker": speaker,
                "start": turn.start,
                "end": turn.end
            })
        return segments
    except Exception as e:
        print(f"❌ Error during diarization: {e}")
        return [{"error": str(e)}]