#!/usr/bin/env python3
"""
Система шифрования AES-256 для AutoRentSteam
Профессиональная реализация безопасности данных
"""

import os
import base64
import secrets
import string
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class AdvancedCrypto:
    """Продвинутая система шифрования с AES-256"""
    
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("Key must be 32 bytes long for AES-256")
        self.key = key
        self.backend = default_backend()
        logger.info("AdvancedCrypto initialized with AES-256")

    def encrypt(self, plaintext: bytes) -> bytes:
        """Шифрует данные с использованием AES-256-CBC"""
        try:
            iv = os.urandom(16)
            cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=self.backend)
            encryptor = cipher.encryptor()
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(plaintext)
            padded_data += padder.finalize()
            ciphertext = encryptor.update(padded_data) + encryptor.finalize()
            return iv + ciphertext
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Расшифровывает данные с использованием AES-256-CBC"""
        try:
            iv = ciphertext[:16]
            actual_ciphertext = ciphertext[16:]
            cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=self.backend)
            decryptor = cipher.decryptor()
            padded_plaintext = decryptor.update(actual_ciphertext) + decryptor.finalize()
            unpadder = padding.PKCS7(128).unpadder()
            plaintext = unpadder.update(padded_plaintext)
            plaintext += unpadder.finalize()
            return plaintext
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise

    def encrypt_string(self, plaintext: str) -> bytes:
        """Шифрует строку и возвращает байты"""
        return self.encrypt(plaintext.encode('utf-8'))

    def decrypt_string(self, encrypted_data: bytes) -> str:
        """Расшифровывает байты и возвращает строку"""
        return self.decrypt(encrypted_data).decode('utf-8')

    def encrypt_to_base64(self, plaintext: str) -> str:
        """Шифрует строку и возвращает base64"""
        encrypted = self.encrypt_string(plaintext)
        return base64.b64encode(encrypted).decode('utf-8')

    def decrypt_from_base64(self, encrypted_b64: str) -> str:
        """Расшифровывает base64 и возвращает строку"""
        encrypted = base64.b64decode(encrypted_b64)
        return self.decrypt_string(encrypted)

def generate_secure_key() -> bytes:
    """Генерирует безопасный 32-байтовый ключ"""
    return secrets.token_bytes(32)

def generate_secure_password(length: int = 16) -> str:
    """Генерирует безопасный случайный пароль"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_api_key() -> str:
    """Генерирует API ключ для внешних интеграций"""
    return secrets.token_urlsafe(32)

# Глобальный экземпляр криптографии
_crypto_instance: Optional[AdvancedCrypto] = None

def initialize_crypto(master_key: str) -> bool:
    """Инициализирует глобальный экземпляр криптографии"""
    global _crypto_instance
    try:
        if len(master_key.encode()) != 32:
            logger.error("Master key must be exactly 32 characters long")
            return False
        
        _crypto_instance = AdvancedCrypto(master_key.encode())
        logger.info("Crypto system initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize crypto: {e}")
        return False

def get_crypto() -> AdvancedCrypto:
    """Возвращает глобальный экземпляр криптографии"""
    if _crypto_instance is None:
        raise RuntimeError("Crypto system not initialized. Call initialize_crypto() first.")
    return _crypto_instance

def encrypt_data(data: str) -> bytes:
    """Шифрует данные (удобная функция)"""
    return get_crypto().encrypt_string(data)

def decrypt_data(encrypted_data: bytes) -> str:
    """Расшифровывает данные (удобная функция)"""
    return get_crypto().decrypt_string(encrypted_data)

def encrypt_to_base64(data: str) -> str:
    """Шифрует данные в base64 (удобная функция)"""
    return get_crypto().encrypt_to_base64(data)

def decrypt_from_base64(encrypted_b64: str) -> str:
    """Расшифровывает данные из base64 (удобная функция)"""
    return get_crypto().decrypt_from_base64(encrypted_b64)

# Функции для работы с конфиденциальными данными
class SecureDataManager:
    """Менеджер для безопасной работы с конфиденциальными данными"""
    
    def __init__(self):
        self.crypto = get_crypto()
    
    def encrypt_steam_credentials(self, login: str, password: str) -> dict:
        """Шифрует Steam учетные данные"""
        return {
            'login_encrypted': self.crypto.encrypt_to_base64(login),
            'password_encrypted': self.crypto.encrypt_to_base64(password)
        }
    
    def decrypt_steam_credentials(self, encrypted_data: dict) -> tuple:
        """Расшифровывает Steam учетные данные"""
        login = self.crypto.decrypt_from_base64(encrypted_data['login_encrypted'])
        password = self.crypto.decrypt_from_base64(encrypted_data['password_encrypted'])
        return login, password
    
    def encrypt_funpay_credentials(self, user_id: str, golden_key: str) -> dict:
        """Шифрует FunPay учетные данные"""
        return {
            'user_id_encrypted': self.crypto.encrypt_to_base64(user_id),
            'golden_key_encrypted': self.crypto.encrypt_to_base64(golden_key)
        }
    
    def decrypt_funpay_credentials(self, encrypted_data: dict) -> tuple:
        """Расшифровывает FunPay учетные данные"""
        user_id = self.crypto.decrypt_from_base64(encrypted_data['user_id_encrypted'])
        golden_key = self.crypto.decrypt_from_base64(encrypted_data['golden_key_encrypted'])
        return user_id, golden_key

def get_secure_data_manager() -> SecureDataManager:
    """Возвращает экземпляр менеджера безопасных данных"""
    return SecureDataManager()
