#!/bin/bash
# setup.sh - EchoAI Backend Setup Script

set -e

echo "🚀 EchoAI Backend Setup Starting..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
check_python() {
    echo "Checking Python version..."
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
    else
        echo -e "${RED}✗ Python 3 not found. Please install Python 3.10+${NC}"
        exit 1
    fi
}

# Create virtual environment
create_venv() {
    echo ""
    echo "Creating virtual environment..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    else
        echo -e "${YELLOW}⚠ Virtual environment already exists${NC}"
    fi
}

# Activate virtual environment
activate_venv() {
    echo ""
    echo "Activating virtual environment..."
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
}

# Install dependencies
install_deps() {
    echo ""
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
}

# Create necessary directories
create_dirs() {
    echo ""
    echo "Creating directories..."
    mkdir -p logs
    mkdir -p data
    mkdir -p models_cache
    echo -e "${GREEN}✓ Directories created${NC}"
}

# Setup environment file
setup_env() {
    echo ""
    echo "Setting up environment file..."
    if [ ! -f ".env" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ .env file created from template${NC}"
        echo -e "${YELLOW}⚠ Please edit .env file and add your API keys${NC}"
    else
        echo -e "${YELLOW}⚠ .env file already exists${NC}"
    fi
}

# Check ffmpeg
check_ffmpeg() {
    echo ""
    echo "Checking for ffmpeg..."
    if command -v ffmpeg &> /dev/null; then
        echo -e "${GREEN}✓ ffmpeg found${NC}"
    else
        echo -e "${YELLOW}⚠ ffmpeg not found. Audio processing may be limited.${NC}"
        echo "Install ffmpeg:"
        echo "  Ubuntu/Debian: sudo apt-get install ffmpeg"
        echo "  macOS: brew install ffmpeg"
        echo "  Windows: Download from https://ffmpeg.org/"
    fi
}

# Initialize database (if using PostgreSQL)
init_db() {
    echo ""
    echo "Database initialization..."
    echo "If using PostgreSQL, ensure your DATABASE_URL is set in .env"
    echo "Run: docker-compose up -d postgres"
}

# Run tests
run_tests() {
    echo ""
    read -p "Run tests? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pytest tests/ -v
    fi
}

# Main setup flow
main() {
    echo "======================================"
    echo "  EchoAI Backend Setup"
    echo "======================================"
    
    check_python
    create_venv
    activate_venv
    install_deps
    create_dirs
    setup_env
    check_ffmpeg
    init_db
    
    echo ""
    echo "======================================"
    echo -e "${GREEN}✓ Setup Complete!${NC}"
    echo "======================================"
    echo ""
    echo "Next steps:"
    echo "1. Edit .env file with your API keys"
    echo "2. Run: source venv/bin/activate (or venv\\Scripts\\activate on Windows)"
    echo "3. Run: python main.py"
    echo "4. Or use: uvicorn main:app --reload"
    echo ""
    echo "For Docker deployment:"
    echo "1. docker-compose up -d"
    echo ""
    echo "Access the API at: http://localhost:8000"
    echo "View docs at: http://localhost:8000/docs"
    echo ""
}

# Run main
main