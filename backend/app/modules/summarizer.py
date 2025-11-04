# backend/modules/summarizer.py

import re
from app.models.summarizer.loader import load_summarizer_model

class Summarizer:
    def __init__(self):
        """Initializes the Summarizer by loading the model pipeline."""
        self.summarizer = load_summarizer_model()

    def generate_summary(self, text: str, max_length: int = 120, min_length: int = 40) -> str:
        """Generates a concise summary of the provided text."""
        if not self.summarizer or not text.strip():
            return "⚠️ Summarizer not loaded or no text provided."
            
        summary = self.summarizer(text, max_length=max_length, min_length=min_length, do_sample=False)
        return summary[0]['summary_text']

    def extract_action_items(self, text: str) -> list:
        """Extracts potential tasks and instructions from the text using regex."""
        if not text.strip():
            return []
            
        # Regex patterns to find action-oriented phrases
        patterns = [
            r"(?:please|kindly)\s+(.*?)(?:\.|$|,)",
            r"(?:you need to|you should|make sure to)\s+(.*?)(?:\.|$|,)",
            r"(?:task:|action item:)\s+(.*?)(?:\.|$|,)",
            r"(?:i will|we will|i'll)\s+(.*?)(?:\.|$|,)",
            r"(?:prepare|schedule|complete|finish|submit|send|fix|create|organize)\s+(.*?)(?:\.|$|,)"
        ]
        
        actions = []
        for pat in patterns:
            matches = re.findall(pat, text, flags=re.IGNORECASE)
            # Clean up matches to be more readable
            cleaned_matches = [m.strip() for m in matches if m.strip() and len(m.split()) < 15]
            actions.extend(cleaned_matches)
            
        return sorted(list(set(actions))) # Return unique, sorted action items