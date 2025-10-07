import os
import time
import hmac
import json
import struct
import base64
import requests
from hashlib import sha1
import argparse

# Импортируем logger
try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def getQueryTime():
    """Получает разность времени между сервером Steam и локальным временем"""
    try:
        request = requests.post(
            "https://api.steampowered.com/ITwoFactorService/QueryTime/v0001", 
            timeout=30
        )
        json_data = request.json()
        server_time = int(json_data["response"]["server_time"]) - time.time()
        logger.debug(f"Steam server time offset: {server_time} seconds")
        return server_time
    except Exception as e:
        logger.warning(f"Failed to get Steam server time: {str(e)}")
        return 0


def getGuardCode(shared_secret):
    """Генерирует Steam Guard код с улучшенной синхронизацией времени"""
    symbols = "23456789BCDFGHJKMNPQRTVWXY"
    code = ""
    
    # Получаем синхронизированное время
    server_offset = getQueryTime()
    timestamp = time.time() + server_offset
    
    # Используем временной интервал 30 секунд
    time_window = int(timestamp / 30)
    
    try:
        # Декодируем shared_secret
        secret_bytes = base64.b64decode(shared_secret)
        
        # Создаем HMAC
        _hmac = hmac.new(
            secret_bytes, 
            struct.pack(">Q", time_window), 
            sha1
        ).digest()
        
        # Извлекаем код
        _ord = ord(_hmac[19:20]) & 0xF
        value = struct.unpack(">I", _hmac[_ord : _ord + 4])[0] & 0x7FFFFFFF
        
        # Генерируем 5-символьный код
        for i in range(5):
            code += symbols[value % len(symbols)]
            value = int(value / len(symbols))
            
        logger.debug(f"Generated Steam Guard code: {code} (time_window: {time_window})")
        return code
        
    except Exception as e:
        logger.error(f"Error generating Steam Guard code: {str(e)}")
        return None


def get_steam_guard_code(mafile_path):
    """Получает Steam Guard код из .maFile с улучшенной обработкой ошибок"""
    try:
        with open(mafile_path, "r", encoding='utf-8') as file:
            data = json.loads(file.read())
            
        # Проверяем наличие необходимых данных
        if "shared_secret" not in data:
            logger.error("Missing shared_secret in .maFile")
            return None
            
        # Генерируем код
        code = getGuardCode(data["shared_secret"])
        
        if code is None:
            logger.error("Failed to generate Steam Guard code")
            return None
            
        logger.info(f"Successfully generated Steam Guard code for {data.get('account_name', 'unknown')}")
        return code

    except FileNotFoundError:
        logger.error(f"Steam Guard file not found: {mafile_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid .maFile format: {str(e)}")
        return None
    except KeyError as e:
        logger.error(f"Missing required data in .maFile: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting Steam Guard code: {str(e)}")
        return None
