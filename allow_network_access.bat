@echo off
REM Allow Network Access to EchoAI Backend
REM Right-click and "Run as Administrator"

echo ========================================
echo   EchoAI Network Access Setup
echo ========================================
echo.

echo Checking for Administrator privileges...
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo Right-click this file and select "Run as Administrator"
    pause
    exit /b 1
)

echo Adding firewall rule for port 8000 (Backend)...
netsh advfirewall firewall delete rule name="EchoAI Backend" >nul 2>&1
netsh advfirewall firewall add rule name="EchoAI Backend" dir=in action=allow protocol=TCP localport=8000
if %errorLevel% equ 0 (
    echo ✓ Backend port 8000 allowed
) else (
    echo ✗ Failed to add backend rule
)

echo.
echo Adding firewall rule for port 5173 (Frontend)...
netsh advfirewall firewall delete rule name="EchoAI Frontend" >nul 2>&1
netsh advfirewall firewall add rule name="EchoAI Frontend" dir=in action=allow protocol=TCP localport=5173
if %errorLevel% equ 0 (
    echo ✓ Frontend port 5173 allowed
) else (
    echo ✗ Failed to add frontend rule
)

echo.
echo ========================================
echo   Network Access Configuration
echo ========================================
echo.
echo Your server IP: 10.68.247.45
echo.
echo Access from other devices:
echo   Frontend: https://10.68.247.45:5173
echo   Backend:  http://10.68.247.45:8000
echo.
echo NOTE: Both devices must be on the same network!
echo ========================================
echo.

pause
