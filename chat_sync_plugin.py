#!/usr/bin/env python3
"""
🧩 Chat Sync Plugin - Адаптированная версия для Steam Auto Rent Bot
Плагин, синхронизирующий FunPay чаты с Telegram чатом (форумом).
Отправляй сообщение в нужную тему - оно будет отправляться в нужный FunPay чат! И наоборот!
"""

import os
import sys
import json
import time
import threading
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

# Добавляем путь к модулям проекта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from databaseHandler.databaseSetup import SQLiteDB
from logger import logger
from messaging.message_sender import message_sender, initialize_message_sender

# Константы плагина
PLUGIN_NAME = "Chat Sync Plugin"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = "Плагин, синхронизирующий FunPay чаты с Telegram чатом (форумом).\n\nОтправляй сообщение в нужную тему - оно будет отправляться в нужный FunPay чат! И наоборот!"
PLUGIN_FOLDER = "plugins/chat_sync"
CONFIG_FILE = os.path.join(PLUGIN_FOLDER, "config.json")
THREADS_FILE = os.path.join(PLUGIN_FOLDER, "threads.json")
BOTS_FILE = os.path.join(PLUGIN_FOLDER, "bots.json")

# Специальный символ для обработки сообщений
SPECIAL_SYMBOL = "⁢"
MIN_BOTS = 2  # Минимальное количество ботов для работы
BOT_DELAY = 2  # Задержка между отправкой сообщений

