@echo off
REM Backend Startup Script for Windows
REM Save this as: backend/start_backend.bat

echo ========================================
echo    EchoAI Backend Startup
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run: python -m venv venv
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if .env file exists
if not exist ".env" (
    echo WARNING: .env file not found!
    echo Creating .env from template...
    echo OPENAI_API_KEY=sk-your-key-here> .env
    echo LOG_LEVEL=INFO>> .env
    echo DEBUG=True>> .env
    echo.
    echo Please edit .env and add your OpenAI API key!
    pause
)

REM Check Python version
echo.
echo Checking Python version...
python --version
echo.

REM Install/update dependencies
echo Checking dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Check if main.py exists
if exist "main.py" (
    set MAIN_MODULE=main:app
    echo Found main.py in current directory
) else if exist "app\main.py" (
    set MAIN_MODULE=app.main:app
    echo Found main.py in app directory
) else (
    echo ERROR: main.py not found!
    echo Please check your project structure.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Starting EchoAI Backend Server...
echo ========================================
echo.
echo Server will be available at:
echo   - Local:  http://localhost:8000
echo   - Docs:   http://localhost:8000/docs
echo   - Health: http://localhost:8000/health
echo.
echo Press CTRL+C to stop the server
echo ========================================
echo.

REM Start the server
uvicorn %MAIN_MODULE% --reload --host 0.0.0.0 --port 8000

REM If uvicorn command fails, try direct python
if errorlevel 1 (
    echo.
    echo Uvicorn failed, trying direct Python...
    python main.py
)

pause