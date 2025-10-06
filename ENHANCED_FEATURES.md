# 🚀 Расширенные функции AutoRentSteam

## 📋 Обзор улучшений

Ваш бот AutoRentSteam был значительно улучшен с интеграцией лучших практик из других ботов. Добавлены следующие модули:

### 🔐 1. Система безопасности (security/)
- **AES-256 шифрование** для всех конфиденциальных данных
- Безопасное хранение Steam и FunPay учетных данных
- Генерация безопасных паролей и API ключей

### 💳 2. Система платежей (payments/)
- **YooKassa интеграция** для приема платежей
- Система подписок с различными тарифами
- Управление балансом пользователей
- История транзакций

### 👥 3. Управление пользователями (user_management/)
- Роли пользователей (user, premium, admin, super_admin)
- Статусы подписок (active, expired, cancelled, pending)
- Детальная статистика пользователей
- Логирование активности

### 🎮 4. Steam интеграция (steamHandler/playwright_steam.py)
- **Playwright автоматизация** браузера
- Автоматическая смена паролей Steam
- Выход из всех сессий
- Сохранение сессий

### 🔗 5. Интеграционный модуль (integration/)
- Объединяет все новые функции
- Упрощенный API для использования
- Централизованная конфигурация

## 🛠️ Установка и настройка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Установка Playwright

```bash
playwright install chromium
```

### 3. Настройка конфигурации

Скопируйте `config_example.py` в `config.py` и настройте:

```python
# Обязательные настройки
MASTER_ENCRYPTION_KEY = "ваш_32_символьный_ключ_здесь"  # Должен быть ровно 32 символа
PAYMENT_SYSTEM_ENABLED = True
USER_MANAGEMENT_ENABLED = True
PLAYWRIGHT_ENABLED = True

# YooKassa (опционально)
YOOKASSA_ENABLED = True
YOOKASSA_ACCOUNT_ID = "ваш_account_id"
YOOKASSA_SECRET_KEY = "ваш_secret_key"
```

## 📖 Использование новых функций

### Инициализация расширенного бота

```python
from integration.enhanced_bot import EnhancedAutoRentSteam
import config

# Инициализация
bot = EnhancedAutoRentSteam(config.__dict__)
```

### Работа с пользователями

```python
# Создание пользователя
bot.create_user(123456789, "username", "Имя", "Фамилия")

# Получение профиля
profile = bot.get_user_profile(123456789)
print(f"Роль: {profile['role']}")
print(f"Подписка: {profile['subscription_status']}")

# Проверка подписки
if bot.is_user_subscribed(123456789):
    print("Пользователь имеет активную подписку")
```

### Работа с платежами

```python
# Получение баланса
balance = bot.get_user_balance(123456789)
print(f"Баланс: {balance} руб.")

# Пополнение баланса
bot.add_balance(123456789, 100.0, "Пополнение через админ панель")

# Покупка подписки
success, message = bot.purchase_subscription(123456789, "1m")
if success:
    print("Подписка активирована!")
else:
    print(f"Ошибка: {message}")

# Получение планов подписок
plans = bot.get_subscription_plans()
for plan_id, plan in plans.items():
    print(f"{plan['name']}: {plan['price']} руб. на {plan['duration_days']} дней")
```

### Работа с Steam

```python
import asyncio

async def change_password_example():
    # Смена пароля Steam аккаунта
    success, logs, screenshots = await bot.change_steam_password(
        login="steam_login",
        password="old_password", 
        new_password="new_password",
        email_login="email@example.com",
        email_password="email_password",
        imap_host="imap.gmail.com"
    )
    
    if success:
        print("Пароль успешно изменен!")
        for log in logs:
            print(log)
    else:
        print("Ошибка смены пароля")

# Запуск
asyncio.run(change_password_example())
```

### Работа с шифрованием

```python
# Шифрование Steam учетных данных
encrypted = bot.encrypt_steam_credentials("login", "password")
print(f"Зашифрованные данные: {encrypted}")

# Расшифровка
login, password = bot.decrypt_steam_credentials(encrypted)
print(f"Логин: {login}, Пароль: {password}")
```

### Администрирование