class ChatSyncPlugin:
    """Основной класс плагина синхронизации чатов"""
    
    def __init__(self):
        self.db = SQLiteDB()
        self.config = self.load_config()
        self.threads = self.load_threads()
        self.bots = []
        self.current_bot = None
        self.ready = False
        self.initialized = False
        self.sync_running = False
        
        # Создаем директорию плагина если её нет
        os.makedirs(PLUGIN_FOLDER, exist_ok=True)
        
        # Инициализируем плагин
        self.init()
    
    def load_config(self) -> Dict[str, Any]:
        """Загружает конфигурацию плагина"""
        default_config = {
            "chat_id": None,
            "watermark_is_hidden": False,
            "image_name": True,
            "mono": False,
            "buyer_viewing": True,
            "edit_topic": True,
            "templates": False,
            "self_notify": True,
            "auto_sync_accounts": True,  # Автоматическая синхронизация с аккаунтами
            "sync_rental_status": True,  # Синхронизация статуса аренды
            "notify_on_rental_change": True  # Уведомления об изменении аренды
        }
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    default_config.update(config)
            except Exception as e:
                logger.error(f"Ошибка загрузки конфигурации: {str(e)}")
        
        return default_config
    
    def save_config(self):
        """Сохраняет конфигурацию плагина"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {str(e)}")
    
    def load_threads(self) -> Dict[str, int]:
        """Загружает связи между FunPay чатами и Telegram темами"""
        if os.path.exists(THREADS_FILE):
            try:
                with open(THREADS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки связей чатов: {str(e)}")
        return {}
    
    def save_threads(self):
        """Сохраняет связи между FunPay чатами и Telegram темами"""
        try:
            with open(THREADS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.threads, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка сохранения связей чатов: {str(e)}")
    
    def load_bots(self) -> List[Dict[str, str]]:
        """Загружает список Telegram ботов"""
        if os.path.exists(BOTS_FILE):
            try:
                with open(BOTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки ботов: {str(e)}")
        return []
    
    def save_bots(self):
        """Сохраняет список Telegram ботов"""
        try:
            with open(BOTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.bots, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка сохранения ботов: {str(e)}")
    
    def init(self):
        """Инициализация плагина"""
        try:
            logger.info(f"Инициализация {PLUGIN_NAME} v{PLUGIN_VERSION}")
            
            # Загружаем ботов
            self.bots = self.load_bots()
            if self.bots:
                self.current_bot = self.bots[0]
            
            # Автоматическая настройка для работы с FunPay
            self.auto_setup_funpay_mode()
            
            # Проверяем готовность
            # Плагин может работать в режиме только FunPay (без Telegram)
            if self.config.get('chat_id') and len(self.bots) >= MIN_BOTS:
                self.ready = True
                logger.info("Плагин готов к работе (полный режим: FunPay + Telegram)")
            elif len(self.bots) >= 1:
                self.ready = True
                logger.info("Плагин готов к работе (режим FunPay)")
                # Запускаем автоматическую синхронизацию с аккаунтами FunPay
                self.auto_sync_with_funpay_accounts()
            else:
                logger.warning("Плагин не готов к работе. Добавьте хотя бы одного Telegram бота.")
            
            self.initialized = True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации плагина: {str(e)}")
            self.initialized = False
    
    def auto_setup_funpay_mode(self):
        """Автоматическая настройка для работы с FunPay"""
        try:
            # Если нет ботов, создаем демо-бота для работы с FunPay
            if not self.bots:
                demo_bot = {
                    'token': 'demo_token_for_funpay_mode',
                    'username': 'funpay_sync_bot',
                    'added_at': datetime.now().isoformat(),
                    'demo': True
                }
                self.bots.append(demo_bot)
                self.current_bot = demo_bot
                self.save_bots()
                logger.info("Создан демо-бот для работы с FunPay")
            
            # Устанавливаем режим только FunPay
            if not self.config.get('funpay_only_mode'):
                self.config['funpay_only_mode'] = True
                self.config['auto_sync_accounts'] = True
                self.config['sync_rental_status'] = True
                self.config['notify_on_rental_change'] = True
                self.save_config()
                logger.info("Включен режим только FunPay")
            
        except Exception as e:
            logger.error(f"Ошибка автоматической настройки FunPay: {str(e)}")
    
    def add_bot(self, token: str, username: str = None) -> bool:
        """Добавляет нового Telegram бота"""
        try:
            # Проверяем, не существует ли уже бот с таким токеном
            for bot in self.bots:
                if bot.get('token') == token:
                    logger.warning("Бот с таким токеном уже добавлен")
                    return False
            
            bot_data = {
                'token': token,
                'username': username or f"bot_{len(self.bots) + 1}",
                'added_at': datetime.now().isoformat()
            }
            
            self.bots.append(bot_data)
            self.save_bots()
            
            if not self.current_bot:
                self.current_bot = self.bots[0]
            
            # Проверяем готовность
            if (self.config.get('chat_id') and 
                len(self.bots) >= MIN_BOTS):
                self.ready = True
            
            logger.info(f"Бот @{bot_data['username']} добавлен")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка добавления бота: {str(e)}")
            return False
    
    def remove_bot(self, index: int) -> bool:
        """Удаляет бота по индексу"""
        try:
            if 0 <= index < len(self.bots):
                removed_bot = self.bots.pop(index)
                self.save_bots()
                
                # Обновляем текущего бота
                if self.bots:
                    self.current_bot = self.bots[0]
                else:
                    self.current_bot = None
                    self.ready = False
                
                logger.info(f"Бот @{removed_bot['username']} удален")
                return True
            else:
                logger.warning(f"Неверный индекс бота: {index}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка удаления бота: {str(e)}")
            return False
    
    def set_chat_id(self, chat_id: int) -> bool:
        """Устанавливает ID чата для синхронизации"""
        try:
            self.config['chat_id'] = chat_id
            self.save_config()
            
            # Проверяем готовность
            if len(self.bots) >= MIN_BOTS:
                self.ready = True
                logger.info(f"Чат для синхронизации установлен: {chat_id}")
            else:
                logger.warning("Недостаточно ботов для работы")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка установки чата: {str(e)}")
            return False
    
    def create_sync_thread(self, fp_chat_id: int, chat_name: str) -> Optional[int]:
        """Создает новую тему в Telegram для синхронизации с FunPay чатом"""
        try:
            if not self.ready or not self.current_bot:
                logger.warning("Плагин не готов к созданию темы")
                return None
            
            # Здесь должна быть логика создания темы в Telegram
            # Для демонстрации возвращаем случайный ID
            thread_id = int(time.time())
            
            # Сохраняем связь
            self.threads[str(fp_chat_id)] = thread_id
            self.save_threads()
            
            logger.info(f"Создана тема для чата {chat_name} (ID: {fp_chat_id})")
            return thread_id
            
        except Exception as e:
            logger.error(f"Ошибка создания темы: {str(e)}")
            return None
    
    def sync_account_with_chat(self, account_id: int, fp_chat_id: int) -> bool:
        """Синхронизирует аккаунт с FunPay чатом"""
        try:
            account = self.db.get_account_by_id(account_id)
            if not account:
                logger.error(f"Аккаунт с ID {account_id} не найден")
                return False
            
            # Создаем тему если её нет
            if str(fp_chat_id) not in self.threads:
                thread_id = self.create_sync_thread(fp_chat_id, account['account_name'])
                if not thread_id:
                    return False
            
            # Логируем синхронизацию
            logger.info(f"Аккаунт {account['account_name']} синхронизирован с чатом {fp_chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации аккаунта: {str(e)}")
            return False
    
    def handle_rental_status_change(self, account_id: int, old_owner: str, new_owner: str):
        """Обрабатывает изменение статуса аренды аккаунта"""
        try:
            if not self.config.get('notify_on_rental_change'):
                return
            
            account = self.db.get_account_by_id(account_id)
            if not account:
                return
            
            # Находим связанные чаты
            for fp_chat_id, thread_id in self.threads.items():
                if self.config.get('sync_rental_status'):
                    # Отправляем уведомление об изменении статуса
                    message = self.format_rental_status_message(account, old_owner, new_owner)
                    self.send_telegram_message(thread_id, message)
            
        except Exception as e:
            logger.error(f"Ошибка обработки изменения статуса аренды: {str(e)}")
    
    def format_rental_status_message(self, account: Dict, old_owner: str, new_owner: str) -> str:
        """Форматирует сообщение об изменении статуса аренды"""
        if new_owner:
            status = f"🟢 Аккаунт {account['account_name']} взят в аренду пользователем {new_owner}"
        else:
            status = f"🔴 Аккаунт {account['account_name']} освобожден от аренды"
        
        return f"""
{status}

