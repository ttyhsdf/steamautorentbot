#!/usr/bin/env python3
"""
Расширенный бот AutoRentSteam с интеграцией всех новых функций
Объединяет платежи, шифрование, Playwright и управление пользователями
"""

import os
import sys
import logging
from datetime import datetime
from typing import Optional, Dict, Any

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.encryption import initialize_crypto, get_secure_data_manager
from payments.payment_manager import PaymentManager
from user_management.user_manager import UserManager, UserRole, SubscriptionStatus
from steamHandler.playwright_steam import PlaywrightSteamManager
from databaseHandler.databaseSetup import SQLiteDB
from logger import logger

class EnhancedAutoRentSteam:
    """Расширенная версия AutoRentSteam с новыми функциями"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db = SQLiteDB()
        
        # Инициализируем компоненты
        self._initialize_security()
        self._initialize_payments()
        self._initialize_user_management()
        self._initialize_steam_integration()
        
        logger.info("Enhanced AutoRentSteam initialized successfully")
    
    def _initialize_security(self):
        """Инициализирует систему безопасности"""
        try:
            master_key = self.config.get('MASTER_ENCRYPTION_KEY')
            if not master_key or len(master_key) != 32:
                raise ValueError("MASTER_ENCRYPTION_KEY must be exactly 32 characters")
            
            if initialize_crypto(master_key):
                self.secure_manager = get_secure_data_manager()
                logger.info("Security system initialized")
            else:
                raise Exception("Failed to initialize crypto system")
                
        except Exception as e:
            logger.error(f"Security initialization error: {e}")
            raise
    
    def _initialize_payments(self):
        """Инициализирует систему платежей"""
        try:
            if self.config.get('PAYMENT_SYSTEM_ENABLED', False):
                payment_config = {
                    'yookassa_enabled': self.config.get('YOOKASSA_ENABLED', False),
                    'yookassa_account_id': self.config.get('YOOKASSA_ACCOUNT_ID', ''),
                    'yookassa_secret_key': self.config.get('YOOKASSA_SECRET_KEY', ''),
                    'yookassa_webhook_url': self.config.get('YOOKASSA_WEBHOOK_URL', ''),
                    'yookassa_return_url': self.config.get('YOOKASSA_RETURN_URL', ''),
                    'min_topup_amount': self.config.get('MIN_TOPUP_AMOUNT', 10.0),
                    'subscription_plans': self.config.get('SUBSCRIPTION_PLANS', {})
                }
                
                self.payment_manager = PaymentManager(payment_config)
                logger.info("Payment system initialized")
            else:
                self.payment_manager = None
                logger.info("Payment system disabled")
                
        except Exception as e:
            logger.error(f"Payment system initialization error: {e}")
            self.payment_manager = None
    
    def _initialize_user_management(self):
        """Инициализирует управление пользователями"""
        try:
            if self.config.get('USER_MANAGEMENT_ENABLED', True):
                self.user_manager = UserManager()
                logger.info("User management system initialized")
            else:
                self.user_manager = None
                logger.info("User management system disabled")
                
        except Exception as e:
            logger.error(f"User management initialization error: {e}")
            self.user_manager = None
    
    def _initialize_steam_integration(self):
        """Инициализирует Steam интеграцию"""
        try:
            if self.config.get('PLAYWRIGHT_ENABLED', False):
                self.steam_manager = PlaywrightSteamManager(
                    headless=self.config.get('PLAYWRIGHT_HEADLESS', True),
                    debug=self.config.get('PLAYWRIGHT_DEBUG', False)
                )
                logger.info("Steam integration initialized")
            else:
                self.steam_manager = None
                logger.info("Steam integration disabled")
                
        except Exception as e:
            logger.error(f"Steam integration initialization error: {e}")
            self.steam_manager = None
    
    # Методы для работы с пользователями
    def create_user(self, user_id: int, username: str = None, first_name: str = None, 
                   last_name: str = None) -> bool:
        """Создает нового пользователя"""
        if not self.user_manager:
            return False
        
        try:
            return self.user_manager.create_user(user_id, username, first_name, last_name)
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return False
    
    def get_user_profile(self, user_id: int) -> Optional[Dict]:
        """Получает профиль пользователя"""
        if not self.user_manager:
            return None
        
        try:
            profile = self.user_manager.get_user_profile(user_id)
            if profile:
                return {
                    'user_id': profile.user_id,
                    'username': profile.username,
                    'first_name': profile.first_name,
                    'last_name': profile.last_name,
                    'role': profile.role.value,
                    'subscription_status': profile.subscription_status.value,
                    'subscription_end': profile.subscription_end.isoformat() if profile.subscription_end else None,
                    'balance': float(profile.balance),
                    'created_at': profile.created_at.isoformat(),
                    'last_activity': profile.last_activity.isoformat(),
                    'is_active': profile.is_active
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None
    
    def is_user_subscribed(self, user_id: int) -> bool:
        """Проверяет, активна ли подписка пользователя"""
        if not self.user_manager:
            return True  # Если система отключена, считаем что подписка есть
        
        try:
            return self.user_manager.is_user_subscribed(user_id)
        except Exception as e:
            logger.error(f"Error checking subscription: {e}")
            return False
    
    # Методы для работы с платежами
    def get_user_balance(self, user_id: int) -> float:
        """Получает баланс пользователя"""
        if not self.payment_manager:
            return 0.0
        
        try:
            return float(self.payment_manager.get_user_balance(user_id))
        except Exception as e:
            logger.error(f"Error getting user balance: {e}")
            return 0.0
    
    def add_balance(self, user_id: int, amount: float, description: str = "Пополнение баланса") -> bool:
        """Пополняет баланс пользователя"""
        if not self.payment_manager:
            return False
        
        try:
            from decimal import Decimal
            return self.payment_manager.add_balance(user_id, Decimal(str(amount)), description)
        except Exception as e:
            logger.error(f"Error adding balance: {e}")
            return False
    
    def purchase_subscription(self, user_id: int, plan_id: str) -> tuple[bool, str]:
        """Покупает подписку для пользователя"""
        if not self.payment_manager:
            return False, "Payment system not available"
        
        try:
            from decimal import Decimal
            return self.payment_manager.purchase_subscription(user_id, plan_id)
        except Exception as e:
            logger.error(f"Error purchasing subscription: {e}")
            return False, f"Error: {str(e)}"
    
    def get_subscription_plans(self) -> Dict:
        """Получает доступные планы подписок"""
        if not self.payment_manager:
            return {}
        
        try:
            plans = self.payment_manager.get_subscription_plans()
            return {plan_id: {
                'id': plan.id,
                'name': plan.name,
                'duration_days': plan.duration_days,
                'price': float(plan.price),
                'description': plan.description,
                'features': plan.features
            } for plan_id, plan in plans.items()}
        except Exception as e:
            logger.error(f"Error getting subscription plans: {e}")
            return {}
    
    # Методы для работы с Steam
    async def change_steam_password(self, login: str, password: str, new_password: str, 
                                  email_login: str = None, email_password: str = None,
                                  imap_host: str = None) -> tuple[bool, list, list]:
        """Меняет пароль Steam аккаунта"""
        if not self.steam_manager:
            return False, ["Steam integration not available"], []
        
        try:
            context, page = await self.steam_manager.get_browser_context(
                login, password, email_login, email_password, imap_host
            )
            
            success, logs, screenshots = await self.steam_manager.change_steam_password(
                context, page, new_password, login
            )
            
            await self.steam_manager.cleanup(context)
            return success, logs, screenshots
            
        except Exception as e:
            logger.error(f"Error changing Steam password: {e}")
            return False, [f"Error: {str(e)}"], []
    
    async def logout_all_steam_sessions(self, login: str, password: str) -> bool:
        """Выходит из всех сессий Steam"""
        if not self.steam_manager:
            return False
        
        try:
            context, page = await self.steam_manager.get_browser_context(login, password)
            success = await self.steam_manager.logout_all_sessions(context, page)
            await self.steam_manager.cleanup(context)
            return success
            
        except Exception as e:
            logger.error(f"Error logging out Steam sessions: {e}")
            return False
    
    # Методы для работы с безопасностью
    def encrypt_steam_credentials(self, login: str, password: str) -> Dict:
        """Шифрует Steam учетные данные"""
        try:
            return self.secure_manager.encrypt_steam_credentials(login, password)
        except Exception as e:
            logger.error(f"Error encrypting Steam credentials: {e}")
            return {}
    
    def decrypt_steam_credentials(self, encrypted_data: Dict) -> tuple:
        """Расшифровывает Steam учетные данные"""
        try:
            return self.secure_manager.decrypt_steam_credentials(encrypted_data)
        except Exception as e:
            logger.error(f"Error decrypting Steam credentials: {e}")
            return "", ""
    
    def encrypt_funpay_credentials(self, user_id: str, golden_key: str) -> Dict:
        """Шифрует FunPay учетные данные"""
        try:
            return self.secure_manager.encrypt_funpay_credentials(user_id, golden_key)
        except Exception as e:
            logger.error(f"Error encrypting FunPay credentials: {e}")
            return {}
    
    def decrypt_funpay_credentials(self, encrypted_data: Dict) -> tuple:
        """Расшифровывает FunPay учетные данные"""
        try:
            return self.secure_manager.decrypt_funpay_credentials(encrypted_data)
        except Exception as e:
            logger.error(f"Error decrypting FunPay credentials: {e}")
            return "", ""
    
    # Методы для статистики и аналитики
    def get_user_statistics(self, user_id: int) -> Dict:
        """Получает статистику пользователя"""
        if not self.user_manager:
            return {}
        
        try:
            stats = self.user_manager.get_user_statistics(user_id)
            if stats:
                return {
                    'total_accounts': stats.total_accounts,
                    'rented_accounts': stats.rented_accounts,
                    'total_rental_hours': stats.total_rental_hours,
                    'total_spent': stats.total_spent,
                    'last_rental': stats.last_rental.isoformat() if stats.last_rental else None,
                    'favorite_games': stats.favorite_games
                }
            return {}
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            return {}
    
    def get_system_statistics(self) -> Dict:
        """Получает общую статистику системы"""
        if not self.user_manager:
            return {}
        
        try:
            return self.user_manager.get_system_statistics()
        except Exception as e:
            logger.error(f"Error getting system statistics: {e}")
            return {}
    
    def cleanup_expired_subscriptions(self) -> int:
        """Очищает истекшие подписки"""
        if not self.user_manager:
            return 0
        
        try:
            return self.user_manager.cleanup_expired_subscriptions()
        except Exception as e:
            logger.error(f"Error cleaning up expired subscriptions: {e}")
            return 0
    
    # Методы для администрирования
    def get_all_users(self, role: str = None, active_only: bool = True) -> list:
        """Получает список всех пользователей"""
        if not self.user_manager:
            return []
        
        try:
            user_role = UserRole(role) if role else None
            users = self.user_manager.get_all_users(user_role, active_only)
            return [{
                'user_id': user.user_id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role.value,
                'subscription_status': user.subscription_status.value,
                'subscription_end': user.subscription_end.isoformat() if user.subscription_end else None,
                'balance': float(user.balance),
                'created_at': user.created_at.isoformat(),
                'last_activity': user.last_activity.isoformat(),
                'is_active': user.is_active
            } for user in users]
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    def update_user_role(self, user_id: int, role: str) -> bool:
        """Обновляет роль пользователя"""
        if not self.user_manager:
            return False
        
        try:
            user_role = UserRole(role)
            return self.user_manager.update_user_role(user_id, user_role)
        except Exception as e:
            logger.error(f"Error updating user role: {e}")
            return False
    
    def deactivate_user(self, user_id: int) -> bool:
        """Деактивирует пользователя"""
        if not self.user_manager:
            return False
        
        try:
            return self.user_manager.deactivate_user(user_id)
        except Exception as e:
            logger.error(f"Error deactivating user: {e}")
            return False
    
    def activate_user(self, user_id: int) -> bool:
        """Активирует пользователя"""
        if not self.user_manager:
            return False
        
        try:
            return self.user_manager.activate_user(user_id)
        except Exception as e:
            logger.error(f"Error activating user: {e}")
            return False
