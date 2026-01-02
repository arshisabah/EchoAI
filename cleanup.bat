@echo off
REM Project Cleanup Script - Removes unused files and folders
REM EchoAI Project Cleanup
REM IMPORTANT: Review PROJECT_AUDIT_REPORT.md before running

echo =====================================
echo EchoAI Project Cleanup Script
echo =====================================
echo.
echo WARNING: This will DELETE unused files permanently
echo Please review PROJECT_AUDIT_REPORT.md first
echo.
set /p confirmation="Continue? (type 'yes' to proceed): "

if not "%confirmation%"=="yes" (
    echo Cleanup cancelled
    exit /b 0
)

echo.
echo Starting cleanup...
echo.

REM Counter for deleted files
set deleted_count=0

REM 1. Delete backup files
echo Removing backup files...
if exist "backend\app\routers\transcript.py.bak" (
    del "backend\app\routers\transcript.py.bak"
    echo    Deleted transcript.py.bak
    set /a deleted_count+=1
)

REM 2. Delete empty auth router
echo Removing empty files...
if exist "backend\app\routers\auth.py" (
    for %%A in ("backend\app\routers\auth.py") do (
        if %%~zA==0 (
            del "backend\app\routers\auth.py"
            echo    Deleted empty auth.py
            set /a deleted_count+=1
        ) else (
            echo    WARNING: auth.py is not empty, skipping
        )
    )
)

REM 3. Delete unused modules
echo Removing unused modules...

if exist "backend\app\modules\bias_detection.py" (
    del "backend\app\modules\bias_detection.py"
    echo    Deleted bias_detection.py
    set /a deleted_count+=1
)

if exist "backend\app\modules\resume_matcher.py" (
    del "backend\app\modules\resume_matcher.py"
    echo    Deleted resume_matcher.py
    set /a deleted_count+=1
)

if exist "backend\app\modules\echo_ai_module.py" (
    del "backend\app\modules\echo_ai_module.py"
    echo    Deleted echo_ai_module.py
    set /a deleted_count+=1
)

if exist "backend\app\modules\sentiment_analysis.py" (
    del "backend\app\modules\sentiment_analysis.py"
    echo    Deleted sentiment_analysis.py (not using model)
    set /a deleted_count+=1
)

REM 4. Delete unused model folders
echo Removing unused model folders...

if exist "backend\app\models\bias" (
    rmdir /s /q "backend\app\models\bias"
    echo    Deleted models\bias\ folder
    set /a deleted_count+=1
)

if exist "backend\app\models\embedding" (
    rmdir /s /q "backend\app\models\embedding"
    echo    Deleted models\embedding\ folder
    set /a deleted_count+=1
)

if exist "backend\app\models\sentiment" (
    rmdir /s /q "backend\app\models\sentiment"
    echo    Deleted models\sentiment\ folder
    set /a deleted_count+=1
)

REM 5. Clean up __pycache__ folders
echo Cleaning Python cache...
for /d /r "backend\app" %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul
echo    Removed __pycache__ folders

REM 6. Clean up .pyc files
echo Cleaning .pyc files...
del /s /q "backend\*.pyc" 2>nul
echo    Removed .pyc files

echo.
echo =====================================
echo Cleanup completed!
echo =====================================
echo Files/folders deleted: %deleted_count%
echo.
echo Next steps:
echo    1. Review laptop_models_config.py (remove bias_detection refs)
echo    2. Review balanced_models_setup.py (remove bias_detection refs)
echo    3. Test the backend: cd backend ^&^& python app\main.py
echo    4. Run tests: cd backend ^&^& pytest tests\
echo.
echo All changes are permanent. No backup was created.
echo =====================================
pause
