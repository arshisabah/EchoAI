# backend/modules/emotion.py

# 1. Import loaders and necessary libraries
from backend.models.wav2vec.emotion_loader import load_emotion_model
import torch
import librosa

# 2. Load the processor and model
print("Initializing emotion detection module...")
emotion_processor, emotion_model = load_emotion_model()
device = "cuda" if torch.cuda.is_available() else "cpu"

def analyze_emotion(audio_file_path):
    """
    Analyzes the emotion from an audio file.

    Args:
        audio_file_path (str): The path to the audio file.

    Returns:
        str: The predicted emotion label (e.g., 'happy', 'sad').
    """
    if not emotion_processor or not emotion_model:
        return "Error: Emotion model not loaded."

    try:
        # 3. Preprocess the audio file
        # Load the audio file and resample it to the required 16kHz
        speech_array, sample_rate = librosa.load(audio_file_path, sr=16000)

        # Use the processor to prepare the audio data for the model
        inputs = emotion_processor(speech_array, sampling_rate=sample_rate, return_tensors="pt", padding=True)
        inputs = {key: val.to(device) for key, val in inputs.items()}

        # 4. Make a prediction
        with torch.no_grad():
            logits = emotion_model(**inputs).logits
        
        # 5. Get the final predicted label
        pred_ids = torch.argmax(logits, dim=-1).item()
        label = emotion_model.config.id2label[pred_ids]
        
        return label.capitalize()

    except Exception as e:
        print(f"❌ An error occurred during emotion analysis: {e}")
        return f"Error: {e}"

if __name__ == '__main__':
    # You must have an audio file available to test this.
    # audio_path = "path/to/your/audio.wav" 
    # emotion = analyze_emotion(audio_path)
    # print(f"\n--- Detected Emotion ---")
    # print(emotion)
    
    print("\nEmotion detection module is ready.")