# backend/models/diarization/loader.py

from pyannote.audio import Pipeline
import torch

def load_diarization_pipeline(auth_token: str):
    """
    Loads the pyannote.audio speaker diarization pipeline.

    Args:
        auth_token (str): Your Hugging Face authentication token.

    Returns:
        The loaded pyannote.audio Pipeline object.
    """
    model_name = "pyannote/speaker-diarization-3.1"
    print(f" diarization pipeline '{model_name}'...")
    
    if not auth_token or not auth_token.startswith("hf_"):
        print("❌ Hugging Face token is invalid or missing.")
        return None
        
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        pipeline = Pipeline.from_pretrained(model_name, use_auth_token=auth_token)
        pipeline.to(torch.device(device))
        print(f"✅ Diarization pipeline loaded successfully on {device.upper()}.")
        return pipeline
    except Exception as e:
        print(f"❌ Error loading diarization pipeline: {e}")
        return None