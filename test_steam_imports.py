#!/usr/bin/env python3
"""
Тест для проверки Steam импортов
Проверяет, что все необходимые модули импортируются без ошибок
"""

import sys
import traceback


def test_import(module_name, description):
    """Тестирует импорт модуля"""
    try:
        __import__(module_name)
        print(f"✅ {description}: OK")
        return True
    except ImportError as e:
        print(f"❌ {description}: FAILED - {e}")
        return False
    except Exception as e:
        print(f"⚠️ {description}: ERROR - {e}")
        return False


def main():
    """Основная функция тестирования"""
    print("🧪 Тестирование Steam импортов...")
    print("=" * 50)
    
    tests = [
        ("pysteamauth", "Steam аутентификация"),
        ("pysteamlib", "Steam библиотека"),
        ("steam", "Steam API"),
        ("steam_totp", "Steam TOTP"),
        ("steamapi", "Steam Web API"),
        ("steamid", "Steam ID"),
        ("selenium", "Selenium WebDriver"),
        ("yarl", "YARL URL"),
        ("lxml", "LXML парсер"),
        ("rsa", "RSA шифрование"),
        ("pydantic", "Pydantic валидация"),
        ("aiohttp", "AIOHTTP клиент"),
    ]
    
    success_count = 0
    total_count = len(tests)
    
    for module_name, description in tests:
        if test_import(module_name, description):
            success_count += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Результат: {success_count}/{total_count} модулей импортированы успешно")
    
    if success_count == total_count:
        print("✅ Все модули импортированы успешно!")
        
        # Тестируем специфичные импорты проекта
        print("\n🔍 Тестирование импортов проекта...")
        project_tests = [
            ("steamHandler.steampassword.steam_trade_alternative", "Steam Trade Alternative"),
            ("steamHandler.steampassword.chpassword", "Steam Password Change"),
            ("steamHandler.SteamGuard", "Steam Guard"),
            ("steamHandler.changePassword", "Change Password"),
        ]
        
        for module_name, description in project_tests:
            if test_import(module_name, description):
                success_count += 1
                total_count += 1
        
        print(f"\n📊 Итоговый результат: {success_count}/{total_count} модулей")
        
        if success_count == total_count:
            print("🎉 Все тесты пройдены! Бот готов к запуску.")
        else:
            print("⚠️ Некоторые модули проекта не импортируются.")
    else:
        print("❌ Не все модули установлены. Запустите:")
        print("   python install_steam_dependencies.py")
        print("   или")
        print("   setup.bat")


if __name__ == "__main__":
    main()
