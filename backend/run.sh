#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Suppress warnings
export PYTHONWARNINGS="ignore::UserWarning,ignore::FutureWarning,ignore::DeprecationWarning"
export TOKENIZERS_PARALLELISM="false"
export PYTHONDONTWRITEBYTECODE=1  # ← This prevents .pyc files from being created

echo "🚀 Starting EchoAI Backend..."
echo "📂 Watching: app/ directory ONLY"
echo "🚫 Ignoring: venv/, *.pyc, __pycache__"
echo "🌐 Server: http://0.0.0.0:8000"
echo ""

# Run uvicorn with exclusions
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --reload-dir app \
  --reload-exclude "venv/*" \
  --reload-exclude "*.pyc" \
  --reload-exclude "__pycache__/*" \
  --reload-exclude "*.db" \
  --reload-exclude "*.log" \
  --log-level info
