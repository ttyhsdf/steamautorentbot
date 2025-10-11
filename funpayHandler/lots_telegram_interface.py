"""
Telegram интерфейс для управления лотами FunPay
"""

import asyncio
from datetime import datetime
from typing import Dict, List

import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from funpayHandler.lots_manager import LotsManager
from logger import logger


class LotsTelegramInterface:
    """Telegram интерфейс для управления лотами"""
    
    def __init__(self, bot: telebot.TeleBot, lots_manager: LotsManager):
        self.bot = bot
        self.lots_manager = lots_manager
        self._register_handlers()
    
    def _register_handlers(self):
        """Регистрирует обработчики команд"""
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith('lots_'))
        def handle_lots_callback(call):
            """Обработчик callback-ов для лотов"""
            try:
                data = call.data
                
                if data == 'lots_menu':
                    self._show_lots_menu(call)
                elif data == 'lots_stats':
                    self._show_lots_stats(call)
                elif data == 'lots_raise':
                    self._raise_lots(call)
                elif data == 'lots_auto_raise_start':
                    self._start_auto_raise(call)
                elif data == 'lots_auto_raise_stop':
                    self._stop_auto_raise(call)
                elif data == 'lots_raise_status':
                    self._show_raise_status(call)
                elif data == 'lots_auto_raise_menu':
                    self._show_auto_raise_menu(call)
                elif data == 'lots_refresh':
                    self._refresh_lots_data(call)
                elif data == 'lots_back':
                    self._show_lots_menu(call)
                    
            except Exception as e:
                logger.error(f"Ошибка обработки callback для лотов: {e}")
                self.bot.answer_callback_query(call.id, "❌ Произошла ошибка")
    
    def _show_lots_menu(self, call):
        """Показывает главное меню лотов"""
        try:
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("📊 Статистика лотов", callback_data='lots_stats'),
                InlineKeyboardButton("🚀 Поднять лоты", callback_data='lots_raise')
            )
            keyboard.row(
                InlineKeyboardButton("🔄 Статус поднятия", callback_data='lots_raise_status'),
                InlineKeyboardButton("⚙️ Автоподнятие", callback_data='lots_auto_raise_menu')
            )
            keyboard.row(
                InlineKeyboardButton("🔄 Обновить", callback_data='lots_refresh')
            )
            
            text = "🏪 <b>Управление лотами FunPay</b>\n\n"
            text += "Выберите действие:"
            
            # Проверяем, изменился ли контент
            try:
                self.bot.edit_message_text(
                    text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            except Exception as edit_error:
                if "message is not modified" in str(edit_error):
                    # Если сообщение не изменилось, просто отвечаем на callback
                    self.bot.answer_callback_query(call.id, "✅ Меню актуально")
                else:
                    raise edit_error
            
            self.bot.answer_callback_query(call.id)
            
        except Exception as e:
            logger.error(f"Ошибка показа меню лотов: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка показа меню")
    
    def _show_lots_stats(self, call):
        """Показывает статистику лотов"""
        try:
            self.bot.answer_callback_query(call.id, "📊 Загружаем статистику...")
            
            # Получаем данные о лотах
            lots_data = self.lots_manager.get_lots_summary()
            
            # Форматируем для отображения
            text = self.lots_manager.format_lots_display(lots_data)
            
            # Добавляем кнопки
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🔄 Обновить", callback_data='lots_stats'),
                InlineKeyboardButton("⬅️ Назад", callback_data='lots_menu')
            )
            
            # Проверяем, изменился ли контент
            try:
                self.bot.edit_message_text(
                    text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            except Exception as edit_error:
                if "message is not modified" in str(edit_error):
                    # Если сообщение не изменилось, просто отвечаем на callback
                    self.bot.answer_callback_query(call.id, "✅ Статистика актуальна")
                else:
                    raise edit_error
            
        except Exception as e:
            logger.error(f"Ошибка показа статистики лотов: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка загрузки статистики")
    
    def _raise_lots(self, call):
        """Поднимает лоты"""
        try:
            self.bot.answer_callback_query(call.id, "🚀 Поднимаем лоты...")
            
            # Сначала проверяем статус
            status = self.lots_manager.get_raise_status()
            
            if not status.get('can_raise_now', True):
                # Есть заблокированные категории
                text = "⏳ <b>Лоты уже были подняты недавно</b>\n\n"
                text += "🚫 <b>Заблокированные категории:</b>\n"
                for blocked in status.get('blocked_categories', []):
                    text += f"• ID {blocked['category_id']}: <code>через {blocked['wait_time']}</code>\n"
                text += "\n💡 <b>Подсказка:</b> Дождитесь окончания блокировки или включите автоподнятие"
            else:
                # Поднимаем лоты
                result = self.lots_manager.raise_lots()
                
                if result['success']:
                    text = "✅ <b>Лоты успешно подняты!</b>\n\n"
                    
                    if result['raised_categories']:
                        text += f"📈 <b>Поднятые категории:</b>\n"
                        for category in result['raised_categories']:
                            text += f"• {category}\n"
                        text += "\n"
                    
                    if result['errors']:
                        text += f"⚠️ <b>Ошибки:</b>\n"
                        for error in result['errors']:
                            text += f"• {error}\n"
                        text += "\n"
                    
                    next_raise = datetime.fromisoformat(result['next_raise_time'])
                    text += f"⏰ <b>Следующее поднятие:</b> <code>{next_raise.strftime('%d.%m.%Y %H:%M:%S')}</code>"
                else:
                    text = "❌ <b>Ошибка поднятия лотов</b>\n\n"
                    text += f"<b>Ошибка:</b> {result.get('error', 'Неизвестная ошибка')}\n"
                    
                    if result.get('errors'):
                        text += f"\n<b>Детали ошибок:</b>\n"
                        for error in result['errors']:
                            text += f"• {error}\n"
            
            # Добавляем кнопки
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🔄 Обновить", callback_data='lots_raise'),
                InlineKeyboardButton("⬅️ Назад", callback_data='lots_menu')
            )
            
            # Проверяем, изменился ли контент
            try:
                self.bot.edit_message_text(
                    text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            except Exception as edit_error:
                if "message is not modified" in str(edit_error):
                    # Если сообщение не изменилось, просто отвечаем на callback
                    self.bot.answer_callback_query(call.id, "✅ Результат актуален")
                else:
                    raise edit_error
            
        except Exception as e:
            logger.error(f"Ошибка поднятия лотов: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка поднятия лотов")
    
    def _show_raise_status(self, call):
        """Показывает статус поднятия лотов"""
        try:
            self.bot.answer_callback_query(call.id, "🔄 Загружаем статус...")
            
            # Получаем статус
            status = self.lots_manager.get_raise_status()
            
            # Форматируем для отображения
            text = self.lots_manager.format_raise_status(status)
            
            # Добавляем кнопки
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🔄 Обновить", callback_data='lots_raise_status'),
                InlineKeyboardButton("⬅️ Назад", callback_data='lots_menu')
            )
            
            # Проверяем, изменился ли контент
            try:
                self.bot.edit_message_text(
                    text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            except Exception as edit_error:
                if "message is not modified" in str(edit_error):
                    # Если сообщение не изменилось, просто отвечаем на callback
                    self.bot.answer_callback_query(call.id, "✅ Статус актуален")
                else:
                    raise edit_error
            
        except Exception as e:
            logger.error(f"Ошибка показа статуса поднятия: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка загрузки статуса")
    
    def _show_auto_raise_menu(self, call):
        """Показывает меню настроек автоподнятия"""
        try:
            self.bot.answer_callback_query(call.id, "⚙️ Загружаем настройки...")
            
            # Получаем статус автоподнятия
            status = self.lots_manager.get_raise_status()
            
            # Формируем текст меню
            text = "⚙️ <b>Настройки автоподнятия</b>\n\n"
            
            if status.get('auto_raise_enabled'):
                text += "🟢 <b>Статус:</b> Включено\n"
                next_raise = datetime.fromisoformat(status.get('next_raise_time', datetime.now().isoformat()))
                now = datetime.now()
                
                if next_raise > now:
                    time_diff = next_raise - now
                    hours, remainder = divmod(time_diff.total_seconds(), 3600)
                    minutes, _ = divmod(remainder, 60)
                    
                    if hours > 0:
                        text += f"⏳ <b>До следующего поднятия:</b> <code>{int(hours)}ч {int(minutes)}м</code>\n"
                    else:
                        text += f"⏳ <b>До следующего поднятия:</b> <code>{int(minutes)} минут</code>\n"
                else:
                    text += "🔄 <b>Готово к поднятию!</b>\n"
            else:
                text += "🔴 <b>Статус:</b> Выключено\n"
                text += "💡 <b>Подсказка:</b> Включите автоподнятие для автоматического поднятия лотов\n"
            
            text += f"🔄 <b>Интервал:</b> <code>{status.get('raise_interval_hours', 4)} часов</code>\n\n"
            text += "Выберите действие:"
            
            # Добавляем кнопки
            keyboard = InlineKeyboardMarkup()
            
            if status.get('auto_raise_enabled'):
                keyboard.row(
                    InlineKeyboardButton("🛑 Остановить", callback_data='lots_auto_raise_stop'),
                    InlineKeyboardButton("📊 Статус", callback_data='lots_raise_status')
                )
            else:
                keyboard.row(
                    InlineKeyboardButton("▶️ Запустить", callback_data='lots_auto_raise_start'),
                    InlineKeyboardButton("📊 Статус", callback_data='lots_raise_status')
                )
            
            keyboard.row(
                InlineKeyboardButton("⬅️ Назад", callback_data='lots_menu')
            )
            
            # Проверяем, изменился ли контент
            try:
                self.bot.edit_message_text(
                    text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            except Exception as edit_error:
                if "message is not modified" in str(edit_error):
                    # Если сообщение не изменилось, просто отвечаем на callback
                    self.bot.answer_callback_query(call.id, "✅ Настройки актуальны")
                else:
                    raise edit_error
            
        except Exception as e:
            logger.error(f"Ошибка показа меню автоподнятия: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка загрузки настроек")
    
    def _start_auto_raise(self, call):
        """Запускает автоподнятие лотов"""
        try:
            self.bot.answer_callback_query(call.id, "🔄 Запускаем автоподнятие...")
            
            # Запускаем автоподнятие с интервалом 4 часа
            self.lots_manager.start_auto_raise(4)
            
            # Получаем актуальный статус после запуска
            status = self.lots_manager.get_raise_status()
            next_raise = datetime.fromisoformat(status.get('next_raise_time', datetime.now().isoformat()))
            now = datetime.now()
            
            text = "✅ <b>Автоподнятие лотов запущено!</b>\n\n"
            text += "🔄 <b>Интервал:</b> 4 часа\n"
            text += "🔄 <b>Синхронизация:</b> Активна с FunPay\n"
            
            if next_raise > now:
                time_diff = next_raise - now
                hours, remainder = divmod(time_diff.total_seconds(), 3600)
                minutes, _ = divmod(remainder, 60)
                
                if hours > 0:
                    text += f"⏰ <b>Следующее поднятие:</b> через {int(hours)}ч {int(minutes)}м\n"
                else:
                    text += f"⏰ <b>Следующее поднятие:</b> через {int(minutes)} минут\n"
                
                text += f"🕐 <b>Время поднятия:</b> {next_raise.strftime('%d.%m.%Y %H:%M:%S')}\n"
            else:
                text += "🔄 <b>Готово к поднятию!</b>\n"
            
            text += "\n💡 Автоподнятие будет работать в фоновом режиме"
            
            # Добавляем кнопки
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🛑 Остановить", callback_data='lots_auto_raise_stop'),
                InlineKeyboardButton("⬅️ Назад", callback_data='lots_menu')
            )
            
            # Проверяем, изменился ли контент
            try:
                self.bot.edit_message_text(
                    text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            except Exception as edit_error:
                if "message is not modified" in str(edit_error):
                    # Если сообщение не изменилось, просто отвечаем на callback
                    self.bot.answer_callback_query(call.id, "✅ Автоподнятие уже запущено")
                else:
                    raise edit_error
            
        except Exception as e:
            logger.error(f"Ошибка запуска автоподнятия: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка запуска автоподнятия")
    
    def _stop_auto_raise(self, call):
        """Останавливает автоподнятие лотов"""
        try:
            self.bot.answer_callback_query(call.id, "🛑 Останавливаем автоподнятие...")
            
            # Останавливаем автоподнятие
            self.lots_manager.stop_auto_raise()
            
            text = "🛑 <b>Автоподнятие лотов остановлено!</b>\n\n"
            text += "💡 Для повторного запуска используйте кнопку \"Запустить\""
            
            # Добавляем кнопки
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("▶️ Запустить", callback_data='lots_auto_raise_start'),
                InlineKeyboardButton("⬅️ Назад", callback_data='lots_menu')
            )
            
            # Проверяем, изменился ли контент
            try:
                self.bot.edit_message_text(
                    text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            except Exception as edit_error:
                if "message is not modified" in str(edit_error):
                    # Если сообщение не изменилось, просто отвечаем на callback
                    self.bot.answer_callback_query(call.id, "✅ Автоподнятие уже остановлено")
                else:
                    raise edit_error
            
        except Exception as e:
            logger.error(f"Ошибка остановки автоподнятия: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка остановки автоподнятия")
    
    def _refresh_lots_data(self, call):
        """Обновляет данные о лотах"""
        try:
            self.bot.answer_callback_query(call.id, "🔄 Обновляем данные...")
            
            # Обновляем данные
            lots_data = self.lots_manager.get_lots_summary()
            text = self.lots_manager.format_lots_display(lots_data)
            
            # Добавляем кнопки
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🔄 Обновить", callback_data='lots_refresh'),
                InlineKeyboardButton("⬅️ Назад", callback_data='lots_menu')
            )
            
            # Проверяем, изменился ли контент
            try:
                self.bot.edit_message_text(
                    text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            except Exception as edit_error:
                if "message is not modified" in str(edit_error):
                    # Если сообщение не изменилось, просто отвечаем на callback
                    self.bot.answer_callback_query(call.id, "✅ Данные актуальны")
                else:
                    raise edit_error
            
        except Exception as e:
            logger.error(f"Ошибка обновления данных лотов: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка обновления данных")
    
    def show_lots_menu(self, chat_id: int, message_id: int = None):
        """Показывает меню лотов в чате"""
        try:
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("📊 Статистика лотов", callback_data='lots_stats'),
                InlineKeyboardButton("🚀 Поднять лоты", callback_data='lots_raise')
            )
            keyboard.row(
                InlineKeyboardButton("🔄 Статус поднятия", callback_data='lots_raise_status'),
                InlineKeyboardButton("⚙️ Автоподнятие", callback_data='lots_auto_raise_menu')
            )
            keyboard.row(
                InlineKeyboardButton("🔄 Обновить", callback_data='lots_refresh')
            )
            
            text = "🏪 <b>Управление лотами FunPay</b>\n\n"
            text += "Выберите действие:"
            
            if message_id:
                self.bot.edit_message_text(
                    text,
                    chat_id,
                    message_id,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            else:
                self.bot.send_message(
                    chat_id,
                    text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                
        except Exception as e:
            logger.error(f"Ошибка показа меню лотов: {e}")
    
    def get_lots_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Возвращает клавиатуру меню лотов"""
        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("📊 Статистика лотов", callback_data='lots_stats'),
            InlineKeyboardButton("🚀 Поднять лоты", callback_data='lots_raise')
        )
        keyboard.row(
            InlineKeyboardButton("🔄 Статус поднятия", callback_data='lots_raise_status'),
            InlineKeyboardButton("⚙️ Автоподнятие", callback_data='lots_auto_raise_menu')
        )
        keyboard.row(
            InlineKeyboardButton("🔄 Обновить", callback_data='lots_refresh')
        )
        keyboard.row(
            InlineKeyboardButton("⬅️ Главное меню", callback_data='back_to_main')
        )
        return keyboard
