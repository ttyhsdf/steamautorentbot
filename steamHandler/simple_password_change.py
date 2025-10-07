#!/usr/bin/env python3
"""
Упрощенная версия смены пароля Steam без сложных зависимостей
"""

import asyncio
import json
import secrets
import string
import sys
import os
from typing import Optional

# Добавляем пути к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import logger

def generate_password(length: int = 12) -> str:
    """
    Генерирует безопасный пароль
    
    Args:
        length: Длина пароля (по умолчанию 12)
        
    Returns:
        str: Сгенерированный пароль
    """
    # Define the character pool
    alphabet = string.ascii_letters + string.digits
    # Generate a secure random password
    password = "".join(secrets.choice(alphabet) for _ in range(length))
    return password

async def changeSteamPassword(path_to_maFile: str, password: str) -> str:
    """
    Упрощенная смена пароля Steam аккаунта
    В этой версии мы просто генерируем новый пароль и возвращаем его
    Реальная смена пароля требует более сложной интеграции с Steam API
    """
    logger.info("Started changing password (simplified version)")

    try:
        with open(path_to_maFile, "r", encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"Started changing password for {data['account_name']}")
            
        # Проверяем наличие всех необходимых данных
        required_fields = ["account_name", "shared_secret", "identity_secret", "device_id", "Session"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        # Генерируем новый пароль
        new_password = generate_password(12)
        logger.info(f"Generated new password for {data['account_name']}")
        
        # В упрощенной версии мы просто возвращаем новый пароль
        # В реальной реализации здесь должна быть интеграция с Steam API
        logger.warning("⚠️ SIMPLIFIED VERSION: Password change not actually performed")
        logger.warning("⚠️ This is a fallback version - install full dependencies for real password change")
        
        logger.info(f"✅ {data['account_name']} new password generated: {new_password}")
        return new_password
                    
    except FileNotFoundError:
        logger.error(f"Steam .maFile not found: {path_to_maFile}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid .maFile format: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        raise

# Функция для проверки доступности полной версии
def is_full_version_available() -> bool:
    """Проверяет, доступна ли полная версия смены пароля"""
    try:
        from steampassword.chpassword import SteamPasswordChange
        return True
    except ImportError:
        return False

# Функция для получения версии
def get_version() -> str:
    """Возвращает версию модуля"""
    if is_full_version_available():
        return "full"
    else:
        return "simplified"
