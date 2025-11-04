# backend/models/embedding/loader.py

from sentence_transformers import SentenceTransformer
import torch

def load_embedding_model():
    """
    Loads the SentenceTransformer model for creating text embeddings,
    used for resume matching and semantic similarity.

    Returns:
        A loaded SentenceTransformer model object if successful, else None.
    """
    model_name = 'all-MiniLM-L6-v2'
    
    print(f" embedding model '{model_name}'...")
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = SentenceTransformer(model_name, device=device)
        print(f"✅ Embedding model loaded successfully on {device.upper()}.")
        return model
    except Exception as e:
        print(f"❌ Error loading embedding model: {e}")
        return None

if __name__ == '__main__':
    embedding_model = load_embedding_model()
    if embedding_model:
        print("Model object:", embedding_model)