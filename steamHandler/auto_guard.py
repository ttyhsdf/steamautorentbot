#!/usr/bin/env python3
"""
Автоматическая система выдачи Steam Guard кодов
Профессиональная реализация для Telegram бота аренды Steam аккаунтов
"""

import time
import threading
import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

from config import (
    AUTO_GUARD_ENABLED, 
    AUTO_GUARD_ON_PURCHASE, 
    AUTO_GUARD_INTERVAL, 
    AUTO_GUARD_MAX_ATTEMPTS, 
    AUTO_GUARD_RETRY_DELAY,
    AUTO_GUARD_NOTIFY_ADMIN,
    AUTO_GUARD_LOG_LEVEL,
    ADMIN_ID
)
from steamHandler.SteamGuard import get_steam_guard_code
from logger import logger
from messaging.message_sender import send_message_by_owner


class AutoGuardManager:
    """Менеджер автоматической выдачи Steam Guard кодов"""
    
    def __init__(self):
        self.enabled = AUTO_GUARD_ENABLED
        self.on_purchase = AUTO_GUARD_ON_PURCHASE
        self.interval = AUTO_GUARD_INTERVAL
        self.max_attempts = AUTO_GUARD_MAX_ATTEMPTS
        self.retry_delay = AUTO_GUARD_RETRY_DELAY
        self.notify_admin = AUTO_GUARD_NOTIFY_ADMIN
        self.log_level = AUTO_GUARD_LOG_LEVEL
        
        # Активные задачи отправки кодов
        self.active_tasks: Dict[str, Dict] = {}
        
        # Поток для периодической отправки кодов
        self.scheduler_thread = None
        self.running = False
        
        logger.info("AutoGuardManager initialized", extra_info=f"Enabled: {self.enabled}, OnPurchase: {self.on_purchase}")
        logger.autoguard_start()
    
    def start_scheduler(self):
        """Запустить планировщик автоматической отправки кодов"""
        if not self.enabled:
            logger.info("AutoGuard scheduler disabled in config")
            return
        
        if self.running:
            logger.warning("AutoGuard scheduler already running")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        logger.info("AutoGuard scheduler started", extra_info=f"Interval: {self.interval}s")
        logger.guard_scheduler_start(self.interval)
    
    def stop_scheduler(self):
        """Остановить планировщик"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("AutoGuard scheduler stopped")
        logger.guard_scheduler_stop()
    
    def _scheduler_loop(self):
        """Основной цикл планировщика"""
        while self.running:
            try:
                self._process_all_active_rentals()
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error in AutoGuard scheduler: {str(e)}")
                time.sleep(60)  # Ждем минуту при ошибке
    
    def _process_all_active_rentals(self):
        """Обработать все активные аренды"""
        try:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            
            # Получаем все активные аренды
            cursor.execute("""
                SELECT id, account_name, login, password, rental_duration, rental_start, owner, path_to_maFile
                FROM accounts 
                WHERE owner IS NOT NULL AND rental_start IS NOT NULL
            """)
            
            active_rentals = cursor.fetchall()
            
            for rental in active_rentals:
                account_id, account_name, login, password, rental_duration, rental_start, owner, mafile_path = rental
                
                # Проверяем, не истекла ли аренда
                if self._is_rental_expired(rental_start, rental_duration):
                    continue
                
                # Отправляем код если нужно
                self._send_guard_code_if_needed(account_id, account_name, owner, mafile_path)
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Error processing active rentals: {str(e)}")
    
    def _is_rental_expired(self, rental_start: str, rental_duration: int) -> bool:
        """Проверить, истекла ли аренда"""
        try:
            start_time = datetime.fromisoformat(rental_start)
            end_time = start_time + timedelta(hours=rental_duration)
            return datetime.now() >= end_time
        except Exception as e:
            logger.error(f"Error checking rental expiration: {str(e)}")
            return True
    
    def _send_guard_code_if_needed(self, account_id: int, account_name: str, owner: str, mafile_path: str):
        """Отправить Steam Guard код если нужно"""
        try:
            # Проверяем, не отправляли ли мы код недавно
            task_key = f"{account_id}_{owner}"
            if task_key in self.active_tasks:
                last_sent = self.active_tasks[task_key].get('last_sent', 0)
                if time.time() - last_sent < self.interval:
                    return  # Слишком рано для повторной отправки
            
            # Получаем код
            guard_code = self._get_guard_code_with_retry(mafile_path, account_name)
            
            if guard_code:
                # Отправляем код
                message = (
                    f"🔐 **Автоматический код подтверждения**\n\n"
                    f"**Аккаунт:** {account_name}\n"
                    f"**Код:** `{guard_code}`\n\n"
                    f"⏰ Код действителен 30 секунд\n"
                    f"🔄 Следующий код будет отправлен через {self.interval // 60} минут"
                )
                
                # Проверяем готовность отправителя сообщений
                from messaging.message_sender import is_message_sender_ready
                if not is_message_sender_ready():
                    logger.warning("Message sender not ready, skipping guard code send")
                    return
                
                success = send_message_by_owner(owner, message)
                
                if success:
                    # Обновляем информацию о задаче
                    self.active_tasks[task_key] = {
                        'last_sent': time.time(),
                        'account_name': account_name,
                        'owner': owner,
                        'success_count': self.active_tasks.get(task_key, {}).get('success_count', 0) + 1
                    }
                    
                    logger.info(f"AutoGuard code sent to {owner} for {account_name}", 
                               extra_info=f"Code: {guard_code}")
                    logger.guard_code_sent(account_name, owner, guard_code)
                    
                    # Уведомляем администратора о успешной отправке (только для первой отправки)
                    if self.active_tasks[task_key]['success_count'] == 1:
                        try:
                            from botHandler.bot import send_message_to_admin
                            admin_message = (
                                f"🔐 **AUTOGUARD: КОД ОТПРАВЛЕН**\n\n"
                                f"👤 **Пользователь:** {owner}\n"
                                f"🎮 **Аккаунт:** {account_name} (ID: {account_id})\n"
                                f"🔑 **Код:** {guard_code}\n"
                                f"⏰ **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                                f"✅ **Автоматическая отправка активирована**"
                            )
                            send_message_to_admin(admin_message)
                        except Exception as admin_error:
                            logger.error(f"Error sending admin notification: {str(admin_error)}")
                else:
                    logger.warning(f"Failed to send AutoGuard code to {owner} for {account_name}")
                    logger.guard_code_error(account_name, owner, "Failed to send message")
                
            else:
                # Не удалось получить код
                self._handle_guard_code_error(account_id, account_name, owner, "Failed to generate code")
                logger.guard_code_error(account_name, owner, "Failed to generate code")
                
                # Уведомляем администратора о критической ошибке
                try:
                    from botHandler.bot import send_message_to_admin
                    admin_message = (
                        f"❌ **AUTOGUARD: КРИТИЧЕСКАЯ ОШИБКА**\n\n"
                        f"👤 **Пользователь:** {owner}\n"
                        f"🎮 **Аккаунт:** {account_name} (ID: {account_id})\n"
                        f"🚨 **Ошибка:** Не удалось сгенерировать Steam Guard код\n"
                        f"⏰ **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                        f"⚠️ **Требуется проверка .maFile файла!**"
                    )
                    send_message_to_admin(admin_message)
                except Exception as admin_error:
                    logger.error(f"Error sending admin error notification: {str(admin_error)}")
                
        except Exception as e:
            logger.error(f"Error sending guard code to {owner} for {account_name}: {str(e)}")
            self._handle_guard_code_error(account_id, account_name, owner, str(e))
            
            # Уведомляем администратора об общей ошибке
            try:
                from botHandler.bot import send_message_to_admin
                admin_message = (
                    f"❌ **AUTOGUARD: ОШИБКА ОТПРАВКИ**\n\n"
                    f"👤 **Пользователь:** {owner}\n"
                    f"🎮 **Аккаунт:** {account_name} (ID: {account_id})\n"
                    f"🚨 **Ошибка:** {str(e)}\n"
                    f"⏰ **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"⚠️ **Проверьте подключение к FunPay!**"
                )
                send_message_to_admin(admin_message)
            except Exception as admin_error:
                logger.error(f"Error sending admin error notification: {str(admin_error)}")
    
    def _get_guard_code_with_retry(self, mafile_path: str, account_name: str) -> Optional[str]:
        """Получить Steam Guard код с повторными попытками"""
        for attempt in range(self.max_attempts):
            try:
                guard_code = get_steam_guard_code(mafile_path)
                if guard_code:
                    return guard_code
                
                if attempt < self.max_attempts - 1:
                    logger.warning(f"Guard code generation failed for {account_name}, attempt {attempt + 1}/{self.max_attempts}")
                    time.sleep(self.retry_delay)
                
            except Exception as e:
                logger.error(f"Error generating guard code for {account_name}, attempt {attempt + 1}: {str(e)}")
                if attempt < self.max_attempts - 1:
                    time.sleep(self.retry_delay)
        
        return None
    
    def _handle_guard_code_error(self, account_id: int, account_name: str, owner: str, error: str):
        """Обработать ошибку получения кода"""
        task_key = f"{account_id}_{owner}"
        
        # Увеличиваем счетчик ошибок
        if task_key not in self.active_tasks:
            self.active_tasks[task_key] = {'error_count': 0}
        
        self.active_tasks[task_key]['error_count'] = self.active_tasks[task_key].get('error_count', 0) + 1
        
        # Уведомляем админа если нужно
        if self.notify_admin and self.active_tasks[task_key]['error_count'] >= 3:
            admin_message = (
                f"⚠️ **Проблема с Steam Guard кодом**\n\n"
                f"**Аккаунт:** {account_name}\n"
                f"**Пользователь:** {owner}\n"
                f"**Ошибка:** {error}\n"
                f"**Количество ошибок:** {self.active_tasks[task_key]['error_count']}\n\n"
                f"Проверьте .maFile и настройки аккаунта."
            )
            
            try:
                # Отправляем уведомление админу через Telegram
                from botHandler.bot import bot
                bot.send_message(ADMIN_ID, admin_message, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to notify admin about guard code error: {str(e)}")
        
        logger.error(f"Guard code error for {account_name} (owner: {owner}): {error}")
    
    def send_guard_code_on_purchase(self, account_id: int, account_name: str, owner: str, mafile_path: str):
        """Отправить Steam Guard код сразу при покупке"""
        if not self.on_purchase:
            return False
        
        try:
            guard_code = self._get_guard_code_with_retry(mafile_path, account_name)
            
            if guard_code:
                message = (
                    f"🎉 **Добро пожаловать!**\n\n"
                    f"**Аккаунт:** {account_name}\n"
                    f"**Steam Guard код:** `{guard_code}`\n\n"
                    f"⏰ Код действителен 30 секунд\n"
                    f"🔄 Для получения нового кода отправьте /code\n"
                    f"❓ Для вопросов отправьте /question\n\n"
                    f"**Удачной игры!** 🎮"
                )
                
                # Проверяем готовность отправителя сообщений
                from messaging.message_sender import is_message_sender_ready
                if not is_message_sender_ready():
                    logger.warning("Message sender not ready, skipping welcome guard code send")
                    return False
                
                success = send_message_by_owner(owner, message)
                
                if success:
                    logger.info(f"Welcome guard code sent to {owner} for {account_name}", 
                               extra_info=f"Code: {guard_code}")
                    logger.guard_welcome_sent(account_name, owner, guard_code)
                    return True
                else:
                    logger.warning(f"Failed to send welcome guard code to {owner} for {account_name}")
                    return False
            else:
                self._handle_guard_code_error(account_id, account_name, owner, "Failed to generate welcome code")
                return False
                
        except Exception as e:
            logger.error(f"Error sending welcome guard code to {owner} for {account_name}: {str(e)}")
            self._handle_guard_code_error(account_id, account_name, owner, str(e))
            return False
    
    def get_statistics(self) -> Dict:
        """Получить статистику работы AutoGuard"""
        total_tasks = len(self.active_tasks)
        successful_tasks = sum(1 for task in self.active_tasks.values() if task.get('success_count', 0) > 0)
        error_tasks = sum(1 for task in self.active_tasks.values() if task.get('error_count', 0) > 0)
        
        return {
            'enabled': self.enabled,
            'on_purchase': self.on_purchase,
            'interval': self.interval,
            'running': self.running,
            'total_tasks': total_tasks,
            'successful_tasks': successful_tasks,
            'error_tasks': error_tasks,
            'success_rate': (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0
        }
    
    def clear_old_tasks(self, max_age_hours: int = 24):
        """Очистить старые задачи"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        tasks_to_remove = []
        for task_key, task_data in self.active_tasks.items():
            last_sent = task_data.get('last_sent', 0)
            if current_time - last_sent > max_age_seconds:
                tasks_to_remove.append(task_key)
        
        for task_key in tasks_to_remove:
            del self.active_tasks[task_key]
        
        if tasks_to_remove:
            logger.info(f"Cleared {len(tasks_to_remove)} old AutoGuard tasks")
            logger.guard_task_cleared(len(tasks_to_remove))


# Глобальный экземпляр менеджера
auto_guard_manager = AutoGuardManager()


def start_auto_guard():
    """Запустить автоматическую систему выдачи кодов"""
    auto_guard_manager.start_scheduler()
    logger.info("AutoGuard system started")
    logger.autoguard_start()


def stop_auto_guard():
    """Остановить автоматическую систему выдачи кодов"""
    auto_guard_manager.stop_scheduler()
    logger.info("AutoGuard system stopped")
    logger.autoguard_stop()


def send_welcome_guard_code(account_id: int, account_name: str, owner: str, mafile_path: str) -> bool:
    """Отправить приветственный Steam Guard код при покупке"""
    return auto_guard_manager.send_guard_code_on_purchase(account_id, account_name, owner, mafile_path)


def get_auto_guard_stats() -> Dict:
    """Получить статистику AutoGuard"""
    return auto_guard_manager.get_statistics()


def cleanup_auto_guard_tasks():
    """Очистить старые задачи AutoGuard"""
    auto_guard_manager.clear_old_tasks()
