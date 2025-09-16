# backend/models/wav2vec/emotion_loader.py

from transformers import Wav2Vec2Processor, Wav2Vec2ForSequenceClassification
import torch

def load_emotion_model():
    """
    Loads the Wav2Vec2 processor and model for speech emotion recognition.

    Returns:
        A tuple containing the loaded (processor, model) if successful, else (None, None).
    """
    processor_name = "facebook/wav2vec2-base"
    model_name = "harshit345/xlsr-wav2vec-speech-emotion-recognition"
    
    print(f" wav2vec emotion model '{model_name}'...")
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        processor = Wav2Vec2Processor.from_pretrained(processor_name)
        model = Wav2Vec2ForSequenceClassification.from_pretrained(model_name).to(device)
        print(f"✅ Emotion detection model loaded successfully on {device.upper()}.")
        return processor, model
    except Exception as e:
        print(f"❌ Error loading emotion detection model: {e}")
        return None, None

if __name__ == '__main__':
    # Example of how to use the loader
    emotion_processor, emotion_model = load_emotion_model()
    if emotion_processor and emotion_model:
        print("Processor object:", emotion_processor)
        print("Model object:", emotion_model)