```python
# Получение всех пользователей
users = bot.get_all_users(role="user", active_only=True)
for user in users:
    print(f"ID: {user['user_id']}, Имя: {user['first_name']}")

# Обновление роли пользователя
bot.update_user_role(123456789, "premium")

# Деактивация пользователя
bot.deactivate_user(123456789)

# Получение статистики системы
stats = bot.get_system_statistics()
print(f"Всего пользователей: {stats['total_users']}")
print(f"Активных: {stats['active_users']}")
print(f"С подпиской: {stats['subscribed_users']}")
```

## 🔧 Интеграция с существующим ботом

### Обновление botHandler/bot.py

```python
# В начале файла добавьте импорт
from integration.enhanced_bot import EnhancedAutoRentSteam

# Инициализируйте расширенный бот
enhanced_bot = EnhancedAutoRentSteam(config.__dict__)

# В обработчиках используйте новые функции
@bot.message_handler(commands=["balance"])
def balance_command(message):
    user_id = message.from_user.id
    balance = enhanced_bot.get_user_balance(user_id)
    bot.send_message(message.chat.id, f"💰 Ваш баланс: {balance} руб.")

@bot.message_handler(commands=["subscribe"])
def subscribe_command(message):
    user_id = message.from_user.id
    plans = enhanced_bot.get_subscription_plans()
    
    keyboard = types.InlineKeyboardMarkup()
    for plan_id, plan in plans.items():
        keyboard.add(types.InlineKeyboardButton(
            f"{plan['name']} - {plan['price']} руб.",
            callback_data=f"buy_plan_{plan_id}"
        ))
    
    bot.send_message(message.chat.id, "📋 Выберите план подписки:", reply_markup=keyboard)
```

### Добавление новых команд

```python
@bot.message_handler(commands=["profile"])
def profile_command(message):
    user_id = message.from_user.id
    profile = enhanced_bot.get_user_profile(user_id)
    
    if profile:
        text = f"""
👤 **Профиль пользователя**
🆔 ID: {profile['user_id']}
👤 Имя: {profile['first_name']} {profile['last_name']}
🎭 Роль: {profile['role']}
💳 Подписка: {profile['subscription_status']}
💰 Баланс: {profile['balance']} руб.
📅 Регистрация: {profile['created_at']}
        """
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Профиль не найден")

@bot.message_handler(commands=["stats"])
def stats_command(message):
    user_id = message.from_user.id
    stats = enhanced_bot.get_user_statistics(user_id)
    
    if stats:
        text = f"""
📊 **Ваша статистика**
🎮 Всего аккаунтов: {stats['total_accounts']}
⏰ Арендовано: {stats['rented_accounts']}
🕐 Часов аренды: {stats['total_rental_hours']}
💸 Потрачено: {stats['total_spent']} руб.
        """
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
```

## 🚨 Важные замечания

### Безопасность
- **Обязательно** установите `MASTER_ENCRYPTION_KEY` длиной ровно 32 символа
- Регулярно делайте резервные копии базы данных
- Не передавайте конфиденциальные данные в логах

### Производительность
- Playwright требует значительных ресурсов
- Рекомендуется запускать в headless режиме
- Настройте таймауты для предотвращения зависания

### Совместимость
- Все новые функции опциональны
- Существующий функционал остается без изменений
- Можно включать/выключать модули через конфигурацию

## 🔄 Миграция данных

При первом запуске с новыми функциями:

1. **База данных** автоматически создаст новые таблицы
2. **Существующие пользователи** будут мигрированы автоматически
3. **Конфиденциальные данные** можно зашифровать через API

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи в папке `logs/`
2. Убедитесь в правильности конфигурации
3. Проверьте установку всех зависимостей
4. Запустите диагностику: `python diagnose_bot.py`

## 🎉 Заключение

Теперь ваш AutoRentSteam бот включает:

✅ **Продвинутую систему безопасности** с AES-256 шифрованием  
✅ **Полноценную систему платежей** с YooKassa интеграцией  
✅ **Управление подписками** с различными тарифами  
✅ **Playwright автоматизацию** для Steam  
✅ **Расширенное управление пользователями** с ролями и статистикой  
✅ **Централизованную интеграцию** всех функций  

Ваш бот теперь соответствует enterprise-уровню и готов к масштабированию! 🚀