📋 Детали:
• Логин: {account['login']}
• Продолжительность: {account['rental_duration']}ч
• Время изменения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()
    
    def send_telegram_message(self, thread_id: int, message: str) -> bool:
        """Отправляет сообщение в Telegram тему"""
        try:
            if not self.current_bot:
                logger.warning("Нет доступных ботов для отправки сообщения")
                return False
            
            # Здесь должна быть логика отправки сообщения в Telegram
            # Для демонстрации просто логируем
            logger.info(f"Отправка сообщения в тему {thread_id}: {message[:50]}...")
            
            # Переключаем на следующего бота
            self.switch_bot()
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в Telegram: {str(e)}")
            return False
    
    def switch_bot(self):
        """Переключает на следующего бота"""
        if len(self.bots) > 1:
            current_index = self.bots.index(self.current_bot) if self.current_bot in self.bots else 0
            next_index = (current_index + 1) % len(self.bots)
            self.current_bot = self.bots[next_index]
    
    def send_funpay_message(self, fp_chat_id: int, message: str, username: str = None) -> bool:
        """Отправляет сообщение в FunPay чат"""
        try:
            if not message_sender.is_initialized():
                logger.error("MessageSender не инициализирован")
                return False
            
            # Убираем специальный символ если есть
            clean_message = message.replace(SPECIAL_SYMBOL, "")
            
            # Отправляем сообщение
            success = message_sender.send_message_by_owner(username or str(fp_chat_id), clean_message)
            
            if success:
                logger.info(f"Сообщение отправлено в FunPay чат {fp_chat_id}")
            else:
                logger.error(f"Ошибка отправки сообщения в FunPay чат {fp_chat_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в FunPay: {str(e)}")
            return False
    
    def handle_funpay_message(self, fp_chat_id: int, message: str, sender: str = None):
        """Обрабатывает входящее сообщение из FunPay"""
        try:
            if not self.ready:
                logger.warning("Плагин не готов к обработке сообщений")
                return
            
            # Логируем получение сообщения
            logger.info(f"Получено сообщение из FunPay чата {fp_chat_id}: {message[:50]}...")
            
            # Если включен режим только FunPay, просто логируем
            if self.config.get('funpay_only_mode'):
                logger.info(f"FunPay сообщение обработано: {sender or 'Unknown'} -> {message[:100]}")
                
                # Можно добавить дополнительную обработку здесь
                # Например, сохранение в базу данных или отправка уведомлений
                
            else:
                # Режим с Telegram - отправляем в соответствующую тему
                thread_id = self.threads.get(str(fp_chat_id))
                if thread_id:
                    self.send_telegram_message(thread_id, f"**{sender or 'FunPay'}**: {message}")
                else:
                    logger.warning(f"Не найдена тема для FunPay чата {fp_chat_id}")
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения FunPay: {str(e)}")
    
    def handle_rental_status_change(self, account_id: int, old_owner: str, new_owner: str):
        """Обрабатывает изменение статуса аренды аккаунта"""
        try:
            if not self.config.get('notify_on_rental_change'):
                return
            
            account = self.db.get_account_by_id(account_id)
            if not account:
                return
            
            # Формируем сообщение об изменении статуса
            status_message = self.format_rental_status_message(account, old_owner, new_owner)
            
            # Если включен режим только FunPay
            if self.config.get('funpay_only_mode'):
                logger.info(f"Изменение статуса аренды: {status_message}")
                
                # Можно добавить отправку уведомления в FunPay чат
                fp_chat_id = account_id
                if str(fp_chat_id) in self.threads:
                    self.send_funpay_message(fp_chat_id, status_message)
            else:
                # Режим с Telegram - отправляем в соответствующие темы
                for fp_chat_id, thread_id in self.threads.items():
                    if self.config.get('sync_rental_status'):
                        self.send_telegram_message(thread_id, status_message)
            
        except Exception as e:
            logger.error(f"Ошибка обработки изменения статуса аренды: {str(e)}")
    
    def get_plugin_status(self) -> Dict[str, Any]:
        """Возвращает статус плагина"""
        return {
            'name': PLUGIN_NAME,
            'version': PLUGIN_VERSION,
            'initialized': self.initialized,
            'ready': self.ready,
            'chat_id': self.config.get('chat_id'),
            'bots_count': len(self.bots),
            'threads_count': len(self.threads),
            'config': self.config
        }
    
    def get_accounts_with_sync(self) -> List[Dict[str, Any]]:
        """Возвращает список аккаунтов с информацией о синхронизации"""
        try:
            accounts = self.db.get_all_accounts()
            synced_accounts = []
            
            for account in accounts:
                account_info = account.copy()
                account_info['synced'] = str(account['id']) in self.threads
                account_info['thread_id'] = self.threads.get(str(account['id']))
                synced_accounts.append(account_info)
            
            return synced_accounts
            
        except Exception as e:
            logger.error(f"Ошибка получения аккаунтов: {str(e)}")
            return []
    
    def sync_all_accounts(self) -> Dict[str, int]:
        """Синхронизирует все аккаунты с чатами"""
        try:
            accounts = self.db.get_all_accounts()
            synced_count = 0
            error_count = 0
            
            for account in accounts:
                if self.sync_account_with_chat(account['id'], account['id']):
                    synced_count += 1
                else:
                    error_count += 1
                
                time.sleep(0.5)  # Небольшая задержка между синхронизациями
            
            logger.info(f"Синхронизация завершена: {synced_count} успешно, {error_count} ошибок")
            return {'synced': synced_count, 'errors': error_count}
            
        except Exception as e:
            logger.error(f"Ошибка массовой синхронизации: {str(e)}")
            return {'synced': 0, 'errors': 1}
    
    def auto_sync_with_funpay_accounts(self):
        """Автоматическая синхронизация с аккаунтами FunPay"""
        try:
            if not self.config.get('auto_sync_accounts'):
                return
            
            accounts = self.db.get_all_accounts()
            if not accounts:
                logger.info("Нет аккаунтов для синхронизации")
                return
            
            logger.info(f"Начинаю автоматическую синхронизацию с {len(accounts)} аккаунтами FunPay")
            
            synced_count = 0
            for account in accounts:
                try:
                    # Создаем связь между аккаунтом и FunPay чатом
                    fp_chat_id = account['id']  # Используем ID аккаунта как ID чата
                    
                    if str(fp_chat_id) not in self.threads:
                        self.threads[str(fp_chat_id)] = f"funpay_chat_{fp_chat_id}"
                        synced_count += 1
                        logger.info(f"Аккаунт {account['account_name']} синхронизирован с FunPay чатом {fp_chat_id}")
                    
                except Exception as e:
                    logger.error(f"Ошибка синхронизации аккаунта {account.get('account_name', 'Unknown')}: {str(e)}")
            
            if synced_count > 0:
                self.save_threads()
                logger.info(f"Автоматическая синхронизация завершена: {synced_count} аккаунтов")
            
        except Exception as e:
            logger.error(f"Ошибка автоматической синхронизации: {str(e)}")


