# 🍎 EchoAI - macOS Setup Guide

## System Requirements

- **macOS 12.0 (Monterey) or later**
- **Apple Silicon (M1/M2/M3)** or **Intel Mac**
- **8GB RAM minimum** (16GB recommended for WhisperX)
- **5GB free disk space**

## Quick Start (Automated)

```bash
# Clone the repository
git clone https://github.com/arshisabah/EchoAI.git
cd EchoAI

# Run automated setup
chmod +x setup_macos.sh
./setup_macos.sh

# Add your API keys to backend/.env
nano backend/.env

# Start everything
./start_all.sh
```

## Manual Setup

### 1. Install Homebrew Dependencies

```bash
brew install python@3.12 postgresql@14 ffmpeg portaudio node
```

### 2. Setup PostgreSQL

```bash
brew services start postgresql@14
createdb echoai
```

### 3. Setup Backend

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install git+https://github.com/m-bain/whisperx.git
```

### 4. Configure Environment

```bash
# Create .env file
cp .env.example .env
nano .env

# Add your API keys:
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### 5. Setup Frontend

```bash
cd ../frontend
npm install
```

### 6. Start Services

```bash
# Terminal 1 - Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - Frontend
cd frontend
npm run dev
```

## Troubleshooting

### Issue: "psycopg2-binary installation failed"

**Solution:**
```bash
brew install postgresql@14
export LDFLAGS="-L/opt/homebrew/opt/postgresql@14/lib"
export CPPFLAGS="-I/opt/homebrew/opt/postgresql@14/include"
pip install psycopg2-binary
```

### Issue: "torch not optimized for Apple Silicon"

**Solution:**
```bash
pip uninstall torch torchvision torchaudio
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cpu
```

### Issue: "WhisperX fails to load"

**Solution:**
```bash
# Use OpenAI API instead (add to .env)
OPENAI_API_KEY=sk-your-key-here

# Or downgrade to standard Whisper
pip uninstall whisperx
# The app will auto-fallback to openai-whisper
```

### Issue: "Port 8000 already in use"

**Solution:**
```bash
# Find and kill process
lsof -ti:8000 | xargs kill -9

# Or use different port
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Issue: "Database connection refused"

**Solution:**
```bash
# Check if PostgreSQL is running
brew services list

# Start PostgreSQL
brew services start postgresql@14

# Verify database exists
psql -l | grep echoai
```

## GPU Acceleration on Apple Silicon

EchoAI automatically detects and uses Apple's Metal Performance Shaders (MPS) for GPU acceleration on M-series chips:

- ✅ **M1/M2/M3 Macs**: Uses MPS for 2-3x faster transcription
- ✅ **Intel Macs with AMD GPU**: Uses CPU (MPS not available)
- ✅ **Standard Whisper**: Full MPS support
- ⚠️ **WhisperX**: Falls back to CPU (MPS support coming soon)

### Verify GPU Acceleration

Check your startup logs for:
```
🍎 Apple MPS (Metal) available - GPU acceleration enabled
✅ Standard Whisper loaded on mps
```

### Force CPU Mode (for debugging)

If you encounter issues with MPS:
```bash
export PYTORCH_ENABLE_MPS_FALLBACK=1
```

## Apple Silicon Specific Notes

- **PyTorch**: Automatically uses Metal Performance Shaders (MPS) for GPU acceleration (requires PyTorch 1.12+)
- **WhisperX**: CPU-only on M-series (still very fast)
- **Memory**: 8GB works but 16GB recommended for large models
- **macOS Version**: Requires macOS 12.3+ for MPS support

## Performance Tips

1. **Use OpenAI API for best transcription**: Add `OPENAI_API_KEY` to `.env`
2. **Optimize Whisper model size**: Set `WHISPER_MODEL=tiny` in `.env` for faster processing
3. **Enable Metal acceleration**: PyTorch automatically uses M-series GPU
4. **Increase buffer size**: For better real-time performance on slower networks

## Production Deployment (macOS Server)

```bash
# Use production settings
cd backend
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Or use pm2
npm install -g pm2
pm2 start ecosystem.config.js
```
