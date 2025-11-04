# backend/models/sentiment/loader.py

# UPDATED to use the better emotion classification model
from transformers import pipeline
import torch

def load_sentiment_model():
    """
    Loads a pipeline for emotion classification.
    This model is better at detecting specific emotions like anger, joy, etc.
    """
    # This is the model from your new script
    model_name = "j-hartmann/emotion-english-distilroberta-base"
    
    print(f" sentiment/emotion model '{model_name}'...")
    try:
        device = 0 if torch.cuda.is_available() else -1
        # Use the pipeline function for easy setup
        classifier = pipeline(
            "sentiment-analysis", # This task name is used for emotion too
            model=model_name,
            device=device
        )
        print(f"✅ Emotion model pipeline loaded successfully.")
        return classifier
    except Exception as e:
        print(f"❌ Error loading emotion model pipeline: {e}")
        return None