#!/bin/bash
# macOS Setup Script for EchoAI
# Supports both Intel and Apple Silicon Macs

set -e

echo "🍎 EchoAI macOS Setup Script"
echo "================================"

# Detect architecture
ARCH=$(uname -m)
echo "📱 Detected architecture: $ARCH"

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "✅ Homebrew installed"
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
brew install python@3.12 postgresql@14 ffmpeg portaudio node npm

# Start PostgreSQL
echo "🗄️ Starting PostgreSQL..."
brew services start postgresql@14

# Wait for PostgreSQL to start
sleep 3

# Create database
echo "🗄️ Creating database..."
if psql -lqt | cut -d \| -f 1 | grep -qw echoai; then
    echo "✅ Database 'echoai' already exists"
else
    createdb echoai
    echo "✅ Database 'echoai' created"
fi

# Setup backend
echo "🐍 Setting up Python backend..."
cd backend

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install PyTorch (macOS optimized)
if [ "$ARCH" = "arm64" ]; then
    echo "🔥 Installing PyTorch for Apple Silicon..."
    pip install torch torchvision torchaudio
else
    echo "🔥 Installing PyTorch for Intel Mac..."
    pip install torch torchvision torchaudio
fi

# Install requirements
echo "📦 Installing Python packages..."
pip install -r requirements.txt

# Install WhisperX (macOS compatible)
echo "🎙️ Installing WhisperX..."
pip install git+https://github.com/m-bain/whisperx.git || pip install whisperx

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "⚙️ Creating .env file..."
    cat > .env << EOF
# Database
DATABASE_URL=postgresql://$(whoami)@localhost:5432/echoai

# API Keys (add your own)
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# App Config
DEBUG=true
LOG_LEVEL=INFO
WHISPER_MODEL=base

# CORS
ALLOWED_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
EOF
    echo "✅ .env file created (please add your API keys)"
fi

cd ..

# Setup frontend
echo "⚛️ Setting up React frontend..."
cd frontend

# Install dependencies
npm install

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "⚙️ Creating frontend .env file..."
    cat > .env << EOF
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_DEBUG=true
EOF
    echo "✅ Frontend .env file created"
fi

cd ..

# Create start scripts
echo "🚀 Creating start scripts..."

cat > start_backend.sh << 'EOF'
#!/bin/bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
EOF
chmod +x start_backend.sh

cat > start_frontend.sh << 'EOF'
#!/bin/bash
cd frontend
npm run dev
EOF
chmod +x start_frontend.sh

cat > start_all.sh << 'EOF'
#!/bin/bash
# Start both backend and frontend
echo "🚀 Starting EchoAI..."

# Start backend in background
echo "Starting backend..."
./start_backend.sh &
BACKEND_PID=$!

# Wait for backend to start
sleep 5

# Start frontend
echo "Starting frontend..."
./start_frontend.sh &
FRONTEND_PID=$!

echo "✅ EchoAI started!"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "🌐 Frontend: http://localhost:5173"
echo "🔧 Backend: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services..."

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
EOF
chmod +x start_all.sh

echo ""
echo "✅ macOS setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Edit backend/.env and add your API keys"
echo "2. Run: ./start_all.sh"
echo "   OR start separately:"
echo "   - Backend: ./start_backend.sh"
echo "   - Frontend: ./start_frontend.sh"
echo ""
echo "🌐 Access the app at: http://localhost:5173"
