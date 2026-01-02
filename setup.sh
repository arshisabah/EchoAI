#!/bin/bash
# Quick setup script for EchoAI on new laptop

echo "🚀 EchoAI Setup Script"
echo "======================="

# Check Python version
echo "Checking Python version..."
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Create virtual environment
echo "Creating virtual environment..."
python -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install backend dependencies
echo "Installing backend dependencies..."
pip install -r backend/requirements.txt

# Check if .env exists
if [ ! -f backend/.env ]; then
    echo "Creating .env file..."
    cat > backend/.env << 'EOF'
# OpenAI API Key (required for emotion analysis)
OPENAI_API_KEY=your_openai_api_key_here

# Deepgram API Key (optional, for alternative transcription)
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# Database URLs (if using database persistence)
DATABASE_URL=postgresql://user:password@localhost/echoai
MONGODB_URL=mongodb://localhost:27017/echoai

# Application Settings
USE_STREAMING_TRANSCRIPTION=True
USE_ROOM_DIARIZATION=False
EOF
    echo "⚠️  Please edit backend/.env and add your API keys!"
fi

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit backend/.env and add your API keys"
echo "2. Start backend: cd backend && uvicorn app.main:app --reload"
echo "3. Start frontend: cd frontend && npm run dev"
echo "4. Open http://localhost:5173"
