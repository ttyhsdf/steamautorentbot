import os
from settings import *



DATA = {
    "config": {
        "path": os.path.join(os.path.dirname(__file__), 'module_settings', 'config.json'),
        "need_restore": True,
        "default": {
            "funpay": {
                "bot": {
                    "log_states": True
                }
            }
        }
    },
    "messages": {
        "path": os.path.join(os.path.dirname(__file__), 'module_settings', 'messages.json'),
        "need_restore": True,
        "default": {
            "cmd_writein": {
                "enabled": True,
                "text": [
                    "✏️ Шаг 1. Ввод фамилии, имени, отчества",
                    "",
                    "💡 Например: Петров Иван Олегович",
                    "",
                    "Введите своё ФИО:"
                ]
            },
            "entering_fullname_error": {
                "enabled": True,
                "text": [
                    "❌ Шаг 1. Ошибка ввода ФИО",
                    "",
                    "Убедитесь, что текст соответствует формату",
                    "",
                    "Введите ФИО снова:"
                ]
            },
            "enter_age": {
                "enabled": True,
                "text": [
                    "✏️ Шаг 2. Ввод возраста",
                    "",
                    "💡 Например: 18",
                    "",
                    "Введите свой возраст:"
                ]
            },
            "entering_age_error": {
                "enabled": True,
                "text": [
                    "❌ Шаг 2. Ошибка ввода возраста",
                    "",
                    "Убедитесь, что вы ввели числовое значение",
                    "",
                    "Введите возраст снова:"
                ]
            },
            "enter_hobby": {
                "enabled": True,
                "text": [
                    "✏️ Шаг 3. Ввод хобби",
                    "",
                    "💡 Например: Рисование",
                    "",
                    "Введите своё хобби:"
                ]
            },
            "entering_username_error": {
                "enabled": True,
                "text": [
                    "❌ Шаг 3. Ошибка ввода хобби",
                    "",
                    "Убедитесь, что текст соответствует формату",
                    "",
                    "Введите хобби снова:"
                ]
            },
            "form_filled_out": {
                "enabled": True,
                "text": [
                    "✅ Анкета была заполнена!",
                    "",
                    "Ваши данные:",
                    "・ ФИО: {fullname}",
                    "・ Возраст: {age}",
                    "・ Хобби: {hobby}",
                    "",
                    "💡 Используйте команду !мояанкета, чтобы просмотреть данные снова"
                ]
            },
            "cmd_myform": {
                "enabled": True,
                "text": [
                    "📝 Ваша анкета",
                    "",
                    "・ ФИО: {fullname}",
                    "・ Возраст: {age}",
                    "・ Хобби: {hobby}",
                    "",
                    "💡 Используйте команду !заполнить, чтобы заполнить анкету заново"
                ]
            },
            "cmd_myform_error": {
                "enabled": True,
                "text": [
                    "❌ При открытии вашей анкеты произошла ошибка",
                    "",
                    "{reason}"
                ]
            }
        },
    }
}

class Settings:
    
    @staticmethod
    def get(name) -> dict:
        return get_json(DATA[name]["path"], DATA[name]["default"], DATA[name]["need_restore"])

    @staticmethod
    def set(name, new) -> dict:
        set_json(DATA[name]["path"], new)