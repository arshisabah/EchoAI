# backend/models/summarizer/loader.py

from transformers import pipeline
import torch

def load_summarizer_model():
    """
    Loads a summarization pipeline using the BART model.
    """
    model_name = "facebook/bart-large-cnn"
    print(f" summarization model pipeline '{model_name}'...")

    try:
        device = 0 if torch.cuda.is_available() else -1
        summarizer_pipeline = pipeline("summarization", model=model_name, device=device)
        print(f"✅ Summarization pipeline loaded successfully.")
        return summarizer_pipeline
    except Exception as e:
        print(f"❌ Error loading summarization pipeline: {e}")
        return None