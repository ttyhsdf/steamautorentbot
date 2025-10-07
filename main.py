from botHandler.bot import main
from funpayHandler.funpay import startFunpay
from config import BOT_TOKEN, FUNPAY_GOLDEN_KEY, ADMIN_ID
from logger import logger
from messaging.message_sender import is_message_sender_ready
from bot_instance_manager import BotInstanceManager, check_bot_instance, force_cleanup_bot

import threading
import asyncio
import sys
import time
import signal


def check_config():
    """Проверяет корректность конфигурации"""
    errors = []
    
    if not BOT_TOKEN or BOT_TOKEN.strip() == "":
        errors.append("BOT_TOKEN не задан в config.py")
    
    if not FUNPAY_GOLDEN_KEY or FUNPAY_GOLDEN_KEY.strip() == "":
        errors.append("FUNPAY_GOLDEN_KEY не задан в config.py")
    
    if not ADMIN_ID or ADMIN_ID == 0:
        errors.append("ADMIN_ID не задан в config.py (должен быть числом, например: 123456789)")
    
    if errors:
        print("❌ Ошибки конфигурации:")
        for error in errors:
            print(f"  - {error}")
        print("\n📝 Отредактируйте файл config.py и заполните все необходимые поля")
        return False
    
    return True


def start_funpay_thread():
    """Запускает поток FunPay с обработкой ошибок"""
    def funpay_wrapper():
        try:
            logger.info("Запуск FunPay потока...")
            startFunpay()
        except Exception as e:
            logger.error(f"Ошибка в FunPay потоке: {str(e)}")
            print(f"❌ Ошибка FunPay: {str(e)}")
    
    thread = threading.Thread(target=funpay_wrapper, daemon=True)
    thread.start()
    return thread


def start_bot_thread():
    """Запускает поток бота с обработкой ошибок"""
    def bot_wrapper():
        try:
            logger.info("Запуск Telegram бота...")
            main()
        except Exception as e:
            logger.error(f"Ошибка в боте: {str(e)}")
            print(f"❌ Ошибка бота: {str(e)}")
    
    thread = threading.Thread(target=bot_wrapper, daemon=True)
    thread.start()
    return thread


def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    print(f"\n🛑 Получен сигнал {signum}, завершение работы...")
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main_loop():
    """Основной цикл работы бота"""
    bot_manager = None
    funpay_thread = None
    bot_thread = None
    success = False
    
    try:
        print("🚀 Запуск Steam Rental Bot...")
        print("=" * 50)
        
        # Проверяем конфигурацию
        if not check_config():
            print("\n⏸️  Нажмите Enter для выхода...")
            input()
            return False
        
        logger.config_check("✅ OK", "✅ OK", "✅ OK")
        print("✅ Конфигурация корректна")
        
        # Создаем менеджер экземпляров
        bot_manager = BotInstanceManager()
        
        # Проверяем, можно ли запустить бота
        print("🔍 Проверка доступности бота...")
        if not check_bot_instance():
            print("❌ Ошибка: Не удается запустить бота")
            print("💡 Возможные причины:")
            print("   • Уже запущен другой экземпляр бота")
            print("   • Неверный BOT_TOKEN")
            print("   • Проблемы с интернетом")
            
            # Предлагаем принудительную очистку
            print("\n🔧 Попытка принудительной очистки...")
            if force_cleanup_bot():
                print("✅ Очистка завершена, повторная попытка...")
                time.sleep(2)
                if not check_bot_instance():
                    print("❌ Очистка не помогла")
                    print("\n⏸️  Нажмите Enter для выхода...")
                    input()
                    return False
            else:
                print("❌ Не удалось выполнить очистку")
                print("\n⏸️  Нажмите Enter для выхода...")
                input()
                return False
        
        # Получаем блокировку
        print("🔒 Получение блокировки...")
        if not bot_manager.acquire_lock():
            print("❌ Не удалось получить блокировку")
            print("💡 Возможно, уже запущен другой экземпляр бота")
            print("\n⏸️  Нажмите Enter для выхода...")
            input()
            return False
        
        print("✅ Блокировка получена")
        
        # Запускаем потоки
        print("🔄 Запуск потоков...")
        logger.info("Запуск потоков бота", extra_info="Starting bot threads")
        
        funpay_thread = start_funpay_thread()
        bot_thread = start_bot_thread()
        
        logger.bot_start()
        logger.funpay_start()
        
        print("✅ Бот успешно запущен!")
        print("📱 Telegram бот активен")
        print("🔄 FunPay интеграция активна")
        
        # Ждем инициализации системы сообщений
        print("⏳ Ожидание инициализации системы сообщений...")
        for i in range(30):  # Ждем до 30 секунд
            if is_message_sender_ready():
                print("✅ Система сообщений готова")
                break
            time.sleep(1)
        else:
            print("⚠️ Система сообщений не инициализирована, но бот продолжает работу")
        
        print("=" * 50)
        print("💡 Для остановки нажмите Ctrl+C")
        
        # Основной цикл работы
        try:
            while True:
                time.sleep(1)
                
                # Проверяем состояние потоков
                if not funpay_thread.is_alive():
                    logger.warning("FunPay поток завершился неожиданно")
                    print("⚠️ FunPay поток завершился, перезапуск...")
                    funpay_thread = start_funpay_thread()
                
                if not bot_thread.is_alive():
                    logger.warning("Bot поток завершился неожиданно")
                    print("⚠️ Bot поток завершился, перезапуск...")
                    bot_thread = start_bot_thread()
                
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки", extra_info="KeyboardInterrupt received")
            print("\n🛑 Получен сигнал остановки...")
            success = True
            
    except Exception as e:
        logger.critical(f"Критическая ошибка: {str(e)}", extra_info=f"Exception type: {type(e).__name__}")
        print(f"❌ Критическая ошибка: {str(e)}")
        success = False
        
    finally:
        # Корректное завершение
        print("⏳ Завершение работы...")
        
        try:
            if bot_manager:
                bot_manager.release_lock()
                print("✅ Блокировка освобождена")
        except Exception as e:
            logger.error(f"Error releasing lock: {str(e)}")
        
        try:
            logger.bot_stop()
            logger.funpay_stop()
            print("✅ Логирование остановлено")
        except Exception as e:
            logger.error(f"Error stopping logging: {str(e)}")
        
        print("✅ Завершение работы завершено")
    
    return success


if __name__ == "__main__":
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        success = main_loop()
        if not success:
            print("\n⏸️  Нажмите Enter для выхода...")
            input()
            sys.exit(1)
    except Exception as e:
        logger.critical(f"Fatal error in main: {str(e)}")
        print(f"❌ Фатальная ошибка: {str(e)}")
        print("\n⏸️  Нажмите Enter для выхода...")
        input()
        sys.exit(1)
