@echo off
chcp 65001 >nul
echo ========================================
echo INSTALLING STEAM RENTAL BOT DEPENDENCIES
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
echo Installing dependencies...
echo.

echo Installing main packages...
pip install -r requirements.txt

echo.
echo Installing additional packages...
pip install webdriver-manager

echo.
echo Installing Steam dependencies...
python install_steam_dependencies.py

echo.
echo Cleaning conflicting packages...
pip uninstall pydantic pydantic-core -y 2>nul

echo.
echo Installing compatible versions...
pip install pydantic==1.9.0 pysteamlib==1.0.1

echo.
echo Installation completed!
echo.
echo You can now run the bot: start.bat
echo.
pause