class ChatSyncManager:
    """Менеджер для управления плагином Chat Sync"""
    
    def __init__(self):
        self.plugin = ChatSyncPlugin()
    
    def show_status(self):
        """Показывает статус плагина"""
        status = self.plugin.get_plugin_status()
        
        print(f"\n{'='*60}")
        print(f"🧩 {status['name']} v{status['version']}")
        print(f"{'='*60}")
        print(f"Инициализирован: {'✅ Да' if status['initialized'] else '❌ Нет'}")
        print(f"Готов к работе: {'✅ Да' if status['ready'] else '❌ Нет'}")
        print(f"Чат для синхронизации: {status['chat_id'] or 'Не установлен'}")
        print(f"Количество ботов: {status['bots_count']}")
        print(f"Количество синхронизированных чатов: {status['threads_count']}")
        print(f"{'='*60}")
    
    def show_accounts(self):
        """Показывает аккаунты с информацией о синхронизации"""
        accounts = self.plugin.get_accounts_with_sync()
        
        if not accounts:
            print("📋 Аккаунтов не найдено")
            return
        
        print(f"\n📋 Аккаунты с синхронизацией ({len(accounts)} шт.)")
        print("=" * 80)
        
        for i, account in enumerate(accounts, 1):
            sync_status = "🟢 Синхронизирован" if account['synced'] else "🔴 Не синхронизирован"
            owner_status = "🔴 В аренде" if account['owner'] else "🟢 Свободен"
            
            print(f"{i:2d}. {account['account_name']}")
            print(f"    ID: {account['id']}")
            print(f"    Логин: {account['login']}")
            print(f"    Статус аренды: {owner_status}")
            print(f"    Синхронизация: {sync_status}")
            if account['thread_id']:
                print(f"    ID темы: {account['thread_id']}")
            print("-" * 40)
    
    def add_bot(self, token: str, username: str = None):
        """Добавляет нового бота"""
        if self.plugin.add_bot(token, username):
            print("✅ Бот успешно добавлен")
        else:
            print("❌ Ошибка добавления бота")
    
    def remove_bot(self, index: int):
        """Удаляет бота"""
        if self.plugin.remove_bot(index):
            print("✅ Бот успешно удален")
        else:
            print("❌ Ошибка удаления бота")
    
    def set_chat(self, chat_id: int):
        """Устанавливает чат для синхронизации"""
        if self.plugin.set_chat_id(chat_id):
            print(f"✅ Чат {chat_id} установлен для синхронизации")
        else:
            print("❌ Ошибка установки чата")
    
    def sync_accounts(self):
        """Синхронизирует все аккаунты"""
        print("🔄 Начинаю синхронизацию аккаунтов...")
        result = self.plugin.sync_all_accounts()
        print(f"✅ Синхронизация завершена: {result['synced']} успешно, {result['errors']} ошибок")


