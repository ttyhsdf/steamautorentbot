#!/usr/bin/env python3
"""
Скрипт для установки Steam зависимостей
Решает проблему с отсутствующими библиотеками
"""

import subprocess
import sys
import os


def install_package(package):
    """Устанавливает пакет через pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ {package} установлен успешно")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки {package}: {e}")
        return False


def main():
    """Основная функция установки"""
    print("🚀 Установка Steam зависимостей...")
    print("=" * 50)
    
    # Список необходимых пакетов
    packages = [
        "pysteamauth==1.1.2",
        "pysteamlib==1.0.1", 
        "steam-totp==1.1.0",
        "steam==1.4.4",
        "steamapi==2.0.0",
        "steamid==1.0.0",
        "selenium==4.15.0",
        "yarl==1.8.2",
        "lxml==5.3.0",
        "rsa==4.7",
        "pydantic==1.9.0",
        "aiohttp==3.10.2"
    ]
    
    success_count = 0
    total_count = len(packages)
    
    for package in packages:
        if install_package(package):
            success_count += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Результат: {success_count}/{total_count} пакетов установлено")
    
    if success_count == total_count:
        print("✅ Все зависимости установлены успешно!")
        print("\n💡 Теперь вы можете запустить бота:")
        print("   python main.py")
    else:
        print("⚠️ Некоторые пакеты не удалось установить")
        print("💡 Попробуйте установить их вручную:")
        for package in packages:
            print(f"   pip install {package}")


if __name__ == "__main__":
    main()
