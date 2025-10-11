import logging
import coloredlogs
import os
import sys
from datetime import datetime
from pathlib import Path

class DetailedFormatter(logging.Formatter):
    """Кастомный форматтер для более подробного логирования"""
    
    def format(self, record):
        # Добавляем информацию о модуле и функции
        if hasattr(record, 'funcName') and record.funcName != '<module>':
            location = f"{record.module}.{record.funcName}:{record.lineno}"
        else:
            location = f"{record.module}:{record.lineno}"
        
        # Форматируем время с миллисекундами
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        # Создаем цветные уровни
        level_colors = {
            'DEBUG': '\033[36m',      # Cyan
            'INFO': '\033[32m',       # Green
            'WARNING': '\033[33m',    # Yellow
            'ERROR': '\033[31m',      # Red
            'CRITICAL': '\033[35m'    # Magenta
        }
        reset_color = '\033[0m'
        
        level_color = level_colors.get(record.levelname, '')
        level_text = f"{level_color}{record.levelname:8}{reset_color}"
        
        # Форматируем сообщение
        if hasattr(record, 'extra_info'):
            extra = f" | {record.extra_info}"
        else:
            extra = ""
            
        formatted_message = (
            f"{timestamp} | {level_text} | {location:30} | {record.getMessage()}{extra}"
        )
        
        return formatted_message

