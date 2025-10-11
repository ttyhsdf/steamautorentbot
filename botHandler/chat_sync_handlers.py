#!/usr/bin/env python3
"""
Обработчики команд для Chat Sync плагина в Telegram боте
"""

import os
import sys
from typing import Optional

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integration.chat_sync_integration import get_chat_sync_integration
from logger import logger


class ChatSyncHandlers:
    """Обработчики команд Chat Sync для Telegram бота"""
    
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.chat_sync = None
    
    def get_chat_sync(self):
        """Получает экземпляр Chat Sync интеграции"""
        if not self.chat_sync:
            self.chat_sync = get_chat_sync_integration()
        return self.chat_sync
    
    def handle_chat_sync_status(self, message):
        """Обрабатывает команду /chat_sync_status"""
        try:
            chat_sync = self.get_chat_sync()
            if not chat_sync:
                self.bot.reply_to(message, "❌ Chat Sync плагин недоступен")
                return
            
            status = chat_sync.get_plugin_status()
            
            status_text = f"""
🧩 **Chat Sync Plugin Status**

📊 **Общая информация:**
• Название: {status['name']}
• Версия: {status['version']}
• Инициализирован: {'✅ Да' if status['initialized'] else '❌ Нет'}
• Готов к работе: {'✅ Да' if status['ready'] else '❌ Нет'}

🤖 **Боты:**
• Количество: {status['bots_count']}
• Чат для синхронизации: {status['chat_id'] or 'Не установлен'}

🔗 **Синхронизация:**
• Синхронизированных чатов: {status['threads_count']}
• Автосинхронизация: {'✅ Включена' if status['config'].get('auto_sync_accounts') else '❌ Отключена'}
• Уведомления об аренде: {'✅ Включены' if status['config'].get('notify_on_rental_change') else '❌ Отключены'}
            """.strip()
            
            self.bot.reply_to(message, status_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in chat_sync_status handler: {str(e)}")
            self.bot.reply_to(message, f"❌ Ошибка получения статуса: {str(e)}")
    
    def handle_chat_sync_accounts(self, message):
        """Обрабатывает команду /chat_sync_accounts"""
        try:
            chat_sync = self.get_chat_sync()
            if not chat_sync:
                self.bot.reply_to(message, "❌ Chat Sync плагин недоступен")
                return
            
            accounts = chat_sync.get_synced_accounts()
            
            if not accounts:
                self.bot.reply_to(message, "📋 Аккаунтов не найдено")
                return
            
            text = f"📋 **Аккаунты с синхронизацией** ({len(accounts)} шт.)\n\n"
            
            for i, account in enumerate(accounts[:10], 1):  # Показываем первые 10
                sync_status = "🟢 Синхронизирован" if account['synced'] else "🔴 Не синхронизирован"
                owner_status = "🔴 В аренде" if account['owner'] else "🟢 Свободен"
                
                text += f"{i}. **{account['account_name']}**\n"
                text += f"   • ID: {account['id']}\n"
                text += f"   • Логин: {account['login']}\n"
                text += f"   • Статус: {owner_status}\n"
                text += f"   • Синхронизация: {sync_status}\n\n"
            
            if len(accounts) > 10:
                text += f"... и еще {len(accounts) - 10} аккаунтов"
            
            self.bot.reply_to(message, text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in chat_sync_accounts handler: {str(e)}")
            self.bot.reply_to(message, f"❌ Ошибка получения аккаунтов: {str(e)}")
    
    def handle_chat_sync_sync(self, message):
        """Обрабатывает команду /chat_sync_sync"""
        try:
            chat_sync = self.get_chat_sync()
            if not chat_sync:
                self.bot.reply_to(message, "❌ Chat Sync плагин недоступен")
                return
            
            self.bot.reply_to(message, "🔄 Начинаю синхронизацию аккаунтов...")
            
            result = chat_sync.sync_all_accounts()
            
            text = f"""
✅ **Синхронизация завершена!**

📊 **Результаты:**
• Успешно синхронизировано: {result['synced']}
• Ошибок: {result['errors']}

💡 Для просмотра статуса используйте /chat_sync_status
            """.strip()
            
            self.bot.reply_to(message, text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in chat_sync_sync handler: {str(e)}")
            self.bot.reply_to(message, f"❌ Ошибка синхронизации: {str(e)}")
    
    def handle_chat_sync_help(self, message):
        """Обрабатывает команду /chat_sync_help"""
        help_text = """
🧩 **Chat Sync Plugin - Справка**

**Основные команды:**
• `/chat_sync_status` - Статус плагина
• `/chat_sync_accounts` - Список аккаунтов
• `/chat_sync_sync` - Синхронизация аккаунтов
• `/chat_sync_help` - Эта справка

**Что делает плагин:**
• Синхронизирует FunPay чаты с Telegram темами
• Отправляет уведомления об изменении статуса аренды
• Позволяет отправлять сообщения в FunPay из Telegram

**Настройка:**
1. Добавьте Telegram ботов (минимум 2)
2. Создайте группу и включите режим тем
3. Добавьте ботов в группу как администраторов
4. Используйте команды для управления

**Поддержка:**
При проблемах проверьте логи и убедитесь, что все настройки корректны.
        """.strip()
        
        self.bot.reply_to(message, help_text, parse_mode='Markdown')
    
    def handle_chat_sync_setup(self, message):
        """Обрабатывает команду /chat_sync_setup"""
        try:
            chat_sync = self.get_chat_sync()
            if not chat_sync:
                self.bot.reply_to(message, "❌ Chat Sync плагин недоступен")
                return
            
            setup_text = """
🔧 **Настройка Chat Sync Plugin**

**Шаг 1: Создание ботов**
1. Создайте ботов через @BotFather
2. Убедитесь, что username начинается с "funpay"
3. Добавьте токены через меню управления

**Шаг 2: Настройка группы**
1. Создайте группу в Telegram
2. Включите режим тем в настройках
3. Добавьте всех ботов в группу
4. Назначьте ботов администраторами

**Шаг 3: Активация**
1. Используйте команду /chat_sync_sync
2. Проверьте статус через /chat_sync_status

**Требования:**
• Минимум 2 бота
• Группа с включенными темами
• Все боты должны быть администраторами

💡 После настройки плагин будет автоматически синхронизировать аккаунты!
            """.strip()
            
            self.bot.reply_to(message, setup_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in chat_sync_setup handler: {str(e)}")
            self.bot.reply_to(message, f"❌ Ошибка получения инструкций: {str(e)}")
    
    def handle_funpay_chats(self, message):
        """Обрабатывает команду /funpay_chats"""
        try:
            if not self.db_bot or not hasattr(self.db_bot, 'get_funpay_chats'):
                self.bot.reply_to(message, "❌ FunPay интеграция недоступна")
                return
            
            chats = self.db_bot.get_funpay_chats()
            if not chats:
                self.bot.reply_to(message, "📋 Чаты FunPay не найдены")
                return
            
            response = f"📋 **Чаты FunPay ({len(chats)} шт.)**\n\n"
            
            for i, chat in enumerate(chats[:10], 1):  # Показываем первые 10 чатов
                chat_info = f"{i}. **{chat.name}**\n"
                chat_info += f"   ID: `{chat.id}`\n"
                chat_info += f"   Тип: {chat.type}\n"
                if hasattr(chat, 'unread_count') and chat.unread_count > 0:
                    chat_info += f"   Непрочитанных: {chat.unread_count}\n"
                chat_info += "\n"
                response += chat_info
            
            if len(chats) > 10:
                response += f"... и еще {len(chats) - 10} чатов"
            
            self.bot.reply_to(message, response, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error handling funpay chats: {str(e)}")
            self.bot.reply_to(message, f"❌ Ошибка получения чатов FunPay: {str(e)}")
    
    def handle_funpay_sync(self, message):
        """Обрабатывает команду /funpay_sync"""
        try:
            if not self.db_bot or not hasattr(self.db_bot, 'sync_accounts_with_funpay'):
                self.bot.reply_to(message, "❌ FunPay интеграция недоступна")
                return
            
            self.bot.reply_to(message, "🔄 Начинаю синхронизацию с FunPay...")
            
            result = self.db_bot.sync_accounts_with_funpay()
            
            if result['synced'] > 0:
                response = f"✅ **Синхронизация завершена**\n\n"
                response += f"🟢 Успешно: {result['synced']}\n"
                response += f"🔴 Ошибок: {result['errors']}\n\n"
                response += "Аккаунты синхронизированы с чатами FunPay"
            else:
                response = f"❌ **Синхронизация не удалась**\n\n"
                response += f"🔴 Ошибок: {result['errors']}\n\n"
                response += "Проверьте настройки FunPay"
            
            self.bot.reply_to(message, response, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error handling funpay sync: {str(e)}")
            self.bot.reply_to(message, f"❌ Ошибка синхронизации с FunPay: {str(e)}")
    
    def register_handlers(self):
        """Регистрирует обработчики команд"""
        try:
            # Регистрируем команды
            self.bot.message_handler(commands=['chat_sync_status'])(self.handle_chat_sync_status)
            self.bot.message_handler(commands=['chat_sync_accounts'])(self.handle_chat_sync_accounts)
            self.bot.message_handler(commands=['chat_sync_sync'])(self.handle_chat_sync_sync)
            self.bot.message_handler(commands=['chat_sync_help'])(self.handle_chat_sync_help)
            self.bot.message_handler(commands=['chat_sync_setup'])(self.handle_chat_sync_setup)
            
            # FunPay команды
            self.bot.message_handler(commands=['funpay_chats'])(self.handle_funpay_chats)
            self.bot.message_handler(commands=['funpay_sync'])(self.handle_funpay_sync)
            
            logger.info("Chat Sync handlers registered successfully")
            
        except Exception as e:
            logger.error(f"Error registering Chat Sync handlers: {str(e)}")


# Функция для регистрации обработчиков
def register_chat_sync_handlers(bot, db):
    """Регистрирует обработчики Chat Sync в боте"""
    try:
        handlers = ChatSyncHandlers(bot, db)
        handlers.register_handlers()
        return handlers
    except Exception as e:
        logger.error(f"Error creating Chat Sync handlers: {str(e)}")
        return None
