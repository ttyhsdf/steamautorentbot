#!/usr/bin/env python3
"""
Система платежей и подписок для AutoRentSteam
Интеграция с YooKassa и управление подписками
"""

import os
import json
import uuid
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

# YooKassa SDK
try:
    import yookassa
    from yookassa import Payment, Webhook
    YOOKASSA_AVAILABLE = True
except ImportError:
    yookassa = None
    Payment = None
    Webhook = None
    YOOKASSA_AVAILABLE = False

from databaseHandler.databaseSetup import SQLiteDB
from security.encryption import get_secure_data_manager
from logger import logger

@dataclass
class SubscriptionPlan:
    """План подписки"""
    id: str
    name: str
    duration_days: int
    price: Decimal
    description: str
    features: List[str]

@dataclass
class PaymentTransaction:
    """Транзакция платежа"""
    id: str
    user_id: int
    amount: Decimal
    currency: str
    payment_method: str
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None
    description: str = ""

class PaymentManager:
    """Менеджер платежей и подписок"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.db = SQLiteDB()
        self.secure_manager = get_secure_data_manager()
        
        # YooKassa настройки
        self.yookassa_enabled = config.get('yookassa_enabled', False)
        if self.yookassa_enabled and YOOKASSA_AVAILABLE:
            yookassa.Configuration.account_id = config.get('yookassa_account_id')
            yookassa.Configuration.secret_key = config.get('yookassa_secret_key')
            logger.info("YooKassa payment system initialized")
        else:
            logger.warning("YooKassa not available or disabled")
        
        # Планы подписок
        self.subscription_plans = self._load_subscription_plans()
        
        # Минимальная сумма пополнения
        self.min_topup_amount = Decimal(str(config.get('min_topup_amount', 10.0)))
        
        logger.info(f"PaymentManager initialized with {len(self.subscription_plans)} subscription plans")
    
    def _load_subscription_plans(self) -> Dict[str, SubscriptionPlan]:
        """Загружает планы подписок из конфигурации"""
        default_plans = {
            '1w': SubscriptionPlan(
                id='1w',
                name='Недельная подписка',
                duration_days=7,
                price=Decimal('50.00'),
                description='Доступ к системе на 7 дней',
                features=['Управление аккаунтами', 'Автоматическая аренда', 'Поддержка 24/7']
            ),
            '1m': SubscriptionPlan(
                id='1m',
                name='Месячная подписка',
                duration_days=30,
                price=Decimal('150.00'),
                description='Доступ к системе на 30 дней',
                features=['Управление аккаунтами', 'Автоматическая аренда', 'Поддержка 24/7', 'Приоритетная поддержка']
            ),
            '3m': SubscriptionPlan(
                id='3m',
                name='Квартальная подписка',
                duration_days=90,
                price=Decimal('400.00'),
                description='Доступ к системе на 90 дней',
                features=['Управление аккаунтами', 'Автоматическая аренда', 'Поддержка 24/7', 'Приоритетная поддержка', 'Расширенная аналитика']
            )
        }
        
        # Загружаем из конфигурации если есть
        config_plans = self.config.get('subscription_plans', {})
        if config_plans:
            plans = {}
            for plan_id, plan_data in config_plans.items():
                plans[plan_id] = SubscriptionPlan(
                    id=plan_id,
                    name=plan_data.get('name', f'Plan {plan_id}'),
                    duration_days=plan_data.get('duration_days', 30),
                    price=Decimal(str(plan_data.get('price', 100.0))),
                    description=plan_data.get('description', ''),
                    features=plan_data.get('features', [])
                )
            return plans
        
        return default_plans
    
    def get_subscription_plans(self) -> Dict[str, SubscriptionPlan]:
        """Возвращает доступные планы подписок"""
        return self.subscription_plans
    
    def get_user_balance(self, user_id: int) -> Decimal:
        """Получает баланс пользователя"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT balance FROM user_balances WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return Decimal(str(result[0]))
            else:
                # Создаем запись для нового пользователя
                self._create_user_balance(user_id)
                return Decimal('0.00')
        except Exception as e:
            logger.error(f"Error getting user balance: {e}")
            return Decimal('0.00')
    
    def _create_user_balance(self, user_id: int):
        """Создает запись баланса для пользователя"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO user_balances (user_id, balance, created_at) VALUES (?, ?, ?)",
                (user_id, 0.00, datetime.now())
            )
            self.db.conn.commit()
            cursor.close()
        except Exception as e:
            logger.error(f"Error creating user balance: {e}")
    
    def add_balance(self, user_id: int, amount: Decimal, description: str = "Пополнение баланса") -> bool:
        """Пополняет баланс пользователя"""
        try:
            cursor = self.db.conn.cursor()
            
            # Получаем текущий баланс
            current_balance = self.get_user_balance(user_id)
            new_balance = current_balance + amount
            
            # Обновляем баланс
            cursor.execute(
                "UPDATE user_balances SET balance = ?, updated_at = ? WHERE user_id = ?",
                (float(new_balance), datetime.now(), user_id)
            )
            
            # Записываем транзакцию
            transaction_id = str(uuid.uuid4())
            cursor.execute(
                """INSERT INTO payment_transactions 
                   (id, user_id, amount, currency, payment_method, status, created_at, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (transaction_id, user_id, float(amount), 'RUB', 'balance_topup', 'completed', 
                 datetime.now(), description)
            )
            
            self.db.conn.commit()
            cursor.close()
            
            logger.info(f"Balance added for user {user_id}: +{amount} RUB")
            return True
        except Exception as e:
            logger.error(f"Error adding balance: {e}")
            return False
    
    def deduct_balance(self, user_id: int, amount: Decimal, description: str = "Списание с баланса") -> bool:
        """Списывает средства с баланса пользователя"""
        try:
            current_balance = self.get_user_balance(user_id)
            
            if current_balance < amount:
                logger.warning(f"Insufficient balance for user {user_id}: {current_balance} < {amount}")
                return False
            
            cursor = self.db.conn.cursor()
            new_balance = current_balance - amount
            
            # Обновляем баланс
            cursor.execute(
                "UPDATE user_balances SET balance = ?, updated_at = ? WHERE user_id = ?",
                (float(new_balance), datetime.now(), user_id)
            )
            
            # Записываем транзакцию
            transaction_id = str(uuid.uuid4())
            cursor.execute(
                """INSERT INTO payment_transactions 
                   (id, user_id, amount, currency, payment_method, status, created_at, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (transaction_id, user_id, float(-amount), 'RUB', 'balance_deduction', 'completed', 
                 datetime.now(), description)
            )
            
            self.db.conn.commit()
            cursor.close()
            
            logger.info(f"Balance deducted for user {user_id}: -{amount} RUB")
            return True
        except Exception as e:
            logger.error(f"Error deducting balance: {e}")
            return False
    
    def create_yookassa_payment(self, user_id: int, amount: Decimal, description: str = "") -> Optional[str]:
        """Создает платеж через YooKassa"""
        if not self.yookassa_enabled or not YOOKASSA_AVAILABLE:
            logger.error("YooKassa not available")
            return None
        
        try:
            payment_id = str(uuid.uuid4())
            
            payment = Payment.create({
                "amount": {
                    "value": str(amount),
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": self.config.get('yookassa_return_url', 'https://t.me/your_bot')
                },
                "capture": True,
                "description": description or f"Пополнение баланса для пользователя {user_id}",
                "metadata": {
                    "user_id": str(user_id),
                    "payment_type": "balance_topup"
                }
            }, payment_id)
            
            # Сохраняем транзакцию
            self._save_payment_transaction(
                payment_id=payment_id,
                user_id=user_id,
                amount=amount,
                currency='RUB',
                payment_method='yookassa',
                status='pending',
                description=description
            )
            
            logger.info(f"YooKassa payment created: {payment_id} for user {user_id}")
            return payment.confirmation.confirmation_url
            
        except Exception as e:
            logger.error(f"Error creating YooKassa payment: {e}")
            return None
    
    def _save_payment_transaction(self, payment_id: str, user_id: int, amount: Decimal, 
                                currency: str, payment_method: str, status: str, description: str = ""):
        """Сохраняет транзакцию в базу данных"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO payment_transactions 
                   (id, user_id, amount, currency, payment_method, status, created_at, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (payment_id, user_id, float(amount), currency, payment_method, status, 
                 datetime.now(), description)
            )
            self.db.conn.commit()
            cursor.close()
        except Exception as e:
            logger.error(f"Error saving payment transaction: {e}")
    
    def process_yookassa_webhook(self, webhook_data: dict) -> bool:
        """Обрабатывает webhook от YooKassa"""
        try:
            if not self.yookassa_enabled or not YOOKASSA_AVAILABLE:
                return False
            
            # Проверяем подпись webhook
            if not self._verify_webhook_signature(webhook_data):
                logger.warning("Invalid webhook signature")
                return False
            
            event = webhook_data.get('event')
            payment_data = webhook_data.get('object', {})
            
            if event == 'payment.succeeded':
                payment_id = payment_data.get('id')
                user_id = int(payment_data.get('metadata', {}).get('user_id', 0))
                amount = Decimal(str(payment_data.get('amount', {}).get('value', 0)))
                
                if user_id and amount > 0:
                    # Обновляем статус транзакции
                    self._update_transaction_status(payment_id, 'completed', datetime.now())
                    
                    # Пополняем баланс
                    self.add_balance(user_id, amount, f"Пополнение через YooKassa (ID: {payment_id})")
                    
                    logger.info(f"Payment {payment_id} processed successfully for user {user_id}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error processing YooKassa webhook: {e}")
            return False
    
    def _verify_webhook_signature(self, webhook_data: dict) -> bool:
        """Проверяет подпись webhook (упрощенная версия)"""
        # В реальном проекте здесь должна быть проверка подписи
        return True
    
    def _update_transaction_status(self, payment_id: str, status: str, paid_at: Optional[datetime] = None):
        """Обновляет статус транзакции"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE payment_transactions SET status = ?, paid_at = ? WHERE id = ?",
                (status, paid_at, payment_id)
            )
            self.db.conn.commit()
            cursor.close()
        except Exception as e:
            logger.error(f"Error updating transaction status: {e}")
    
    def purchase_subscription(self, user_id: int, plan_id: str) -> Tuple[bool, str]:
        """Покупает подписку для пользователя"""
        try:
            if plan_id not in self.subscription_plans:
                return False, "Неверный план подписки"
            
            plan = self.subscription_plans[plan_id]
            current_balance = self.get_user_balance(user_id)
            
            if current_balance < plan.price:
                return False, f"Недостаточно средств. Требуется: {plan.price} RUB, доступно: {current_balance} RUB"
            
            # Списываем средства
            if not self.deduct_balance(user_id, plan.price, f"Покупка подписки: {plan.name}"):
                return False, "Ошибка при списании средств"
            
            # Активируем подписку
            if self._activate_subscription(user_id, plan):
                return True, f"Подписка '{plan.name}' успешно активирована!"
            else:
                # Возвращаем средства при ошибке
                self.add_balance(user_id, plan.price, "Возврат средств за неудачную покупку подписки")
                return False, "Ошибка при активации подписки"
                
        except Exception as e:
            logger.error(f"Error purchasing subscription: {e}")
            return False, f"Ошибка: {str(e)}"
    
    def _activate_subscription(self, user_id: int, plan: SubscriptionPlan) -> bool:
        """Активирует подписку для пользователя"""
        try:
            cursor = self.db.conn.cursor()
            
            # Получаем текущую подписку
            cursor.execute(
                "SELECT subscription_end FROM user_subscriptions WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            
            if result and result[0]:
                # Продлеваем существующую подписку
                current_end = datetime.fromisoformat(result[0])
                if current_end > datetime.now():
                    new_end = current_end + timedelta(days=plan.duration_days)
                else:
                    new_end = datetime.now() + timedelta(days=plan.duration_days)
            else:
                # Создаем новую подписку
                new_end = datetime.now() + timedelta(days=plan.duration_days)
            
            # Сохраняем/обновляем подписку
            cursor.execute(
                """INSERT OR REPLACE INTO user_subscriptions 
                   (user_id, plan_id, subscription_end, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, plan.id, new_end.isoformat(), datetime.now(), datetime.now())
            )
            
            self.db.conn.commit()
            cursor.close()
            
            logger.info(f"Subscription activated for user {user_id}: {plan.name} until {new_end}")
            return True
            
        except Exception as e:
            logger.error(f"Error activating subscription: {e}")
            return False
    
    def is_user_subscribed(self, user_id: int) -> bool:
        """Проверяет, активна ли подписка пользователя"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT subscription_end FROM user_subscriptions WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            
            if result and result[0]:
                subscription_end = datetime.fromisoformat(result[0])
                return subscription_end > datetime.now()
            
            return False
        except Exception as e:
            logger.error(f"Error checking subscription: {e}")
            return False
    
    def get_user_subscription_info(self, user_id: int) -> Optional[Dict]:
        """Получает информацию о подписке пользователя"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT plan_id, subscription_end, created_at 
                   FROM user_subscriptions WHERE user_id = ?""",
                (user_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                plan_id, subscription_end, created_at = result
                plan = self.subscription_plans.get(plan_id)
                
                return {
                    'plan': plan,
                    'subscription_end': datetime.fromisoformat(subscription_end),
                    'created_at': datetime.fromisoformat(created_at),
                    'is_active': datetime.fromisoformat(subscription_end) > datetime.now()
                }
            
            return None
        except Exception as e:
            logger.error(f"Error getting subscription info: {e}")
            return None
    
    def get_user_transactions(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Получает историю транзакций пользователя"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT id, amount, currency, payment_method, status, created_at, description
                   FROM payment_transactions 
                   WHERE user_id = ? 
                   ORDER BY created_at DESC 
                   LIMIT ?""",
                (user_id, limit)
            )
            results = cursor.fetchall()
            cursor.close()
            
            transactions = []
            for row in results:
                transactions.append({
                    'id': row[0],
                    'amount': Decimal(str(row[1])),
                    'currency': row[2],
                    'payment_method': row[3],
                    'status': row[4],
                    'created_at': datetime.fromisoformat(row[5]),
                    'description': row[6]
                })
            
            return transactions
        except Exception as e:
            logger.error(f"Error getting user transactions: {e}")
            return []
