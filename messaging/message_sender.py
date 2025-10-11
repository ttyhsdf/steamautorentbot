#!/usr/bin/env python3
"""
Модуль для отправки сообщений в FunPay
Решает проблему циклических импортов
"""

from logger import logger


class MessageSender:
    """Класс для отправки сообщений в FunPay чаты"""
    
    def __init__(self):
        self.acc = None
        self._initialized = False
    
    def initialize(self, account):
        """Инициализация с аккаунтом FunPay"""
        self.acc = account
        self._initialized = True
        logger.debug("MessageSender initialized")
    
    def send_message_by_owner(self, owner, message):
        """Send a message to the specified owner."""
        if not self._initialized or not self.acc:
            logger.error("MessageSender not initialized")
            return False
        
        try:
            chat = self.acc.get_chat_by_name(owner, True)
            self.acc.send_message(chat.id, message)
            logger.debug(f"Message sent to {owner}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {owner}: {str(e)}")
            return False
    
    def is_initialized(self):
        """Проверка инициализации"""
        return self._initialized and self.acc is not None


# Глобальный экземпляр отправителя сообщений
message_sender = MessageSender()


def send_message_by_owner(owner, message):
    """Функция-обертка для отправки сообщений"""
    return message_sender.send_message_by_owner(owner, message)


def initialize_message_sender(account):
    """Инициализация отправителя сообщений"""
    message_sender.initialize(account)


def is_message_sender_ready():
    """Проверка готовности отправителя сообщений"""
    return message_sender.is_initialized()
