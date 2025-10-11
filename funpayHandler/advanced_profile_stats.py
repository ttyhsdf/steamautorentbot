"""
Адаптированный плагин для расширенной статистики профиля FunPay
Основан на adv_profile_stat.py, адаптирован под структуру проекта
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from os.path import exists

from FunPayAPI.updater.events import NewMessageEvent, MessageTypes
from FunPayAPI.common.utils import RegularExpressions
from FunPayAPI.common.enums import OrderStatuses
from FunPayAPI.types import OrderShortcut
from bs4 import BeautifulSoup as bs

from logger import logger


class AdvancedProfileStats:
    """Класс для расширенной статистики профиля FunPay"""
    
    def __init__(self, funpay_account, telegram_bot=None):
        self.funpay_account = funpay_account
        self.telegram_bot = telegram_bot
        self.order_confirmed = {}
        self.data_file = "data/adv_profile_stat.json"
        self._load_data()
    
    def _load_data(self):
        """Загружает сохраненные данные о заказах"""
        try:
            if exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.order_confirmed = json.loads(f.read())
        except Exception as e:
            logger.error(f"Ошибка загрузки данных профиля: {e}")
    
    def _get_balance_safe(self):
        """Безопасное получение баланса с обработкой ошибок"""
        try:
            # Пытаемся получить баланс с первым доступным лотом
            profile = self._get_user_profile_safe()
            if not profile:
                logger.warning("Профиль пользователя недоступен, создаем пустой баланс")
                from FunPayAPI.types import Balance
                return Balance(0, 0, 0, 0, 0, 0)
                
            lots = profile.get_lots()
            
            if lots:
                # Используем первый лот для получения баланса
                lot_id = lots[0].id
                balance = self.funpay_account.get_balance(lot_id)
                logger.debug(f"Баланс получен с лота {lot_id}")
                return balance
            else:
                # Если лотов нет, создаем пустой баланс
                logger.warning("Лоты не найдены, создаем пустой баланс")
                from FunPayAPI.types import Balance
                return Balance(0, 0, 0, 0, 0, 0)
                
        except Exception as e:
            logger.warning(f"Не удалось получить баланс: {e}")
            # Создаем пустой баланс при ошибке
            from FunPayAPI.types import Balance
            return Balance(0, 0, 0, 0, 0, 0)
    
    def _get_user_profile_safe(self):
        """Безопасное получение профиля пользователя"""
        try:
            profile = self.funpay_account.get_user(self.funpay_account.id)
            return profile
        except Exception as e:
            logger.warning(f"Не удалось получить профиль пользователя: {e}")
            return None
    
    def _save_data(self):
        """Сохраняет данные о заказах"""
        try:
            import os
            os.makedirs("data", exist_ok=True)
            with open(self.data_file, "w", encoding="UTF-8") as f:
                f.write(json.dumps(self.order_confirmed, indent=4, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Ошибка сохранения данных профиля: {e}")
    
    def generate_advanced_profile(self) -> str:
        """
        Генерирует расширенную статистику профиля
        
        Returns:
            str: Отформатированная статистика профиля
        """
        try:
            # Получаем данные аккаунта
            try:
                self.funpay_account.get()
            except Exception as e:
                logger.warning(f"Не удалось получить данные аккаунта: {e}")
                return f"❌ <b>Ошибка получения данных аккаунта</b>\n\n<b>Детали:</b> {str(e)}"
            
            # Инициализируем счетчики
            sales = {"day": 0, "week": 0, "month": 0, "all": 0}
            sales_price = {"day": 0, "week": 0, "month": 0, "all": 0}
            refunds = {"day": 0, "week": 0, "month": 0, "all": 0}
            refunds_price = {"day": 0, "week": 0, "month": 0, "all": 0}
            can_withdraw = {}
            
            # Очищаем старые заказы (старше 2 дней)
            current_time = time.time()
            for order_id in list(self.order_confirmed.keys()):
                if current_time - self.order_confirmed[order_id]["time"] > 172800:  # 2 дня
                    del self.order_confirmed[order_id]
            
            # Рассчитываем доступные для вывода средства
            for order_id, order_data in self.order_confirmed.items():
                currency = order_data.get("currency", "¤")
                order_time = order_data["time"]
                price = order_data["price"]
                
                if current_time - order_time > 169200:  # 47 часов
                    key = "hour_" + currency
                elif current_time - order_time > 86400:  # 24 часа
                    key = "day_" + currency
                else:
                    key = "2day_" + currency
                
                can_withdraw[key] = can_withdraw.get(key, 0) + price
            
            # Получаем баланс безопасным способом
            balance = self._get_balance_safe()
            
            # Получаем данные о продажах
            try:
                next_order_id, all_sales, locale, subcs = self.funpay_account.get_sales()
            except Exception as e:
                logger.warning(f"Не удалось получить данные о продажах: {e}")
                next_order_id, all_sales, locale, subcs = None, [], "ru", {}
            
            c = 1
            
            # Загружаем все продажи
            while next_order_id is not None:
                for attempts in range(2, -1, -1):
                    try:
                        time.sleep(1)
                        next_order_id, new_sales, locale, subcs = self.funpay_account.get_sales(
                            start_from=next_order_id, 
                            locale=locale,
                            sudcategories=subcs
                        )
                        break
                    except Exception as e:
                        logger.debug(f"Не удалось получить список заказов (#{next_order_id}). Осталось попыток: {attempts}")
                        if attempts == 0:
                            raise Exception("Не удалось получить список заказов")
                
                all_sales += new_sales
                c += 1
            
            # Обрабатываем продажи
            for sale in all_sales:
                try:
                    currency = str(sale.currency)
                except:
                    currency = "?"
                
                if sale.status == OrderStatuses.REFUNDED:
                    refunds["all"] += 1
                    refunds_price.setdefault("all_" + currency, 0)
                    refunds_price["all_" + currency] += sale.price
                else:
                    sales["all"] += 1
                    sales_price.setdefault("all_" + currency, 0)
                    sales_price["all_" + currency] += sale.price
                
                # Парсим дату из HTML
                try:
                    date_element = bs(sale.html, "lxml").find("div", {"class": "tc-date-left"})
                    if date_element:
                        date = date_element.text
                    else:
                        continue
                except:
                    continue
                
                # Определяем период по дате
                if any(word in date.lower() for word in ["час", "мин", "сек", "годин", "хвилин", "hour", "min", "sec"]):
                    # Сегодня
                    if sale.status == OrderStatuses.REFUNDED:
                        refunds["day"] += 1
                        refunds["week"] += 1
                        refunds["month"] += 1
                        refunds_price.setdefault("day_" + currency, 0)
                        refunds_price["day_" + currency] += sale.price
                        refunds_price.setdefault("week_" + currency, 0)
                        refunds_price["week_" + currency] += sale.price
                        refunds_price.setdefault("month_" + currency, 0)
                        refunds_price["month_" + currency] += sale.price
                    else:
                        sales["day"] += 1
                        sales["week"] += 1
                        sales["month"] += 1
                        sales_price.setdefault("day_" + currency, 0)
                        sales_price["day_" + currency] += sale.price
                        sales_price.setdefault("week_" + currency, 0)
                        sales_price["week_" + currency] += sale.price
                        sales_price.setdefault("month_" + currency, 0)
                        sales_price["month_" + currency] += sale.price
                        
                elif any(word in date.lower() for word in ["день", "дня", "дней", "дні", "day"]):
                    # На этой неделе
                    if sale.status == OrderStatuses.REFUNDED:
                        refunds["week"] += 1
                        refunds["month"] += 1
                        refunds_price.setdefault("week_" + currency, 0)
                        refunds_price["week_" + currency] += sale.price
                        refunds_price.setdefault("month_" + currency, 0)
                        refunds_price["month_" + currency] += sale.price
                    else:
                        sales["week"] += 1
                        sales["month"] += 1
                        sales_price.setdefault("week_" + currency, 0)
                        sales_price["week_" + currency] += sale.price
                        sales_price.setdefault("month_" + currency, 0)
                        sales_price["month_" + currency] += sale.price
                        
                elif any(word in date.lower() for word in ["недел", "тижд", "тижні", "week"]):
                    # В этом месяце
                    if sale.status == OrderStatuses.REFUNDED:
                        refunds["month"] += 1
                        refunds_price.setdefault("month_" + currency, 0)
                        refunds_price["month_" + currency] += sale.price
                    else:
                        sales["month"] += 1
                        sales_price.setdefault("month_" + currency, 0)
                        sales_price["month_" + currency] += sale.price
            
            # Форматируем числа
            def format_number(number):
                num_str = f"{number:,}".replace(',', ' ')
                if '.' in num_str:
                    integer_part, decimal_part = num_str.split('.')
                    decimal_part = decimal_part.rstrip("0")
                    decimal_part = f".{decimal_part}" if decimal_part else ""
                else:
                    integer_part = num_str
                    decimal_part = ""
                
                # Убираем пробел для чисел 1000-9999.99
                if integer_part.count(' ') == 1 and len(integer_part) == 5:
                    integer_part = integer_part.replace(' ', "")
                
                return integer_part + decimal_part
            
            # Форматируем доступные для вывода средства
            for period in ("hour", "day", "2day"):
                can_withdraw[period] = ", ".join([
                    f"{format_number(round(v, 2))} {k[-1]}" 
                    for k, v in sorted(can_withdraw.items()) 
                    if k.startswith(period + "_")
                ])
                if not can_withdraw[period]:
                    can_withdraw[period] = "0 ¤"
            
            # Форматируем цены продаж и возвратов
            for period in ("day", "week", "month", "all"):
                refunds_price[period] = ", ".join([
                    f"{format_number(round(v, 2))} {k[-1]}" 
                    for k, v in sorted(refunds_price.items()) 
                    if k.startswith(period + "_")
                ])
                sales_price[period] = ", ".join([
                    f"{format_number(round(v, 2))} {k[-1]}" 
                    for k, v in sorted(sales_price.items()) 
                    if k.startswith(period + "_")
                ])
                
                if refunds_price[period] == "":
                    refunds_price[period] = "0 ¤"
                if sales_price[period] == "":
                    sales_price[period] = "0 ¤"
            
            # Получаем количество активных продаж безопасным способом
            try:
                active_sales = self.funpay_account.active_sales
            except Exception as e:
                logger.warning(f"Не удалось получить количество активных продаж: {e}")
                active_sales = 0
            
            # Формируем итоговый текст
            profile_text = f"""📊 <b>Расширенная статистика аккаунта</b>

