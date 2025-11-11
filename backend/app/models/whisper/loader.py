# backend/models/whisper/loader.py

import whisper
import torch

def load_whisper_model(model_name="small"):
    """
    Loads a specified Whisper model from the cache or downloads it if not present.

    Args:
        model_name (str): The name of the Whisper model to load (e.g., "base", "small").

    Returns:
        A loaded Whisper model object.
    """
    print(f" whisper model '{model_name}'...")
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = whisper.load_model(model_name, device=device)
        print(f"✅ Whisper model '{model_name}' loaded successfully on {device.upper()}.")
        return model
    except Exception as e:
        print(f"❌ Error loading Whisper model: {e}")
        return None

if __name__ == '__main__':
    # Example of how to use the loader
    transcription_model = load_whisper_model()
    if transcription_model:
        print("Model object:", transcription_model)