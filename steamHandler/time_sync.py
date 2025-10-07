#!/usr/bin/env python3
"""
Утилита для проверки синхронизации времени с Steam
Используется для диагностики проблем с Steam Guard кодами
"""

import time
import requests
import json
from datetime import datetime

def check_steam_time_sync():
    """Проверяет синхронизацию времени с сервером Steam"""
    try:
        print("🕐 Проверка синхронизации времени с Steam...")
        
        # Получаем время сервера Steam
        response = requests.post(
            "https://api.steampowered.com/ITwoFactorService/QueryTime/v0001",
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Ошибка получения времени Steam: HTTP {response.status_code}")
            return False
            
        data = response.json()
        steam_time = int(data["response"]["server_time"])
        local_time = int(time.time())
        
        time_diff = steam_time - local_time
        
        print(f"📊 Результаты проверки:")
        print(f"   Steam время: {steam_time} ({datetime.fromtimestamp(steam_time)})")
        print(f"   Локальное время: {local_time} ({datetime.fromtimestamp(local_time)})")
        print(f"   Разница: {time_diff} секунд")
        
        if abs(time_diff) <= 30:
            print("✅ Синхронизация времени в норме")
            return True
        elif abs(time_diff) <= 60:
            print("⚠️  Небольшое расхождение времени, но допустимое")
            return True
        else:
            print("❌ Критическое расхождение времени!")
            print("💡 Рекомендации:")
            print("   • Синхронизируйте время системы")
            print("   • Проверьте настройки часового пояса")
            print("   • Перезагрузите компьютер")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Таймаут при подключении к Steam")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка подключения к Steam")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {str(e)}")
        return False

def test_steam_guard_generation(mafile_path):
    """Тестирует генерацию Steam Guard кода"""
    try:
        print(f"\n🔐 Тестирование генерации Steam Guard кода...")
        print(f"📁 Файл: {mafile_path}")
        
        with open(mafile_path, "r", encoding='utf-8') as f:
            data = json.load(f)
            
        if "shared_secret" not in data:
            print("❌ Отсутствует shared_secret в .maFile")
            return False
            
        # Импортируем функцию генерации
        from SteamGuard import get_steam_guard_code
        
        # Генерируем код
        code = get_steam_guard_code(mafile_path)
        
        if code:
            print(f"✅ Steam Guard код сгенерирован: {code}")
            return True
        else:
            print("❌ Не удалось сгенерировать Steam Guard код")
            return False
            
    except FileNotFoundError:
        print(f"❌ Файл .maFile не найден: {mafile_path}")
        return False
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔧 Диагностика Steam Guard")
    print("=" * 40)
    
    # Проверяем синхронизацию времени
    time_ok = check_steam_time_sync()
    
    # Если есть .maFile, тестируем генерацию кода
    import os
    mafile_path = "test.maFile"  # Замените на путь к вашему .maFile
    if os.path.exists(mafile_path):
        code_ok = test_steam_guard_generation(mafile_path)
    else:
        print(f"\n⚠️  Файл .maFile не найден: {mafile_path}")
        print("   Создайте тестовый .maFile для полной диагностики")
        code_ok = False
    
    print("\n" + "=" * 40)
    if time_ok and code_ok:
        print("✅ Все проверки пройдены успешно!")
    else:
        print("❌ Обнаружены проблемы, требующие внимания")
