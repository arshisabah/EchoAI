# GPU Installation Guide for EchoAI

## Problem
- PyTorch is installed without CUDA support
- Your NVIDIA RTX 3050 GPU is not being utilized
- System is running on CPU which is much slower

## Solution

### Step 1: Uninstall current PyTorch
```bash
pip uninstall torch torchvision torchaudio
```

### Step 2: Install PyTorch with CUDA 11.8 (RTX 3050 compatible)
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Step 3: Verify GPU is detected
```bash
python check_cuda.py
```

Expected output:
```
CUDA available: True
CUDA version: 11.8
GPU count: 1
GPU name: NVIDIA GeForce RTX 3050
```

### Step 4: Restart your backend server
The Faster-Whisper model will automatically detect and use your GPU.

## Performance Improvement
- **CPU Mode**: ~4-5 seconds per transcription
- **GPU Mode**: ~0.5-1 second per transcription (8-10x faster!)
- **Emotion Analysis**: Will also benefit from GPU acceleration

## Note
After installing CUDA-enabled PyTorch, restart the backend server (`uvicorn app.main:app --reload --port 8000`) for changes to take effect.
