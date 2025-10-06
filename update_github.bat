@echo off
chcp 65001 >nul
echo 🚀 Обновление GitHub репозитория AutoRentSteam...
echo.

echo 📋 Проверка статуса Git...
git status

echo.
echo 📦 Добавление всех изменений...
git add .

echo.
echo 💾 Создание коммита...
git commit -m "🚀 Major Update: Enterprise-Level Steam Rental Bot

✨ New Features:
- 🔐 AES-256 encryption for sensitive data
- 💳 YooKassa payment integration  
- 🎭 Playwright-based Steam automation
- 👥 Advanced user management system
- 📊 Enhanced analytics and monitoring
- 🛡️ Improved security and access control

🔧 Improvements:
- Fixed requirements.txt dependencies
- Enhanced database schema with payment tables
- Added comprehensive documentation
- Improved error handling and logging
- Better Steam Guard code generation

📚 Documentation:
- USER_GUIDE.md - Complete user manual
- QUICK_START.md - 5-minute setup guide
- INSTALLATION_GUIDE.md - Detailed installation
- ENHANCED_FEATURES.md - New features overview

🎯 Ready for production use with enterprise-level features!"

echo.
echo 🔄 Синхронизация с удаленным репозиторием...
git pull origin main --no-edit

echo.
echo 🚀 Отправка изменений на GitHub...
git push origin main

echo.
echo ✅ Обновление завершено!
echo 📱 Ваш репозиторий: https://github.com/ttyhsdf/steamautorentbot
echo.
pause
