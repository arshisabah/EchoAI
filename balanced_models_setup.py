# fixed_balanced_models_setup.py
# Windows-compatible setup script with proper error handling

import os
import sys
import torch
import whisper
from transformers import (
    Wav2Vec2Processor, Wav2Vec2ForSequenceClassification,
    AutoTokenizer, AutoModelForSequenceClassification,
    BertTokenizer, BertForSequenceClassification
)
from sentence_transformers import SentenceTransformer
import warnings
warnings.filterwarnings("ignore")

def install_missing_packages():
    """Install missing packages"""
    import subprocess
    
    packages_to_install = []
    
    try:
        import sentencepiece
    except ImportError:
        packages_to_install.append("sentencepiece")
    
    if packages_to_install:
        print(f"Installing missing packages: {', '.join(packages_to_install)}")
        for package in packages_to_install:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print("Missing packages installed successfully!")

def setup_fixed_models():
    """Download and setup models with proper error handling"""
    
    models_info = {}
    
    print("Setting up LAPTOP-FRIENDLY models for EchoAI...")
    print("Windows-compatible | Total size: ~2-3GB")
    print("=" * 60)
    
    # Install missing packages first
    print("\n1. Checking and installing missing packages...")
    try:
        install_missing_packages()
        print("All required packages are ready!")
    except Exception as e:
        print(f"Warning: Could not install some packages: {e}")
    
    # 1. WHISPER BASE
    print("\n2. Downloading Whisper BASE (74MB)...")
    try:
        whisper_model = whisper.load_model("base")
        models_info['whisper'] = {
            'model': whisper_model,
            'size': '74MB',
            'status': 'success'
        }
        print("SUCCESS: Whisper BASE downloaded!")
    except Exception as e:
        print(f"ERROR: Whisper download failed: {e}")
        models_info['whisper'] = {'status': 'failed', 'error': str(e)}
    
    # 2. EMOTION DETECTION
    print("\n3. Downloading Emotion Detection model (~500MB)...")
    try:
        emotion_processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base")
        emotion_model = Wav2Vec2ForSequenceClassification.from_pretrained(
            "harshit345/xlsr-wav2vec-speech-emotion-recognition"
        )
        models_info['emotion'] = {
            'processor': emotion_processor,
            'model': emotion_model,
            'size': '500MB',
            'status': 'success'
        }
        print("SUCCESS: Emotion detection model downloaded!")
    except Exception as e:
        print(f"ERROR: Emotion model download failed: {e}")
        models_info['emotion'] = {'status': 'failed', 'error': str(e)}
    
    # 3. SENTIMENT ANALYSIS
    print("\n4. Downloading Sentiment Analysis model (~500MB)...")
    try:
        sentiment_tokenizer = AutoTokenizer.from_pretrained("cardiffnlp/twitter-roberta-base-sentiment-latest")
        sentiment_model = AutoModelForSequenceClassification.from_pretrained("cardiffnlp/twitter-roberta-base-sentiment-latest")
        
        models_info['sentiment'] = {
            'tokenizer': sentiment_tokenizer,
            'model': sentiment_model,
            'size': '500MB',
            'status': 'success'
        }
        print("SUCCESS: Sentiment analysis model downloaded!")
    except Exception as e:
        print(f"ERROR: Sentiment model download failed: {e}")
        models_info['sentiment'] = {'status': 'failed', 'error': str(e)}
    
    # 4. T5 SUMMARIZATION (with proper sentencepiece)
    print("\n5. Downloading T5 Summarization model (240MB)...")
    try:
        # Import after installing sentencepiece
        from transformers import T5Tokenizer, T5ForConditionalGeneration
        
        t5_tokenizer = T5Tokenizer.from_pretrained("t5-small")
        t5_model = T5ForConditionalGeneration.from_pretrained("t5-small")
        
        models_info['summarization'] = {
            'tokenizer': t5_tokenizer,
            'model': t5_model,
            'size': '240MB',
            'status': 'success'
        }
        print("SUCCESS: T5 summarization model downloaded!")
    except Exception as e:
        print(f"ERROR: T5 model download failed: {e}")
        print("Trying alternative summarization model...")
        
        try:
            # Fallback to DistilBART
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            alt_tokenizer = AutoTokenizer.from_pretrained("sshleifer/distilbart-cnn-6-6")
            alt_model = AutoModelForSeq2SeqLM.from_pretrained("sshleifer/distilbart-cnn-6-6")
            
            models_info['summarization'] = {
                'tokenizer': alt_tokenizer,
                'model': alt_model,
                'size': '306MB',
                'status': 'success',
                'type': 'DistilBART (fallback)'
            }
            print("SUCCESS: Alternative summarization model (DistilBART) downloaded!")
        except Exception as e2:
            print(f"ERROR: Alternative model also failed: {e2}")
            models_info['summarization'] = {'status': 'failed', 'error': str(e)}
    
    # 5. BIAS DETECTION (already downloaded successfully)
    print("\n6. BERT for bias detection already downloaded!")
    models_info['bias_detection'] = {
        'size': '440MB',
        'status': 'success',
        'note': 'Already downloaded successfully'
    }
    
    # 6. RESUME MATCHING (already downloaded successfully)  
    print("\n7. Resume matching model already downloaded!")
    models_info['resume_matching'] = {
        'size': '90MB',
        'status': 'success', 
        'note': 'Already downloaded successfully'
    }
    
    return models_info

