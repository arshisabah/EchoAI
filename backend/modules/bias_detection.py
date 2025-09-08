# backend/modules/bias_detection.py

# 1. Import the loader and other necessary libraries
from backend.models.bias.loader import load_bias_model
import torch

# 2. Load the model and tokenizer
print("Initializing bias detection module...")
bias_tokenizer, bias_model = load_bias_model()
device = "cuda" if torch.cuda.is_available() else "cpu"

# These labels are hypothetical. A real fine-tuned model would have specific labels.
LABELS = {0: 'Not Biased', 1: 'Potentially Biased'}

def detect_bias(text: str):
    """
    Analyzes a block of text for potential bias using a BERT model.
    
    IMPORTANT: The underlying bert-base-uncased model is NOT fine-tuned for bias
    detection. Its predictions will be random until it is trained on a
    specific bias dataset. This function provides the pipeline for a future model.

    Args:
        text (str): The text to analyze.

    Returns:
        str: The predicted bias label (e.g., 'Not Biased', 'Potentially Biased').
    """
    if not bias_model or not bias_tokenizer:
        return "Error: Bias detection model not loaded."

    try:
        # 3. Tokenize the input text
        inputs = bias_tokenizer(
            text, 
            return_tensors="pt", 
            truncation=True, 
            padding=True,
            max_length=512
        ).to(device)

        # 4. Make a prediction
        with torch.no_grad():
            outputs = bias_model(**inputs)
            logits = outputs.logits
        
        # 5. Get the final predicted label
        prediction = torch.argmax(logits, dim=-1).item()
        return LABELS.get(prediction, "Unknown")

    except Exception as e:
        print(f"❌ An error occurred during bias detection: {e}")
        return f"Error: {e}"

if __name__ == '__main__':
    sample_text_1 = "The new policy will be challenging for older employees to adapt to."
    sample_text_2 = "All team members contributed equally to the project's success."
    
    # Note: These results are from an UNTRAINED model and are not meaningful.
    bias_result_1 = detect_bias(sample_text_1)
    bias_result_2 = detect_bias(sample_text_2)

    print("\n--- Bias Detection Results (Demonstration Only) ---")
    print(f"Text: '{sample_text_1}'")
    print(f"Result: {bias_result_1}\n")
    print(f"Text: '{sample_text_2}'")
    print(f"Result: {bias_result_2}")
    
    print("\nBias detection module is ready.")