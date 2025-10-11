"""
FunPay интеграция для steamautorentbot

Включает:
- Управление лотами FunPay
- Автоподнятие лотов
- Расширенную статистику профиля
- Telegram интерфейс
"""

from .funpay_integration import FunPayIntegration
from .lots_manager import LotsManager
from .advanced_profile_stats import AdvancedProfileStats
from .lots_telegram_interface import LotsTelegramInterface

__version__ = "1.0.0"
__author__ = "steamautorentbot"
__description__ = "FunPay интеграция с управлением лотами и статистикой профиля"

__all__ = [
    "FunPayIntegration",
    "LotsManager", 
    "AdvancedProfileStats",
    "LotsTelegramInterface"
]
