#!/usr/bin/env python3
"""
Пример использования Chat Sync Plugin
Демонстрирует основные возможности плагина
"""

import os
import sys
import time
from datetime import datetime

# Добавляем путь к модулям проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chat_sync_plugin import ChatSyncPlugin
from integration.chat_sync_integration import ChatSyncIntegration
from databaseHandler.databaseSetup import SQLiteDB
from logger import logger


def example_basic_usage():
    """Пример базового использования плагина"""
    print("🧩 Пример базового использования Chat Sync Plugin")
    print("=" * 60)
    
    # Создаем экземпляр плагина
    plugin = ChatSyncPlugin()
    
    # Показываем статус
    status = plugin.get_plugin_status()
    print(f"Статус плагина: {status['name']} v{status['version']}")
    print(f"Инициализирован: {'Да' if status['initialized'] else 'Нет'}")
    print(f"Готов к работе: {'Да' if status['ready'] else 'Нет'}")
    
    # Добавляем тестового бота
    print("\n🤖 Добавление тестового бота...")
    bot_added = plugin.add_bot("1234567890:ABCdefGHIjklMNOpqrsTUVwxyz", "funpay_test_bot")
    print(f"Бот добавлен: {'Да' if bot_added else 'Нет'}")
    
    # Устанавливаем чат
    print("\n💬 Установка чата...")
    chat_set = plugin.set_chat_id(-1001234567890)
    print(f"Чат установлен: {'Да' if chat_set else 'Нет'}")
    
    # Показываем обновленный статус
    status = plugin.get_plugin_status()
    print(f"\nОбновленный статус:")
    print(f"Готов к работе: {'Да' if status['ready'] else 'Нет'}")
    print(f"Количество ботов: {status['bots_count']}")
    print(f"ID чата: {status['chat_id']}")


def example_account_sync():
    """Пример синхронизации аккаунтов"""
    print("\n🔄 Пример синхронизации аккаунтов")
    print("=" * 60)
    
    # Создаем экземпляр плагина
    plugin = ChatSyncPlugin()
    
    # Получаем список аккаунтов
    accounts = plugin.get_accounts_with_sync()
    print(f"Найдено аккаунтов: {len(accounts)}")
    
    if accounts:
        print("\nСписок аккаунтов:")
        for i, account in enumerate(accounts[:3], 1):  # Показываем первые 3
            sync_status = "Синхронизирован" if account['synced'] else "Не синхронизирован"
            print(f"{i}. {account['account_name']} - {sync_status}")
    
    # Синхронизируем все аккаунты
    print("\nСинхронизация всех аккаунтов...")
    result = plugin.sync_all_accounts()
    print(f"Результат: {result['synced']} успешно, {result['errors']} ошибок")


def example_integration_usage():
    """Пример использования интеграции"""
    print("\n🔗 Пример использования интеграции")
    print("=" * 60)
    
    # Создаем экземпляр интеграции
    integration = ChatSyncIntegration()
    
    # Показываем статус
    status = integration.get_plugin_status()
    print(f"Статус интеграции: {status['name']} v{status['version']}")
    print(f"Готов к работе: {'Да' if status['ready'] else 'Нет'}")
    
    # Получаем синхронизированные аккаунты
    synced_accounts = integration.get_synced_accounts()
    print(f"Синхронизированных аккаунтов: {len(synced_accounts)}")
    
    # Пример отправки сообщения
    if synced_accounts:
        account = synced_accounts[0]
        print(f"\nОтправка тестового сообщения для аккаунта {account['account_name']}...")
        success = integration.send_funpay_message(
            account['id'], 
            "Тестовое сообщение от Chat Sync Plugin"
        )
        print(f"Сообщение отправлено: {'Да' if success else 'Нет'}")


def example_rental_status_handling():
    """Пример обработки изменения статуса аренды"""
    print("\n📊 Пример обработки изменения статуса аренды")
    print("=" * 60)
    
    # Создаем экземпляр интеграции
    integration = ChatSyncIntegration()
    
    # Симулируем изменение статуса аренды
    test_account_id = 1
    old_owner = None
    new_owner = "test_user"
    
    print(f"Симуляция начала аренды аккаунта {test_account_id} пользователем {new_owner}")
    integration.handle_rental_start_with_chat_sync(test_account_id, new_owner)
    
    print(f"Симуляция окончания аренды аккаунта {test_account_id}")
    integration.handle_rental_end_with_chat_sync(test_account_id)


def example_configuration_management():
    """Пример управления конфигурацией"""
    print("\n⚙️ Пример управления конфигурацией")
    print("=" * 60)
    
    # Создаем экземпляр плагина
    plugin = ChatSyncPlugin()
    
    # Показываем текущую конфигурацию
    config = plugin.config
    print("Текущая конфигурация:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    
    # Изменяем настройку
    print("\nИзменение настройки 'self_notify'...")
    plugin.config['self_notify'] = not plugin.config['self_notify']
    plugin.save_config()
    print(f"self_notify: {plugin.config['self_notify']}")
    
    # Возвращаем обратно
    plugin.config['self_notify'] = not plugin.config['self_notify']
    plugin.save_config()
    print(f"self_notify (восстановлено): {plugin.config['self_notify']}")


def main():
    """Главная функция с примерами"""
    print("🚀 Примеры использования Chat Sync Plugin")
    print("=" * 80)
    
    try:
        # Базовое использование
        example_basic_usage()
        
        # Синхронизация аккаунтов
        example_account_sync()
        
        # Использование интеграции
        example_integration_usage()
        
        # Обработка статуса аренды
        example_rental_status_handling()
        
        # Управление конфигурацией
        example_configuration_management()
        
        print("\n✅ Все примеры выполнены успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении примеров: {str(e)}")
        logger.error(f"Error in examples: {str(e)}")
    
    finally:
        print("\n👋 Завершение работы с примерами")


if __name__ == "__main__":
    main()
