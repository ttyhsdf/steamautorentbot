#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📝 Упрощенная система шаблонов сообщений для FunPay
Только необходимые данные аккаунта без лишних инструкций
"""

from typing import Dict, Any
from datetime import datetime

class MessageTemplates:
    """Класс для управления шаблонами сообщений"""
    
    def __init__(self):
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, str]:
        """Загрузка всех шаблонов сообщений"""
        return {
            # Основной шаблон для заказов - только данные аккаунта
            "order_data": """🎮 **ДАННЫЕ АККАУНТА STEAM**

👤 **Логин:** `{login}`
🔑 **Пароль:** `{password}`
🔐 **Steam Guard код:** `{steam_guard_code}`

⏱ **Срок аренды:** {rental_duration} часов
📅 **Начало:** {start_time}

⚠️ **Правила:**
• НЕ меняйте пароль
• НЕ добавляйте друзей
• После окончания пароль будет изменен

⭐ **За отзыв получите +{bonus_hours} час бонуса!**

Удачной игры! 🎯""",

            # Уведомление о бонусе за отзыв
            "bonus_activated": """🎉 **БОНУС АКТИВИРОВАН!**

⭐ **Ваш отзыв принят!**

🎁 **Получено:**
• +{bonus_hours} часов бонусного времени
• Скидка 10% на следующую аренду

💳 **Бонусное время:** {bonus_time}

Спасибо за отзыв! 🙏"""
        }
    
    def get_template(self, template_name: str) -> str:
        """Получить шаблон по имени"""
        return self.templates.get(template_name, "")
    
    def format_template(self, template_name: str, **kwargs) -> str:
        """Форматировать шаблон с данными"""
        template = self.get_template(template_name)
        if not template:
            return ""
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"Ошибка форматирования шаблона {template_name}: отсутствует параметр {e}"
    
    def get_all_templates(self) -> Dict[str, str]:
        """Получить все шаблоны"""
        return self.templates
    
    def add_template(self, name: str, template: str) -> bool:
        """Добавить новый шаблон"""
        try:
            self.templates[name] = template
            return True
        except Exception:
            return False
    
    def update_template(self, name: str, template: str) -> bool:
        """Обновить существующий шаблон"""
        if name in self.templates:
            self.templates[name] = template
            return True
        return False

# Глобальный экземпляр
message_templates = MessageTemplates()

def get_message_template(template_name: str, **kwargs) -> str:
    """Удобная функция для получения форматированного шаблона"""
    return message_templates.format_template(template_name, **kwargs)