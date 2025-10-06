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
