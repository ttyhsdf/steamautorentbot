#!/usr/bin/env python3
"""
FunPay Chat Sync Integration
Интеграция для синхронизации чатов FunPay с Chat Sync плагином
"""

import os
import sys
import time
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

# Добавляем путь к модулям проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from FunPayAPI.account import Account
from FunPayAPI.types import Message, Chat
from logger import logger
from config import FUNPAY_GOLDEN_KEY

class FunPayChatSync:
    """Класс для синхронизации чатов FunPay с Chat Sync плагином"""
    
    def __init__(self, chat_sync_plugin=None):
        self.account = None
        self.chat_sync_plugin = chat_sync_plugin
        self.monitoring_active = False
        self.monitor_thread = None
        self.last_message_ids = {}  # Хранит ID последних сообщений для каждого чата
        self.chats_cache = {}  # Кэш чатов
        self.initialized = False
        
        # Инициализируем FunPay аккаунт
        self.init_funpay_account()
    
    def init_funpay_account(self):
        """Инициализация FunPay аккаунта"""
        try:
            if not FUNPAY_GOLDEN_KEY or FUNPAY_GOLDEN_KEY.strip() == "":
                logger.error("FunPay Golden Key не задан в config.py")
                return False
            
            logger.info("Инициализация FunPay аккаунта...")
            self.account = Account(FUNPAY_GOLDEN_KEY)
            self.account.get()  # Инициализируем аккаунт
            
            # Проверяем статус инициализации
            if hasattr(self.account, 'is_initiated') and not self.account.is_initiated:
                logger.error("FunPay аккаунт не инициализирован после get()")
                return False
            
            logger.info(f"FunPay аккаунт инициализирован: {self.account.username}")
            logger.info(f"ID аккаунта: {self.account.id}")
            self.initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации FunPay аккаунта: {str(e)}")
            self.initialized = False
            return False
    
    def get_all_chats(self) -> List[Chat]:
        """Получает все чаты FunPay"""
        try:
            if not self.initialized or not self.account:
                logger.error("FunPay аккаунт не инициализирован")
                return []
            
            logger.info("Запрос чатов из FunPay API...")
            
            # Получаем список чатов
            chats = self.account.get_chats()
            logger.info(f"Получено {len(chats)} чатов из FunPay")
            
            # Если чатов нет, это нормально - чаты появляются при активных заказах
            if len(chats) == 0:
                logger.info("Активных чатов не найдено - это нормально, чаты появляются при заказах")
                # Попробуем переинициализировать аккаунт для проверки
                try:
                    self.account.get()  # Переинициализируем
                    chats = self.account.get_chats()
                    logger.info(f"После переинициализации получено {len(chats)} чатов")
                except Exception as e:
                    logger.error(f"Ошибка переинициализации: {str(e)}")
            
            # Кэшируем чаты
            for chat in chats:
                self.chats_cache[chat.id] = chat
                logger.debug(f"Кэширован чат: {chat.name} (ID: {chat.id})")
            
            return chats
            
        except Exception as e:
            logger.error(f"Ошибка получения чатов FunPay: {str(e)}")
            return []
    
    def get_chat_messages(self, chat_id: int, limit: int = 50) -> List[Message]:
        """Получает сообщения из конкретного чата"""
        try:
            if not self.initialized or not self.account:
                logger.error("FunPay аккаунт не инициализирован")
                return []
            
            # Получаем историю чата
            last_message_id = self.last_message_ids.get(chat_id, 99999999999999999999999)
            messages = self.account.get_chat_history(chat_id, last_message_id)
            
            # Обновляем ID последнего сообщения
            if messages:
                self.last_message_ids[chat_id] = messages[0].id
                logger.info(f"Получено {len(messages)} новых сообщений из чата {chat_id}")
            
            return messages
            
        except Exception as e:
            logger.error(f"Ошибка получения сообщений из чата {chat_id}: {str(e)}")
            return []
    
    def send_chat_message(self, chat_id: int, message: str) -> bool:
        """Отправляет сообщение в FunPay чат"""
        try:
            if not self.initialized or not self.account:
                logger.error("FunPay аккаунт не инициализирован")
                return False
            
            # Отправляем сообщение
            self.account.send_message(chat_id, message)
            logger.info(f"Сообщение отправлено в FunPay чат {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в чат {chat_id}: {str(e)}")
            return False
    
    def start_monitoring(self):
        """Запускает мониторинг чатов"""
        if self.monitoring_active:
            logger.warning("Мониторинг чатов уже запущен")
            return
        
        if not self.initialized:
            logger.error("FunPay аккаунт не инициализирован")
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Мониторинг чатов FunPay запущен")
    
    def stop_monitoring(self):
        """Останавливает мониторинг чатов"""
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        logger.info("Мониторинг чатов FunPay остановлен")
    
    def _monitor_loop(self):
        """Основной цикл мониторинга"""
        while self.monitoring_active:
            try:
                # Получаем все чаты
                chats = self.get_all_chats()
                
                for chat in chats:
                    if not self.monitoring_active:
                        break
                    
                    # Получаем новые сообщения из чата
                    messages = self.get_chat_messages(chat.id)
                    
                    for message in messages:
                        if not self.monitoring_active:
                            break
                        
                        # Обрабатываем сообщение через Chat Sync плагин
                        self._handle_message(chat, message)
                    
                    # Небольшая задержка между чатами
                    time.sleep(1)
                
                # Задержка между циклами мониторинга
                time.sleep(10)  # Проверяем каждые 10 секунд
                
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {str(e)}")
                time.sleep(30)  # При ошибке ждем 30 секунд
    
    def _handle_message(self, chat: Chat, message: Message):
        """Обрабатывает полученное сообщение"""
        try:
            # Формируем информацию о сообщении
            message_info = {
                'chat_id': chat.id,
                'message_id': message.id,
                'text': message.text,
                'sender': message.author,
                'timestamp': message.date,
                'is_system': message.type == 'system'
            }
            
            logger.info(f"Обработка сообщения из чата {chat.id}: {message.text[:50]}...")
            
            # Передаем сообщение в Chat Sync плагин
            if self.chat_sync_plugin and hasattr(self.chat_sync_plugin, 'handle_funpay_message'):
                self.chat_sync_plugin.handle_funpay_message(
                    chat.id, 
                    message.text, 
                    message.author
                )
            
            # Дополнительная обработка для системных сообщений
            if message.type == 'system':
                self._handle_system_message(chat, message)
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {str(e)}")
    
    def _handle_system_message(self, chat: Chat, message: Message):
        """Обрабатывает системные сообщения"""
        try:
            text = message.text.lower()
            
            # Обработка различных типов системных сообщений
            if 'заказ' in text and 'создан' in text:
                logger.info(f"Новый заказ в чате {chat.id}")
                # Здесь можно добавить логику обработки новых заказов
            
            elif 'аренда' in text and ('началась' in text or 'завершилась' in text):
                logger.info(f"Изменение статуса аренды в чате {chat.id}")
                # Здесь можно добавить логику обработки изменений аренды
            
            elif 'отзыв' in text:
                logger.info(f"Новый отзыв в чате {chat.id}")
                # Здесь можно добавить логику обработки отзывов
            
        except Exception as e:
            logger.error(f"Ошибка обработки системного сообщения: {str(e)}")
    
    def sync_with_accounts(self, accounts: List[Dict[str, Any]]) -> Dict[str, int]:
        """Синхронизирует чаты с аккаунтами Steam"""
        try:
            if not self.initialized:
                logger.error("FunPay аккаунт не инициализирован")
                return {'synced': 0, 'errors': 1}
            
            synced_count = 0
            error_count = 0
            
            # Получаем все чаты
            chats = self.get_all_chats()
            
            for account in accounts:
                try:
                    # Ищем чат, связанный с аккаунтом
                    # Можно использовать различные критерии поиска
                    account_name = account.get('account_name', '')
                    login = account.get('login', '')
                    
                    # Простой поиск по имени аккаунта в чатах
                    for chat in chats:
                        if (account_name.lower() in chat.name.lower() or 
                            login.lower() in chat.name.lower()):
                            
                            # Синхронизируем через Chat Sync плагин
                            if self.chat_sync_plugin:
                                self.chat_sync_plugin.sync_account_with_chat(
                                    account['id'], 
                                    chat.id
                                )
                            
                            synced_count += 1
                            logger.info(f"Аккаунт {account_name} синхронизирован с чатом {chat.id}")
                            break
                    else:
                        logger.warning(f"Чат для аккаунта {account_name} не найден")
                        error_count += 1
                
                except Exception as e:
                    logger.error(f"Ошибка синхронизации аккаунта {account.get('account_name', 'Unknown')}: {str(e)}")
                    error_count += 1
            
            logger.info(f"Синхронизация завершена: {synced_count} успешно, {error_count} ошибок")
            return {'synced': synced_count, 'errors': error_count}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации с аккаунтами: {str(e)}")
            return {'synced': 0, 'errors': 1}
    
    def get_chat_info(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Получает информацию о чате"""
        try:
            if chat_id in self.chats_cache:
                chat = self.chats_cache[chat_id]
                return {
                    'id': chat.id,
                    'name': chat.name,
                    'type': chat.type,
                    'last_message': chat.last_message,
                    'unread_count': chat.unread_count
                }
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о чате {chat_id}: {str(e)}")
            return None
    
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            self.stop_monitoring()
            self.account = None
            self.initialized = False
            logger.info("FunPay Chat Sync очищен")
            
        except Exception as e:
            logger.error(f"Ошибка очистки FunPay Chat Sync: {str(e)}")


# Глобальный экземпляр
funpay_chat_sync = None

def initialize_funpay_chat_sync(chat_sync_plugin=None):
    """Инициализирует FunPay Chat Sync"""
    global funpay_chat_sync
    try:
        funpay_chat_sync = FunPayChatSync(chat_sync_plugin)
        if funpay_chat_sync.initialized:
            funpay_chat_sync.start_monitoring()
            logger.info("FunPay Chat Sync инициализирован и запущен")
            return True
        else:
            logger.error("Не удалось инициализировать FunPay Chat Sync")
            return False
    except Exception as e:
        logger.error(f"Ошибка инициализации FunPay Chat Sync: {str(e)}")
        return False

def get_funpay_chat_sync():
    """Возвращает экземпляр FunPay Chat Sync"""
    return funpay_chat_sync

def cleanup_funpay_chat_sync():
    """Очищает FunPay Chat Sync"""
    global funpay_chat_sync
    if funpay_chat_sync:
        funpay_chat_sync.cleanup()
        funpay_chat_sync = None
