import json
import os
import secrets
import string
import sys
import asyncio


sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import logger
# Импортируем только то, что нужно для базовой функциональности
try:
    from steampassword.chpassword import SteamPasswordChange
    from steampassword.steam import CustomSteam
    FULL_VERSION_AVAILABLE = True
except ImportError:
    # Fallback если есть проблемы с импортами
    SteamPasswordChange = None
    CustomSteam = None
    FULL_VERSION_AVAILABLE = False
    logger.warning("Full Steam password change not available, using simplified version")


def generate_password(length: int = 12) -> str:
    """
    Generate a secure random password.

    Args:
        length (int): Length of the password. Default is 12.

    Returns:
        str: A randomly generated password.
    """
    if length < 8:
        raise ValueError("Password length should be at least 8 characters.")

    # Define the character pool
    alphabet = string.ascii_letters + string.digits
    # Generate a secure random password
    password = "".join(secrets.choice(alphabet) for _ in range(length))
    return password


async def changeSteamPassword(path_to_maFile: str, password: str) -> str:
    """Смена пароля Steam аккаунта с улучшенной обработкой ошибок"""
    logger.info("Started changing password")

    try:
        with open(path_to_maFile, "r", encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"Started changing password for {data['account_name']}")
            
        # Проверяем наличие всех необходимых данных
        required_fields = ["account_name", "shared_secret", "identity_secret", "device_id", "Session"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field in .maFile: {field}")
                
        if "SteamID" not in data["Session"]:
            raise ValueError("Missing SteamID in Session data")
            
        steam = CustomSteam(
            login=data["account_name"],
            password=password,
            shared_secret=data["shared_secret"],
            identity_secret=data["identity_secret"],
            device_id=data["device_id"],
            steamid=int(data["Session"]["SteamID"]),
        )

        new_password = generate_password(12)
        logger.info(f"Generated new password for {data['account_name']}")

        # Проверяем доступность полной версии
        if not FULL_VERSION_AVAILABLE:
            logger.warning("⚠️ Full Steam password change not available")
            logger.warning("⚠️ Using simplified version - password generation only")
            logger.info(f"✅ {data['account_name']} new password generated: {new_password}")
            return new_password

        # Пытаемся сменить пароль с повторными попытками
            
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                logger.info(f"Password change attempt {attempt + 1}/{max_attempts}")
                await SteamPasswordChange(steam).change(new_password)
                logger.info(f"✅ {data['account_name']} password changed successfully -> {new_password}")
                return new_password
                
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Password change attempt {attempt + 1} failed: {error_msg}")
                
                if "TwoFactorCodeMismatch" in error_msg:
                    logger.error("Steam Guard code mismatch - possible time sync issue")
                    if attempt < max_attempts - 1:
                        logger.info("Waiting 5 seconds before retry...")
                        await asyncio.sleep(5)
                        continue
                elif "RateLimitExceeded" in error_msg:
                    logger.error("Rate limit exceeded - waiting longer before retry")
                    if attempt < max_attempts - 1:
                        wait_time = 30 * (attempt + 1)  # Увеличиваем время ожидания
                        logger.info(f"Waiting {wait_time} seconds before retry...")
                        await asyncio.sleep(wait_time)
                        continue
                        
                # Если это последняя попытка, пробрасываем ошибку
                if attempt == max_attempts - 1:
                    raise e
                    
    except FileNotFoundError:
        logger.error(f"Steam .maFile not found: {path_to_maFile}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid .maFile format: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        raise
