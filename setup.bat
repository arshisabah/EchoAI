@echo off
REM Quick setup script for EchoAI on Windows

echo ================================
echo EchoAI Setup Script (Windows)
echo ================================
echo.

REM Check Python
echo Checking Python...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python not found! Please install Python 3.10+
    pause
    exit /b 1
)
echo.

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
echo.

REM Install backend dependencies
echo Installing backend dependencies...
pip install -r backend\requirements.txt
echo.

REM Check if .env exists
if not exist backend\.env (
    echo Creating .env file...
    (
        echo # OpenAI API Key ^(required for emotion analysis^)
        echo OPENAI_API_KEY=your_openai_api_key_here
        echo.
        echo # Deepgram API Key ^(optional^)
        echo DEEPGRAM_API_KEY=your_deepgram_api_key_here
        echo.
        echo # Database URLs
        echo DATABASE_URL=postgresql://user:password@localhost/echoai
        echo MONGODB_URL=mongodb://localhost:27017/echoai
        echo.
        echo # Application Settings
        echo USE_STREAMING_TRANSCRIPTION=True
        echo USE_ROOM_DIARIZATION=False
    ) > backend\.env
    echo WARNING: Please edit backend\.env and add your API keys!
    echo.
)

REM Install frontend dependencies
echo Installing frontend dependencies...
cd frontend
call npm install
cd ..
echo.

echo ================================
echo Setup Complete!
echo ================================
echo.
echo Next steps:
echo 1. Edit backend\.env and add your API keys
echo 2. Start backend: cd backend ^&^& uvicorn app.main:app --reload
echo 3. Start frontend: cd frontend ^&^& npm run dev
echo 4. Open http://localhost:5173
echo.
pause
