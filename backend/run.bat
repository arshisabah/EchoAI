@echo off

REM Activate virtual environment (assumes you're in the backend folder)
call venv\Scripts\activate.bat

REM Suppress warnings (set environment variables for Python on Windows)
set PYTHONWARNINGS=ignore::UserWarning,ignore::FutureWarning,ignore::DeprecationWarning
set TOKENIZERS_PARALLELISM=false
set PYTHONDONTWRITEBYTECODE=1

echo 🚀 Starting EchoAI Backend...
echo 📂 Watching: app/ directory ONLY
echo 🚫 Ignoring: venv/, *.pyc, __pycache__
echo 🌐 Server: http://127.0.0.1:8000
echo.

REM Uvicorn reload flags for Windows

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app --reload-exclude "venv/*" --reload-exclude "*.pyc" --reload-exclude "__pycache__/*" --reload-exclude "*.db" --reload-exclude "*.log" --log-level info

REM End of script