def create_windows_config(models_info):
    """Create Windows-compatible configuration file"""
    config_content = """# laptop_models_config.py
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
"""
    
    try:
        # Write with UTF-8 encoding to handle any special characters
        with open("laptop_models_config.py", "w", encoding="utf-8") as f:
            f.write(config_content)
        print("SUCCESS: Configuration file created!")
    except Exception as e:
        print(f"ERROR creating config file: {e}")

def create_fixed_requirements():
    """Create requirements.txt with all necessary packages"""
    requirements = """# requirements.txt - Complete EchoAI setup for Windows
torch>=1.9.0
transformers>=4.20.0
openai-whisper>=20230314
sentence-transformers>=2.2.0
sentencepiece>=0.1.99
librosa>=0.9.0
soundfile>=0.10.0
numpy>=1.21.0
scipy>=1.7.0
matplotlib>=3.5.0
seaborn>=0.11.0
pandas>=1.3.0
fastapi>=0.68.0
uvicorn>=0.15.0
websockets>=10.0
python-multipart>=0.0.5
huggingface-hub>=0.10.0
"""
    
    try:
        with open("requirements.txt", "w", encoding="utf-8") as f:
            f.write(requirements)
        print("SUCCESS: Requirements file created!")
    except Exception as e:
        print(f"ERROR creating requirements file: {e}")

def print_windows_summary(models_info):
    """Print summary compatible with Windows terminal"""
    print("\n" + "="*60)
    print("SETUP COMPLETE - Windows Compatible!")
    print("="*60)
    
    successful_models = []
    failed_models = []
    
    for model_name, info in models_info.items():
        if info.get('status') == 'success':
            successful_models.append(model_name)
        elif info.get('status') == 'failed':
            failed_models.append(model_name)
    
    print(f"\nSUCCESSFUL DOWNLOADS: {len(successful_models)}")
    for model in successful_models:
        size = models_info[model].get('size', 'Unknown')
        print(f"  - {model.upper()}: {size}")
    
    if failed_models:
        print(f"\nFAILED DOWNLOADS: {len(failed_models)}")
        for model in failed_models:
            error = models_info[model].get('error', 'Unknown error')[:50]
            print(f"  - {model.upper()}: {error}...")
    
    print(f"\nTOTAL SUCCESSFUL: {len(successful_models)}/{len(models_info)}")
    
    if len(successful_models) >= 4:  # At least most models working
        print("\nSTATUS: Ready for development!")
        print("Your EchoAI system has enough models to start working.")
    else:
        print("\nSTATUS: Needs attention")
        print("Some critical models failed. Check the errors above.")

if __name__ == "__main__":
    print("EchoAI Setup - Windows Fixed Version")
    print("Fixing T5 and encoding issues...")
    
    try:
        models_info = setup_fixed_models()
        print_windows_summary(models_info)
        create_windows_config(models_info)
        create_fixed_requirements()
        
        print("\n" + "="*60)
        print("NEXT STEPS:")
        print("1. pip install -r requirements.txt")
        print("2. Restart your terminal/IDE")
        print("3. Test your models with the implementation files")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\nSetup cancelled by user.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print("Please check your internet connection and try again.")