👤 <b>Пользователь:</b> <code>{self.funpay_account.username}</code>
🆔 <b>ID:</b> <code>{self.funpay_account.id}</code>
💰 <b>Баланс:</b> <code>{format_number(balance.total_rub)} ₽, {format_number(balance.total_usd)} $, {format_number(balance.total_eur)} €</code>
📦 <b>Незавершенных заказов:</b> <code>{active_sales}</code>

💸 <b>Доступно для вывода</b>
🟢 <b>Сейчас:</b> <code>{format_number(balance.available_rub)} ₽, {format_number(balance.available_usd)} $, {format_number(balance.available_eur)} €</code>
⏰ <b>Через час:</b> <code>+{can_withdraw["hour"]}</code>
📅 <b>Через день:</b> <code>+{can_withdraw["day"]}</code>
📆 <b>Через 2 дня:</b> <code>+{can_withdraw["2day"]}</code>

📈 <b>Товаров продано</b>
📊 <b>За день:</b> <code>{format_number(sales["day"])} ({sales_price["day"]})</code>
📊 <b>За неделю:</b> <code>{format_number(sales["week"])} ({sales_price["week"]})</code>
📊 <b>За месяц:</b> <code>{format_number(sales["month"])} ({sales_price["month"]})</code>
📊 <b>За всё время:</b> <code>{format_number(sales["all"])} ({sales_price["all"]})</code>

