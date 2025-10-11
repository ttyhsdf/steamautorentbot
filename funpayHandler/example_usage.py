"""
Пример использования FunPay интеграции
"""

import asyncio
from FunPayAPI.account import Account
from funpayHandler.funpay_integration import FunPayIntegration
import telebot

# Пример инициализации
def setup_funpay_integration():
    """Настройка FunPay интеграции"""
    
    # Настройки
    FUNPAY_GOLDEN_KEY = "ваш_golden_key_здесь"
    BOT_TOKEN = "ваш_telegram_bot_token_здесь"
    
    # Создаем аккаунт FunPay
    funpay_account = Account(golden_key=FUNPAY_GOLDEN_KEY)
    
    # Создаем Telegram бота
    bot = telebot.TeleBot(BOT_TOKEN)
    
    # Создаем интеграцию
    integration = FunPayIntegration(funpay_account, bot)
    
    return integration

# Пример использования команд
def example_commands():
    """Примеры использования команд"""
    
    integration = setup_funpay_integration()
    
    # Получение статистики лотов
    lots_summary = integration.get_lots_summary()
    print("Статистика лотов:")
    print(integration.format_lots_display(lots_summary))
    
    # Поднятие лотов
    raise_result = integration.raise_lots_now()
    print("Результат поднятия лотов:")
    print(f"Успешно: {raise_result['success']}")
    print(f"Поднятые категории: {raise_result['raised_categories']}")
    
    # Получение статистики профиля
    profile_stats = integration.get_advanced_profile_stats()
    print("Статистика профиля:")
    print(profile_stats)
    
    # Запуск автоподнятия
    integration.start_auto_raise(interval_hours=4)
    print("Автоподнятие запущено с интервалом 4 часа")
    
    # Получение статуса поднятия
    raise_status = integration.get_raise_status()
    print("Статус поднятия:")
    print(integration.format_raise_status(raise_status))

# Пример обработки сообщений FunPay
def example_message_handling():
    """Пример обработки сообщений FunPay"""
    
    integration = setup_funpay_integration()
    
    # В реальном приложении это будет вызываться автоматически
    # при получении новых сообщений от FunPay
    def handle_funpay_message(event):
        """Обработчик сообщений FunPay"""
        integration.handle_new_message(event)
    
    return handle_funpay_message

# Пример настройки Telegram интерфейса
def example_telegram_setup():
    """Пример настройки Telegram интерфейса"""
    
    integration = setup_funpay_integration()
    bot = integration.telegram_bot
    
    # Добавление команд
    @bot.message_handler(commands=['funpay'])
    def funpay_command(message):
        integration.show_lots_menu(message.chat.id)
    
    @bot.message_handler(commands=['profile'])
    def profile_command(message):
        profile_text = integration.get_advanced_profile_stats()
        keyboard = integration.get_profile_stats_keyboard()
        bot.reply_to(message, profile_text, reply_markup=keyboard, parse_mode='HTML')
    
    # Запуск бота
    bot.infinity_polling()

if __name__ == "__main__":
    # Запуск примеров
    print("=== Пример использования FunPay интеграции ===")
    
    # Пример команд
    try:
        example_commands()
    except Exception as e:
        print(f"Ошибка в примере команд: {e}")
    
    # Пример обработки сообщений
    try:
        message_handler = example_message_handling()
        print("Обработчик сообщений создан")
    except Exception as e:
        print(f"Ошибка в примере обработки сообщений: {e}")
    
    print("=== Примеры завершены ===")
