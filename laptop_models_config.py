# laptop_models_config.py
# Windows-compatible configuration for EchoAI models

import torch
import os

# Model paths and configuration
LAPTOP_MODELS = {
    "whisper": {
        "model_name": "base",
        "size": "74MB",
        "accuracy": "good",
        "speed": "fast"
    },
    "emotion": {
        "processor": "facebook/wav2vec2-base",
        "model": "harshit345/xlsr-wav2vec-speech-emotion-recognition",
        "size": "500MB"
    },
    "sentiment": {
        "model": "cardiffnlp/twitter-roberta-base-sentiment-latest",
        "size": "500MB"
    },
    "summarization": {
        "model": "t5-small",
        "fallback": "sshleifer/distilbart-cnn-6-6",
        "size": "240MB"
    },
    "bias_detection": {
        "model": "bert-base-uncased",
        "size": "440MB"
    },
    "resume_matching": {
        "model": "all-MiniLM-L6-v2",
        "size": "90MB"
    }
}

# Windows-specific settings
WINDOWS_CONFIG = {
    "device": "cuda" if torch.cuda.is_available() else "cpu",
    "encoding": "utf-8",
    "cache_dir": os.path.expanduser("~/.cache/huggingface"),
    "temp_dir": os.path.expanduser("~/AppData/Local/Temp/echoai")
}

# Performance settings for laptops
PERFORMANCE_CONFIG = {
    "batch_size": 1,
    "max_length": 512,
    "num_workers": 2,
    "low_memory_mode": True
}

print("Windows-compatible configuration loaded successfully!")
print(f"Device: {WINDOWS_CONFIG['device'].upper()}")