📉 <b>Товаров возвращено</b>
📊 <b>За день:</b> <code>{format_number(refunds["day"])} ({refunds_price["day"]})</code>
📊 <b>За неделю:</b> <code>{format_number(refunds["week"])} ({refunds_price["week"]})</code>
📊 <b>За месяц:</b> <code>{format_number(refunds["month"])} ({refunds_price["month"]})</code>
📊 <b>За всё время:</b> <code>{format_number(refunds["all"])} ({refunds_price["all"]})</code>

🕐 <b>Обновлено:</b> <code>{time.strftime('%H:%M:%S', time.localtime(getattr(self.funpay_account, 'last_update', time.time())))}</code>"""
            
            return profile_text
            
        except Exception as e:
            logger.error(f"Ошибка генерации расширенной статистики: {e}")
            return f"❌ <b>Ошибка получения статистики</b>\n\n<b>Детали:</b> {str(e)}"
    
    def handle_new_message(self, event: NewMessageEvent):
        """
        Обрабатывает новые сообщения для отслеживания заказов
        
        Args:
            event: Событие нового сообщения
        """
        try:
            # Проверяем тип сообщения
            if event.message.type not in [
                MessageTypes.ORDER_CONFIRMED, 
                MessageTypes.ORDER_CONFIRMED_BY_ADMIN,
                MessageTypes.ORDER_REOPENED, 
                MessageTypes.REFUND, 
                MessageTypes.REFUND_BY_ADMIN
            ]:
                return
            
            # Исключаем сообщения от самого аккаунта
            if event.message.type == MessageTypes.ORDER_CONFIRMED and event.message.initiator_id == self.funpay_account.id:
                return
            if event.message.type == MessageTypes.REFUND and event.message.initiator_id != self.funpay_account.id:
                return
            
            # Извлекаем ID заказа
            order_id = RegularExpressions().ORDER_ID.findall(str(event.message))[0][1:]
            
            # Обрабатываем в зависимости от типа сообщения
            if event.message.type in [MessageTypes.ORDER_REOPENED, MessageTypes.REFUND, MessageTypes.REFUND_BY_ADMIN]:
                # Удаляем заказ из отслеживания
                if order_id in self.order_confirmed:
                    del self.order_confirmed[order_id]
                    self._save_data()
            else:
                # Добавляем заказ в отслеживание
                try:
                    # Получаем информацию о заказе
                    order = self.funpay_account.get_order_shortcut(order_id)
                    if order and order.buyer_id != self.funpay_account.id:
                        self.order_confirmed[order_id] = {
                            "time": int(time.time()),
                            "price": order.sum,
                            "currency": str(order.currency)
                        }
                        self._save_data()
                except Exception as e:
                    logger.debug(f"Ошибка обработки заказа {order_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения для статистики: {e}")
    
    def get_profile_stats_keyboard(self) -> 'InlineKeyboardMarkup':
        """Возвращает клавиатуру для статистики профиля"""
        try:
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🔄 Обновить", callback_data='profile_stats_refresh'),
                InlineKeyboardButton("📊 Детальная статистика", callback_data='profile_stats_detailed')
            )
            keyboard.row(
                InlineKeyboardButton("⬅️ Главное меню", callback_data='back_to_main')
            )
            return keyboard
        except ImportError:
            return None
