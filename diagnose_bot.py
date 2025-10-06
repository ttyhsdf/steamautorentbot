#!/usr/bin/env python3
"""
Утилита диагностики проблем с ботом
Помогает выявить и исправить проблемы с Error 409
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot_instance_manager import BotInstanceManager, force_cleanup_bot
from config import BOT_TOKEN, ADMIN_ID
from logger import logger


def check_telegram_api():
    """Проверить доступность Telegram API"""
    print("🔍 Проверка Telegram API...")
    
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getMe",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                bot_info = data.get("result", {})
                print(f"✅ Bot доступен: @{bot_info.get('username', 'Unknown')}")
                print(f"   ID: {bot_info.get('id', 'Unknown')}")
                print(f"   Имя: {bot_info.get('first_name', 'Unknown')}")
                return True
            else:
                print(f"❌ API вернул ошибку: {data.get('description', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка сети: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {str(e)}")
        return False


def check_webhook_status():
    """Проверить статус webhook"""
    print("\n🔍 Проверка webhook...")
    
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                webhook_info = data.get("result", {})
                url = webhook_info.get("url", "")
                
                if url:
                    print(f"⚠️ Webhook установлен: {url}")
                    print("   Это может вызывать конфликты с polling")
                    
                    # Предлагаем удалить webhook
                    print("\n🔧 Удаление webhook...")
                    delete_response = requests.get(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook",
                        timeout=10
                    )
                    
                    if delete_response.status_code == 200:
                        delete_data = delete_response.json()
                        if delete_data.get("ok"):
                            print("✅ Webhook успешно удален")
                        else:
                            print(f"❌ Ошибка удаления webhook: {delete_data.get('description', 'Unknown error')}")
                    else:
                        print(f"❌ HTTP ошибка при удалении webhook: {delete_response.status_code}")
                else:
                    print("✅ Webhook не установлен")
                    return True
            else:
                print(f"❌ API вернул ошибку: {data.get('description', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка сети: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {str(e)}")
        return False


def check_bot_instance_status():
    """Проверить статус экземпляров бота"""
    print("\n🔍 Проверка экземпляров бота...")
    
    try:
        manager = BotInstanceManager()
        status = manager.get_status()
        
        print(f"📊 Статус системы:")
        print(f"   Lock файл существует: {status.get('lock_exists', False)}")
        print(f"   Lock валиден: {status.get('lock_valid', False)}")
        print(f"   Bot доступен: {status.get('bot_accessible', False)}")
        print(f"   Python процессов: {status.get('python_processes', 0)}")
        print(f"   Heartbeat существует: {status.get('heartbeat_exists', False)}")
        
        if status.get('lock_info'):
            lock_info = status['lock_info']
            print(f"\n📋 Информация о блокировке:")
            print(f"   PID: {lock_info.get('pid', 'Unknown')}")
            print(f"   Время запуска: {lock_info.get('start_time', 'Unknown')}")
            print(f"   Токен: {lock_info.get('token', 'Unknown')}")
            print(f"   Admin ID: {lock_info.get('admin_id', 'Unknown')}")
        
        return status
        
    except Exception as e:
        print(f"❌ Ошибка проверки статуса: {str(e)}")
        return None


def diagnose_and_fix():
    """Диагностика и исправление проблем"""
    print("🔧 ДИАГНОСТИКА STEAM RENTAL BOT")
    print("=" * 50)
    
    # Проверяем Telegram API
    api_ok = check_telegram_api()
    if not api_ok:
        print("\n❌ Проблема с Telegram API. Проверьте BOT_TOKEN в config.py")
        return False
    
    # Проверяем webhook
    webhook_ok = check_webhook_status()
    if not webhook_ok:
        print("\n❌ Проблема с webhook")
        return False
    
    # Проверяем статус экземпляров
    status = check_bot_instance_status()
    if status is None:
        print("\n❌ Не удалось получить статус системы")
        return False
    
    # Анализируем проблемы
    print("\n🔍 Анализ проблем...")
    
    problems = []
    
    if not status.get('bot_accessible', False):
        problems.append("Bot недоступен через API")
    
    if status.get('lock_valid', False):
        problems.append("Активная блокировка (другой экземпляр запущен)")
    
    if status.get('python_processes', 0) > 1:
        problems.append("Множественные Python процессы")
    
    if problems:
        print(f"\n⚠️ Найдены проблемы:")
        for i, problem in enumerate(problems, 1):
            print(f"   {i}. {problem}")
        
        print(f"\n🔧 Попытка автоматического исправления...")
        
        # Принудительная очистка
        if force_cleanup_bot():
            print("✅ Принудительная очистка завершена")
            
            # Повторная проверка
            print("\n🔍 Повторная проверка...")
            time.sleep(2)
            
            new_status = check_bot_instance_status()
            if new_status and not new_status.get('lock_valid', False):
                print("✅ Проблемы исправлены!")
                return True
            else:
                print("❌ Проблемы не исправлены автоматически")
                return False
        else:
            print("❌ Не удалось выполнить очистку")
            return False
    else:
        print("\n✅ Проблем не найдено!")
        return True


def interactive_fix():
    """Интерактивное исправление"""
    print("\n🔧 ИНТЕРАКТИВНОЕ ИСПРАВЛЕНИЕ")
    print("=" * 30)
    
    while True:
        print("\nВыберите действие:")
        print("1. 🔍 Диагностика")
        print("2. 🧹 Принудительная очистка")
        print("3. 🔒 Проверка блокировок")
        print("4. 🌐 Проверка API")
        print("5. ❌ Выход")
        
        choice = input("\nВведите номер (1-5): ").strip()
        
        if choice == "1":
            diagnose_and_fix()
        elif choice == "2":
            print("\n🧹 Выполнение принудительной очистки...")
            if force_cleanup_bot():
                print("✅ Очистка завершена")
            else:
                print("❌ Очистка не удалась")
        elif choice == "3":
            check_bot_instance_status()
        elif choice == "4":
            check_telegram_api()
            check_webhook_status()
        elif choice == "5":
            print("👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор")


if __name__ == "__main__":
    try:
        print("🚀 Запуск диагностики...")
        
        if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
            interactive_fix()
        else:
            success = diagnose_and_fix()
            if success:
                print("\n✅ Диагностика завершена успешно!")
                print("💡 Теперь можно запустить бота: start.bat")
            else:
                print("\n❌ Диагностика выявила проблемы")
                print("💡 Попробуйте интерактивный режим: python diagnose_bot.py --interactive")
        
    except KeyboardInterrupt:
        print("\n\n👋 Диагностика прервана пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка диагностики: {str(e)}")
        logger.error(f"Diagnostic error: {str(e)}")
    
    print("\n⏸️  Нажмите Enter для выхода...")
    input()
