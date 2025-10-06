@echo off
chcp 65001 >nul
echo ========================================
echo STARTING STEAM RENTAL BOT
echo ========================================
echo.

cd /d "%~dp0"

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python from https://python.org
    echo.
    pause
    exit /b 1
)

echo Python found

echo.
echo Starting bot...
python main.py

echo.
echo Press any key to exit...
pause >nul