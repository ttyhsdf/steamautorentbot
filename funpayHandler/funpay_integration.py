"""
Интеграция FunPay с основным ботом
Объединяет управление лотами и расширенную статистику профиля
"""

import asyncio
from datetime import datetime
from typing import Optional

from FunPayAPI.account import Account
from FunPayAPI.updater.events import NewMessageEvent

from funpayHandler.lots_manager import LotsManager
from funpayHandler.lots_telegram_interface import LotsTelegramInterface
from funpayHandler.advanced_profile_stats import AdvancedProfileStats
from logger import logger


class FunPayIntegration:
    """Основной класс интеграции FunPay"""
    
    def __init__(self, funpay_account: Account, telegram_bot):
        self.funpay_account = funpay_account
        self.telegram_bot = telegram_bot
        
        # Инициализируем компоненты
        self.lots_manager = LotsManager(funpay_account)
        self.lots_interface = LotsTelegramInterface(telegram_bot, self.lots_manager)
        self.profile_stats = AdvancedProfileStats(funpay_account, telegram_bot)
        
        logger.info("FunPay интеграция инициализирована")
    
    def handle_new_message(self, event: NewMessageEvent):
        """
        Обрабатывает новые сообщения FunPay
        
        Args:
            event: Событие нового сообщения
        """
        try:
            # Передаем сообщение в профиль статистики
            self.profile_stats.handle_new_message(event)
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения FunPay: {e}")
    
    def get_lots_menu_keyboard(self):
        """Возвращает клавиатуру меню лотов"""
        return self.lots_interface.get_lots_menu_keyboard()
    
    def show_lots_menu(self, chat_id: int, message_id: int = None):
        """Показывает меню лотов"""
        self.lots_interface.show_lots_menu(chat_id, message_id)
    
    def get_advanced_profile_stats(self) -> str:
        """Получает расширенную статистику профиля"""
        return self.profile_stats.generate_advanced_profile()
    
    def get_profile_stats_keyboard(self):
        """Возвращает клавиатуру для статистики профиля"""
        return self.profile_stats.get_profile_stats_keyboard()
    
    def start_auto_raise(self, interval_hours: int = 4):
        """Запускает автоподнятие лотов"""
        self.lots_manager.start_auto_raise(interval_hours)
    
    def stop_auto_raise(self):
        """Останавливает автоподнятие лотов"""
        self.lots_manager.stop_auto_raise()
    
    def raise_lots_now(self):
        """Поднимает лоты сейчас"""
        return self.lots_manager.raise_lots()
    
    def get_lots_summary(self):
        """Получает сводку по лотам"""
        return self.lots_manager.get_lots_summary()
    
    def get_raise_status(self):
        """Получает статус поднятия лотов"""
        return self.lots_manager.get_raise_status()
    
    def format_lots_display(self, lots_data):
        """Форматирует отображение лотов"""
        return self.lots_manager.format_lots_display(lots_data)
    
    def format_raise_status(self, status):
        """Форматирует статус поднятия"""
        return self.lots_manager.format_raise_status(status)
