# EchoAI Setup Guide

## Quick Setup for New Laptop

### Prerequisites
- Python 3.10 or higher
- Node.js 16+ (for frontend)
- Git

### Backend Setup

1. **Create virtual environment:**
```bash
cd EchoAI
python -m venv venv
```

2. **Activate virtual environment:**
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. **Install Python dependencies:**
```bash
pip install -r backend/requirements.txt
```

4. **Set up environment variables:**
```bash
# Copy example env file
cp backend/.env.example backend/.env

# Edit backend/.env and add your API keys:
# - OPENAI_API_KEY=your_key_here
# - DEEPGRAM_API_KEY=your_key_here (optional)
```

5. **Run backend:**
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
<!-- '''patel-> cd C:\Users\vishal\OneDrive\Desktop\EchoAI\backend; C:/Users/vishal/OneDrive/Desktop/EchoAI/backend/venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 -->
### Frontend Setup

1. **Install dependencies:**
```bash
cd frontend
npm install
```

2. **Run frontend:**
```bash
npm run dev
```

### Access the Application
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## GPU Setup (for faster transcription)

### For NVIDIA GPU:
```bash
# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### For AMD GPU:
```bash
# Install PyTorch with ROCm support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
```

## Troubleshooting

### Port already in use:
```bash
# Change port in backend
uvicorn app.main:app --reload --port 8001

# Change port in frontend (vite.config.js)
```

### Missing dependencies:
```bash
pip install --upgrade pip
pip install -r backend/requirements.txt --force-reinstall
```

### Audio issues:
```bash
# Install system audio libraries (Linux)
sudo apt-get install portaudio19-dev python3-pyaudio

# Install system audio libraries (Mac)
brew install portaudio
```

## Features Enabled
- ✅ Real-time transcription (Faster-Whisper)
- ✅ Emotion analysis (OpenAI GPT-4o-mini)
- ✅ Audio emotion detection
- ✅ Meeting recording
- ✅ Multi-user rooms
- ✅ WebRTC video/audio
- ✅ Continuous transcript bars
- ✅ Emotion guidance

## Configuration

Edit `backend/app/core/config.py` to customize:
- `USE_STREAMING_TRANSCRIPTION`: Enable/disable streaming
- `USE_ROOM_DIARIZATION`: Enable/disable speaker diarization
- Model settings for Faster-Whisper

## Need Help?
Check the logs in:
- Backend: Terminal output
- Frontend: Browser console (F12)
