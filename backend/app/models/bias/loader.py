# backend/models/bias/loader.py

from transformers import BertTokenizer, BertForSequenceClassification
import torch

def load_bias_model():
    """
    Loads the BERT tokenizer and model for bias detection.
    Note: This loads a general pre-trained BERT. Fine-tuning on a specific
    bias detection dataset is required for effective performance.

    Returns:
        A tuple containing the loaded (tokenizer, model) if successful, else (None, None).
    """
    model_name = "bert-base-uncased"
    
    print(f" bias detection model '{model_name}'...")
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # We assume 2 labels for a fine-tuned model (e.g., 'biased', 'not biased')
        tokenizer = BertTokenizer.from_pretrained(model_name)
        model = BertForSequenceClassification.from_pretrained(model_name, num_labels=2).to(device)
        print(f"✅ Bias detection model loaded successfully on {device.upper()}.")
        return tokenizer, model
    except Exception as e:
        print(f"❌ Error loading bias detection model: {e}")
        return None, None

if __name__ == '__main__':
    bias_tokenizer, bias_model = load_bias_model()
    if bias_tokenizer and bias_model:
        print("Tokenizer object:", bias_tokenizer)
        print("Model object:", bias_model)