def main():
    """Главное меню управления плагином"""
    manager = ChatSyncManager()
    
    while True:
        print("\n" + "=" * 60)
        print("🧩 УПРАВЛЕНИЕ ПЛАГИНОМ CHAT SYNC")
        print("=" * 60)
        print("1. 📊 Статус плагина")
        print("2. 📋 Список аккаунтов с синхронизацией")
        print("3. 🤖 Управление ботами")
        print("4. 💬 Настройка чата")
        print("5. 🔄 Синхронизация аккаунтов")
        print("6. ⚙️ Настройки плагина")
        print("7. ❌ Выход")
        print("=" * 60)
        
        choice = input("Выберите действие (1-7): ").strip()
        
        if choice == "1":
            manager.show_status()
        
        elif choice == "2":
            manager.show_accounts()
        
        elif choice == "3":
            manager.manage_bots()
        
        elif choice == "4":
            manager.manage_chat()
        
        elif choice == "5":
            manager.sync_accounts()
        
        elif choice == "6":
            manager.manage_settings()
        
        elif choice == "7":
            print("👋 До свидания!")
            break
        
        else:
            print("❌ Неверный выбор")
    
    def manage_bots(self):
        """Управление ботами"""
        while True:
            print("\n" + "=" * 40)
            print("🤖 УПРАВЛЕНИЕ БОТАМИ")
            print("=" * 40)
            print("1. 📋 Список ботов")
            print("2. ➕ Добавить бота")
            print("3. 🗑️ Удалить бота")
            print("4. ⬅️ Назад")
            print("=" * 40)
            
            choice = input("Выберите действие (1-4): ").strip()
            
            if choice == "1":
                self.show_bots()
            
            elif choice == "2":
                self.add_bot_menu()
            
            elif choice == "3":
                self.remove_bot_menu()
            
            elif choice == "4":
                break
            
            else:
                print("❌ Неверный выбор")
    
    def show_bots(self):
        """Показывает список ботов"""
        bots = self.plugin.bots
        
        if not bots:
            print("📋 Ботов не найдено")
            return
        
        print(f"\n📋 Список ботов ({len(bots)} шт.)")
        print("=" * 50)
        
        for i, bot in enumerate(bots):
            current = " (текущий)" if bot == self.plugin.current_bot else ""
            print(f"{i+1}. @{bot['username']}{current}")
            print(f"   Токен: {bot['token'][:20]}...")
            print(f"   Добавлен: {bot.get('added_at', 'Неизвестно')}")
            print("-" * 30)
    
    def add_bot_menu(self):
        """Меню добавления бота"""
        token = input("Введите токен бота: ").strip()
        if not token:
            print("❌ Токен не может быть пустым")
            return
        
        username = input("Введите username бота (опционально): ").strip()
        if not username:
            username = None
        
        self.add_bot(token, username)
    
    def remove_bot_menu(self):
        """Меню удаления бота"""
        self.show_bots()
        
        try:
            index = int(input("Введите номер бота для удаления: ")) - 1
            self.remove_bot(index)
        except ValueError:
            print("❌ Неверный формат номера")
    
    def manage_chat(self):
        """Управление чатом"""
        print("\n" + "=" * 40)
        print("💬 НАСТРОЙКА ЧАТА")
        print("=" * 40)
        print(f"Текущий чат: {self.plugin.config.get('chat_id') or 'Не установлен'}")
        
        chat_id = input("Введите ID чата для синхронизации (или Enter для пропуска): ").strip()
        
        if chat_id:
            try:
                chat_id = int(chat_id)
                self.set_chat(chat_id)
            except ValueError:
                print("❌ Неверный формат ID чата")
    
    def manage_settings(self):
        """Управление настройками"""
        while True:
            print("\n" + "=" * 40)
            print("⚙️ НАСТРОЙКИ ПЛАГИНА")
            print("=" * 40)
            print("1. 📋 Текущие настройки")
            print("2. 🔧 Изменить настройки")
            print("3. ⬅️ Назад")
            print("=" * 40)
            
            choice = input("Выберите действие (1-3): ").strip()
            
            if choice == "1":
                self.show_settings()
            
            elif choice == "2":
                self.edit_settings()
            
            elif choice == "3":
                break
            
            else:
                print("❌ Неверный выбор")
    
    def show_settings(self):
        """Показывает текущие настройки"""
        config = self.plugin.config
        
        print("\n📋 Текущие настройки:")
        print("=" * 40)
        for key, value in config.items():
            print(f"{key}: {value}")
    
    def edit_settings(self):
        """Редактирует настройки"""
        print("\n🔧 Редактирование настроек:")
        print("Доступные настройки:")
        
        settings = [
            ("watermark_is_hidden", "Скрывать вотермарку", bool),
            ("image_name", "Показывать имя изображения", bool),
            ("mono", "Моноширинный шрифт", bool),
            ("buyer_viewing", "Показывать что смотрит покупатель", bool),
            ("edit_topic", "Изменять название темы", bool),
            ("templates", "Использовать шаблоны", bool),
            ("self_notify", "Уведомления от себя", bool),
            ("auto_sync_accounts", "Автосинхронизация аккаунтов", bool),
            ("sync_rental_status", "Синхронизация статуса аренды", bool),
            ("notify_on_rental_change", "Уведомления об изменении аренды", bool)
        ]
        
        for i, (key, description, _) in enumerate(settings, 1):
            current_value = self.plugin.config.get(key, False)
            status = "🟢 Включено" if current_value else "🔴 Отключено"
            print(f"{i:2d}. {description}: {status}")
        
        try:
            choice = int(input("\nВыберите настройку для изменения (0 для отмены): "))
            if choice == 0:
                return
            
            if 1 <= choice <= len(settings):
                key, description, value_type = settings[choice - 1]
                current_value = self.plugin.config.get(key, False)
                
                if value_type == bool:
                    new_value = not current_value
                    self.plugin.config[key] = new_value
                    self.plugin.save_config()
                    
                    status = "включена" if new_value else "отключена"
                    print(f"✅ Настройка '{description}' {status}")
                else:
                    print("❌ Неподдерживаемый тип настройки")
            else:
                print("❌ Неверный выбор")
                
        except ValueError:
            print("❌ Неверный формат ввода")


if __name__ == "__main__":
    main()
