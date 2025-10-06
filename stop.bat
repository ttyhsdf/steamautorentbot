@echo off
chcp 65001 >nul
echo ========================================
echo 🛑 ОСТАНОВКА STEAM RENTAL BOT
echo ========================================
echo.

echo 🔍 Поиск запущенных процессов бота...
python -c "from bot_instance_manager import force_cleanup_bot; force_cleanup_bot()" 2>nul

echo.
echo 🧹 Принудительная очистка процессов...
taskkill /f /im python.exe 2>nul

echo.
echo 🗑️ Удаление файлов блокировки...
if exist "locks\bot_instance.lock" del "locks\bot_instance.lock"
if exist "locks\bot_instance.pid" del "locks\bot_instance.pid"
if exist "locks\bot_heartbeat.json" del "locks\bot_heartbeat.json"

echo.
echo ✅ Остановка завершена!
echo.
pause