class BotLogger:
    """Улучшенный логер для бота"""
    
    def __init__(self, name="SteamRentBot"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Очищаем существующие обработчики
        self.logger.handlers.clear()
        
        # Создаем директорию для логов
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Настраиваем консольный вывод
        self._setup_console_handler()
        
        # Настраиваем файловый вывод
        self._setup_file_handlers(log_dir)
        
        # Добавляем специальные методы
        self._add_special_methods()
        
        self.info("🚀 Логер инициализирован", extra_info="Logger started")
    
    def _setup_console_handler(self):
        """Настройка консольного вывода"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Используем coloredlogs для консоли
        coloredlogs.install(
            level="INFO",
            logger=self.logger,
            fmt="%(asctime)s | %(levelname)-8s | %(message)s",
            field_styles={
                'asctime': {'color': 'blue'},
                'levelname': {'color': 'white', 'bold': True},
                'message': {'color': 'white'}
            },
            level_styles={
                'debug': {'color': 'cyan'},
                'info': {'color': 'green'},
                'warning': {'color': 'yellow'},
                'error': {'color': 'red'},
                'critical': {'color': 'magenta', 'bold': True}
            }
        )
    
    def _setup_file_handlers(self, log_dir):
        """Настройка файлового вывода"""
        # Основной лог файл
        main_file_handler = logging.FileHandler(
            log_dir / "application.log", 
            encoding="utf-8-sig"
        )
        main_file_handler.setLevel(logging.DEBUG)
        main_formatter = DetailedFormatter()
        main_file_handler.setFormatter(main_formatter)
        self.logger.addHandler(main_file_handler)
        
        # Лог ошибок
        error_file_handler = logging.FileHandler(
            log_dir / "errors.log", 
            encoding="utf-8-sig"
        )
        error_file_handler.setLevel(logging.ERROR)
        error_formatter = DetailedFormatter()
        error_file_handler.setFormatter(error_formatter)
        self.logger.addHandler(error_file_handler)
        
        # Лог событий FunPay
        funpay_file_handler = logging.FileHandler(
            log_dir / "funpay.log", 
            encoding="utf-8-sig"
        )
        funpay_file_handler.setLevel(logging.DEBUG)
        funpay_formatter = DetailedFormatter()
        funpay_file_handler.setFormatter(funpay_formatter)
        self.logger.addHandler(funpay_file_handler)
        
        # Лог Telegram бота
        telegram_file_handler = logging.FileHandler(
            log_dir / "telegram.log", 
            encoding="utf-8-sig"
        )
        telegram_file_handler.setLevel(logging.DEBUG)
        telegram_formatter = DetailedFormatter()
        telegram_file_handler.setFormatter(telegram_formatter)
        self.logger.addHandler(telegram_file_handler)
        
        # Лог AutoGuard системы
        autoguard_file_handler = logging.FileHandler(
            log_dir / "autoguard.log", 
            encoding="utf-8-sig"
        )
        autoguard_file_handler.setLevel(logging.DEBUG)
        autoguard_formatter = DetailedFormatter()
        autoguard_file_handler.setFormatter(autoguard_formatter)
        self.logger.addHandler(autoguard_file_handler)
    
    def _add_special_methods(self):
        """Добавление специальных методов логирования"""
        
        def log_bot_start():
            self.info("🤖 Telegram бот запущен", extra_info="Bot started")
        
        def log_bot_stop():
            self.info("🛑 Telegram бот остановлен", extra_info="Bot stopped")
        
        def log_funpay_start():
            self.info("🔄 FunPay интеграция запущена", extra_info="FunPay started")
        
        def log_funpay_stop():
            self.info("⏹️ FunPay интеграция остановлена", extra_info="FunPay stopped")
        
        def log_new_order(order_id, buyer, amount, price):
            self.info(
                f"🛒 Новый заказ #{order_id} от {buyer}",
                extra_info=f"Amount: {amount}, Price: {price}₽"
            )
        
        def log_account_assigned(account_id, buyer, account_name):
            self.info(
                f"✅ Аккаунт {account_id} выдан пользователю {buyer}",
                extra_info=f"Account: {account_name}"
            )
        
        def log_password_changed(account_id, new_password):
            self.info(
                f"🔐 Пароль изменен для аккаунта {account_id}",
                extra_info=f"New password: {new_password}"
            )
        
        def log_rental_expired(account_id, owner):
            self.warning(
                f"⏰ Аренда истекла для аккаунта {account_id}",
                extra_info=f"Owner: {owner}"
            )
        
        def log_error(component, error_msg, extra_data=None):
            self.error(
                f"❌ Ошибка в {component}: {error_msg}",
                extra_info=extra_data or "No additional data"
            )
        
        def log_config_check(token_status, funpay_status, admin_status):
            self.info(
                "⚙️ Проверка конфигурации",
                extra_info=f"Bot: {token_status}, FunPay: {funpay_status}, Admin: {admin_status}"
            )
        
        def log_order_paid(order_id, buyer, amount, price):
            self.info(
                f"💰 Заказ #{order_id} оплачен пользователем {buyer}",
                extra_info=f"Amount: {amount}, Price: {price}₽"
            )
        
        def log_order_confirmed(order_id, buyer):
            self.info(
                f"✅ Заказ #{order_id} подтвержден",
                extra_info=f"Buyer: {buyer}"
            )
        
        def log_order_refunded(order_id, buyer, reason):
            self.warning(
                f"💸 Заказ #{order_id} возвращен",
                extra_info=f"Buyer: {buyer}, Reason: {reason}"
            )
        
        def log_chat_opened(user):
            self.info(
                f"💬 Чат открыт с пользователем {user}",
                extra_info="Chat opened"
            )
        
        def log_chat_closed(user):
            self.info(
                f"🔒 Чат закрыт с пользователем {user}",
                extra_info="Chat closed"
            )
        
        def log_lot_updated(lot_name, changes):
            self.info(
                f"📝 Лот '{lot_name}' обновлен",
                extra_info=f"Changes: {changes}"
            )
        
        def log_feedback_received(author, rating, text):
            self.info(
                f"⭐ Отзыв от {author}",
                extra_info=f"Rating: {rating}, Text: {text[:50]}..."
            )
        
        def log_autoguard_start():
            self.info("🔐 AutoGuard система запущена", extra_info="AutoGuard started")
        
        def log_autoguard_stop():
            self.info("⏹️ AutoGuard система остановлена", extra_info="AutoGuard stopped")
        
        def log_guard_code_sent(account_name, owner, code):
            self.info(
                f"🔑 Steam Guard код отправлен для {account_name}",
                extra_info=f"Owner: {owner}, Code: {code}"
            )
        
        def log_guard_code_error(account_name, owner, error):
            self.error(
                f"❌ Ошибка получения Steam Guard кода для {account_name}",
                extra_info=f"Owner: {owner}, Error: {error}"
            )
        
        def log_guard_scheduler_start(interval):
            self.info(
                f"⏰ AutoGuard планировщик запущен",
                extra_info=f"Interval: {interval}s"
            )
        
        def log_guard_scheduler_stop():
            self.info("⏹️ AutoGuard планировщик остановлен", extra_info="Scheduler stopped")
        
        def log_guard_welcome_sent(account_name, owner, code):
            self.info(
                f"🎉 Приветственный Steam Guard код отправлен для {account_name}",
                extra_info=f"Owner: {owner}, Code: {code}"
            )
        
        def log_guard_task_cleared(count):
            self.info(
                f"🧹 Очищено {count} старых задач AutoGuard",
                extra_info="Old tasks cleaned"
            )
        
        # Добавляем методы к логеру
        self.bot_start = log_bot_start
        self.bot_stop = log_bot_stop
        self.funpay_start = log_funpay_start
        self.funpay_stop = log_funpay_stop
        self.new_order = log_new_order
        self.account_assigned = log_account_assigned
        self.password_changed = log_password_changed
        self.rental_expired = log_rental_expired
        self.log_error = log_error
        self.config_check = log_config_check
        self.log_order_paid = log_order_paid
        self.log_order_confirmed = log_order_confirmed
        self.log_order_refunded = log_order_refunded
        self.log_chat_opened = log_chat_opened
        self.log_chat_closed = log_chat_closed
        self.log_lot_updated = log_lot_updated
        self.log_feedback_received = log_feedback_received
        self.autoguard_start = log_autoguard_start
        self.autoguard_stop = log_autoguard_stop
        self.guard_code_sent = log_guard_code_sent
        self.guard_code_error = log_guard_code_error
        self.guard_scheduler_start = log_guard_scheduler_start
        self.guard_scheduler_stop = log_guard_scheduler_stop
        self.guard_welcome_sent = log_guard_welcome_sent
        self.guard_task_cleared = log_guard_task_cleared
    
    def info(self, message, extra_info=None):
        """Логирование информационного сообщения"""
        if extra_info:
            self.logger.info(message, extra={'extra_info': extra_info})
        else:
            self.logger.info(message)
    
    def debug(self, message, extra_info=None):
        """Логирование отладочного сообщения"""
        if extra_info:
            self.logger.debug(message, extra={'extra_info': extra_info})
        else:
            self.logger.debug(message)
    
    def warning(self, message, extra_info=None):
        """Логирование предупреждения"""
        if extra_info:
            self.logger.warning(message, extra={'extra_info': extra_info})
        else:
            self.logger.warning(message)
    
    def error(self, message, extra_info=None):
        """Логирование ошибки"""
        if extra_info:
            self.logger.error(message, extra={'extra_info': extra_info})
        else:
            self.logger.error(message)
    
    def critical(self, message, extra_info=None):
        """Логирование критической ошибки"""
        if extra_info:
            self.logger.critical(message, extra={'extra_info': extra_info})
        else:
            self.logger.critical(message)

# Создаем глобальный экземпляр логера
logger = BotLogger()

# Для обратной совместимости
def get_logger(name=None):
    if name:
        return logging.getLogger(name)
    return logger.logger
