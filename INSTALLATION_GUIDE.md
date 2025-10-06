# 🚀 Руководство по установке AutoRentSteam

## ✅ Готово к установке

Файл `requirements.txt` уже исправлен и содержит только необходимые зависимости.

## ✅ Решение

### 1. Установите зависимости

```bash
pip install -r requirements.txt
```

### 2. Или установите зависимости по частям

```bash
# Основные зависимости
pip install pyTelegramBotAPI==4.15.2
pip install requests==2.31.0
pip install aiohttp==3.10.2

# Криптография
pip install cryptography==42.0.8
pip install bcrypt==4.3.0

# Веб-автоматизация
pip install playwright==1.44.0
pip install selenium==4.15.0

# Платежи
pip install yookassa==2.3.0

# Остальные зависимости
pip install beautifulsoup4==4.13.3
pip install psutil==7.0.0
pip install coloredlogs==15.0.1
pip install pydantic==2.5.0
pip install python-dateutil==2.8.2
pip install ujson==5.8.0
```

### 3. Установите Playwright браузеры

```bash
playwright install chromium
```

## 🔧 Альтернативная установка (если проблемы продолжаются)

### Вариант 1: Минимальная установка

```bash
# Только основные зависимости
pip install pyTelegramBotAPI requests aiohttp cryptography playwright yookassa
playwright install chromium
```

### Вариант 2: Поэтапная установка

```bash
# Шаг 1: Основные модули
pip install pyTelegramBotAPI requests aiohttp

# Шаг 2: Криптография
pip install cryptography bcrypt

# Шаг 3: Веб-автоматизация
pip install playwright selenium
playwright install chromium

# Шаг 4: Платежи
pip install yookassa

# Шаг 5: Остальное
pip install beautifulsoup4 psutil coloredlogs pydantic python-dateutil ujson
```

## 🐛 Устранение проблем

### Проблема: "No module named 'OpenSSL'"

**Решение:**
```bash
# Удалите проблемный пакет
pip uninstall secrets

# Установите только нужные зависимости
pip install cryptography==42.0.8
```

### Проблема: "Playwright not found"

**Решение:**
```bash
# Установите Playwright
pip install playwright==1.44.0

# Установите браузеры
playwright install chromium
```

### Проблема: "YooKassa import error"

**Решение:**
```bash
# Установите YooKassa
pip install yookassa==2.3.0

# Или отключите в конфигурации
YOOKASSA_ENABLED = False
```

## 📋 Проверка установки

Создайте файл `test_installation.py`:

```python
#!/usr/bin/env python3
"""Тест установки зависимостей"""

def test_imports():
    """Проверяет импорт всех модулей"""
    try:
        # Основные модули
        import telebot
        import requests
        import aiohttp
        print("✅ Основные модули: OK")
        
        # Криптография
        import cryptography
        import bcrypt
        print("✅ Криптография: OK")
        
        # Playwright
        try:
            from playwright.async_api import async_playwright
            print("✅ Playwright: OK")
        except ImportError:
            print("❌ Playwright: НЕ УСТАНОВЛЕН")
        
        # YooKassa
        try:
            import yookassa
            print("✅ YooKassa: OK")
        except ImportError:
            print("❌ YooKassa: НЕ УСТАНОВЛЕН")
        
        # Остальные модули
        import beautifulsoup4
        import psutil
        import coloredlogs
        import pydantic
        print("✅ Дополнительные модули: OK")
        
        print("\n🎉 Все зависимости установлены успешно!")
        return True
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False

if __name__ == "__main__":
    test_imports()
```

Запустите тест:
```bash
python test_installation.py
```

## 🚀 Запуск бота

После успешной установки:

1. **Настройте конфигурацию:**
   ```bash
   cp config_example.py config.py
   # Отредактируйте config.py
   ```

2. **Запустите бота:**
   ```bash
   python main.py
   ```

## 📞 Поддержка

Если проблемы продолжаются:

1. **Проверьте версию Python:**
   ```bash
   python --version
   # Должна быть 3.8 или выше
   ```

2. **Обновите pip:**
   ```bash
   python -m pip install --upgrade pip
   ```

3. **Очистите кэш pip:**
   ```bash
   pip cache purge
   ```

4. **Установите в виртуальном окружении:**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # или
   source venv/bin/activate  # Linux/Mac
   pip install -r requirements_fixed.txt
   ```

## 🎯 Минимальная рабочая конфигурация

Если нужен только базовый функционал:

```python
# config.py - минимальная конфигурация
BOT_TOKEN = "ваш_токен"
ADMIN_ID = 123456789
FUNPAY_GOLDEN_KEY = "ваш_ключ"
SECRET_PHRASE = "ваша_фраза"

# Отключите новые функции
PAYMENT_SYSTEM_ENABLED = False
USER_MANAGEMENT_ENABLED = False
PLAYWRIGHT_ENABLED = False
```

Это позволит запустить бота с базовым функционалом без дополнительных зависимостей.
