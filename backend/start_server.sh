#!/bin/bash

# Navigate to backend
cd ~/Desktop/EchoAI/EchoAI/backend

# Activate virtual environment
source venv/bin/activate

# Set SSL certificate paths
export SSL_CERT_FILE=$(python -m certifi)
export REQUESTS_CA_BUNDLE=$(python -m certifi)
export PYTHONDONTWRITEBYTECODE=1

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 EchoAI Backend - Deepgram Real-Time Transcription"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 SSL Certificates: $SSL_CERT_FILE"
echo "🌐 Server: http://0.0.0.0:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000 
