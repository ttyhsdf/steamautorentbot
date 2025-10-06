# ========================================
# SteamRentLK1 - Пример конфигурации
# Скопируйте этот файл в config.py и заполните своими данными
# ========================================

# 🔑 FunPay API ключ
FUNPAY_GOLDEN_KEY = "ваш_golden_key_здесь"

# 🤖 Telegram Bot токен
BOT_TOKEN = "ваш_bot_token_здесь"

# 👑 ID администратора (ваш Telegram ID)
ADMIN_ID = 123456789  # Замените на ваш реальный ID

# 🔐 Секретная фраза для доступа к боту
SECRET_PHRASE = "ваша_секретная_фраза"

# ⏰ Настройки продления аренды
HOURS_FOR_REVIEW = 1  # Количество часов для продления при отзыве
AUTO_EXTEND_ENABLED = True  # Включить автоматическое продление
MAX_EXTENSION_HOURS = 24  # Максимальное количество часов для продления

# 🌐 Настройки прокси (опционально)
PROXY_URL = ""  # http://proxy:port или https://proxy:port
PROXY_LOGIN = ""  # логин для прокси
PROXY_PASSWORD = ""  # пароль для прокси

# ⚙️ Системные настройки
REFRESH_INTERVAL = 1300  # Интервал обновления сессии FunPay (в секундах)
RENTAL_CHECK_INTERVAL = 30  # Интервал проверки истечения аренды (в секундах)
MAX_RETRY_ATTEMPTS = 3  # Максимальное количество попыток для операций

# 📊 Настройки логирования
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_TO_FILE = True  # Сохранять логи в файл
LOG_TO_CONSOLE = True  # Выводить логи в консоль

# 🔔 Настройки уведомлений
NOTIFY_NEW_ORDERS = True  # Уведомления о новых заказах
NOTIFY_RENTAL_EXPIRY = True  # Уведомления об истечении аренды
NOTIFY_ERRORS = True  # Уведомления об ошибках

# 🗄️ Настройки базы данных
DB_BACKUP_ENABLED = True  # Включить автоматическое резервное копирование
DB_BACKUP_INTERVAL = 24  # Интервал резервного копирования (в часах)
DB_CLEANUP_ENABLED = True  # Включить очистку старых записей
DB_CLEANUP_DAYS = 30  # Удалять записи старше N дней

# 🔐 Настройки безопасности и шифрования
MASTER_ENCRYPTION_KEY = "ваш_32_символьный_ключ_шифрования_здесь"  # Должен быть ровно 32 символа
ENCRYPT_SENSITIVE_DATA = True  # Шифровать чувствительные данные
AUTO_GUARD_ENABLED = True  # Включить автоматическую выдачу Steam Guard кодов
AUTO_GUARD_ON_PURCHASE = True  # Выдавать код сразу при покупке
AUTO_GUARD_INTERVAL = 300  # Интервал проверки (в секундах)
AUTO_GUARD_MAX_ATTEMPTS = 3  # Максимальное количество попыток
AUTO_GUARD_RETRY_DELAY = 60  # Задержка между попытками (в секундах)
AUTO_GUARD_NOTIFY_ADMIN = True  # Уведомлять админа об ошибках
AUTO_GUARD_LOG_LEVEL = "INFO"  # Уровень логирования AutoGuard

# 💳 Настройки платежей и подписок
PAYMENT_SYSTEM_ENABLED = True  # Включить систему платежей
YOOKASSA_ENABLED = False  # Включить YooKassa (требует настройки)
YOOKASSA_ACCOUNT_ID = ""  # ID аккаунта YooKassa
YOOKASSA_SECRET_KEY = ""  # Секретный ключ YooKassa
YOOKASSA_WEBHOOK_URL = ""  # URL для webhook YooKassa
YOOKASSA_RETURN_URL = "https://t.me/your_bot"  # URL возврата после оплаты
MIN_TOPUP_AMOUNT = 10.0  # Минимальная сумма пополнения
SUBSCRIPTION_PLANS = {
    '1w': {'name': 'Недельная подписка', 'duration_days': 7, 'price': 50.00, 'description': 'Доступ на 7 дней'},
    '1m': {'name': 'Месячная подписка', 'duration_days': 30, 'price': 150.00, 'description': 'Доступ на 30 дней'},
    '3m': {'name': 'Квартальная подписка', 'duration_days': 90, 'price': 400.00, 'description': 'Доступ на 90 дней'}
}

# 🎮 Настройки Steam интеграции
PLAYWRIGHT_ENABLED = True  # Включить Playwright для Steam
PLAYWRIGHT_HEADLESS = True  # Запускать браузер в фоновом режиме
PLAYWRIGHT_DEBUG = False  # Режим отладки Playwright
STEAM_AUTO_LOGOUT = True  # Автоматический выход из всех сессий
STEAM_PASSWORD_CHANGE_ENABLED = True  # Включить автоматическую смену паролей
STEAM_SESSION_SAVE = True  # Сохранять сессии Steam

# 👥 Настройки управления пользователями
USER_MANAGEMENT_ENABLED = True  # Включить продвинутое управление пользователями
DEFAULT_USER_ROLE = "user"  # Роль по умолчанию для новых пользователей
USER_ACTIVITY_LOGGING = True  # Логировать активность пользователей
USER_STATISTICS_ENABLED = True  # Включить статистику пользователей
AUTO_CLEANUP_EXPIRED_SUBSCRIPTIONS = True  # Автоматически очищать истекшие подписки
SUBSCRIPTION_GRACE_PERIOD = 24  # Период отсрочки после истечения подписки (в часах)

# 📱 Настройки Telegram интерфейса
TELEGRAM_PAYMENT_BUTTONS = True  # Показывать кнопки оплаты в Telegram
TELEGRAM_SUBSCRIPTION_MENU = True  # Показывать меню подписок
TELEGRAM_USER_STATS = True  # Показывать статистику пользователя
TELEGRAM_ADMIN_PANEL = True  # Включить админ панель