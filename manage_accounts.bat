@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo 👥 УПРАВЛЕНИЕ АККАУНТАМИ STEAM RENTAL BOT
echo ========================================
echo.
echo 🚀 Запуск менеджера аккаунтов...
python account_manager.py
echo.
pause