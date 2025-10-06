# 🚀 Обновление GitHub репозитория AutoRentSteam
Write-Host "🚀 Обновление GitHub репозитория AutoRentSteam..." -ForegroundColor Green
Write-Host ""

Write-Host "📋 Проверка статуса Git..." -ForegroundColor Yellow
git status

Write-Host ""
Write-Host "📦 Добавление всех изменений..." -ForegroundColor Yellow
git add .

Write-Host ""
Write-Host "💾 Создание коммита..." -ForegroundColor Yellow
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

Write-Host ""
Write-Host "🔄 Синхронизация с удаленным репозиторием..." -ForegroundColor Yellow
git pull origin main --no-edit

Write-Host ""
Write-Host "🚀 Отправка изменений на GitHub..." -ForegroundColor Yellow
git push origin main

Write-Host ""
Write-Host "✅ Обновление завершено!" -ForegroundColor Green
Write-Host "📱 Ваш репозиторий: https://github.com/ttyhsdf/steamautorentbot" -ForegroundColor Cyan
Write-Host ""
Read-Host "Нажмите Enter для выхода"
