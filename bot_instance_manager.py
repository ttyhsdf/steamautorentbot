#!/usr/bin/env python3
"""
Менеджер экземпляров бота для предотвращения конфликтов
Профессиональное решение для Error 409: Conflict
"""

import os
import sys
import time
import json
import psutil
import requests
import threading
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logger import logger
from config import BOT_TOKEN, ADMIN_ID


class BotInstanceManager:
    """Менеджер экземпляров бота для предотвращения конфликтов"""
    
    def __init__(self):
        self.bot_token = BOT_TOKEN
        self.admin_id = ADMIN_ID
        self.lock_file = "bot_instance.lock"
        self.pid_file = "bot_instance.pid"
        self.heartbeat_file = "bot_heartbeat.json"
        self.heartbeat_timeout = 30  # секунд
        self.cleanup_interval = 60  # секунд
        
        # Создаем директорию для файлов блокировки
        self.lock_dir = Path("locks")
        self.lock_dir.mkdir(exist_ok=True)
        
        self.lock_file_path = self.lock_dir / self.lock_file
        self.pid_file_path = self.lock_dir / self.pid_file
        self.heartbeat_file_path = self.lock_dir / self.heartbeat_file
        
        # Флаг для остановки мониторинга
        self._stop_monitoring = False
        self._monitor_thread = None
    
    def is_bot_running(self):
        """Проверить, запущен ли бот через Telegram API"""
        try:
            # Проверяем через getMe API
            response = requests.get(
                f"https://api.telegram.org/bot{self.bot_token}/getMe",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    logger.debug("Bot is accessible via API")
                    return True
                else:
                    logger.warning(f"Bot API returned error: {data.get('description', 'Unknown error')}")
                    return False
            else:
                logger.warning(f"Bot API returned status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking bot via API: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking bot: {str(e)}")
            return False
    
    def get_running_python_processes(self):
        """Получить список запущенных Python процессов"""
        python_processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline']
                        if cmdline and any('main.py' in arg for arg in cmdline):
                            python_processes.append({
                                'pid': proc.info['pid'],
                                'name': proc.info['name'],
                                'cmdline': ' '.join(cmdline) if cmdline else '',
                                'create_time': proc.info['create_time']
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                    
        except Exception as e:
            logger.error(f"Error getting Python processes: {str(e)}")
            
        return python_processes
    
    def kill_bot_processes(self):
        """Завершить все процессы бота"""
        killed_count = 0
        
        try:
            python_processes = self.get_running_python_processes()
            
            for proc_info in python_processes:
                try:
                    pid = proc_info['pid']
                    cmdline = proc_info['cmdline']
                    
                    # Проверяем, что это процесс нашего бота
                    if 'main.py' in cmdline and 'AutoRentSteam' in cmdline:
                        logger.info(f"Killing bot process PID {pid}: {cmdline}")
                        
                        try:
                            process = psutil.Process(pid)
                            process.terminate()
                            
                            # Ждем завершения процесса
                            try:
                                process.wait(timeout=5)
                                killed_count += 1
                                logger.info(f"Successfully killed process PID {pid}")
                            except psutil.TimeoutExpired:
                                # Принудительно завершаем процесс
                                process.kill()
                                killed_count += 1
                                logger.warning(f"Force killed process PID {pid}")
                                
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            logger.debug(f"Process PID {pid} already terminated or access denied")
                            
                except Exception as e:
                    logger.error(f"Error killing process {proc_info.get('pid', 'unknown')}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in kill_bot_processes: {str(e)}")
            
        return killed_count
    
    def create_lock(self):
        """Создать файл блокировки"""
        try:
            current_pid = os.getpid()
            current_time = datetime.now().isoformat()
            
            lock_data = {
                'pid': current_pid,
                'start_time': current_time,
                'token': self.bot_token[:10] + '...',  # Частичный токен для идентификации
                'admin_id': self.admin_id
            }
            
            with open(self.lock_file_path, 'w', encoding='utf-8') as f:
                json.dump(lock_data, f, indent=2, ensure_ascii=False)
            
            with open(self.pid_file_path, 'w', encoding='utf-8') as f:
                f.write(str(current_pid))
            
            logger.info(f"Created lock file for PID {current_pid}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating lock file: {str(e)}")
            return False
    
    def remove_lock(self):
        """Удалить файл блокировки"""
        try:
            if self.lock_file_path.exists():
                self.lock_file_path.unlink()
                logger.info("Removed lock file")
            
            if self.pid_file_path.exists():
                self.pid_file_path.unlink()
                logger.info("Removed PID file")
                
            if self.heartbeat_file_path.exists():
                self.heartbeat_file_path.unlink()
                logger.info("Removed heartbeat file")
                
            return True
            
        except Exception as e:
            logger.error(f"Error removing lock files: {str(e)}")
            return False
    
    def is_lock_valid(self):
        """Проверить, действителен ли файл блокировки"""
        try:
            if not self.lock_file_path.exists():
                return False
            
            with open(self.lock_file_path, 'r', encoding='utf-8') as f:
                lock_data = json.load(f)
            
            pid = lock_data.get('pid')
            if not pid:
                return False
            
            # Проверяем, существует ли процесс
            try:
                process = psutil.Process(pid)
                if not process.is_running():
                    logger.info(f"Process PID {pid} is not running, lock is invalid")
                    return False
                    
                # Проверяем, что это действительно наш процесс
                cmdline = process.cmdline()
                if not (cmdline and 'main.py' in ' '.join(cmdline)):
                    logger.info(f"Process PID {pid} is not our bot process, lock is invalid")
                    return False
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                logger.info(f"Process PID {pid} not found or access denied, lock is invalid")
                return False
            
            # Проверяем heartbeat
            if self.heartbeat_file_path.exists():
                try:
                    with open(self.heartbeat_file_path, 'r', encoding='utf-8') as f:
                        heartbeat_data = json.load(f)
                    
                    last_heartbeat = datetime.fromisoformat(heartbeat_data.get('last_heartbeat', ''))
                    if datetime.now() - last_heartbeat > timedelta(seconds=self.heartbeat_timeout):
                        logger.info("Heartbeat timeout, lock is invalid")
                        return False
                        
                except Exception as e:
                    logger.warning(f"Error checking heartbeat: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking lock validity: {str(e)}")
            return False
    
    def update_heartbeat(self):
        """Обновить heartbeat"""
        try:
            heartbeat_data = {
                'last_heartbeat': datetime.now().isoformat(),
                'pid': os.getpid()
            }
            
            with open(self.heartbeat_file_path, 'w', encoding='utf-8') as f:
                json.dump(heartbeat_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Error updating heartbeat: {str(e)}")
    
    def start_heartbeat_monitor(self):
        """Запустить мониторинг heartbeat"""
        def heartbeat_worker():
            while not self._stop_monitoring:
                try:
                    self.update_heartbeat()
                    time.sleep(10)  # Обновляем каждые 10 секунд
                except Exception as e:
                    logger.error(f"Error in heartbeat worker: {str(e)}")
                    time.sleep(5)
        
        self._monitor_thread = threading.Thread(target=heartbeat_worker, daemon=True)
        self._monitor_thread.start()
        logger.info("Started heartbeat monitor")
    
    def stop_heartbeat_monitor(self):
        """Остановить мониторинг heartbeat"""
        self._stop_monitoring = True
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        logger.info("Stopped heartbeat monitor")
    
    def cleanup_stale_locks(self):
        """Очистить устаревшие файлы блокировки"""
        try:
            if not self.is_lock_valid():
                logger.info("Cleaning up stale lock files")
                self.remove_lock()
                return True
            return False
        except Exception as e:
            logger.error(f"Error cleaning up stale locks: {str(e)}")
            return False
    
    def acquire_lock(self):
        """Получить блокировку для запуска бота"""
        try:
            # Очищаем устаревшие блокировки
            self.cleanup_stale_locks()
            
            # Проверяем, есть ли активная блокировка
            if self.is_lock_valid():
                logger.warning("Another bot instance is already running")
                return False
            
            # Создаем новую блокировку
            if self.create_lock():
                logger.info("Successfully acquired bot lock")
                self.start_heartbeat_monitor()
                return True
            else:
                logger.error("Failed to create lock file")
                return False
                
        except Exception as e:
            logger.error(f"Error acquiring lock: {str(e)}")
            return False
    
    def release_lock(self):
        """Освободить блокировку"""
        try:
            self.stop_heartbeat_monitor()
            self.remove_lock()
            logger.info("Successfully released bot lock")
            return True
        except Exception as e:
            logger.error(f"Error releasing lock: {str(e)}")
            return False
    
    def force_cleanup(self):
        """Принудительная очистка всех блокировок и процессов"""
        try:
            logger.info("Starting force cleanup...")
            
            # Завершаем все процессы бота
            killed_count = self.kill_bot_processes()
            logger.info(f"Killed {killed_count} bot processes")
            
            # Удаляем все файлы блокировки
            self.remove_lock()
            
            # Ждем немного для завершения процессов
            time.sleep(2)
            
            logger.info("Force cleanup completed")
            return True
            
        except Exception as e:
            logger.error(f"Error in force cleanup: {str(e)}")
            return False
    
    def get_status(self):
        """Получить статус системы"""
        try:
            status = {
                'lock_exists': self.lock_file_path.exists(),
                'lock_valid': self.is_lock_valid(),
                'bot_accessible': self.is_bot_running(),
                'python_processes': len(self.get_running_python_processes()),
                'heartbeat_exists': self.heartbeat_file_path.exists()
            }
            
            if self.lock_file_path.exists():
                try:
                    with open(self.lock_file_path, 'r', encoding='utf-8') as f:
                        lock_data = json.load(f)
                    status['lock_info'] = lock_data
                except Exception as e:
                    status['lock_info'] = {'error': str(e)}
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting status: {str(e)}")
            return {'error': str(e)}


def check_bot_instance():
    """Проверить, можно ли запустить бота"""
    manager = BotInstanceManager()
    
    try:
        # Проверяем статус
        status = manager.get_status()
        logger.info(f"Bot status: {status}")
        
        # Если есть валидная блокировка, не запускаем
        if status.get('lock_valid', False):
            logger.warning("Another bot instance is already running")
            return False
        
        # Очищаем устаревшие блокировки
        if status.get('lock_exists', False):
            logger.info("Cleaning up stale lock files")
            manager.cleanup_stale_locks()
        
        # Проверяем доступность бота через API
        if not status.get('bot_accessible', False):
            logger.warning("Bot is not accessible via Telegram API")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking bot instance: {str(e)}")
        return False


def force_cleanup_bot():
    """Принудительная очистка бота"""
    manager = BotInstanceManager()
    return manager.force_cleanup()


if __name__ == "__main__":
    # Тестирование менеджера
    manager = BotInstanceManager()
    
    print("🔍 Bot Instance Manager Test")
    print("=" * 50)
    
    status = manager.get_status()
    print(f"Status: {json.dumps(status, indent=2, ensure_ascii=False)}")
    
    if status.get('lock_valid', False):
        print("❌ Another bot instance is running")
    else:
        print("✅ No conflicting bot instances found")
    
    print("\n🧹 Force cleanup test:")
    if manager.force_cleanup():
        print("✅ Force cleanup completed")
    else:
        print("❌ Force cleanup failed")
