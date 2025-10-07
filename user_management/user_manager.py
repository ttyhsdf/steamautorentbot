#!/usr/bin/env python3
"""
Продвинутая система управления пользователями для AutoRentSteam
Включает подписки, роли и расширенную аналитику
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum

from databaseHandler.databaseSetup import SQLiteDB
from security.encryption import get_secure_data_manager
from logger import logger

class UserRole(Enum):
    """Роли пользователей"""
    USER = "user"
    PREMIUM = "premium"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class SubscriptionStatus(Enum):
    """Статусы подписки"""
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"

@dataclass
class UserProfile:
    """Профиль пользователя"""
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    role: UserRole
    subscription_status: SubscriptionStatus
    subscription_end: Optional[datetime]
    balance: float
    created_at: datetime
    last_activity: datetime
    is_active: bool
    permissions: List[str]

@dataclass
class UserStats:
    """Статистика пользователя"""
    total_accounts: int
    rented_accounts: int
    total_rental_hours: int
    total_spent: float
    last_rental: Optional[datetime]
    favorite_games: List[str]

class UserManager:
    """Менеджер пользователей с расширенными возможностями"""
    
    def __init__(self):
        self.db = SQLiteDB()
        self.secure_manager = get_secure_data_manager()
        self._create_user_tables()
        logger.info("UserManager initialized")
    
    def _create_user_tables(self):
        """Создает таблицы для управления пользователями"""
        try:
            cursor = self.db.conn.cursor()
            
            # Расширенная таблица пользователей
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    role TEXT DEFAULT 'user',
                    subscription_status TEXT DEFAULT 'expired',
                    subscription_end TIMESTAMP,
                    balance DECIMAL(10, 2) DEFAULT 0.00,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    permissions TEXT DEFAULT '[]',
                    funpay_user_id_encrypted BLOB,
                    funpay_golden_key_encrypted BLOB,
                    telegram_settings TEXT DEFAULT '{}'
                )
                """
            )
            
            # Таблица статистики пользователей
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_statistics (
                    user_id INTEGER PRIMARY KEY,
                    total_accounts INTEGER DEFAULT 0,
                    rented_accounts INTEGER DEFAULT 0,
                    total_rental_hours INTEGER DEFAULT 0,
                    total_spent DECIMAL(10, 2) DEFAULT 0.00,
                    last_rental TIMESTAMP,
                    favorite_games TEXT DEFAULT '[]',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            
            # Таблица активности пользователей
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            
            self.db.conn.commit()
            cursor.close()
            logger.info("User management tables created successfully")
            
        except Exception as e:
            logger.error(f"Error creating user tables: {e}")
    
    def create_user(self, user_id: int, username: str = None, first_name: str = None, 
                   last_name: str = None, role: UserRole = UserRole.USER) -> bool:
        """Создает нового пользователя"""
        try:
            cursor = self.db.conn.cursor()
            
            # Проверяем, существует ли пользователь
            cursor.execute("SELECT user_id FROM user_profiles WHERE user_id = ?", (user_id,))
            if cursor.fetchone():
                logger.warning(f"User {user_id} already exists")
                return False
            
            # Создаем профиль пользователя
            cursor.execute(
                """INSERT INTO user_profiles 
                   (user_id, username, first_name, last_name, role, created_at, last_activity)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, username, first_name, last_name, role.value, 
                 datetime.now(), datetime.now())
            )
            
            # Создаем статистику
            cursor.execute(
                """INSERT INTO user_statistics (user_id) VALUES (?)""",
                (user_id,)
            )
            
            self.db.conn.commit()
            cursor.close()
            
            logger.info(f"User {user_id} created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return False
    
    def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
        """Получает профиль пользователя"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT user_id, username, first_name, last_name, role, subscription_status,
                          subscription_end, balance, created_at, last_activity, is_active, permissions
                   FROM user_profiles WHERE user_id = ?""",
                (user_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return UserProfile(
                    user_id=result[0],
                    username=result[1],
                    first_name=result[2],
                    last_name=result[3],
                    role=UserRole(result[4]),
                    subscription_status=SubscriptionStatus(result[5]),
                    subscription_end=datetime.fromisoformat(result[6]) if result[6] else None,
                    balance=float(result[7]),
                    created_at=datetime.fromisoformat(result[8]),
                    last_activity=datetime.fromisoformat(result[9]),
                    is_active=bool(result[10]),
                    permissions=eval(result[11]) if result[11] else []
                )
            return None
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None
    
    def update_user_activity(self, user_id: int, action: str, details: str = None, 
                           ip_address: str = None, user_agent: str = None) -> bool:
        """Обновляет активность пользователя"""
        try:
            cursor = self.db.conn.cursor()
            
            # Обновляем время последней активности
            cursor.execute(
                "UPDATE user_profiles SET last_activity = ? WHERE user_id = ?",
                (datetime.now(), user_id)
            )
            
            # Записываем действие в лог
            cursor.execute(
                """INSERT INTO user_activity_log 
                   (user_id, action, details, ip_address, user_agent)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, action, details, ip_address, user_agent)
            )
            
            self.db.conn.commit()
            cursor.close()
            return True
            
        except Exception as e:
            logger.error(f"Error updating user activity: {e}")
            return False
    
    def update_user_role(self, user_id: int, role: UserRole) -> bool:
        """Обновляет роль пользователя"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE user_profiles SET role = ? WHERE user_id = ?",
                (role.value, user_id)
            )
            self.db.conn.commit()
            cursor.close()
            
            logger.info(f"User {user_id} role updated to {role.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user role: {e}")
            return False
    
    def update_user_subscription(self, user_id: int, status: SubscriptionStatus, 
                               end_date: datetime = None) -> bool:
        """Обновляет подписку пользователя"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE user_profiles SET subscription_status = ?, subscription_end = ? WHERE user_id = ?",
                (status.value, end_date.isoformat() if end_date else None, user_id)
            )
            self.db.conn.commit()
            cursor.close()
            
            logger.info(f"User {user_id} subscription updated to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating subscription: {e}")
            return False
    
    def is_user_subscribed(self, user_id: int) -> bool:
        """Проверяет, активна ли подписка пользователя"""
        try:
            profile = self.get_user_profile(user_id)
            if not profile:
                return False
            
            if profile.subscription_status != SubscriptionStatus.ACTIVE:
                return False
            
            if profile.subscription_end and profile.subscription_end < datetime.now():
                # Подписка истекла
                self.update_user_subscription(user_id, SubscriptionStatus.EXPIRED)
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking subscription: {e}")
            return False
    
    def get_user_statistics(self, user_id: int) -> Optional[UserStats]:
        """Получает статистику пользователя"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT total_accounts, rented_accounts, total_rental_hours, total_spent,
                          last_rental, favorite_games
                   FROM user_statistics WHERE user_id = ?""",
                (user_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return UserStats(
                    total_accounts=result[0],
                    rented_accounts=result[1],
                    total_rental_hours=result[2],
                    total_spent=float(result[3]),
                    last_rental=datetime.fromisoformat(result[4]) if result[4] else None,
                    favorite_games=eval(result[5]) if result[5] else []
                )
            return None
            
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            return None
    
    def update_user_statistics(self, user_id: int, **kwargs) -> bool:
        """Обновляет статистику пользователя"""
        try:
            cursor = self.db.conn.cursor()
            
            # Формируем запрос обновления
            update_fields = []
            values = []
            
            for key, value in kwargs.items():
                if key in ['total_accounts', 'rented_accounts', 'total_rental_hours']:
                    update_fields.append(f"{key} = ?")
                    values.append(value)
                elif key == 'total_spent':
                    update_fields.append(f"{key} = ?")
                    values.append(float(value))
                elif key == 'last_rental':
                    update_fields.append(f"{key} = ?")
                    values.append(value.isoformat() if value else None)
                elif key == 'favorite_games':
                    update_fields.append(f"{key} = ?")
                    values.append(str(value))
            
            if update_fields:
                update_fields.append("updated_at = ?")
                values.append(datetime.now())
                values.append(user_id)
                
                query = f"UPDATE user_statistics SET {', '.join(update_fields)} WHERE user_id = ?"
                cursor.execute(query, values)
                self.db.conn.commit()
            
            cursor.close()
            return True
            
        except Exception as e:
            logger.error(f"Error updating user statistics: {e}")
            return False
    
    def get_all_users(self, role: UserRole = None, active_only: bool = True) -> List[UserProfile]:
        """Получает список всех пользователей"""
        try:
            cursor = self.db.conn.cursor()
            
            query = "SELECT user_id, username, first_name, last_name, role, subscription_status, subscription_end, balance, created_at, last_activity, is_active, permissions FROM user_profiles"
            conditions = []
            params = []
            
            if role:
                conditions.append("role = ?")
                params.append(role.value)
            
            if active_only:
                conditions.append("is_active = 1")
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            
            users = []
            for result in results:
                users.append(UserProfile(
                    user_id=result[0],
                    username=result[1],
                    first_name=result[2],
                    last_name=result[3],
                    role=UserRole(result[4]),
                    subscription_status=SubscriptionStatus(result[5]),
                    subscription_end=datetime.fromisoformat(result[6]) if result[6] else None,
                    balance=float(result[7]),
                    created_at=datetime.fromisoformat(result[8]),
                    last_activity=datetime.fromisoformat(result[9]),
                    is_active=bool(result[10]),
                    permissions=eval(result[11]) if result[11] else []
                ))
            
            return users
            
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    def get_user_activity_log(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Получает лог активности пользователя"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT action, details, ip_address, user_agent, created_at
                   FROM user_activity_log 
                   WHERE user_id = ? 
                   ORDER BY created_at DESC 
                   LIMIT ?""",
                (user_id, limit)
            )
            results = cursor.fetchall()
            cursor.close()
            
            activities = []
            for result in results:
                activities.append({
                    'action': result[0],
                    'details': result[1],
                    'ip_address': result[2],
                    'user_agent': result[3],
                    'created_at': datetime.fromisoformat(result[4])
                })
            
            return activities
            
        except Exception as e:
            logger.error(f"Error getting user activity log: {e}")
            return []
    
    def deactivate_user(self, user_id: int) -> bool:
        """Деактивирует пользователя"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE user_profiles SET is_active = 0 WHERE user_id = ?",
                (user_id,)
            )
            self.db.conn.commit()
            cursor.close()
            
            logger.info(f"User {user_id} deactivated")
            return True
            
        except Exception as e:
            logger.error(f"Error deactivating user: {e}")
            return False
    
    def activate_user(self, user_id: int) -> bool:
        """Активирует пользователя"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE user_profiles SET is_active = 1 WHERE user_id = ?",
                (user_id,)
            )
            self.db.conn.commit()
            cursor.close()
            
            logger.info(f"User {user_id} activated")
            return True
            
        except Exception as e:
            logger.error(f"Error activating user: {e}")
            return False
    
    def get_system_statistics(self) -> Dict:
        """Получает общую статистику системы"""
        try:
            cursor = self.db.conn.cursor()
            
            # Общее количество пользователей
            cursor.execute("SELECT COUNT(*) FROM user_profiles")
            total_users = cursor.fetchone()[0]
            
            # Активные пользователи
            cursor.execute("SELECT COUNT(*) FROM user_profiles WHERE is_active = 1")
            active_users = cursor.fetchone()[0]
            
            # Пользователи с подпиской
            cursor.execute("SELECT COUNT(*) FROM user_profiles WHERE subscription_status = 'active'")
            subscribed_users = cursor.fetchone()[0]
            
            # Общий баланс
            cursor.execute("SELECT SUM(balance) FROM user_profiles")
            total_balance = cursor.fetchone()[0] or 0
            
            # Пользователи по ролям
            cursor.execute("SELECT role, COUNT(*) FROM user_profiles GROUP BY role")
            users_by_role = dict(cursor.fetchall())
            
            cursor.close()
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'subscribed_users': subscribed_users,
                'total_balance': float(total_balance),
                'users_by_role': users_by_role
            }
            
        except Exception as e:
            logger.error(f"Error getting system statistics: {e}")
            return {}
    
    def cleanup_expired_subscriptions(self) -> int:
        """Очищает истекшие подписки"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """UPDATE user_profiles 
                   SET subscription_status = 'expired' 
                   WHERE subscription_status = 'active' 
                   AND subscription_end < ?""",
                (datetime.now(),)
            )
            updated_count = cursor.rowcount
            self.db.conn.commit()
            cursor.close()
            
            if updated_count > 0:
                logger.info(f"Cleaned up {updated_count} expired subscriptions")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired subscriptions: {e}")
            return 0
