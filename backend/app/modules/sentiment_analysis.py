# backend/modules/sentiment_analysis.py

from app.models.sentiment.loader import load_sentiment_model

print("Initializing sentiment analysis module...")
emotion_classifier = load_sentiment_model()

def analyze_sentiment(text: str):
    """
    Analyzes the emotion of a text and provides advice.
    """
    if not emotion_classifier or not text.strip():
        return "neutral", 0.0, "No clear emotion detected."

    try:
        result = emotion_classifier(text)[0]
        emotion = result["label"]
        score = result["score"]

        advice_map = {
            "anger": "Stay calm, acknowledge frustration, and reply with empathy.",
            "joy": "Encourage positivity and keep the conversation flowing.",
            "sadness": "Show support, listen carefully, and offer encouragement.",
        }
        advice = advice_map.get(emotion.lower(), "Respond neutrally.")

        return emotion.capitalize(), score, advice
    except Exception as e:
        print(f"Error in sentiment analysis: {e}")
        return "error", 0.0, "Could not analyze text."