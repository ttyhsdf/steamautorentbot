"""
Модуль для управления лотами FunPay
Включает отображение, автоподнятие и управление лотами
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import os
from threading import Thread

from FunPayAPI.account import Account
from FunPayAPI.common.enums import SubCategoryTypes, OrderStatuses
from FunPayAPI.common.exceptions import RaiseError, RequestFailedError
from FunPayAPI.types import LotShortcut, MyLotShortcut, UserProfile, Category, SubCategory
from logger import logger


class LotsManager:
    """Класс для управления лотами FunPay"""
    
    def __init__(self, funpay_account: Account):
        self.funpay_account = funpay_account
        self.lots_raise_next_time = datetime.now()
        self.categories_raise_time = {}
        self.auto_raise_enabled = False
        self.raise_interval_hours = 4
        self._load_raise_times()
        self._ensure_account_initialized()
        
    def _load_raise_times(self):
        """Загружает время последнего поднятия категорий из файла"""
        try:
            if os.path.exists("data/categories_raise_time.json"):
                with open("data/categories_raise_time.json", "r", encoding="utf-8") as f:
                    self.categories_raise_time = json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки времени поднятия категорий: {e}")
    
    def _ensure_account_initialized(self):
        """Убеждается, что аккаунт инициализирован"""
        try:
            if not hasattr(self.funpay_account, 'is_initiated') or not self.funpay_account.is_initiated:
                logger.info("Инициализируем аккаунт FunPay...")
                self.funpay_account.get()
                logger.info("Аккаунт FunPay успешно инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации аккаунта FunPay: {e}")
    
    def _get_real_funpay_blocking_time(self) -> Optional[datetime]:
        """
        Получает реальное время блокировки от FunPay API
        
        Returns:
            Optional[datetime]: Время окончания блокировки или None если нет блокировки
        """
        try:
            # Убеждаемся, что аккаунт инициализирован
            self._ensure_account_initialized()
            
            profile = self.funpay_account.get_user(self.funpay_account.id)
            sorted_lots = profile.get_sorted_lots(2)
            
            earliest_unblock_time = None
            
            for subcategory, lots in sorted_lots.items():
                category = subcategory.category
                category_key = str(subcategory.id)
                
                # Проверяем, есть ли блокировка для этой категории
                if category_key in self.categories_raise_time:
                    next_raise_time = datetime.fromisoformat(self.categories_raise_time[category_key])
                    if next_raise_time > datetime.now():
                        if earliest_unblock_time is None or next_raise_time < earliest_unblock_time:
                            earliest_unblock_time = next_raise_time
            
            return earliest_unblock_time
            
        except Exception as e:
            logger.warning(f"Ошибка получения реального времени блокировки FunPay: {e}")
            return None
    
    def _sync_with_funpay_timing(self):
        """Синхронизирует время следующего поднятия с реальным временем FunPay"""
        try:
            real_blocking_time = self._get_real_funpay_blocking_time()
            
            if real_blocking_time:
                # Обновляем время следующего поднятия на реальное время блокировки
                self.lots_raise_next_time = real_blocking_time
                logger.info(f"Синхронизировано с FunPay: следующее поднятие в {real_blocking_time.strftime('%H:%M:%S')}")
            else:
                # Если нет блокировки, устанавливаем время через интервал
                self.lots_raise_next_time = datetime.now() + timedelta(hours=self.raise_interval_hours)
                logger.info(f"Нет блокировки FunPay, следующее поднятие через {self.raise_interval_hours} часов")
                
        except Exception as e:
            logger.error(f"Ошибка синхронизации с FunPay: {e}")
            # Fallback на стандартный интервал
            self.lots_raise_next_time = datetime.now() + timedelta(hours=self.raise_interval_hours)
            
    def _save_raise_times(self):
        """Сохраняет время последнего поднятия категорий в файл"""
        try:
            os.makedirs("data", exist_ok=True)
            with open("data/categories_raise_time.json", "w", encoding="utf-8") as f:
                json.dump(self.categories_raise_time, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения времени поднятия категорий: {e}")
    
    def get_all_lots(self) -> Dict[str, List[MyLotShortcut]]:
        """
        Получает все лоты пользователя, сгруппированные по подкатегориям
        
        Returns:
            Dict[str, List[MyLotShortcut]]: Словарь с лотами по подкатегориям
        """
        try:
            # Убеждаемся, что аккаунт инициализирован
            self._ensure_account_initialized()
            
            profile = self.funpay_account.get_user(self.funpay_account.id)
            sorted_lots = profile.get_sorted_lots(2)  # Группировка по подкатегориям
            
            lots_by_subcategory = {}
            for subcategory, lots in sorted_lots.items():
                subcategory_name = f"{subcategory.category.name} - {subcategory.name}"
                lots_by_subcategory[subcategory_name] = lots
                
            return lots_by_subcategory
        except Exception as e:
            logger.error(f"Ошибка получения лотов: {e}")
            return {}
    
    def get_lots_summary(self) -> Dict:
        """
        Получает сводную информацию о лотах
        
        Returns:
            Dict: Сводная информация о лотах
        """
        try:
            # Убеждаемся, что аккаунт инициализирован
            self._ensure_account_initialized()
            
            all_lots = self.get_all_lots()
            total_lots = 0
            active_lots = 0
            total_value = 0
            categories_count = 0
            
            summary = {
                "total_lots": 0,
                "active_lots": 0,
                "inactive_lots": 0,
                "total_value": 0,
                "categories_count": 0,
                "subcategories": {}
            }
            
            for subcategory_name, lots in all_lots.items():
                categories_count += 1
                subcategory_info = {
                    "total": len(lots),
                    "active": 0,
                    "inactive": 0,
                    "total_value": 0
                }
                
                for lot in lots:
                    total_lots += 1
                    subcategory_info["total"] += 1
                    
                    # Безопасное получение цены
                    try:
                        if hasattr(lot, 'price') and lot.price is not None:
                            if isinstance(lot.price, (int, float)):
                                price = lot.price
                            elif hasattr(lot.price, 'price'):
                                price = lot.price.price
                            else:
                                price = 0
                        else:
                            price = 0
                    except Exception as e:
                        logger.warning(f"Ошибка получения цены лота: {e}")
                        price = 0
                    
                    subcategory_info["total_value"] += price
                    total_value += price
                    
                    # Безопасная проверка активности лота
                    try:
                        if hasattr(lot, 'active') and lot.active is not None:
                            if isinstance(lot.active, bool):
                                is_active = lot.active
                            elif hasattr(lot.active, 'active'):
                                is_active = lot.active.active
                            else:
                                # Если не можем определить активность, считаем активным
                                is_active = True
                        else:
                            # Если атрибут active отсутствует, считаем активным
                            is_active = True
                    except Exception as e:
                        logger.warning(f"Ошибка проверки активности лота: {e}")
                        is_active = True
                    
                    if is_active:
                        active_lots += 1
                        subcategory_info["active"] += 1
                    else:
                        subcategory_info["inactive"] += 1
                
                summary["subcategories"][subcategory_name] = subcategory_info
            
            summary.update({
                "total_lots": total_lots,
                "active_lots": active_lots,
                "inactive_lots": total_lots - active_lots,
                "total_value": total_value,
                "categories_count": categories_count
            })
            
            return summary
        except Exception as e:
            logger.error(f"Ошибка получения сводки лотов: {e}")
            return {}
    
    def raise_lots(self) -> Dict:
        """
        Поднимает все лоты всех категорий
        
        Returns:
            Dict: Результат операции поднятия
        """
        try:
            # Убеждаемся, что аккаунт инициализирован
            self._ensure_account_initialized()
            
            self.lots_raise_next_time = datetime.now() + timedelta(hours=self.raise_interval_hours)
            raised_categories = []
            errors = []
            
            profile = self.funpay_account.get_user(self.funpay_account.id)
            sorted_lots = profile.get_sorted_lots(2)
            
            for subcategory, lots in sorted_lots.items():
                category = subcategory.category
                category_key = str(subcategory.id)
                
                # Проверяем, можно ли поднимать эту категорию
                if category_key in self.categories_raise_time:
                    next_raise_time = datetime.fromisoformat(self.categories_raise_time[category_key])
                    if datetime.now() < next_raise_time:
                        # Лоты уже были подняты недавно
                        time_diff = next_raise_time - datetime.now()
                        hours, remainder = divmod(time_diff.total_seconds(), 3600)
                        minutes, _ = divmod(remainder, 60)
                        
                        if hours > 0:
                            wait_time = f"{int(hours)}ч {int(minutes)}м"
                        else:
                            wait_time = f"{int(minutes)}м"
                        
                        logger.info(f"Категория {category.name} уже была поднята. Следующее поднятие через {wait_time}")
                        continue
                
                try:
                    # Поднимаем категорию
                    self.funpay_account.raise_lots(category.id)
                    raised_categories.append(category.name)
                    
                    # Пытаемся поднять еще раз, чтобы получить время следующего поднятия
                    self.funpay_account.raise_lots(category.id)
                    
                except RaiseError as e:
                    if e.wait_time is not None:
                        next_raise_time = datetime.now() + timedelta(seconds=e.wait_time)
                        self.categories_raise_time[category_key] = next_raise_time.isoformat()
                    else:
                        if category_key in self.categories_raise_time:
                            del self.categories_raise_time[category_key]
                            
                except RequestFailedError as e:
                    if e.status_code == 429:
                        logger.warning("Ошибка 429: слишком частые запросы. Повтор через 5 минут")
                        self.lots_raise_next_time = datetime.now() + timedelta(minutes=5)
                        errors.append(f"Ошибка 429 для категории {category.name}")
                    else:
                        errors.append(f"Ошибка запроса для категории {category.name}: {e}")
                        
                except Exception as e:
                    errors.append(f"Неизвестная ошибка для категории {category.name}: {e}")
                
                time.sleep(1)  # Пауза между запросами
            
            # Обновляем время следующего поднятия
            for category_key, raise_time in self.categories_raise_time.items():
                if datetime.fromisoformat(raise_time) < self.lots_raise_next_time:
                    self.lots_raise_next_time = datetime.fromisoformat(raise_time)
            
            # Сохраняем время поднятия
            self._save_raise_times()
            
            result = {
                "success": True,
                "raised_categories": raised_categories,
                "errors": errors,
                "next_raise_time": self.lots_raise_next_time.isoformat()
            }
            
            if raised_categories:
                logger.info(f"Подняты категории: {', '.join(raised_categories)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка поднятия лотов: {e}")
            return {
                "success": False,
                "error": str(e),
                "raised_categories": [],
                "errors": [str(e)]
            }
    
    def start_auto_raise(self, interval_hours: int = 4):
        """
        Запускает автоматическое поднятие лотов
        
        Args:
            interval_hours: Интервал поднятия в часах
        """
        self.auto_raise_enabled = True
        self.raise_interval_hours = interval_hours
        
        # Синхронизируем с реальным временем FunPay при запуске
        self._sync_with_funpay_timing()
        
        def auto_raise_loop():
            while self.auto_raise_enabled:
                try:
                    # Синхронизируем с FunPay каждые 5 минут
                    if datetime.now().minute % 5 == 0:
                        self._sync_with_funpay_timing()
                    
                    if datetime.now() >= self.lots_raise_next_time:
                        logger.info("Начинаем автоматическое поднятие лотов")
                        result = self.raise_lots()
                        
                        if result["success"]:
                            logger.info(f"Автоподнятие завершено. Следующее поднятие: {result['next_raise_time']}")
                            # Синхронизируем время после поднятия
                            self._sync_with_funpay_timing()
                        else:
                            logger.error(f"Ошибка автоподнятия: {result.get('error', 'Неизвестная ошибка')}")
                    
                    time.sleep(60)  # Проверяем каждую минуту
                    
                except Exception as e:
                    logger.error(f"Ошибка в цикле автоподнятия: {e}")
                    time.sleep(300)  # При ошибке ждем 5 минут
        
        thread = Thread(target=auto_raise_loop, daemon=True)
        thread.start()
        logger.info(f"Автоподнятие лотов запущено с интервалом {interval_hours} часов")
    
    def stop_auto_raise(self):
        """Останавливает автоматическое поднятие лотов"""
        self.auto_raise_enabled = False
        logger.info("Автоподнятие лотов остановлено")
    
    def get_raise_status(self) -> Dict:
        """
        Получает статус поднятия лотов
        
        Returns:
            Dict: Статус поднятия
        """
        # Синхронизируем с реальным временем FunPay
        if self.auto_raise_enabled:
            self._sync_with_funpay_timing()
        
        # Проверяем, есть ли категории, которые нельзя поднимать
        blocked_categories = []
        now = datetime.now()
        
        for category_key, raise_time in self.categories_raise_time.items():
            next_raise_time = datetime.fromisoformat(raise_time)
            if now < next_raise_time:
                time_diff = next_raise_time - now
                hours, remainder = divmod(time_diff.total_seconds(), 3600)
                minutes, _ = divmod(remainder, 60)
                
                if hours > 0:
                    wait_time = f"{int(hours)}ч {int(minutes)}м"
                else:
                    wait_time = f"{int(minutes)}м"
                
                blocked_categories.append({
                    "category_id": category_key,
                    "next_raise_time": raise_time,
                    "wait_time": wait_time
                })
        
        return {
            "auto_raise_enabled": self.auto_raise_enabled,
            "next_raise_time": self.lots_raise_next_time.isoformat(),
            "raise_interval_hours": self.raise_interval_hours,
            "categories_raise_times": self.categories_raise_time,
            "blocked_categories": blocked_categories,
            "can_raise_now": len(blocked_categories) == 0,
            "synced_with_funpay": True  # Флаг синхронизации
        }
    
    def format_lots_display(self, lots_data: Dict) -> str:
        """
        Форматирует данные о лотах для отображения
        
        Args:
            lots_data: Данные о лотах
            
        Returns:
            str: Отформатированная строка
        """
        if not lots_data:
            return "❌ Не удалось получить данные о лотах"
        
        text = "📊 <b>Статистика лотов FunPay</b>\n\n"
        
        # Общая статистика
        text += f"📈 <b>Общая статистика:</b>\n"
        text += f"• Всего лотов: <code>{lots_data.get('total_lots', 0)}</code>\n"
        text += f"• Активных: <code>{lots_data.get('active_lots', 0)}</code>\n"
        text += f"• Неактивных: <code>{lots_data.get('inactive_lots', 0)}</code>\n"
        text += f"• Общая стоимость: <code>{lots_data.get('total_value', 0):.2f} ₽</code>\n"
        text += f"• Категорий: <code>{lots_data.get('categories_count', 0)}</code>\n\n"
        
        # Детали по подкатегориям
        text += "📋 <b>По подкатегориям:</b>\n"
        for subcategory, info in lots_data.get('subcategories', {}).items():
            text += f"\n🔹 <b>{subcategory}</b>\n"
            text += f"   • Всего: <code>{info['total']}</code>\n"
            text += f"   • Активных: <code>{info['active']}</code>\n"
            text += f"   • Неактивных: <code>{info['inactive']}</code>\n"
            text += f"   • Стоимость: <code>{info['total_value']:.2f} ₽</code>\n"
        
        return text
    
    def format_raise_status(self, status: Dict) -> str:
        """
        Форматирует статус поднятия для отображения
        
        Args:
            status: Статус поднятия
            
        Returns:
            str: Отформатированная строка
        """
        text = "🚀 <b>Статус поднятия лотов</b>\n\n"
        
        # Информация о синхронизации
        if status.get('synced_with_funpay'):
            text += "🔄 <b>Синхронизация:</b> Активна с FunPay\n"
        else:
            text += "⚠️ <b>Синхронизация:</b> Не активна\n"
        
        text += "\n"
        
        # Статус автоподнятия
        if status.get('auto_raise_enabled'):
            text += "🟢 <b>Автоподнятие:</b> Включено\n"
            
            # Время до следующего поднятия
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
                
                text += f"⏰ <b>Время поднятия:</b> <code>{next_raise.strftime('%d.%m.%Y %H:%M:%S')}</code>\n"
            else:
                text += "🔄 <b>Готово к поднятию!</b>\n"
                text += f"⏰ <b>Последнее поднятие:</b> <code>{next_raise.strftime('%d.%m.%Y %H:%M:%S')}</code>\n"
        else:
            text += "🔴 <b>Автоподнятие:</b> Выключено\n"
            text += "💡 <b>Подсказка:</b> Включите автоподнятие для автоматического поднятия лотов\n"
        
        # Интервал
        text += f"🔄 <b>Интервал:</b> <code>{status.get('raise_interval_hours', 4)} часов</code>\n\n"
        
        # Информация о заблокированных категориях
        if status.get('blocked_categories'):
            text += "🚫 <b>Заблокированные категории:</b>\n"
            for blocked in status['blocked_categories']:
                text += f"• ID {blocked['category_id']}: <code>через {blocked['wait_time']}</code>\n"
            text += "\n"
        
        # Время поднятия по категориям
        if status.get('categories_raise_times'):
            text += "📅 <b>Время поднятия по категориям:</b>\n"
            for category_id, raise_time in status['categories_raise_times'].items():
                try:
                    category_time = datetime.fromisoformat(raise_time)
                    now = datetime.now()
                    
                    if category_time > now:
                        time_diff = category_time - now
                        hours, remainder = divmod(time_diff.total_seconds(), 3600)
                        minutes, _ = divmod(remainder, 60)
                        
                        if hours > 0:
                            time_str = f"{int(hours)}ч {int(minutes)}м"
                        else:
                            time_str = f"{int(minutes)}м"
                        
                        text += f"• ID {category_id}: <code>{category_time.strftime('%d.%m.%Y %H:%M:%S')}</code> (через {time_str})\n"
                    else:
                        text += f"• ID {category_id}: <code>{category_time.strftime('%d.%m.%Y %H:%M:%S')}</code> (готово)\n"
                except Exception as e:
                    logger.warning(f"Ошибка форматирования времени категории {category_id}: {e}")
                    text += f"• ID {category_id}: <code>Ошибка формата времени</code>\n"
        
        return text
