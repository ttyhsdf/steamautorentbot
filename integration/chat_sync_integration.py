#!/usr/bin/env python3
"""
Модуль интеграции Chat Sync Plugin с основным ботом
Обеспечивает связь между плагином и системой управления аккаунтами
"""

import os
import sys
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional

# Добавляем путь к модулям проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chat_sync_plugin import ChatSyncPlugin
from databaseHandler.databaseSetup import SQLiteDB
from logger import logger
from messaging.message_sender import initialize_message_sender
from funpayHandler.funpay_chat_sync import initialize_funpay_chat_sync, get_funpay_chat_sync, cleanup_funpay_chat_sync


class ChatSyncIntegration:
    """Класс интеграции плагина Chat Sync с основным ботом"""
    
    def __init__(self):
        self.plugin = ChatSyncPlugin()
        self.db = SQLiteDB()
        self.monitoring_active = False
        self.monitor_thread = None
        
        # Инициализируем интеграцию
        self.init()
    
    def init(self):
        """Инициализация интеграции"""
        try:
            logger.info("Инициализация Chat Sync интеграции")
            
            # Инициализируем FunPay Chat Sync
            if initialize_funpay_chat_sync(self.plugin):
                logger.info("FunPay Chat Sync инициализирован")
            else:
                logger.warning("Не удалось инициализировать FunPay Chat Sync")
            
            # Запускаем мониторинг изменений аккаунтов
            self.start_account_monitoring()
            
            logger.info("Chat Sync интеграция инициализирована")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации интеграции: {str(e)}")
    
    def start_account_monitoring(self):
        """Запускает мониторинг изменений аккаунтов"""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitor_thread = threading.Thread(target=self._monitor_accounts, daemon=True)
            self.monitor_thread.start()
            logger.info("Мониторинг аккаунтов запущен")
    
    def stop_account_monitoring(self):
        """Останавливает мониторинг изменений аккаунтов"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Мониторинг аккаунтов остановлен")
    
    def _monitor_accounts(self):
        """Мониторит изменения в аккаунтах"""
        last_rental_states = {}
        
        while self.monitoring_active:
            try:
                # Получаем текущее состояние всех аккаунтов
                accounts = self.db.get_all_accounts()
                current_rental_states = {
                    acc['id']: acc['owner'] for acc in accounts
                }
                
                # Проверяем изменения
                for account_id, current_owner in current_rental_states.items():
                    last_owner = last_rental_states.get(account_id)
                    
                    if last_owner != current_owner:
                        # Статус аренды изменился
                        self._handle_rental_status_change(account_id, last_owner, current_owner)
                        last_rental_states[account_id] = current_owner
                
                # Обновляем последние состояния
                last_rental_states.update(current_rental_states)
                
                # Пауза между проверками
                time.sleep(30)  # Проверяем каждые 30 секунд
                
            except Exception as e:
                logger.error(f"Ошибка мониторинга аккаунтов: {str(e)}")
                time.sleep(60)  # При ошибке ждем дольше
    
    def _handle_rental_status_change(self, account_id: int, old_owner: str, new_owner: str):
        """Обрабатывает изменение статуса аренды аккаунта"""
        try:
            logger.info(f"Изменение статуса аренды аккаунта {account_id}: {old_owner} -> {new_owner}")
            
            # Уведомляем плагин об изменении
            self.plugin.handle_rental_status_change(account_id, old_owner, new_owner)
            
            # Если включена автосинхронизация, синхронизируем аккаунт
            if self.plugin.config.get('auto_sync_accounts', True):
                self.sync_account(account_id)
            
        except Exception as e:
            logger.error(f"Ошибка обработки изменения статуса аренды: {str(e)}")
    
    def sync_account(self, account_id: int) -> bool:
        """Синхронизирует конкретный аккаунт"""
        try:
            account = self.db.get_account_by_id(account_id)
            if not account:
                logger.error(f"Аккаунт с ID {account_id} не найден")
                return False
            
            # Синхронизируем с плагином
            success = self.plugin.sync_account_with_chat(account_id, account_id)
            
            if success:
                logger.info(f"Аккаунт {account['account_name']} синхронизирован")
            else:
                logger.warning(f"Не удалось синхронизировать аккаунт {account['account_name']}")
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации аккаунта {account_id}: {str(e)}")
            return False
    
    def sync_all_accounts(self) -> Dict[str, int]:
        """Синхронизирует все аккаунты"""
        try:
            logger.info("Начинаю синхронизацию всех аккаунтов")
            result = self.plugin.sync_all_accounts()
            logger.info(f"Синхронизация завершена: {result['synced']} успешно, {result['errors']} ошибок")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка массовой синхронизации: {str(e)}")
            return {'synced': 0, 'errors': 1}
    
    def send_funpay_message(self, account_id: int, message: str) -> bool:
        """Отправляет сообщение в FunPay чат для аккаунта"""
        try:
            account = self.db.get_account_by_id(account_id)
            if not account:
                logger.error(f"Аккаунт с ID {account_id} не найден")
                return False
            
            # Отправляем сообщение через плагин
            success = self.plugin.send_funpay_message(account_id, message, account['account_name'])
            
            if success:
                logger.info(f"Сообщение отправлено для аккаунта {account['account_name']}")
            else:
                logger.error(f"Ошибка отправки сообщения для аккаунта {account['account_name']}")
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {str(e)}")
            return False
    
    def get_plugin_status(self) -> Dict[str, Any]:
        """Возвращает статус плагина"""
        return self.plugin.get_plugin_status()
    
    def get_synced_accounts(self) -> list:
        """Возвращает список синхронизированных аккаунтов"""
        return self.plugin.get_accounts_with_sync()
    
    def initialize_message_sender(self, account):
        """Инициализирует отправитель сообщений"""
        try:
            initialize_message_sender(account)
            logger.info("MessageSender инициализирован для Chat Sync")
        except Exception as e:
            logger.error(f"Ошибка инициализации MessageSender: {str(e)}")
    
    def handle_new_order(self, order_data: Dict[str, Any]):
        """Обрабатывает новый заказ"""
        try:
            buyer_username = order_data.get('buyer_username')
            if not buyer_username:
                return
            
            # Находим аккаунт для заказа
            accounts = self.db.get_unowned_accounts()
            if not accounts:
                logger.warning("Нет свободных аккаунтов для заказа")
                return
            
            # Выбираем первый свободный аккаунт
            account = accounts[0]
            
            # Синхронизируем аккаунт с чатом покупателя
            self.sync_account(account['id'])
            
            # Отправляем уведомление о новом заказе
            message = f"🛒 Новый заказ от {buyer_username}\nАккаунт: {account['account_name']}"
            self.plugin.send_telegram_message(
                self.plugin.threads.get(str(account['id'])), 
                message
            )
            
        except Exception as e:
            logger.error(f"Ошибка обработки нового заказа: {str(e)}")
    
    def handle_rental_start(self, account_id: int, owner: str):
        """Обрабатывает начало аренды"""
        try:
            account = self.db.get_account_by_id(account_id)
            if not account:
                return
            
            # Синхронизируем аккаунт
            self.sync_account(account_id)
            
            # Отправляем уведомление
            message = f"🟢 Начало аренды\nАккаунт: {account['account_name']}\nАрендатор: {owner}"
            self.plugin.send_telegram_message(
                self.plugin.threads.get(str(account_id)), 
                message
            )
            
        except Exception as e:
            logger.error(f"Ошибка обработки начала аренды: {str(e)}")
    
    def handle_rental_end(self, account_id: int):
        """Обрабатывает окончание аренды"""
        try:
            account = self.db.get_account_by_id(account_id)
            if not account:
                return
            
            # Отправляем уведомление
            message = f"🔴 Окончание аренды\nАккаунт: {account['account_name']}"
            self.plugin.send_telegram_message(
                self.plugin.threads.get(str(account_id)), 
                message
            )
            
        except Exception as e:
            logger.error(f"Ошибка обработки окончания аренды: {str(e)}")
    
    def handle_funpay_message(self, fp_chat_id: int, message: str, sender: str = None):
        """Обрабатывает входящее сообщение из FunPay"""
        try:
            if not self.plugin.ready:
                return
            
            # Передаем сообщение в плагин для обработки
            self.plugin.handle_funpay_message(fp_chat_id, message, sender)
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения FunPay: {str(e)}")
    
    def get_funpay_chats(self):
        """Получает список чатов FunPay"""
        try:
            funpay_sync = get_funpay_chat_sync()
            if funpay_sync and funpay_sync.initialized:
                return funpay_sync.get_all_chats()
            return []
        except Exception as e:
            logger.error(f"Ошибка получения чатов FunPay: {str(e)}")
            return []
    
    def sync_accounts_with_funpay(self):
        """Синхронизирует аккаунты с чатами FunPay"""
        try:
            funpay_sync = get_funpay_chat_sync()
            if not funpay_sync or not funpay_sync.initialized:
                logger.error("FunPay Chat Sync не инициализирован")
                return {'synced': 0, 'errors': 1}
            
            accounts = self.db.get_all_accounts()
            return funpay_sync.sync_with_accounts(accounts)
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации аккаунтов с FunPay: {str(e)}")
            return {'synced': 0, 'errors': 1}
    
    def send_funpay_message(self, chat_id: int, message: str) -> bool:
        """Отправляет сообщение в FunPay чат"""
        try:
            funpay_sync = get_funpay_chat_sync()
            if not funpay_sync or not funpay_sync.initialized:
                logger.error("FunPay Chat Sync не инициализирован")
                return False
            
            return funpay_sync.send_chat_message(chat_id, message)
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в FunPay: {str(e)}")
            return False
    
    def get_funpay_chat_info(self, chat_id: int):
        """Получает информацию о чате FunPay"""
        try:
            funpay_sync = get_funpay_chat_sync()
            if not funpay_sync or not funpay_sync.initialized:
                return None
            
            return funpay_sync.get_chat_info(chat_id)
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о чате FunPay: {str(e)}")
            return None
    
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            self.stop_account_monitoring()
            
            # Очищаем FunPay Chat Sync
            cleanup_funpay_chat_sync()
            
            logger.info("Chat Sync интеграция остановлена")
        except Exception as e:
            logger.error(f"Ошибка при остановке интеграции: {str(e)}")


# Глобальный экземпляр интеграции
chat_sync_integration = None


def initialize_chat_sync_integration():
    """Инициализирует интеграцию Chat Sync"""
    global chat_sync_integration
    
    try:
        if chat_sync_integration is None:
            chat_sync_integration = ChatSyncIntegration()
            logger.info("Chat Sync интеграция инициализирована")
        return chat_sync_integration
    except Exception as e:
        logger.error(f"Ошибка инициализации Chat Sync интеграции: {str(e)}")
        return None


def get_chat_sync_integration():
    """Возвращает экземпляр интеграции Chat Sync"""
    return chat_sync_integration


def cleanup_chat_sync_integration():
    """Очищает ресурсы интеграции Chat Sync"""
    global chat_sync_integration
    
    if chat_sync_integration:
        chat_sync_integration.cleanup()
        chat_sync_integration = None
