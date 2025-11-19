#this module is just for testing purpose of the models, if all the models are working fine 

import os
import torch
import whisper
from pyannote.audio import Pipeline
from transformers import pipeline as hf_pipeline
from pydub import AudioSegment
from huggingface_hub import login
from app.core.config import settings
HF_TOKEN = settings.HUGGING_FACE_TOKEN

# ----------- CONFIG -----------
AUDIO_FILE = r"C:\Users\Parvej\Desktop\EchoAI\backend\tests\test.wav"   # Path to your audio file
if not HF_TOKEN or not HF_TOKEN.startswith("hf_"):
    raise ValueError("⚠️ Hugging Face Token not set correctly. Please update HF_TOKEN.")

HF_TOKEN = HF_TOKEN.strip()  # remove any accidental whitespace/newlines
login(token=HF_TOKEN) 
# ------------------------------

# Device check
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"✅ Using device: {DEVICE}")

# Load Whisper
whisper_model = whisper.load_model("base", device=DEVICE)

# Load HuggingFace Emotion Classifier
sentiment_analyzer = hf_pipeline(
    "sentiment-analysis",
    model="j-hartmann/emotion-english-distilroberta-base"
)

# Load Speaker Diarization Model (✅ Correct call)
diarization_pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token=HF_TOKEN
)

# ---------------- HELPER FUNCTIONS ----------------
def analyze_sentiment(text: str):
    """Analyze sentiment and suggest reply."""
    if not text.strip():
        return "neutral", 0.0, "No clear emotion detected."

    result = sentiment_analyzer(text)[0]
    emotion = result["label"]
    score = result["score"]

    # Suggest reply
    advice_map = {
        "anger": "Stay calm, acknowledge frustration, and reply with empathy.",
        "joy": "Encourage positivity and keep the conversation flowing.",
        "sadness": "Show support, listen carefully, and offer encouragement.",
    }
    advice = advice_map.get(emotion.lower(), "Respond neutrally and let the speaker express more.")

    return emotion, score, advice


def cut_audio_segment(audio_file, start, end, output_file="temp_segment.wav"):
    """Extract audio segment and save as wav."""
    audio = AudioSegment.from_wav(audio_file)
    segment = audio[start * 1000:end * 1000]  # sec → ms
    segment.export(output_file, format="wav")
    return output_file


# ---------------- SINGLE SPEAKER ----------------
def process_single_speaker(audio_file):
    print("\n--- Single Speaker Mode ---")
    result = whisper_model.transcribe(audio_file, fp16=False, verbose=False)
    text = result["text"].strip()
    print(f"\n📝 Transcript: {text}")

    emotion, score, advice = analyze_sentiment(text)
    print(f"🎭 Detected Emotion: {emotion} (score={score:.2f})")
    print(f"💡 Suggested Reply: {advice}")


# ---------------- MULTI SPEAKER ----------------
def process_multi_speaker(audio_file):
    print("\n--- Multi Speaker Mode ---")

    # ✅ Run diarization
    diarization = diarization_pipeline(audio_file)

    transcript_entries = []

    for turn, _, speaker in diarization.itertracks(yield_label=True):
        start, end = turn.start, turn.end

        # Extract audio segment
        segment_file = cut_audio_segment(audio_file, start, end)

        # Transcribe
        result = whisper_model.transcribe(segment_file, fp16=False, verbose=False)
        segment_text = result["text"].strip()

        if segment_text:
            transcript_entries.append({
                "speaker": speaker,
                "start": start,
                "end": end,
                "text": segment_text
            })

    # Sort transcript
    transcript_entries.sort(key=lambda x: x["start"])

    # Print results
    for entry in transcript_entries:
        print(f"\n👤 {entry['speaker']} [{entry['start']:.1f}s - {entry['end']:.1f}s]: {entry['text']}")

        emotion, score, advice = analyze_sentiment(entry["text"])
        print(f"🎭 Emotion: {emotion} (score={score:.2f})")
        print(f"💡 Suggested Reply: {advice}")


# ---------------- MAIN ----------------
if __name__ == "__main__":
    print("Choose Mode:")
    print("1️⃣ Single Speaker")
    print("2️⃣ Multi-Speaker (with diarization)")

    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":
        process_single_speaker(AUDIO_FILE)
    elif choice == "2":
        process_multi_speaker(AUDIO_FILE)
    else:
        print("⚠️ Invalid choice. Please enter 1 or 2.")
