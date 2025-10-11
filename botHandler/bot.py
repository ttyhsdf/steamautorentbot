import asyncio
import os
import sys
import sqlite3
import time
from datetime import datetime

import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_ID, BOT_TOKEN, HOURS_FOR_REVIEW, SECRET_PHRASE, FUNPAY_GOLDEN_KEY, PROXY_URL as CONF_PROXY_URL, PROXY_LOGIN as CONF_PROXY_LOGIN, PROXY_PASSWORD as CONF_PROXY_PASSWORD
from databaseHandler.databaseSetup import SQLiteDB
from messaging.message_sender import send_message_by_owner
from logger import logger
from steamHandler.changePassword import changeSteamPassword
from botHandler.chat_sync_handlers import register_chat_sync_handlers

# FunPay интеграция
try:
    from FunPayAPI.account import Account
    from funpayHandler.funpay_integration import FunPayIntegration
    FUNPAY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"FunPay интеграция недоступна: {e}")
    FUNPAY_AVAILABLE = False

import requests

db_bot = SQLiteDB()
API_TOKEN = BOT_TOKEN

# --- ПРОКСИ НАСТРОЙКА ---
PROXY_URL = os.getenv("PROXY_URL") or CONF_PROXY_URL
PROXY_LOGIN = os.getenv("PROXY_LOGIN") or CONF_PROXY_LOGIN
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD") or CONF_PROXY_PASSWORD

def configure_proxy():
    import telebot.apihelper
    if PROXY_URL:
        telebot.apihelper.proxy = {
            "http": PROXY_URL,
            "https": PROXY_URL,
        }
    else:
        telebot.apihelper.proxy = None

configure_proxy()
# --- КОНЕЦ ПРОКСИ ---

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts")
try:
    os.makedirs(SAVE_DIR, exist_ok=True)
except PermissionError:
    SAVE_DIR = os.path.join(os.path.expanduser("~"), "UniFlex_accounts")
    os.makedirs(SAVE_DIR, exist_ok=True)

bot = telebot.TeleBot(API_TOKEN)
user_states = {}

# Инициализация FunPay интеграции
funpay_integration = None
if FUNPAY_AVAILABLE and FUNPAY_GOLDEN_KEY:
    try:
        funpay_account = Account(golden_key=FUNPAY_GOLDEN_KEY)
        funpay_integration = FunPayIntegration(funpay_account, bot)
        logger.info("FunPay интеграция успешно инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации FunPay интеграции: {e}")
        funpay_integration = None

# Проверка на запуск только одного экземпляра бота
def check_bot_instance():
    """Проверяет, не запущен ли уже экземпляр бота"""
    try:
        # Пытаемся получить информацию о боте
        bot_info = bot.get_me()
        logger.info(f"Bot instance check: {bot_info.username} is running")
        return True
    except Exception as e:
        logger.error(f"Bot instance check failed: {str(e)}")
        return False

bot.set_my_commands(
    [
        telebot.types.BotCommand("/start", "Начать бота"),
        telebot.types.BotCommand("/accounts", "Посмотреть аккаунты"),
        telebot.types.BotCommand("/code", "Получить Steam Guard код"),
        telebot.types.BotCommand("/manage", "Управление аккаунтами (админ)"),
        telebot.types.BotCommand("/autoguard", "Управление AutoGuard (админ)"),
        telebot.types.BotCommand("/test_accounts", "Тест аккаунтов (админ)"),
        telebot.types.BotCommand("/setproxy", "Установить прокси для бота"),
        telebot.types.BotCommand("/unsetproxy", "Сбросить прокси для бота"),
        telebot.types.BotCommand("/restart", "Перезапустить бота"),
        telebot.types.BotCommand("/restart_info", "Информация о перезапусках (админ)"),
        telebot.types.BotCommand("/unowned", "Свободные аккаунты"),
        telebot.types.BotCommand("/users", "Управление пользователями (админ)"),
        telebot.types.BotCommand("/funpay", "Управление лотами FunPay"),
        telebot.types.BotCommand("/profile", "Статистика профиля FunPay"),
    ]
)

def set_user_state(user_id, state, data=None):
    user_states[user_id] = {"state": state, "data": data or {}}

def get_user_state(user_id):
    return user_states.get(user_id, {"state": None, "data": {}})

def clear_user_state(user_id):
    if user_id in user_states:
        del user_states[user_id]

def is_user_authorized(user_id):
    """Check if user is authorized using database."""
    return db_bot.is_user_authorized(user_id)

def authorize_user(user_id, username=None, first_name=None, last_name=None, permissions='user'):
    """Authorize user and save to database."""
    return db_bot.add_authorized_user(user_id, username, first_name, last_name, permissions)

def update_user_activity(user_id):
    """Update user's last activity."""
    return db_bot.update_user_activity(user_id)

def get_user_info(user_id):
    """Get user information."""
    return db_bot.get_user_info(user_id)

# --- КРАСИВЫЕ КЛАВИАТУРЫ ---

def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📋 Мои аккаунты", callback_data="show_accounts"),
        InlineKeyboardButton("➕ Добавить аккаунты", callback_data="add_account"),
    )
    keyboard.add(
        InlineKeyboardButton("🔄 Сменить пароль", callback_data="change_password"),
        InlineKeyboardButton("⏹ Остановить аренду", callback_data="stop_rent"),
    )
    keyboard.add(
        InlineKeyboardButton("🤝 Ручная аренда", callback_data="manual_rent"),
        InlineKeyboardButton("⏰ Продлить время", callback_data="extend_rental"),
    )
    keyboard.add(
        InlineKeyboardButton("📊 Статистика", callback_data="statistics"),
        InlineKeyboardButton("🛠️ Настройки", callback_data="settings_menu"),
    )
    keyboard.add(
        InlineKeyboardButton("👥 Пользователи", callback_data="users_menu"),
        InlineKeyboardButton("🔧 Управление аккаунтами", callback_data="manage_accounts"),
    )
    # Добавляем кнопку FunPay только для админа
    if funpay_integration:
        keyboard.add(
            InlineKeyboardButton("🏪 FunPay", callback_data="funpay_main_menu"),
            InlineKeyboardButton("📈 Профиль FunPay", callback_data="funpay_profile_menu"),
    )
    keyboard.add(
        InlineKeyboardButton("🧩 Chat Sync", callback_data="chat_sync_menu"),
        InlineKeyboardButton("💬 FunPay", callback_data="funpay_menu"),
    )
    keyboard.add(
        InlineKeyboardButton("🔐 AutoGuard", callback_data="autoguard_menu"),
        InlineKeyboardButton("❓ Помощь", callback_data="help_menu"),
    )
    return keyboard

ACCOUNTS_PER_PAGE = 5

def get_manage_accounts_keyboard():
    """Клавиатура для управления аккаунтами (только для админа)"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📋 Список всех аккаунтов", callback_data="manage_list_all"),
        InlineKeyboardButton("🔍 Найти аккаунт", callback_data="manage_search"),
    )
    keyboard.add(
        InlineKeyboardButton("🗑 Удалить аккаунт", callback_data="manage_delete"),
        InlineKeyboardButton("📁 Заменить .maFile", callback_data="manage_replace_mafile"),
    )
    keyboard.add(
        InlineKeyboardButton("✏️ Редактировать аккаунт", callback_data="manage_edit"),
        InlineKeyboardButton("🔍 Проверить .maFile", callback_data="manage_validate_mafile"),
    )
    keyboard.add(
        InlineKeyboardButton("📊 Статистика аккаунтов", callback_data="manage_stats"),
        InlineKeyboardButton("🧹 Очистить неиспользуемые", callback_data="manage_cleanup"),
    )
    keyboard.add(
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"),
    )
    return keyboard

def get_autoguard_keyboard():
    """Клавиатура для управления AutoGuard (только для админа)"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Статистика AutoGuard", callback_data="autoguard_stats"),
        InlineKeyboardButton("⚙️ Настройки", callback_data="autoguard_settings"),
    )
    keyboard.add(
        InlineKeyboardButton("🔄 Перезапустить", callback_data="autoguard_restart"),
        InlineKeyboardButton("⏹ Остановить", callback_data="autoguard_stop"),
    )
    keyboard.add(
        InlineKeyboardButton("🧹 Очистить задачи", callback_data="autoguard_cleanup"),
        InlineKeyboardButton("📋 Активные задачи", callback_data="autoguard_tasks"),
    )
    keyboard.add(
        InlineKeyboardButton("🔍 Тест кода", callback_data="autoguard_test"),
        InlineKeyboardButton("📝 Логи", callback_data="autoguard_logs"),
    )
    keyboard.add(
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"),
    )
    return keyboard

def get_accounts_pagination_keyboard(page, total_pages):
    keyboard = InlineKeyboardMarkup(row_width=2)
    if page > 0:
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"accounts_page_{page - 1}"))
    if page < total_pages - 1:
        keyboard.add(InlineKeyboardButton("➡️ Вперёд", callback_data=f"accounts_page_{page + 1}"))
    keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main"))
    return keyboard

@bot.callback_query_handler(func=lambda call: call.data == "show_accounts")
def show_accounts_callback(call):
    accounts = db_bot.get_all_accounts()
    if not accounts:
        bot.edit_message_text(
            "Аккаунты не найдены.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_main_keyboard()
        )
        return
    set_user_state(call.from_user.id, "viewing_accounts", {"accounts": accounts, "page": 0})
    send_accounts_page(call.message.chat.id, accounts, 0, call.message.message_id)

def send_accounts_page(chat_id, accounts, page, message_id=None):
    start = page * ACCOUNTS_PER_PAGE
    end = start + ACCOUNTS_PER_PAGE
    accounts_page = accounts[start:end]
    total_pages = (len(accounts) + ACCOUNTS_PER_PAGE - 1) // ACCOUNTS_PER_PAGE

    if not accounts_page:
        msg = "❗Нет больше аккаунтов для отображения."
    else:
        grouped_accounts = {}
        for account in accounts_page:
            account_name = account["account_name"]
            if account_name not in grouped_accounts:
                grouped_accounts[account_name] = []
            grouped_accounts[account_name].append(account)

        response = []
        for account_name, account_list in grouped_accounts.items():
            response.append(f"**📝 Название лота: `{account_name}`**")
            for account in account_list:
                account_id = account["id"]
                login = account["login"]
                password = account["password"]
                owner = account["owner"]
                account_info = (
                    f"🆔 ID: `{account_id}`\n"
                    f"🔑 Логин: `{login}`\n"
                    f"🔒 Пароль: `{password}`\n"
                )
                if owner:
                    account_info += f"👤 Владелец: `{owner}`"
                response.append(account_info)
        msg = "\n\n".join(response)

    keyboard = get_accounts_pagination_keyboard(page, total_pages)
    if message_id:
        bot.edit_message_text(
            msg,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    else:
        bot.send_message(
            chat_id,
            msg,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("accounts_page_"))
def handle_accounts_pagination(call):
    page = int(call.data.split("_")[-1])
    state = get_user_state(call.from_user.id)
    if state["state"] == "viewing_accounts":
        accounts = state["data"]["accounts"]
        send_accounts_page(
            call.message.chat.id, accounts, page, message_id=call.message.message_id
        )
        set_user_state(
            call.from_user.id, "viewing_accounts", {"accounts": accounts, "page": page}
        )
    bot.answer_callback_query(call.id)


def get_settings_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔌 Прокси", callback_data="proxy_settings"),
        InlineKeyboardButton("👑 Голд кей", callback_data="gold_key_settings"),
    )
    keyboard.add(
        InlineKeyboardButton("⚙️ Система", callback_data="system_settings"),
        InlineKeyboardButton("📱 Уведомления", callback_data="notification_settings"),
    )
    keyboard.add(
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"),
    )
    return keyboard

def get_proxy_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔌 Установить/сменить", callback_data="proxy_set"),
        InlineKeyboardButton("❌ Сбросить", callback_data="proxy_unset"),
    )
    keyboard.add(
        InlineKeyboardButton("📊 Статус", callback_data="proxy_status"),
        InlineKeyboardButton("⬅️ Назад", callback_data="settings_menu"),
    )
    return keyboard

def get_gold_key_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✏️ Изменить", callback_data="gold_key_change"),
        InlineKeyboardButton("🔎 Проверить", callback_data="gold_key_check"),
    )
    keyboard.add(
        InlineKeyboardButton("⬅️ Назад", callback_data="settings_menu"),
    )
    return keyboard

def get_system_settings_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔄 Автообновление", callback_data="auto_refresh_toggle"),
        InlineKeyboardButton("⏰ Таймауты", callback_data="timeout_settings"),
    )
    keyboard.add(
        InlineKeyboardButton("🗄️ База данных", callback_data="database_settings"),
        InlineKeyboardButton("⬅️ Назад", callback_data="settings_menu"),
    )
    return keyboard

def get_notification_settings_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔔 Новые заказы", callback_data="notify_new_orders"),
        InlineKeyboardButton("⏰ Истечение аренды", callback_data="notify_expiry"),
    )
    keyboard.add(
        InlineKeyboardButton("❌ Ошибки", callback_data="notify_errors"),
        InlineKeyboardButton("⬅️ Назад", callback_data="settings_menu"),
    )
    return keyboard

def get_accounts_pagination_keyboard(page, total_pages):
    keyboard = InlineKeyboardMarkup(row_width=2)
    if page > 0:
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"accounts_page_{page - 1}"))
    if page < total_pages - 1:
        keyboard.add(InlineKeyboardButton("➡️ Вперёд", callback_data=f"accounts_page_{page + 1}"))
    keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main"))
    return keyboard

# --- МЕНЮ НАСТРОЕК ---
@bot.callback_query_handler(func=lambda call: call.data == "settings_menu")
def settings_menu_callback(call):
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="🛠️ <b>Настройки</b>",
        reply_markup=get_settings_keyboard(),
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# --- ГОЛД КЕЙ НАСТРОЙКИ ---
@bot.callback_query_handler(func=lambda call: call.data == "gold_key_settings")
def gold_key_settings_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.", show_alert=True)
        return
    keyboard = get_gold_key_keyboard()
    current_key = get_gold_key_from_config()
    display_key = current_key if current_key else "Не задан"
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"👑 <b>Голд кей</b>\n\nТекущий Голд кей: <code>{display_key}</code>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "gold_key_change")
def gold_key_change_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.", show_alert=True)
        return
    set_user_state(call.from_user.id, "waiting_for_gold_key")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="✏️ Введите новый Голд кей:",
        reply_markup=get_gold_key_keyboard()
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "gold_key_check")
def gold_key_check_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.", show_alert=True)
        return
    key = get_gold_key_from_config()
    check_result, error_msg = check_funpay_golden_key(key)
    if check_result:
        bot.answer_callback_query(call.id, "Голд кей валидный ✅", show_alert=True)
    else:
        bot.answer_callback_query(call.id, f"Голд кей невалидный ❌\n{error_msg}", show_alert=True)

@bot.message_handler(func=lambda message: get_user_state(message.from_user.id)["state"] == "waiting_for_gold_key")
def process_gold_key(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Доступ запрещён.")
        return
    new_key = message.text.strip()
    res = update_gold_key_in_config(new_key)
    if res:
        bot.send_message(message.chat.id, f"🤑Голд кей успешно изменён!\nНовый ключ: <code>{new_key}</code>", parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "❌Ошибка при сохранении ключа в config.py. Проверьте права доступа.")
    clear_user_state(message.from_user.id)

def get_gold_key_from_config():
    try:
        import importlib.util
        import sys
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.py'))
        spec = importlib.util.spec_from_file_location("config", config_path)
        config = importlib.util.module_from_spec(spec)
        sys.modules["config"] = config
        spec.loader.exec_module(config)
        return getattr(config, "FUNPAY_GOLDEN_KEY", "")
    except Exception as e:
        print(f"[get_gold_key_from_config] {e}")
        return ""

def update_gold_key_in_config(new_key):
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.py'))
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        found = False
        for idx, line in enumerate(lines):
            if line.strip().startswith("FUNPAY_GOLDEN_KEY"):
                lines[idx] = f'FUNPAY_GOLDEN_KEY = "{new_key}"\n'
                found = True
                break
        if not found:
            lines.append(f'\nFUNPAY_GOLDEN_KEY = "{new_key}"\n')
        with open(config_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True
    except Exception as e:
        print(f"Ошибка при записи FUNPAY_GOLDEN_KEY: {e}")
        return False

def check_funpay_golden_key(key):
    try:
        headers = {
            "cookie": f"golden_key={key}",
            "user-agent": "Mozilla/5.0"
        }
        resp = requests.get("https://funpay.com/", headers=headers, timeout=7)
        if resp.status_code == 200:
            if "Профиль" in resp.text or "profile" in resp.text.lower():
                return True, ""
            if "Войти" in resp.text or "login" in resp.text.lower():
                return False, "Ключ не авторизован (вы не вошли в профиль)"
            return False, "Не удалось однозначно определить валидность ключа"
        else:
            return False, f"Сайт ответил с кодом {resp.status_code}"
    except Exception as e:
        return False, f"Ошибка проверки: {e}"

# --- ПРОКСИ СОХРАНЕНИЕ В CONFIG.PY ---
def update_proxy_in_config(proxy_url, proxy_login, proxy_password):
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.py'))
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        params = {
            "PROXY_URL": proxy_url,
            "PROXY_LOGIN": proxy_login,
            "PROXY_PASSWORD": proxy_password
        }
        for key, value in params.items():
            found = False
            for idx, line in enumerate(lines):
                if line.strip().startswith(f"{key}"):
                    lines[idx] = f'{key} = "{value}"\n'
                    found = True
                    break
            if not found:
                lines.append(f'\n{key} = "{value}"\n')
        with open(config_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True
    except Exception as e:
        print(f"Ошибка при записи прокси: {e}")
        return False
# --- КОНЕЦ ПРОКСИ СОХРАНЕНИЯ ---

# --- ПРОКСИ КНОПКИ ---
@bot.callback_query_handler(func=lambda call: call.data == "proxy_settings")
def proxy_settings_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.", show_alert=True)
        return
    keyboard = get_proxy_keyboard()
    current_proxy = PROXY_URL if PROXY_URL else "Не задан"
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🛡️ <b>Прокси</b>\n\nПрокси сейчас: <code>{current_proxy}</code>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "proxy_set")
def proxy_set_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.", show_alert=True)
        return
    set_user_state(call.from_user.id, "waiting_for_proxy_url")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="🔌 <b>Установка прокси</b>\n\nОтправьте прокси в формате:\n<code>http(s)://[login:password@]host:port</code>",
        parse_mode="HTML",
        reply_markup=get_proxy_keyboard()
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "proxy_unset")
def proxy_unset_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.", show_alert=True)
        return
    import telebot.apihelper
    telebot.apihelper.proxy = None
    os.environ.pop("PROXY_URL", None)
    os.environ.pop("PROXY_LOGIN", None)
    os.environ.pop("PROXY_PASSWORD", None)
    global PROXY_URL, PROXY_LOGIN, PROXY_PASSWORD
    PROXY_URL = ""
    PROXY_LOGIN = ""
    PROXY_PASSWORD = ""
    update_proxy_in_config("", "", "")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="❌ Прокси сброшен! Рекомендуется перезапустить бота.",
        reply_markup=get_proxy_keyboard()
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "proxy_check")
def proxy_check_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.", show_alert=True)
        return
    proxy_url = PROXY_URL
    if not proxy_url:
        bot.answer_callback_query(call.id, "Прокси не задан.", show_alert=True)
        return
    if "://" not in proxy_url:
        bot.answer_callback_query(call.id, "Прокси некорректный.", show_alert=True)
        return
    proxies = { "http": proxy_url, "https": proxy_url }
    try:
        r = requests.get("https://api.telegram.org", proxies=proxies, timeout=7)
        if r.status_code == 200:
            bot.answer_callback_query(call.id, "Прокси рабочий ✅", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"Ошибка прокси: {r.status_code}", show_alert=True)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Прокси не работает: {e}", show_alert=True)

# --- ПРОКСИ КОМАНДЫ ---
@bot.message_handler(commands=["setproxy"])
def set_proxy_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Доступ запрещён.")
        return
    set_user_state(message.from_user.id, "waiting_for_proxy_url")
    bot.send_message(message.chat.id, "🔌 <b>Установка прокси</b>\n\nОтправьте прокси в формате:\n<code>http(s)://[login:password@]host:port</code>", parse_mode="HTML")

@bot.message_handler(commands=["unsetproxy"])
def unset_proxy_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Доступ запрещён.")
        return
    import telebot.apihelper
    telebot.apihelper.proxy = None
    os.environ.pop("PROXY_URL", None)
    os.environ.pop("PROXY_LOGIN", None)
    os.environ.pop("PROXY_PASSWORD", None)
    global PROXY_URL, PROXY_LOGIN, PROXY_PASSWORD
    PROXY_URL = ""
    PROXY_LOGIN = ""
    PROXY_PASSWORD = ""
    update_proxy_in_config("", "", "")
    bot.send_message(message.chat.id, "❌ Прокси сброшен! Рекомендуется перезапустить бота.")

@bot.message_handler(func=lambda message: get_user_state(message.from_user.id)["state"] == "waiting_for_proxy_url")
def process_proxy_url(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Доступ запрещён.")
        return
    import telebot.apihelper
    url = message.text.strip()
    try:
        if "://" not in url:
            bot.send_message(message.chat.id, "Ошибка: укажите протокол (http:// или https://) в начале строки прокси!")
            return
        os.environ["PROXY_URL"] = url
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            auth, endpoint = rest.split("@", 1)
            if ":" in auth:
                login, password = auth.split(":", 1)
                os.environ["PROXY_LOGIN"] = login
                os.environ["PROXY_PASSWORD"] = password
            else:
                os.environ["PROXY_LOGIN"] = auth
                os.environ["PROXY_PASSWORD"] = ""
            proxy_url_auth = f"{scheme}://{auth}@{endpoint}"
        else:
            os.environ["PROXY_LOGIN"] = ""
            os.environ["PROXY_PASSWORD"] = ""
            proxy_url_auth = url
        telebot.apihelper.proxy = {
            "http": proxy_url_auth,
            "https": proxy_url_auth,
        }
        global PROXY_URL, PROXY_LOGIN, PROXY_PASSWORD
        PROXY_URL = url
        PROXY_LOGIN = os.environ.get("PROXY_LOGIN")
        PROXY_PASSWORD = os.environ.get("PROXY_PASSWORD")
        update_proxy_in_config(PROXY_URL, PROXY_LOGIN, PROXY_PASSWORD)
        proxies = {"http": proxy_url_auth, "https": proxy_url_auth}
        try:
            r = requests.get("https://api.telegram.org", proxies=proxies, timeout=7)
            if r.status_code == 200:
                bot.send_message(message.chat.id, f"Прокси установлен и рабочий ✅\n{proxy_url_auth}\nРекомендуется перезапустить бота для применения прокси во всех потоках.")
            else:
                bot.send_message(message.chat.id, f"Прокси установлен (но не рабочий, код {r.status_code}): {proxy_url_auth}")
        except Exception as e:
            bot.send_message(message.chat.id, f"Прокси установлен, но не рабочий: {e}")
        clear_user_state(message.from_user.id)
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка установки прокси: {e}")

# --- КОНЕЦ ПРОКСИ ---

@bot.callback_query_handler(func=lambda call: call.data == "statistics")
def statistics_callback(call):
    if not is_user_authorized(call.from_user.id):
        bot.answer_callback_query(call.id, "У вас нет доступа к этой функции")
        return
    
    try:
        stats = db_bot.get_rental_statistics()
        
        if stats:
            message = (
                "📊 **Статистика системы аренды:**\n\n"
                f"🔢 **Всего аккаунтов:** `{stats['total_accounts']}`\n"
                f"✅ **Активных аренд:** `{stats['active_rentals']}`\n"
                f"🆓 **Свободных аккаунтов:** `{stats['available_accounts']}`\n"
                f"⏰ **Общее время аренды:** `{stats['total_hours']}` часов\n"
                f"🆕 **Новых аренд (24ч):** `{stats['recent_rentals']}`\n\n"
                f"📈 **Загруженность:** `{(stats['active_rentals'] / stats['total_accounts'] * 100):.1f}%`"
            )
        else:
            message = "❌ Не удалось получить статистику"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Обновить", callback_data="statistics"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
        
        bot.edit_message_text(
            message,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "help_menu")
def help_menu_callback(call):
    help_text = (
        "❓ **Справка по использованию бота:**\n\n"
        "📋 **Мои аккаунты** - просмотр всех ваших арендованных аккаунтов\n"
        "➕ **Добавить аккаунты** - добавление новых аккаунтов в систему\n"
        "🔄 **Сменить пароль** - смена пароля для конкретного аккаунта\n"
        "⏹ **Остановить аренду** - досрочное прекращение аренды\n"
        "🤝 **Ручная аренда** - ручное назначение аккаунта пользователю\n"
        "⏰ **Продлить время** - продление срока аренды\n"
        "📊 **Статистика** - общая статистика системы\n"
        "🛠️ **Настройки** - настройка прокси и других параметров\n\n"
        "💡 **Полезные команды:**\n"
        "/start - главное меню\n"
        "/accounts - список всех аккаунтов\n"
        "/setproxy - установить прокси\n"
        "/unsetproxy - сбросить прокси\n"
        "/restart - перезапустить бота\n\n"
        "🔐 **Система продления:**\n"
        "• Автоматическое продление на 1 час при оставлении отзыва\n"
        "• Ручное продление через меню 'Продлить время'\n"
        "• Автоматическая смена пароля при истечении срока\n"
        "• Предупреждение за 10 минут до истечения аренды"
    )
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
    
    bot.edit_message_text(
        help_text,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main_callback(call):
    bot.edit_message_text(
        "🎮 **Steam Rental by Lini**\n\n"
        "Выберите нужную функцию:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "get_guard_code")
def get_guard_code_callback(call):
    """Получение Steam Guard кода через кнопку"""
    user_id = str(call.from_user.id)
    username = call.from_user.username or "unknown"
    
    try:
        # Сначала пробуем найти по Telegram ID
        accounts = db_bot.get_user_active_accounts(user_id)
        
        # Если не найдено, пробуем найти по username
        if not accounts and username != "unknown":
            accounts = db_bot.get_user_active_accounts(username)
        
        if not accounts:
            bot.edit_message_text(
                "🔑 **Steam Guard код**\n\n"
                "У вас нет активных арендованных аккаунтов.\n\n"
                "💡 Для аренды аккаунта перейдите на FunPay и совершите покупку.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            return
        
        # Если у пользователя несколько аккаунтов, показываем меню выбора
        if len(accounts) > 1:
            keyboard = InlineKeyboardMarkup()
            for account in accounts:
                keyboard.add(InlineKeyboardButton(
                    f"🔑 {account['account_name']}", 
                    callback_data=f"get_code_{account['id']}"
                ))
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
            
            bot.edit_message_text(
                "🔑 **Выберите аккаунт для получения кода:**",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            return
        
        # Если аккаунт один, сразу генерируем код
        account = accounts[0]
        account_id = account['id']
        account_name = account['account_name']
        
        # Получаем путь к .maFile
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT path_to_maFile FROM accounts WHERE ID = ?", (account_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result[0]:
            bot.edit_message_text(
                f"❌ **Ошибка получения кода**\n\n"
                f"Для аккаунта {account_name} не найден .maFile.\n"
                f"Обратитесь к администратору.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
            return
        
        mafile_path = result[0]
        
        # Генерируем Steam Guard код
        from steamHandler.SteamGuard import get_steam_guard_code
        
        guard_code = get_steam_guard_code(mafile_path)
        
        if guard_code:
            # Обновляем счетчик доступа
            db_bot.increment_access_count(account_id, user_id)
            
            message_text = (
                f"🔑 **Steam Guard код**\n\n"
                f"**Аккаунт:** {account_name}\n"
                f"**Код:** `{guard_code}`\n\n"
                f"⏰ Код действителен 30 секунд\n"
                f"🔄 Для получения нового кода отправьте /code\n\n"
                f"💡 **Полезные команды:**\n"
                f"/accounts - мои аккаунты\n"
                f"/extend - продлить аренду"
            )
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔄 Новый код", callback_data="get_guard_code"))
            keyboard.add(InlineKeyboardButton("📋 Мои аккаунты", callback_data="show_accounts"))
            keyboard.add(InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main"))
            
            bot.edit_message_text(
                message_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
            logger.info(f"Steam Guard code sent to user {user_id} for account {account_name}")
            
        else:
            bot.edit_message_text(
                f"❌ **Ошибка генерации кода**\n\n"
                f"Не удалось сгенерировать Steam Guard код для {account_name}.\n"
                f"Возможные причины:\n"
                f"• Неверный .maFile\n"
                f"• Проблемы с системным временем\n"
                f"• Поврежденный файл\n\n"
                f"Обратитесь к администратору.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
            
            logger.error(f"Failed to generate Steam Guard code for user {user_id}, account {account_name}")
        
    except Exception as e:
        logger.error(f"Error in get_guard_code_callback: {str(e)}")
        try:
            bot.edit_message_text(
                f"❌ **Ошибка получения кода**\n\n{str(e)}",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
        except:
            pass
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("get_code_"))
def get_code_for_account_callback(call):
    """Получение Steam Guard кода для конкретного аккаунта"""
    user_id = str(call.from_user.id)
    account_id = int(call.data.split("_")[2])
    
    try:
        # Получаем информацию об аккаунте
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT account_name, path_to_maFile, owner 
            FROM accounts 
            WHERE ID = ? AND owner = ?
        """, (account_id, user_id))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            bot.edit_message_text(
                "❌ **Ошибка**\n\nАккаунт не найден или не принадлежит вам.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
            return
        
        account_name, mafile_path, owner = result
        
        if not mafile_path:
            bot.edit_message_text(
                f"❌ **Ошибка получения кода**\n\n"
                f"Для аккаунта {account_name} не найден .maFile.\n"
                f"Обратитесь к администратору.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
            return
        
        # Генерируем Steam Guard код
        from steamHandler.SteamGuard import get_steam_guard_code
        
        guard_code = get_steam_guard_code(mafile_path)
        
        if guard_code:
            # Обновляем счетчик доступа
            db_bot.increment_access_count(account_id, user_id)
            
            message_text = (
                f"🔑 **Steam Guard код**\n\n"
                f"**Аккаунт:** {account_name}\n"
                f"**Код:** `{guard_code}`\n\n"
                f"⏰ Код действителен 30 секунд\n"
                f"🔄 Для получения нового кода отправьте /code\n\n"
                f"💡 **Полезные команды:**\n"
                f"/accounts - мои аккаунты\n"
                f"/extend - продлить аренду"
            )
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔄 Новый код", callback_data="get_guard_code"))
            keyboard.add(InlineKeyboardButton("📋 Мои аккаунты", callback_data="show_accounts"))
            keyboard.add(InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main"))
            
            bot.edit_message_text(
                message_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
            logger.info(f"Steam Guard code sent to user {user_id} for account {account_name}")
            
        else:
            bot.edit_message_text(
                f"❌ **Ошибка генерации кода**\n\n"
                f"Не удалось сгенерировать Steam Guard код для {account_name}.\n"
                f"Возможные причины:\n"
                f"• Неверный .maFile\n"
                f"• Проблемы с системным временем\n"
                f"• Поврежденный файл\n\n"
                f"Обратитесь к администратору.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
            
            logger.error(f"Failed to generate Steam Guard code for user {user_id}, account {account_name}")
        
    except Exception as e:
        logger.error(f"Error in get_code_for_account_callback: {str(e)}")
        try:
            bot.edit_message_text(
                f"❌ **Ошибка получения кода**\n\n{str(e)}",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
        except:
            pass
    
    bot.answer_callback_query(call.id)




@bot.message_handler(commands=["manage"])
def manage_accounts_command(message):
    """Команда управления аккаунтами (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещён. Только для администратора.")
        return
    
    bot.send_message(
        message.chat.id,
        "🔧 **Управление аккаунтами**\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_manage_accounts_keyboard()
    )

@bot.message_handler(commands=["autoguard"])
def autoguard_command(message):
    """Команда управления AutoGuard (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещён. Только для администратора.")
        return
    
    bot.send_message(
        message.chat.id,
        "🔐 **AutoGuard - Автоматическая выдача Steam Guard кодов**\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_autoguard_keyboard()
    )

@bot.message_handler(commands=["test_accounts"])
def test_accounts_command(message):
    """Команда тестирования аккаунтов (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещён. Только для администратора.")
        return
    
    try:
        # Получаем все аккаунты с владельцами
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ID, account_name, owner, rental_start, rental_duration, login, password
            FROM accounts 
            WHERE owner IS NOT NULL
            ORDER BY rental_start DESC
        """)
        all_accounts = cursor.fetchall()
        conn.close()
        
        if not all_accounts:
            bot.send_message(
                message.chat.id,
                "🔍 **Тест аккаунтов**\n\n"
                "В базе данных нет аккаунтов с назначенными владельцами.",
                parse_mode="Markdown"
            )
            return
        
        message_text = "🔍 **Тест аккаунтов**\n\n"
        message_text += f"**Всего аккаунтов с владельцами:** {len(all_accounts)}\n\n"
        
        for i, account in enumerate(all_accounts[:10], 1):  # Показываем первые 10
            account_id, account_name, owner, rental_start, rental_duration, login, password = account
            message_text += (
                f"**{i}. ID: {account_id}**\n"
                f"   📝 Название: `{account_name}`\n"
                f"   👤 Владелец: `{owner}`\n"
                f"   🔑 Логин: `{login}`\n"
                f"   🔐 Пароль: `{password}`\n"
                f"   ⏰ Начало аренды: `{rental_start}`\n"
                f"   ⏱ Длительность: {rental_duration}ч\n\n"
            )
        
        if len(all_accounts) > 10:
            message_text += f"... и еще {len(all_accounts) - 10} аккаунтов\n\n"
        
        message_text += (
            "💡 **Для тестирования:**\n"
            "• Используйте username владельца для команды `/code`\n"
            "• Проверьте, что username совпадает с именем на FunPay\n"
            "• Убедитесь, что аккаунты не истекли"
        )
        
        bot.send_message(
            message.chat.id,
            message_text,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in test_accounts command: {str(e)}")
        bot.send_message(
            message.chat.id,
            f"❌ **Ошибка тестирования аккаунтов**\n\n{str(e)}",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=["accounts"])
def accounts_command(message):
    """Команда просмотра аккаунтов пользователя"""
    user_id = str(message.from_user.id)
    username = message.from_user.username or "unknown"
    
    try:
        # Сначала пробуем найти по Telegram ID
        accounts = db_bot.get_user_active_accounts(user_id)
        
        # Если не найдено, пробуем найти по username
        if not accounts and username != "unknown":
            accounts = db_bot.get_user_active_accounts(username)
        
        # Отладочная информация
        logger.info(f"User {user_id} (@{username}) requested accounts, found {len(accounts)} accounts")
        
        # Проверяем все аккаунты в базе для отладки
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT ID, account_name, owner, rental_start FROM accounts WHERE owner IS NOT NULL")
        all_accounts = cursor.fetchall()
        conn.close()
        
        logger.info(f"All accounts with owners: {all_accounts}")
        logger.info(f"Looking for user_id: {user_id}, username: {username}")
        
        if not accounts:
            # Проверяем, есть ли аккаунты с этим пользователем
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT ID, account_name, owner FROM accounts WHERE owner = ? OR owner = ?", (user_id, username))
            user_accounts = cursor.fetchall()
            conn.close()
            
            logger.info(f"Direct query for user {user_id} or {username}: {user_accounts}")
            
            bot.send_message(
                message.chat.id,
                f"📋 **Мои аккаунты**\n\n"
                f"У вас нет активных арендованных аккаунтов.\n\n"
                f"🔍 **Отладочная информация:**\n"
                f"• Ваш Telegram ID: `{user_id}`\n"
                f"• Ваш username: `@{username}`\n"
                f"• Найдено аккаунтов: {len(user_accounts)}\n"
                f"• Всего аккаунтов с владельцами: {len(all_accounts)}\n\n"
                f"💡 **Для получения аккаунта:**\n"
                f"1. Перейдите на FunPay\n"
                f"2. Совершите покупку\n"
                f"3. Используйте команду `/code` для получения Steam Guard кода\n\n"
                f"⚠️ **Важно:** Убедитесь, что ваш username в Telegram совпадает с именем на FunPay!",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            return
        
        # Формируем сообщение с аккаунтами
        message_text = "📋 **Мои аккаунты**\n\n"
        
        for i, account in enumerate(accounts, 1):
            # Вычисляем оставшееся время
            if account['rental_start']:
                from datetime import datetime, timedelta
                start_time = datetime.fromisoformat(account['rental_start'])
                end_time = start_time + timedelta(hours=account['rental_duration'])
                remaining_time = end_time - datetime.now()
                
                if remaining_time.total_seconds() > 0:
                    hours = int(remaining_time.total_seconds() // 3600)
                    minutes = int((remaining_time.total_seconds() % 3600) // 60)
                    time_left = f"{hours}ч {minutes}м"
                else:
                    time_left = "Истек"
            else:
                time_left = "Неизвестно"
            
            message_text += (
                f"**{i}. {account['account_name']}**\n"
                f"   🔑 Логин: `{account['login']}`\n"
                f"   🔐 Пароль: `{account['password']}`\n"
                f"   ⏰ Осталось: {time_left}\n"
                f"   📊 Доступов: {account.get('access_count', 0)}/{account.get('max_access_count', 3)}\n\n"
            )
        
        message_text += (
            "💡 **Полезные команды:**\n"
            "/code - получить Steam Guard код\n"
            "/extend - продлить аренду\n"
            "/change - сменить пароль"
        )
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Обновить", callback_data="show_accounts"))
        keyboard.add(InlineKeyboardButton("🔑 Получить код", callback_data="get_guard_code"))
        keyboard.add(InlineKeyboardButton("⏰ Продлить", callback_data="extend_rental"))
        keyboard.add(InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main"))
        
        bot.send_message(
            message.chat.id,
            message_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in accounts command: {str(e)}")
        bot.send_message(
            message.chat.id,
            f"❌ **Ошибка получения аккаунтов**\n\n{str(e)}",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=["code"])
def code_command(message):
    """Команда получения Steam Guard кода"""
    user_id = str(message.from_user.id)
    username = message.from_user.username or "unknown"
    
    try:
        # Сначала пробуем найти по Telegram ID
        accounts = db_bot.get_user_active_accounts(user_id)
        
        # Если не найдено, пробуем найти по username
        if not accounts and username != "unknown":
            accounts = db_bot.get_user_active_accounts(username)
        
        # Отладочная информация
        logger.info(f"User {user_id} (@{username}) requested Steam Guard code, found {len(accounts)} accounts")
        
        # Проверяем все аккаунты в базе для отладки
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT ID, account_name, owner, rental_start FROM accounts WHERE owner IS NOT NULL")
        all_accounts = cursor.fetchall()
        conn.close()
        
        logger.info(f"All accounts with owners: {all_accounts}")
        logger.info(f"Looking for user_id: {user_id}, username: {username}")
        
        if not accounts:
            # Проверяем, есть ли аккаунты с этим пользователем
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT ID, account_name, owner FROM accounts WHERE owner = ? OR owner = ?", (user_id, username))
            user_accounts = cursor.fetchall()
            conn.close()
            
            logger.info(f"Direct query for user {user_id} or {username}: {user_accounts}")
            
            bot.send_message(
                message.chat.id,
                f"🔑 **Steam Guard код**\n\n"
                f"У вас нет активных арендованных аккаунтов.\n\n"
                f"🔍 **Отладочная информация:**\n"
                f"• Ваш Telegram ID: `{user_id}`\n"
                f"• Ваш username: `@{username}`\n"
                f"• Найдено аккаунтов: {len(user_accounts)}\n"
                f"• Всего аккаунтов с владельцами: {len(all_accounts)}\n\n"
                f"💡 **Для получения аккаунта:**\n"
                f"1. Перейдите на FunPay\n"
                f"2. Совершите покупку\n"
                f"3. Используйте команду `/code` для получения Steam Guard кода\n\n"
                f"⚠️ **Важно:** Убедитесь, что ваш username в Telegram совпадает с именем на FunPay!",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            return
        
        # Если у пользователя несколько аккаунтов, показываем меню выбора
        if len(accounts) > 1:
            keyboard = InlineKeyboardMarkup()
            for account in accounts:
                keyboard.add(InlineKeyboardButton(
                    f"🔑 {account['account_name']}", 
                    callback_data=f"get_code_{account['id']}"
                ))
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
            
            bot.send_message(
                message.chat.id,
                "🔑 **Выберите аккаунт для получения кода:**",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            return
        
        # Если аккаунт один, сразу генерируем код
        account = accounts[0]
        account_id = account['id']
        account_name = account['account_name']
        
        # Получаем путь к .maFile
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT path_to_maFile FROM accounts WHERE ID = ?", (account_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result[0]:
            bot.send_message(
                message.chat.id,
                f"❌ **Ошибка получения кода**\n\n"
                f"Для аккаунта {account_name} не найден .maFile.\n"
                f"Обратитесь к администратору.",
                parse_mode="Markdown"
            )
            return
        
        mafile_path = result[0]
        
        # Генерируем Steam Guard код
        from steamHandler.SteamGuard import get_steam_guard_code
        
        guard_code = get_steam_guard_code(mafile_path)
        
        if guard_code:
            # Обновляем счетчик доступа
            db_bot.increment_access_count(account_id, user_id)
            
            message_text = (
                f"🔑 **Steam Guard код**\n\n"
                f"**Аккаунт:** {account_name}\n"
                f"**Код:** `{guard_code}`\n\n"
                f"⏰ Код действителен 30 секунд\n"
                f"🔄 Для получения нового кода отправьте /code\n\n"
                f"💡 **Полезные команды:**\n"
                f"/accounts - мои аккаунты\n"
                f"/extend - продлить аренду"
            )
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔄 Новый код", callback_data="get_guard_code"))
            keyboard.add(InlineKeyboardButton("📋 Мои аккаунты", callback_data="show_accounts"))
            keyboard.add(InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main"))
            
            bot.send_message(
                message.chat.id,
                message_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
            logger.info(f"Steam Guard code sent to user {user_id} for account {account_name}")
            
        else:
            bot.send_message(
                message.chat.id,
                f"❌ **Ошибка генерации кода**\n\n"
                f"Не удалось сгенерировать Steam Guard код для {account_name}.\n"
                f"Возможные причины:\n"
                f"• Неверный .maFile\n"
                f"• Проблемы с системным временем\n"
                f"• Поврежденный файл\n\n"
                f"Обратитесь к администратору.",
                parse_mode="Markdown"
            )
            
            logger.error(f"Failed to generate Steam Guard code for user {user_id}, account {account_name}")
        
    except Exception as e:
        logger.error(f"Error in code command: {str(e)}")
        bot.send_message(
            message.chat.id,
            f"❌ **Ошибка получения кода**\n\n{str(e)}",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=["start"])
def start(message):
    # Обновляем активность пользователя
    update_user_activity(message.from_user.id)
    
    if not is_user_authorized(message.from_user.id):
        set_user_state(message.from_user.id, "waiting_for_secret_phrase", {})
        bot.send_message(
            message.chat.id,
            "🔐 **Добро пожаловать в Steam Rental by Lini!**\n\n"
            "Для доступа к системе введите секретную фразу:",
            parse_mode="Markdown"
        )
        return

    # Получаем статистику для приветствия
    try:
        stats = db_bot.get_rental_statistics()
        welcome_stats = ""
        if stats:
            welcome_stats = (
                f"\n📊 **Статистика системы:**\n"
                f"• Активных аренд: `{stats['active_rentals']}`\n"
                f"• Свободных аккаунтов: `{stats['available_accounts']}`\n"
                f"• Загруженность: `{(stats['active_rentals'] / stats['total_accounts'] * 100):.1f}%`"
            )
    except:
        welcome_stats = ""

    welcome_message = (
        "🎮 **Добро пожаловать в Steam Rental by Lini!**\n\n"
        "🚀 **Система автоматической аренды Steam аккаунтов**\n\n"
        "✨ **Возможности:**\n"
        "• Автоматическая обработка заказов с FunPay\n"
        "• Умная система продления аренды\n"
        "• Автоматическая смена паролей\n"
        "• Telegram бот для управления\n"
        "• Статистика и аналитика\n"
        "• 🏪 **Управление лотами FunPay**\n"
        "• 📈 **Расширенная статистика профиля**\n\n"
        "🔐 **Система продления:**\n"
        "• Автоматическое продление на 1 час при отзыве\n"
        "• Ручное продление через бот\n"
        "• Уведомления об истечении срока\n\n"
        "Выберите нужную функцию:" + welcome_stats
    )

    bot.send_message(
        message.chat.id,
        welcome_message,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"] == "waiting_for_secret_phrase"
)
def process_secret_phrase(message):
    if message.text == SECRET_PHRASE:
        # Авторизуем пользователя и сохраняем в базу данных
        success = authorize_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            permissions='user'
        )
        
        if success:
            clear_user_state(message.from_user.id)
            all_accounts = len(db_bot.get_all_accounts())
            owned_accounts = all_accounts - len(db_bot.get_unowned_accounts())
            
            # Получаем информацию о пользователе для приветствия
            user_info = get_user_info(message.from_user.id)
            welcome_name = user_info.get('first_name', 'Пользователь') if user_info else 'Пользователь'
            
            bot.send_message(
                message.chat.id,
                f"✅ **Добро пожаловать, {welcome_name}!**\n\n"
                f"🎉 Вы успешно авторизованы в системе!\n"
                f"📊 Статистика на данный момент: {owned_accounts}/{all_accounts} аккаунтов\n\n"
                f"💡 **Ваша информация сохранена** - при следующем запуске бота вам не нужно будет вводить секретную фразу!",
                reply_markup=get_main_keyboard(),
                parse_mode="Markdown"
            )
            
            # Логируем успешную авторизацию
            logger.info(f"User {message.from_user.id} ({message.from_user.username or 'Unknown'}) successfully authorized")
        else:
            bot.send_message(message.chat.id, "❌ Ошибка при сохранении авторизации. Попробуйте снова.")
    else:
        bot.send_message(message.chat.id, "❌ Неверная фраза. Попробуйте снова.")

@bot.callback_query_handler(func=lambda call: call.data == "add_account")
def process_add_account(call):
    set_user_state(call.from_user.id, "waiting_for_lot_count", {})
    bot.send_message(call.message.chat.id, "Сколько лотов вы хотите добавить?")
    bot.answer_callback_query(call.id)

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_lot_count"
)
def process_lot_count(message):
    if not message.text.isdigit() or int(message.text) <= 0:
        bot.send_message(message.chat.id, "Пожалуйста, введите положительное число.")
        return

    lot_count = int(message.text)
    set_user_state(
        message.from_user.id,
        "waiting_for_lot_names",
        {"lot_count": lot_count, "current_lot": 0, "lot_names": []},
    )
    bot.send_message(message.chat.id, "Введите название для лота 1.")

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_lot_names"
)
def process_lot_names(message):
    state_data = get_user_state(message.from_user.id)["data"]
    state_data["lot_names"].append(message.text)
    state_data["current_lot"] += 1

    if state_data["current_lot"] < state_data["lot_count"]:
        set_user_state(message.from_user.id, "waiting_for_lot_names", state_data)
        bot.send_message(
            message.chat.id,
            f"Введите название для лота {state_data['current_lot'] + 1}.",
        )
    else:
        set_user_state(
            message.from_user.id,
            "waiting_for_count",
            {"lot_names": state_data["lot_names"]},
        )
        bot.send_message(
            message.chat.id, "Сколько аккаунтов вы хотите добавить для каждого лота?"
        )

@bot.callback_query_handler(func=lambda call: call.data == "delete_account")
def process_delete_account(call):
    set_user_state(call.from_user.id, "waiting_for_account_id", {})
    bot.send_message(
        call.message.chat.id, "Введите ID аккаунта, который вы хотите удалить."
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "change_password")
def process_change_password(call):
    set_user_state(call.from_user.id, "waiting_for_change_password_id", {})
    bot.send_message(
        call.message.chat.id,
        "Введите ID аккаунта, для которого вы хотите сменить пароль.",
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "stop_rent")
def process_stop_rent(call):
    set_user_state(call.from_user.id, "waiting_for_stop_rent_id", {})
    bot.send_message(
        call.message.chat.id,
        "Введите ID аккаунта, аренду которого вы хотите остановить.",
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "manual_rent")
def manual_rent_callback(call):
    set_user_state(call.from_user.id, "waiting_for_manual_rent_id", {})
    bot.send_message(
        call.message.chat.id, "Введите ID аккаунта, который вы хотите арендовать."
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "extend_rental")
def extend_rental_callback(call):
    set_user_state(call.from_user.id, "waiting_for_extend_rental_id", {})
    bot.send_message(
        call.message.chat.id, "Введите ID аккаунта, аренду которого вы хотите продлить."
    )
    bot.answer_callback_query(call.id)

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_owner_name"
)
def process_owner_name(message):
    owner_name = message.text
    state_data = {"owner_name": owner_name}
    set_user_state(message.from_user.id, "waiting_for_hours_to_add", state_data)
    bot.send_message(
        message.chat.id,
        f"Введите количество часов, которые вы хотите добавить для {owner_name}.",
    )

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_hours_to_add"
)
def process_hours_to_add(message):
    if not message.text.isdigit() or int(message.text) <= 0:
        bot.send_message(
            message.chat.id, "Пожалуйста, введите положительное число часов."
        )
        return

    hours_to_add = int(message.text)
    state_data = get_user_state(message.from_user.id)["data"]
    owner_name = state_data["owner_name"]

    try:
        if db_bot.add_time_to_owner_accounts(
            owner_name, -hours_to_add
        ):
            bot.send_message(
                message.chat.id,
                f"Успешно добавлено {hours_to_add} часов для всех аккаунтов владельца '{owner_name}'.",
            )

            send_message_by_owner(
                owner=owner_name,
                message=(
                    f"Вам добавлено {hours_to_add} часов аренды.\n\n"
                    f"Если вы хотите продлить аренду, напишите администратору."
                ),
            )
        else:
            bot.send_message(
                message.chat.id,
                f"Не удалось найти аккаунты для владельца '{owner_name}' или добавить часы.",
            )
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при добавлении часов: {str(e)}")
    finally:
        clear_user_state(message.from_user.id)

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_count"
)
def process_count(message):
    if not message.text.isdigit() or int(message.text) <= 0:
        bot.send_message(message.chat.id, "Пожалуйста, введите положительное число.")
        return

    count = int(message.text)
    state_data = get_user_state(message.from_user.id)["data"]
    state_data.update({"total_count": count, "current_lot": 0, "lot_durations": {}})
    set_user_state(message.from_user.id, "waiting_for_lot_duration", state_data)
    bot.send_message(
        message.chat.id,
        f"На сколько часов будет сдаваться лот \n```{state_data['lot_names'][0]}```",
        parse_mode="Markdown",
    )

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_lot_duration"
)
def process_lot_duration(message):
    if not message.text.isdigit() or int(message.text) <= 0:
        bot.send_message(
            message.chat.id, "Пожалуйста, введите положительное число часов."
        )
        return

    state_data = get_user_state(message.from_user.id)["data"]
    current_lot = state_data["current_lot"]
    lot_name = state_data["lot_names"][current_lot]
    state_data["lot_durations"][lot_name] = int(message.text)

    if current_lot + 1 < len(state_data["lot_names"]):
        state_data["current_lot"] += 1
        set_user_state(message.from_user.id, "waiting_for_lot_duration", state_data)
        bot.send_message(
            message.chat.id,
            f"На сколько часов будет сдаваться лот \n```{state_data['lot_names'][current_lot + 1]}```",
            parse_mode="Markdown",
        )
    else:
        state_data["current_count"] = 0
        set_user_state(message.from_user.id, "waiting_for_mafile", state_data)
        bot.send_message(
            message.chat.id, "Пожалуйста, загрузите .maFile для аккаунта 1."
        )

@bot.message_handler(content_types=["document"])
def process_mafile(message):
    state = get_user_state(message.from_user.id)
    if state["state"] != "waiting_for_mafile":
        return

    if not message.document.file_name.endswith(".maFile"):
        bot.send_message(
            message.chat.id, "Пожалуйста, загрузите валидный .maFile файл."
        )
        return

    state_data = state["data"]
    current_count = state_data["current_count"]

    try:
        file_name = message.document.file_name
        file_path = os.path.join(SAVE_DIR, file_name)

        if os.path.exists(file_path):
            os.remove(file_path)

        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(file_path, "wb") as f:
            f.write(downloaded_file)

        relative_path = os.path.relpath(file_path, start=os.getcwd())
        state_data["mafile_path"] = relative_path

        set_user_state(message.from_user.id, "waiting_for_login", state_data)
        bot.send_message(
            message.chat.id, "Ваш .maFile сохранен. Теперь отправьте логин."
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при сохранении файла: {str(e)}")

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_login"
)
def process_login(message):
    state_data = get_user_state(message.from_user.id)["data"]
    state_data["login"] = message.text
    set_user_state(message.from_user.id, "waiting_for_password", state_data)
    bot.send_message(message.chat.id, "Логин сохранен. Теперь отправьте пароль.")

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_password"
)
def process_password(message):
    state_data = get_user_state(message.from_user.id)["data"]
    current_count = state_data.get("current_count", 0)

    for lot_name in state_data["lot_names"]:
        db_bot.add_account(
            account_name=lot_name,
            path_to_maFile=state_data["mafile_path"],
            login=state_data["login"],
            password=message.text,
            duration=state_data["lot_durations"][lot_name],
        )

    current_count += 1
    if current_count < state_data["total_count"]:
        state_data["current_count"] = current_count
        set_user_state(message.from_user.id, "waiting_for_mafile", state_data)
        bot.send_message(
            message.chat.id,
            f"Пожалуйста, загрузите .maFile для аккаунта {current_count + 1}.",
        )
    else:
        clear_user_state(message.from_user.id)
        bot.send_message(
            message.chat.id,
            f"Все {state_data['total_count']} аккаунтов успешно добавлены! Настройка завершена.",
        )

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_account_id"
)
def delete_account_by_id_handler(message):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "Пожалуйста, введите валидный числовой ID.")
        return

    account_id = int(message.text)
    if db_bot.delete_account_by_id(account_id):
        bot.send_message(message.chat.id, f"Аккаунт с ID {account_id} успешно удален.")
    else:
        bot.send_message(
            message.chat.id, f"Не удалось найти или удалить аккаунт с ID {account_id}."
        )

    clear_user_state(message.from_user.id)

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_change_password_id"
)
def change_password_by_id_handler(message):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "Пожалуйста, введите валидный числовой ID.")
        return

    account_id = int(message.text)
    bot.send_message(
        message.chat.id, f"🔐 Изменение пароля для аккаунта с ID {account_id}..."
    )
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT path_to_maFile, password
            FROM accounts
            WHERE ID = ?
            """,
            (account_id,),
        )
        account = cursor.fetchone()

        if not account:
            bot.send_message(message.chat.id, f"Аккаунт с ID {account_id} не найден.")
            return

        cursor.execute(
            """
            SELECT login, path_to_maFile, password
            FROM accounts
            WHERE ID = ?
            """,
            (account_id,),
        )
        account = cursor.fetchone()

        if account is None:
            bot.send_message(message.chat.id, f"Аккаунт с ID {account_id} не найден.")
        else:
            login, path_to_maFile, current_password = account
            new_password = asyncio.run(
                changeSteamPassword(path_to_maFile, current_password)
            )

            cursor.execute(
                """
                UPDATE accounts
                SET password = ?
                WHERE login = ?
                """,
                (new_password, login),
            )
            conn.commit()

            bot.send_message(
                message.chat.id,
                f"Пароль для всех аккаунтов с логином '{login}' успешно изменен на {new_password}.",
            )
    finally:
        conn.close()
        clear_user_state(message.from_user.id)

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_stop_rent_id"
)
def stop_rent_by_id_handler(message):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "Пожалуйста, введите валидный числовой ID.")
        return

    account_id = int(message.text)
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT login
            FROM accounts
            WHERE ID = ?
            """,
            (account_id,),
        )
        result = cursor.fetchone()

        if not result:
            bot.send_message(
                message.chat.id,
                f"Аккаунт с ID {account_id} не найден.",
            )
            return

        login = result[0]

        cursor.execute(
            """
            UPDATE accounts
            SET owner = NULL, rental_start = NULL
            WHERE login = ?
            """,
            (login,),
        )

        if cursor.rowcount > 0:
            conn.commit()
            bot.send_message(
                message.chat.id,
                f"Аренда всех аккаунтов с логином '{login}' успешно остановлена.",
            )
        else:
            bot.send_message(
                message.chat.id,
                f"Аккаунты с логином '{login}' не найдены или аренда уже остановлена.",
            )
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при остановке аренды: {str(e)}")
    finally:
        conn.close()
        clear_user_state(message.from_user.id)

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_manual_rent_id"
)
def process_manual_rent_id(message):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "Пожалуйста, введите валидный числовой ID.")
        return

    account_id = int(message.text)
    state_data = {"account_id": account_id}
    set_user_state(message.from_user.id, "waiting_for_manual_rent_owner", state_data)
    bot.send_message(message.chat.id, "Введите никнейм владельца для аренды.")

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_manual_rent_owner"
)
def process_manual_rent_owner(message):
    state_data = get_user_state(message.from_user.id)["data"]
    account_id = state_data["account_id"]
    owner_nickname = message.text

    try:
        if db_bot.set_account_owner(account_id, owner_nickname):
            account = db_bot.get_account_by_id(account_id)
            bot.send_message(
                message.chat.id,
                f"Аккаунт с ID {account_id} успешно передан в аренду пользователю '{owner_nickname}'.",
            )
            send_message_by_owner(
                owner=owner_nickname,
                message=(
                    f"Ваш аккаунт:\n"
                    f"📝 Уникальный ID: {account['id']}\n"
                    f"🔑 Название: `{account['account_name']}`\n"
                    f"⏱ Срок аренды: {account['rental_duration']} часа \n\n"
                    f"Логин: {account['login']}\n"
                    f"Пароль: {account['password']}\n\n"
                    f"Что-бы запросить код подтверждения, отправьте /code\n"
                    f"Чтобы задать вопрос, отправьте /question\n\n"
                    f"‼️За отзыв - вы получите дополнительные {HOURS_FOR_REVIEW} час/часа аренды.\n"
                    f"‼️ВАЖНО! Отзыв надо оставить до окончания вашей аренды.‼️\n\n"
                    f"------------------------------------------------------------------------------"
                ),
            )
        else:
            bot.send_message(
                message.chat.id,
                f"Не удалось найти аккаунт с ID {account_id} или установить владельца.",
            )
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при установке владельца: {str(e)}")
    finally:
        clear_user_state(message.from_user.id)

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_extend_rental_id"
)
def process_extend_rental_id(message):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "Пожалуйста, введите валидный числовой ID.")
        return

    account_id = int(message.text)
    state_data = {"account_id": account_id}
    set_user_state(message.from_user.id, "waiting_for_extend_rental_duration", state_data)
    bot.send_message(message.chat.id, "На сколько часов вы хотите продлить аренду?")

@bot.message_handler(
    func=lambda message: get_user_state(message.from_user.id)["state"]
    == "waiting_for_extend_rental_duration"
)
def process_extend_rental_duration(message):
    if not message.text.isdigit() or int(message.text) <= 0:
        bot.send_message(message.chat.id, "Пожалуйста, введите положительное число часов.")
        return

    state_data = get_user_state(message.from_user.id)["data"]
    account_id = state_data["account_id"]
    duration_to_add = int(message.text)

    try:
        if db_bot.extend_rental_duration(account_id, duration_to_add):
            account = db_bot.get_account_by_id(account_id)
            bot.send_message(
                message.chat.id,
                f"‼️Аренда аккаунта с ID {account_id} успешно продлена на {duration_to_add} часов.\n"
                f"‼️Новый срок аренды: {account['rental_duration']} часов.\n"
                f"‼️Срок аренды: {account['rental_start']} - {account['rental_duration']} часов."
            )
            send_message_by_owner(
                owner=account["owner"],
                message=(
                    f"‼️Ваш аккаунт с ID {account_id} был продлен на {duration_to_add} часов.\n"
                    f"Новый срок аренды: {account['rental_duration']} часов.\n"
                    f"Срок аренды: {account['rental_start']} - {account['rental_duration']} часов."
                )
            )
        else:
            bot.send_message(
                message.chat.id,
                f"Не удалось найти аккаунт с ID {account_id} или продлить аренду.",
            )
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при продлении аренды: {str(e)}")
    finally:
        clear_user_state(message.from_user.id)

def send_message_to_admin(message):
    bot.send_message(ADMIN_ID, message)

@bot.callback_query_handler(func=lambda call: call.data == "system_settings")
def system_settings_callback(call):
    if not is_user_authorized(call.from_user.id):
        bot.answer_callback_query(call.id, "У вас нет доступа к этой функции")
        return
    
    bot.edit_message_text(
        "⚙️ **Настройки системы:**\n\n"
        "Выберите параметр для настройки:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
        reply_markup=get_system_settings_keyboard()
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "notification_settings")
def notification_settings_callback(call):
    if not is_user_authorized(call.from_user.id):
        bot.answer_callback_query(call.id, "У вас нет доступа к этой функции")
        return
    
    bot.edit_message_text(
        "📱 **Настройки уведомлений:**\n\n"
        "Выберите тип уведомлений для настройки:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
        reply_markup=get_notification_settings_keyboard()
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "proxy_status")
def proxy_status_callback(call):
    if not is_user_authorized(call.from_user.id):
        bot.answer_callback_query(call.id, "У вас нет доступа к этой функции")
        return
    
    proxy_status = "✅ **Активен**" if PROXY_URL else "❌ **Не настроен**"
    proxy_info = f"🔌 **Прокси:** {proxy_status}\n"
    
    if PROXY_URL:
        proxy_info += f"🌐 **URL:** `{PROXY_URL}`\n"
        if PROXY_LOGIN:
            proxy_info += f"👤 **Логин:** `{PROXY_LOGIN}`\n"
    
    bot.edit_message_text(
        f"📊 **Статус прокси:**\n\n{proxy_info}",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
        reply_markup=get_proxy_keyboard()
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "database_settings")
def database_settings_callback(call):
    if not is_user_authorized(call.from_user.id):
        bot.answer_callback_query(call.id, "У вас нет доступа к этой функции")
        return
    
    try:
        stats = db_bot.get_rental_statistics()
        db_info = (
            "🗄️ **Информация о базе данных:**\n\n"
            f"📊 **Размер:** `{stats.get('total_accounts', 0)}` записей\n"
            f"✅ **Статус:** Подключена\n"
            f"🔄 **Последнее обновление:** Только что\n\n"
            "💡 **Доступные операции:**\n"
            "• Резервное копирование\n"
            "• Очистка старых записей\n"
            "• Оптимизация"
        )
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("💾 Резервная копия", callback_data="db_backup"))
        keyboard.add(InlineKeyboardButton("🧹 Очистка", callback_data="db_cleanup"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="system_settings"))
        
        bot.edit_message_text(
            db_info,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "auto_refresh_toggle")
def auto_refresh_toggle_callback(call):
    if not is_user_authorized(call.from_user.id):
        bot.answer_callback_query(call.id, "У вас нет доступа к этой функции")
        return
    
    bot.answer_callback_query(call.id, "Функция в разработке")

@bot.callback_query_handler(func=lambda call: call.data == "timeout_settings")
def timeout_settings_callback(call):
    if not is_user_authorized(call.from_user.id):
        bot.answer_callback_query(call.id, "У вас нет доступа к этой функции")
        return
    
    bot.answer_callback_query(call.id, "Функция в разработке")

# --- УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ---

def get_users_keyboard():
    """Клавиатура для управления пользователями."""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📋 Список пользователей", callback_data="users_list"),
        InlineKeyboardButton("➕ Добавить пользователя", callback_data="users_add"),
    )
    keyboard.add(
        InlineKeyboardButton("🔍 Найти пользователя", callback_data="users_search"),
        InlineKeyboardButton("📊 Статистика пользователей", callback_data="users_stats"),
    )
    keyboard.add(
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"),
    )
    return keyboard

@bot.callback_query_handler(func=lambda call: call.data == "users_menu")
def users_menu_callback(call):
    """Меню управления пользователями."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    try:
        bot.edit_message_text(
            "👥 **Управление пользователями**\n\n"
            "Выберите действие:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_users_keyboard()
        )
    except Exception as edit_error:
        if "message is not modified" not in str(edit_error):
            bot.send_message(
                call.message.chat.id,
                "👥 **Управление пользователями**\n\n"
                "Выберите действие:",
                parse_mode="Markdown",
                reply_markup=get_users_keyboard()
            )
    
    bot.answer_callback_query(call.id)

def split_message(text, max_length=4000):
    """Разбивает длинное сообщение на части"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    lines = text.split('\n')
    
    for line in lines:
        if len(current_part + line + '\n') <= max_length:
            current_part += line + '\n'
        else:
            if current_part:
                parts.append(current_part.strip())
            current_part = line + '\n'
    
    if current_part:
        parts.append(current_part.strip())
    
    return parts

@bot.callback_query_handler(func=lambda call: call.data == "users_list")
def users_list_callback(call):
    """Список всех пользователей."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    try:
        users = db_bot.get_all_users_info()
        
        if not users:
            message = "📋 **Список пользователей пуст**"
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔄 Обновить", callback_data="users_list"))
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="users_menu"))
            
            try:
                bot.edit_message_text(
                    message,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as edit_error:
                if "message is not modified" not in str(edit_error):
                    bot.send_message(call.message.chat.id, message, parse_mode="Markdown", reply_markup=keyboard)
        else:
            # Создаем сообщение
            message = "👥 **Список пользователей:**\n\n"
            for i, user in enumerate(users, 1):
                status = "✅ Активен" if user['is_active'] else "❌ Заблокирован"
                username = f"@{user['username']}" if user['username'] else "Без username"
                name = f"{user['first_name']} {user['last_name']}".strip() or "Без имени"
                
                user_info = (
                    f"**{i}.** {name}\n"
                    f"   🆔 ID: `{user['user_id']}`\n"
                    f"   👤 Username: {username}\n"
                    f"   📅 Регистрация: {user['authorized_at']}\n"
                    f"   🕐 Последняя активность: {user['last_activity']}\n"
                    f"   🔐 Права: {user['permissions']}\n"
                    f"   📊 Статус: {status}\n\n"
                )
                
                # Проверяем, не превысит ли добавление лимит
                if len(message + user_info) > 4000:
                    # Отправляем текущую часть
                    keyboard = InlineKeyboardMarkup()
                    keyboard.add(InlineKeyboardButton("🔄 Обновить", callback_data="users_list"))
                    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="users_menu"))
                    
                    try:
                        bot.edit_message_text(
                            message,
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            parse_mode="Markdown",
                            reply_markup=keyboard
                        )
                    except Exception as edit_error:
                        if "message is not modified" not in str(edit_error):
                            bot.send_message(call.message.chat.id, message, parse_mode="Markdown", reply_markup=keyboard)
                    
                    # Начинаем новое сообщение
                    message = f"👥 **Список пользователей (продолжение):**\n\n{user_info}"
                else:
                    message += user_info
            
            # Отправляем последнюю часть
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔄 Обновить", callback_data="users_list"))
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="users_menu"))
            
            try:
                bot.edit_message_text(
                    message,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as edit_error:
                if "message is not modified" not in str(edit_error):
                    bot.send_message(call.message.chat.id, message, parse_mode="Markdown", reply_markup=keyboard)
                    
    except Exception as e:
        logger.error(f"Error in users_list_callback: {str(e)}")
        try:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:100]}...")
        except:
            pass
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "users_add")
def users_add_callback(call):
    """Добавление пользователя."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    set_user_state(call.from_user.id, "waiting_for_user_id")
    
    try:
        bot.edit_message_text(
            "➕ **Добавление пользователя**\n\n"
            "Отправьте Telegram ID пользователя для добавления:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_users_keyboard()
        )
    except Exception as edit_error:
        if "message is not modified" not in str(edit_error):
            bot.send_message(
                call.message.chat.id,
                "➕ **Добавление пользователя**\n\n"
                "Отправьте Telegram ID пользователя для добавления:",
                parse_mode="Markdown",
                reply_markup=get_users_keyboard()
            )
    
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: get_user_state(message.from_user.id)["state"] == "waiting_for_user_id")
def process_user_id(message):
    """Обработка ID пользователя для добавления."""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Доступ запрещён.")
        return
    
    try:
        user_id = int(message.text.strip())
        
        # Проверяем, не добавлен ли уже пользователь
        if db_bot.is_user_authorized(user_id):
            bot.send_message(message.chat.id, f"❌ Пользователь с ID {user_id} уже авторизован.")
        else:
            # Добавляем пользователя
            success = db_bot.add_authorized_user(
                user_id=user_id,
                username="Added by admin",
                first_name="Admin added",
                last_name="user",
                permissions='user'
            )
            
            if success:
                bot.send_message(
                    message.chat.id,
                    f"✅ Пользователь с ID {user_id} успешно добавлен!\n\n"
                    f"💡 Пользователь может теперь использовать бота без ввода секретной фразы."
                )
                logger.info(f"Admin {message.from_user.id} added user {user_id}")
            else:
                bot.send_message(message.chat.id, f"❌ Ошибка при добавлении пользователя {user_id}")
        
        clear_user_state(message.from_user.id)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат ID. Введите числовой ID пользователя.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")
        clear_user_state(message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "users_stats")
def users_stats_callback(call):
    """Статистика пользователей."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    try:
        users = db_bot.get_all_users_info()
        active_users = [u for u in users if u['is_active']]
        inactive_users = [u for u in users if not u['is_active']]
        
        # Статистика по правам
        permissions_stats = {}
        for user in users:
            perm = user['permissions']
            permissions_stats[perm] = permissions_stats.get(perm, 0) + 1
        
        perm_text = "\n".join([f"   • {perm}: {count}" for perm, count in permissions_stats.items()])
        
        message = (
            f"📊 **Статистика пользователей:**\n\n"
            f"👥 **Всего пользователей:** {len(users)}\n"
            f"✅ **Активных:** {len(active_users)}\n"
            f"❌ **Заблокированных:** {len(inactive_users)}\n\n"
            f"🔐 **По правам доступа:**\n{perm_text}\n\n"
            f"📈 **Активность:** {len(active_users)/len(users)*100:.1f}% пользователей активны"
        )
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Обновить", callback_data="users_stats"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="users_menu"))
        
        bot.edit_message_text(
            message,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")
    
    bot.answer_callback_query(call.id)

@bot.message_handler(commands=["users"])
def users_command(message):
    """Команда управления пользователями."""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещён. Только для администратора.")
        return
    
    bot.send_message(
        message.chat.id,
        "👥 **Управление пользователями**\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_users_keyboard()
    )

@bot.message_handler(commands=["funpay"])
def funpay_command(message):
    """Команда управления лотами FunPay."""
    if not funpay_integration:
        bot.reply_to(message, "❌ FunPay интеграция недоступна. Проверьте настройки.")
        return
    
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав для выполнения этой команды.")
        return
    
    funpay_integration.show_lots_menu(message.chat.id)

@bot.message_handler(commands=["profile"])
def profile_command(message):
    """Команда статистики профиля FunPay."""
    if not funpay_integration:
        bot.reply_to(message, "❌ FunPay интеграция недоступна. Проверьте настройки.")
        return
    
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        # Получаем расширенную статистику профиля
        profile_text = funpay_integration.get_advanced_profile_stats()
        keyboard = funpay_integration.get_profile_stats_keyboard()
        
        bot.reply_to(message, profile_text, reply_markup=keyboard, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка получения статистики профиля: {e}")
        bot.reply_to(message, f"❌ Ошибка получения статистики профиля: {str(e)}")

@bot.message_handler(commands=["restart"])
def restart_command(message):
    """Команда перезапуска бота."""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        logger.info(f"Команда перезапуска получена от пользователя {message.from_user.id}")
        
        # Отправляем уведомление о начале перезапуска
        restart_message = bot.reply_to(
            message, 
            "🔄 <b>Перезапуск бота...</b>\n\n"
            "⏳ Пожалуйста, подождите несколько секунд\n"
            "✅ Бот будет перезапущен автоматически",
            parse_mode='HTML'
        )
        
        # Логируем перезапуск
        logger.info("Инициирован перезапуск бота")
        
        # Сохраняем состояние перед перезапуском
        _save_bot_state()
        
        # Запускаем перезапуск в отдельном потоке
        import threading
        restart_thread = threading.Thread(target=_restart_bot_process, daemon=True)
        restart_thread.start()
        
    except Exception as e:
        logger.error(f"Ошибка при перезапуске бота: {e}")
        bot.reply_to(message, f"❌ Ошибка при перезапуске: {str(e)}")

@bot.message_handler(commands=["restart_info"])
def restart_info_command(message):
    """Команда информации о перезапусках бота."""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        import json
        import os
        
        state_file = os.path.join("bot_state", "restart_state.json")
        
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            last_restart = data.get("last_restart", "Неизвестно")
            restart_count = data.get("restart_count", 0)
            
            # Парсим время последнего перезапуска
            try:
                from datetime import datetime
                last_restart_dt = datetime.fromisoformat(last_restart)
                last_restart_formatted = last_restart_dt.strftime("%d.%m.%Y %H:%M:%S")
            except:
                last_restart_formatted = last_restart
            
            info_text = f"""📊 <b>Информация о перезапусках бота</b>

🔄 <b>Количество перезапусков:</b> <code>{restart_count}</code>
⏰ <b>Последний перезапуск:</b> <code>{last_restart_formatted}</code>
🤖 <b>Текущий статус:</b> <code>Активен</code>
📅 <b>Время запуска:</b> <code>{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</code>

💡 <b>Команды:</b>
• <code>/restart</code> - Перезапустить бота
• <code>/restart_info</code> - Эта информация"""
            
        else:
            info_text = f"""📊 <b>Информация о перезапусках бота</b>

🔄 <b>Количество перезапусков:</b> <code>0</code>
⏰ <b>Последний перезапуск:</b> <code>Не было</code>
🤖 <b>Текущий статус:</b> <code>Активен</code>
📅 <b>Время запуска:</b> <code>{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</code>

💡 <b>Команды:</b>
• <code>/restart</code> - Перезапустить бота
• <code>/restart_info</code> - Эта информация"""
        
        bot.reply_to(message, info_text, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о перезапусках: {e}")
        bot.reply_to(message, f"❌ Ошибка получения информации: {str(e)}")


@bot.message_handler(commands=["customers"])
def show_customers(message):
    """Показать активность покупателей."""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещён. Только для администратора.")
        return

    try:
        # Получаем активность покупателей
        activity = db_bot.get_customer_activity()
        
        if not activity:
            bot.send_message(message.chat.id, "📋 Нет данных о покупателях.")
            return

        # Группируем по покупателям
        customers = {}
        for record in activity:
            username = record['customer_username']
            if username not in customers:
                customers[username] = []
            customers[username].append(record)

        response = "👥 **Активность покупателей:**\n\n"
        
        for username, records in list(customers.items())[:10]:  # Показываем только первых 10
            # Получаем статистику покупателя
            stats = db_bot.get_customer_stats(username)
            
            response += f"🛒 **Покупатель:** `{username}`\n"
            response += f"📊 **Покупок:** {stats.get('total_purchases', 0)}\n"
            response += f"⏱ **Часов аренды:** {stats.get('total_rental_hours', 0)}\n"
            response += f"🔑 **Обращений к данным:** {stats.get('total_accesses', 0)}\n"
            response += f"⭐ **Средний рейтинг:** {stats.get('avg_rating', 'Нет отзывов')}\n"
            response += f"🔄 **Продлений:** {stats.get('total_extensions', 0)} (+{stats.get('total_extension_hours', 0)}ч)\n\n"
            
            # Показываем последние активности
            recent_records = sorted(records, key=lambda x: x['updated_at'], reverse=True)[:3]
            for record in recent_records:
                status = "🟢 Активна" if record['is_active'] else "🔴 Завершена"
                response += f"  📝 **Аккаунт:** {record['account_name']} (ID: {record['account_id']}) - {status}\n"
                if record['feedback_rating']:
                    response += f"  ⭐ **Отзыв:** {record['feedback_rating']}/5 - {record['feedback_text'][:50]}...\n"
                response += f"  🔑 **Обращений:** {record['access_count']}/{record['max_access_count']}\n"
                response += f"  📅 **Обновлено:** {record['updated_at']}\n\n"
            
            response += "─" * 40 + "\n\n"

        if len(customers) > 10:
            response += f"... и еще {len(customers) - 10} покупателей\n\n"

        response += "💡 **Команды:**\n"
        response += "• `/customer <username>` - детальная информация о покупателе\n"
        response += "• `/customers_recent` - последние активности\n"

        # Разбиваем сообщение если оно слишком длинное
        if len(response) > 4000:
            parts = response.split("─" * 40)
            for i, part in enumerate(parts):
                if part.strip():
                    bot.send_message(message.chat.id, part.strip(), parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, response, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при получении данных покупателей: {str(e)}")


@bot.message_handler(commands=["customer"])
def show_customer_details(message):
    """Показать детальную информацию о покупателе."""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещён. Только для администратора.")
        return

    try:
        # Извлекаем username из команды
        command_parts = message.text.split()
        if len(command_parts) < 2:
            bot.send_message(message.chat.id, "❌ Использование: `/customer <username>`")
            return

        username = command_parts[1]
        
        # Получаем активность конкретного покупателя
        activity = db_bot.get_customer_activity(customer_username=username)
        
        if not activity:
            bot.send_message(message.chat.id, f"❌ Покупатель `{username}` не найден.")
            return

        # Получаем статистику
        stats = db_bot.get_customer_stats(username)
        
        response = f"🛒 **Детальная информация о покупателе:** `{username}`\n\n"
        
        response += f"📊 **Общая статистика:**\n"
        response += f"• Покупок: {stats.get('total_purchases', 0)}\n"
        response += f"• Часов аренды: {stats.get('total_rental_hours', 0)}\n"
        response += f"• Обращений к данным: {stats.get('total_accesses', 0)}\n"
        response += f"• Средний рейтинг: {stats.get('avg_rating', 'Нет отзывов')}\n"
        response += f"• Продлений: {stats.get('total_extensions', 0)} (+{stats.get('total_extension_hours', 0)}ч)\n\n"
        
        response += f"📝 **История активности:**\n\n"
        
        for i, record in enumerate(activity, 1):
            status = "🟢 Активна" if record['is_active'] else "🔴 Завершена"
            response += f"**{i}. Аккаунт:** {record['account_name']} (ID: {record['account_id']})\n"
            response += f"• Статус: {status}\n"
            response += f"• Покупка: {record['purchase_time']}\n"
            response += f"• Длительность: {record['rental_duration']} часов\n"
            response += f"• Обращений к данным: {record['access_count']}/{record['max_access_count']}\n"
            
            if record['last_access_time']:
                response += f"• Последний доступ: {record['last_access_time']}\n"
            
            if record['feedback_rating']:
                response += f"• Отзыв: {record['feedback_rating']}/5\n"
                response += f"• Текст отзыва: {record['feedback_text']}\n"
                response += f"• Время отзыва: {record['feedback_time']}\n"
            
            if record['rental_extended_count'] > 0:
                response += f"• Продлений: {record['rental_extended_count']} (+{record['total_extension_hours']}ч)\n"
            
            response += f"• Обновлено: {record['updated_at']}\n\n"

        # Разбиваем сообщение если оно слишком длинное
        if len(response) > 4000:
            parts = response.split("**История активности:**")
            bot.send_message(message.chat.id, parts[0], parse_mode="Markdown")
            if len(parts) > 1:
                bot.send_message(message.chat.id, "**История активности:**" + parts[1], parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, response, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при получении информации о покупателе: {str(e)}")


@bot.message_handler(commands=["customers_recent"])
def show_recent_customers(message):
    """Показать последние активности покупателей."""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещён. Только для администратора.")
        return

    try:
        # Получаем последние активности
        activity = db_bot.get_customer_activity()
        
        if not activity:
            bot.send_message(message.chat.id, "📋 Нет данных о покупателях.")
            return

        # Сортируем по времени обновления и берем последние 20
        recent_activity = sorted(activity, key=lambda x: x['updated_at'], reverse=True)[:20]

        response = "🕒 **Последние активности покупателей:**\n\n"
        
        for record in recent_activity:
            status = "🟢" if record['is_active'] else "🔴"
            response += f"{status} **{record['customer_username']}** - {record['account_name']}\n"
            response += f"  📅 {record['updated_at']}\n"
            response += f"  🔑 Обращений: {record['access_count']}/{record['max_access_count']}\n"
            
            if record['feedback_rating']:
                response += f"  ⭐ Отзыв: {record['feedback_rating']}/5\n"
            
            response += "\n"

        bot.send_message(message.chat.id, response, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при получении последних активностей: {str(e)}")

# --- УПРАВЛЕНИЕ АККАУНТАМИ ---

@bot.callback_query_handler(func=lambda call: call.data == "manage_accounts")
def manage_accounts_callback(call):
    """Меню управления аккаунтами."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    try:
        bot.edit_message_text(
            "🔧 **Управление аккаунтами**\n\n"
            "Выберите действие:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_manage_accounts_keyboard()
        )
    except Exception as edit_error:
        if "message is not modified" not in str(edit_error):
            bot.send_message(
                call.message.chat.id,
                "🔧 **Управление аккаунтами**\n\n"
                "Выберите действие:",
                parse_mode="Markdown",
                reply_markup=get_manage_accounts_keyboard()
            )
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "manage_list_all")
def manage_list_all_callback(call):
    """Список всех аккаунтов для управления."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    try:
        accounts = db_bot.get_all_accounts()
        
        if not accounts:
            message = "📋 **Список аккаунтов пуст**"
        else:
            message = "📋 **Все аккаунты в системе:**\n\n"
            for i, account in enumerate(accounts, 1):
                status = "🔴 В аренде" if account['owner'] else "🟢 Свободен"
                owner_info = f"Владелец: {account['owner']}" if account['owner'] else "Свободен"
                
                message += (
                    f"**{i}.** {account['account_name']}\n"
                    f"   🆔 ID: `{account['id']}`\n"
                    f"   👤 Логин: `{account['login']}`\n"
                    f"   ⏰ Продолжительность: {account['rental_duration']}ч\n"
                    f"   📊 Статус: {status}\n"
                    f"   👥 {owner_info}\n\n"
                )
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Обновить", callback_data="manage_list_all"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="manage_accounts"))
        
        try:
            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                bot.send_message(call.message.chat.id, message, parse_mode="Markdown", reply_markup=keyboard)
                
    except Exception as e:
        logger.error(f"Error in manage_list_all_callback: {str(e)}")
        try:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:100]}...")
        except:
            pass
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "manage_delete")
def manage_delete_callback(call):
    """Удаление аккаунта."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    set_user_state(call.from_user.id, "waiting_for_account_id_to_delete")
    
    try:
        bot.edit_message_text(
            "🗑 **Удаление аккаунта**\n\n"
            "⚠️ **ВНИМАНИЕ:** Это действие необратимо!\n"
            "Будет удален аккаунт и его .maFile файл.\n\n"
            "Отправьте ID аккаунта для удаления:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_manage_accounts_keyboard()
        )
    except Exception as edit_error:
        if "message is not modified" not in str(edit_error):
            bot.send_message(
                call.message.chat.id,
                "🗑 **Удаление аккаунта**\n\n"
                "⚠️ **ВНИМАНИЕ:** Это действие необратимо!\n"
                "Будет удален аккаунт и его .maFile файл.\n\n"
                "Отправьте ID аккаунта для удаления:",
                parse_mode="Markdown",
                reply_markup=get_manage_accounts_keyboard()
            )
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "manage_replace_mafile")
def manage_replace_mafile_callback(call):
    """Замена .maFile аккаунта."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    set_user_state(call.from_user.id, "waiting_for_account_id_to_replace_mafile")
    
    try:
        bot.edit_message_text(
            "📁 **Замена .maFile**\n\n"
            "Отправьте ID аккаунта для замены .maFile:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_manage_accounts_keyboard()
        )
    except Exception as edit_error:
        if "message is not modified" not in str(edit_error):
            bot.send_message(
                call.message.chat.id,
                "📁 **Замена .maFile**\n\n"
                "Отправьте ID аккаунта для замены .maFile:",
                parse_mode="Markdown",
                reply_markup=get_manage_accounts_keyboard()
            )
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "manage_validate_mafile")
def manage_validate_mafile_callback(call):
    """Проверка .maFile."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    set_user_state(call.from_user.id, "waiting_for_mafile_to_validate")
    
    try:
        bot.edit_message_text(
            "🔍 **Проверка .maFile**\n\n"
            "Отправьте .maFile для проверки:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_manage_accounts_keyboard()
        )
    except Exception as edit_error:
        if "message is not modified" not in str(edit_error):
            bot.send_message(
                call.message.chat.id,
                "🔍 **Проверка .maFile**\n\n"
                "Отправьте .maFile для проверки:",
                parse_mode="Markdown",
                reply_markup=get_manage_accounts_keyboard()
            )
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "manage_stats")
def manage_stats_callback(call):
    """Статистика аккаунтов."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    try:
        accounts = db_bot.get_all_accounts()
        owned_accounts = [acc for acc in accounts if acc['owner']]
        free_accounts = [acc for acc in accounts if not acc['owner']]
        
        # Статистика по продолжительности аренды
        duration_stats = {}
        for acc in accounts:
            duration = acc['rental_duration']
            duration_stats[duration] = duration_stats.get(duration, 0) + 1
        
        duration_text = "\n".join([f"   • {dur}ч: {count} аккаунтов" for dur, count in sorted(duration_stats.items())])
        
        message = (
            f"📊 **Статистика аккаунтов:**\n\n"
            f"📈 **Общая статистика:**\n"
            f"   • Всего аккаунтов: {len(accounts)}\n"
            f"   • В аренде: {len(owned_accounts)}\n"
            f"   • Свободных: {len(free_accounts)}\n"
            f"   • Загруженность: {len(owned_accounts)/len(accounts)*100:.1f}%\n\n"
            f"⏰ **По продолжительности аренды:**\n{duration_text}\n\n"
            f"📁 **Файлы .maFile:**\n"
            f"   • Всего файлов: {len(accounts)}\n"
            f"   • Требуют проверки: {len([acc for acc in accounts if not acc.get('path_to_maFile')])}"
        )
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Обновить", callback_data="manage_stats"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="manage_accounts"))
        
        try:
            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                bot.send_message(call.message.chat.id, message, parse_mode="Markdown", reply_markup=keyboard)
                
    except Exception as e:
        logger.error(f"Error in manage_stats_callback: {str(e)}")
        try:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:100]}...")
        except:
            pass
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

# Обработчики состояний для управления аккаунтами

@bot.message_handler(func=lambda message: get_user_state(message.from_user.id)["state"] == "waiting_for_account_id_to_delete")
def process_account_id_to_delete(message):
    """Обработка ID аккаунта для удаления."""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Доступ запрещён.")
        return
    
    try:
        account_id = int(message.text.strip())
        
        # Получаем информацию об аккаунте
        account = db_bot.get_account_by_id(account_id)
        if not account:
            bot.send_message(message.chat.id, f"❌ Аккаунт с ID {account_id} не найден.")
            clear_user_state(message.from_user.id)
            return
        
        # Показываем информацию об аккаунте для подтверждения
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{account_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data="manage_accounts")
        )
        
        bot.send_message(
            message.chat.id,
            f"⚠️ **Подтверждение удаления**\n\n"
            f"**Аккаунт:** {account['account_name']}\n"
            f"**Логин:** {account['login']}\n"
            f"**ID:** {account['id']}\n"
            f"**Статус:** {'В аренде' if account['owner'] else 'Свободен'}\n\n"
            f"🗑 **Это действие необратимо!**\n"
            f"Будет удален аккаунт и файл .maFile.\n\n"
            f"Вы уверены?",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
        clear_user_state(message.from_user.id)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат ID. Введите числовой ID аккаунта.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")
        clear_user_state(message.from_user.id)

@bot.message_handler(func=lambda message: get_user_state(message.from_user.id)["state"] == "waiting_for_account_id_to_replace_mafile")
def process_account_id_to_replace_mafile(message):
    """Обработка ID аккаунта для замены .maFile."""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Доступ запрещён.")
        return
    
    try:
        account_id = int(message.text.strip())
        
        # Получаем информацию об аккаунте
        account = db_bot.get_account_by_id(account_id)
        if not account:
            bot.send_message(message.chat.id, f"❌ Аккаунт с ID {account_id} не найден.")
            clear_user_state(message.from_user.id)
            return
        
        # Сохраняем ID аккаунта в состоянии
        set_user_state(message.from_user.id, "waiting_for_new_mafile", {"account_id": account_id})
        
        bot.send_message(
            message.chat.id,
            f"📁 **Замена .maFile для аккаунта {account['account_name']}**\n\n"
            f"Текущий .maFile: `{account['path_to_maFile']}`\n\n"
            f"Отправьте новый .maFile файл:",
            parse_mode="Markdown"
        )
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат ID. Введите числовой ID аккаунта.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")
        clear_user_state(message.from_user.id)

@bot.message_handler(func=lambda message: get_user_state(message.from_user.id)["state"] == "waiting_for_new_mafile", content_types=['document'])
def process_new_mafile(message):
    """Обработка нового .maFile файла."""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Доступ запрещён.")
        return
    
    try:
        state_data = get_user_state(message.from_user.id)["data"]
        account_id = state_data["account_id"]
        
        # Получаем информацию об аккаунте
        account = db_bot.get_account_by_id(account_id)
        if not account:
            bot.send_message(message.chat.id, f"❌ Аккаунт с ID {account_id} не найден.")
            clear_user_state(message.from_user.id)
            return
        
        # Скачиваем файл
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Создаем новое имя файла
        import os
        import time
        file_extension = os.path.splitext(message.document.file_name)[1] or '.maFile'
        new_filename = f"account_{account_id}_{int(time.time())}{file_extension}"
        new_filepath = os.path.join(SAVE_DIR, new_filename)
        
        # Сохраняем файл
        with open(new_filepath, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        # Проверяем .maFile
        validation_result = db_bot.validate_mafile(new_filepath)
        
        if not validation_result["valid"]:
            # Удаляем невалидный файл
            os.remove(new_filepath)
            bot.send_message(
                message.chat.id,
                f"❌ **Неверный .maFile:**\n\n"
                f"Ошибка: {validation_result['error']}\n\n"
                f"Файл не был сохранен. Попробуйте другой .maFile.",
                parse_mode="Markdown"
            )
            return
        
        # Обновляем путь к .maFile в базе данных
        success = db_bot.update_account_mafile(account_id, new_filepath)
        
        if success:
            bot.send_message(
                message.chat.id,
                f"✅ **.maFile успешно заменен!**\n\n"
                f"**Аккаунт:** {account['account_name']}\n"
                f"**Новый файл:** `{new_filepath}`\n\n"
                f"Файл проверен и готов к использованию.",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(message.chat.id, f"❌ Ошибка при обновлении .maFile в базе данных.")
        
        clear_user_state(message.from_user.id)
        
    except Exception as e:
        logger.error(f"Error processing new mafile: {str(e)}")
        bot.send_message(message.chat.id, f"❌ Ошибка при обработке .maFile: {str(e)}")
        clear_user_state(message.from_user.id)

@bot.message_handler(func=lambda message: get_user_state(message.from_user.id)["state"] == "waiting_for_mafile_to_validate", content_types=['document'])
def process_mafile_to_validate(message):
    """Обработка .maFile для проверки."""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Доступ запрещён.")
        return
    
    try:
        # Скачиваем файл
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Создаем временный файл
        import os
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.maFile') as temp_file:
            temp_file.write(downloaded_file)
            temp_filepath = temp_file.name
        
        # Проверяем .maFile
        validation_result = db_bot.validate_mafile(temp_filepath)
        
        # Удаляем временный файл
        os.unlink(temp_filepath)
        
        if validation_result["valid"]:
            data = validation_result["data"]
            bot.send_message(
                message.chat.id,
                f"✅ **.maFile валиден!**\n\n"
                f"**Аккаунт:** {data['account_name']}\n"
                f"**Steam ID:** {data['Session']['SteamID']}\n"
                f"**Device ID:** {data['device_id']}\n\n"
                f"Файл готов к использованию.",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                message.chat.id,
                f"❌ **.maFile невалиден!**\n\n"
                f"**Ошибка:** {validation_result['error']}\n\n"
                f"Проверьте формат файла и попробуйте снова.",
                parse_mode="Markdown"
            )
        
        clear_user_state(message.from_user.id)
        
    except Exception as e:
        logger.error(f"Error validating mafile: {str(e)}")
        bot.send_message(message.chat.id, f"❌ Ошибка при проверке .maFile: {str(e)}")
        clear_user_state(message.from_user.id)

# Обработчик подтверждения удаления
@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_delete_"))
def confirm_delete_callback(call):
    """Подтверждение удаления аккаунта."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    try:
        account_id = int(call.data.split("_")[2])
        
        # Удаляем аккаунт
        success = db_bot.delete_account(account_id)
        
        if success:
            bot.edit_message_text(
                f"✅ **Аккаунт успешно удален!**\n\n"
                f"ID: {account_id}\n"
                f"Аккаунт и .maFile файл удалены из системы.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=get_manage_accounts_keyboard()
            )
        else:
            bot.edit_message_text(
                f"❌ **Ошибка при удалении аккаунта!**\n\n"
                f"ID: {account_id}\n"
                f"Проверьте логи для подробностей.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=get_manage_accounts_keyboard()
            )
        
    except Exception as e:
        logger.error(f"Error in confirm_delete_callback: {str(e)}")
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:100]}...")
    
    bot.answer_callback_query(call.id)

# --- AUTOGUARD УПРАВЛЕНИЕ ---

@bot.callback_query_handler(func=lambda call: call.data == "chat_sync_menu")
def chat_sync_menu_callback(call):
    """Меню Chat Sync."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    try:
        from integration.chat_sync_integration import get_chat_sync_integration
        
        chat_sync = get_chat_sync_integration()
        if not chat_sync:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ **Chat Sync Plugin недоступен**\n\nПлагин не инициализирован или отключен.",
                parse_mode="Markdown"
            )
            return
        
        status = chat_sync.get_plugin_status()
        
        menu_text = f"""
🧩 **Chat Sync Plugin**

📊 **Статус:**
• Готов к работе: {'✅ Да' if status['ready'] else '❌ Нет'}
• Ботов: {status['bots_count']}
• Синхронизированных чатов: {status['threads_count']}

🔧 **Управление:**
        """.strip()
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📊 Статус", callback_data="chat_sync_status"),
            InlineKeyboardButton("📋 Аккаунты", callback_data="chat_sync_accounts"),
        )
        keyboard.add(
            InlineKeyboardButton("🔄 Синхронизация", callback_data="chat_sync_sync"),
            InlineKeyboardButton("⚙️ Настройка", callback_data="chat_sync_setup"),
        )
        keyboard.add(
            InlineKeyboardButton("❓ Справка", callback_data="chat_sync_help"),
            InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"),
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=menu_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in chat_sync_menu_callback: {str(e)}")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"❌ **Ошибка Chat Sync**\n\n{str(e)}",
            parse_mode="Markdown"
        )

# --- CHAT SYNC ОБРАБОТЧИКИ ---

@bot.callback_query_handler(func=lambda call: call.data == "chat_sync_status")
def chat_sync_status_callback(call):
    """Обработчик статуса Chat Sync."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    try:
        from integration.chat_sync_integration import get_chat_sync_integration
        
        chat_sync = get_chat_sync_integration()
        if not chat_sync:
            bot.answer_callback_query(call.id, "Chat Sync недоступен")
            return
        
        status = chat_sync.get_plugin_status()
        
        status_text = f"""
🧩 **Chat Sync Plugin Status**

📊 **Общая информация:**
• Название: {status['name']}
• Версия: {status['version']}
• Инициализирован: {'✅ Да' if status['initialized'] else '❌ Нет'}
• Готов к работе: {'✅ Да' if status['ready'] else '❌ Нет'}

🤖 **Боты:**
• Количество: {status['bots_count']}
• Чат для синхронизации: {status['chat_id'] or 'Не установлен'}

🔗 **Синхронизация:**
• Синхронизированных чатов: {status['threads_count']}
• Автосинхронизация: {'✅ Включена' if status['config'].get('auto_sync_accounts') else '❌ Отключена'}
• Уведомления об аренде: {'✅ Включены' if status['config'].get('notify_on_rental_change') else '❌ Отключены'}
        """.strip()
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="chat_sync_menu"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=status_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in chat_sync_status_callback: {str(e)}")
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "chat_sync_accounts")
def chat_sync_accounts_callback(call):
    """Обработчик списка аккаунтов Chat Sync."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    try:
        from integration.chat_sync_integration import get_chat_sync_integration
        
        chat_sync = get_chat_sync_integration()
        if not chat_sync:
            bot.answer_callback_query(call.id, "Chat Sync недоступен")
            return
        
        accounts = chat_sync.get_synced_accounts()
        
        if not accounts:
            text = "📋 Аккаунтов не найдено"
        else:
            text = f"📋 **Аккаунты с синхронизацией** ({len(accounts)} шт.)\n\n"
            
            for i, account in enumerate(accounts[:10], 1):  # Показываем первые 10
                sync_status = "🟢 Синхронизирован" if account['synced'] else "🔴 Не синхронизирован"
                owner_status = "🔴 В аренде" if account['owner'] else "🟢 Свободен"
                
                text += f"{i}. **{account['account_name']}**\n"
                text += f"   • ID: {account['id']}\n"
                text += f"   • Логин: {account['login']}\n"
                text += f"   • Статус: {owner_status}\n"
                text += f"   • Синхронизация: {sync_status}\n\n"
            
            if len(accounts) > 10:
                text += f"... и еще {len(accounts) - 10} аккаунтов"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="chat_sync_menu"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in chat_sync_accounts_callback: {str(e)}")
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "chat_sync_sync")
def chat_sync_sync_callback(call):
    """Обработчик синхронизации Chat Sync."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    try:
        from integration.chat_sync_integration import get_chat_sync_integration
        
        chat_sync = get_chat_sync_integration()
        if not chat_sync:
            bot.answer_callback_query(call.id, "Chat Sync недоступен")
            return
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🔄 Синхронизация аккаунтов...",
            parse_mode="Markdown"
        )
        
        result = chat_sync.sync_all_accounts()
        
        text = f"""
✅ **Синхронизация завершена!**

📊 **Результаты:**
• Успешно синхронизировано: {result['synced']}
• Ошибок: {result['errors']}

💡 Для просмотра статуса используйте кнопку "Статус"
        """.strip()
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="chat_sync_menu"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in chat_sync_sync_callback: {str(e)}")
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "chat_sync_setup")
def chat_sync_setup_callback(call):
    """Обработчик настройки Chat Sync."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    setup_text = """
🔧 **Настройка Chat Sync Plugin**

**Шаг 1: Создание ботов**
1. Создайте ботов через @BotFather
2. Убедитесь, что username начинается с "funpay"
3. Добавьте токены через меню управления

**Шаг 2: Настройка группы**
1. Создайте группу в Telegram
2. Включите режим тем в настройках
3. Добавьте всех ботов в группу
4. Назначьте ботов администраторами

**Шаг 3: Активация**
1. Используйте кнопку "Синхронизация"
2. Проверьте статус через кнопку "Статус"

**Требования:**
• Минимум 2 бота
• Группа с включенными темами
• Все боты должны быть администраторами

💡 После настройки плагин будет автоматически синхронизировать аккаунты!
    """.strip()
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="chat_sync_menu"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=setup_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "chat_sync_help")
def chat_sync_help_callback(call):
    """Обработчик справки Chat Sync."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    help_text = """
🧩 **Chat Sync Plugin - Справка**

**Основные функции:**
• Синхронизация FunPay чатов с Telegram темами
• Отправка уведомлений об изменении статуса аренды
• Позволяет отправлять сообщения в FunPay из Telegram

**Управление:**
• **Статус** - текущее состояние плагина
• **Аккаунты** - список синхронизированных аккаунтов
• **Синхронизация** - ручная синхронизация всех аккаунтов
• **Настройка** - инструкции по настройке

**Команды:**
• `/chat_sync_status` - статус плагина
• `/chat_sync_accounts` - список аккаунтов
• `/chat_sync_sync` - синхронизация
• `/chat_sync_help` - справка

**Поддержка:**
При проблемах проверьте логи и убедитесь, что все настройки корректны.
    """.strip()
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="chat_sync_menu"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=help_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# --- FUNPAY ОБРАБОТЧИКИ ---

@bot.callback_query_handler(func=lambda call: call.data == "funpay_menu")
def funpay_menu_callback(call):
    """Меню FunPay."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    try:
        from integration.enhanced_bot import get_enhanced_bot
        
        enhanced_bot = get_enhanced_bot()
        if not enhanced_bot or not enhanced_bot.chat_sync:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ **FunPay интеграция недоступна**\n\nChat Sync плагин не инициализирован.",
                parse_mode="Markdown"
            )
            return
        
        menu_text = """
💬 **FunPay Интеграция**

Выберите действие:

📋 **Чаты** - просмотр чатов FunPay
🔄 **Синхронизация** - синхронизация с аккаунтами
📊 **Статус** - статус интеграции
❓ **Помощь** - справка по FunPay
        """.strip()
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📋 Чаты", callback_data="funpay_chats"),
            InlineKeyboardButton("🔄 Синхронизация", callback_data="funpay_sync")
        )
        keyboard.add(
            InlineKeyboardButton("📊 Статус", callback_data="funpay_status"),
            InlineKeyboardButton("❓ Помощь", callback_data="funpay_help")
        )
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=menu_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in funpay_menu_callback: {str(e)}")
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "funpay_chats")
def funpay_chats_callback(call):
    """Обработчик чатов FunPay."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    try:
        from integration.enhanced_bot import get_enhanced_bot
        
        enhanced_bot = get_enhanced_bot()
        if not enhanced_bot:
            bot.answer_callback_query(call.id, "Enhanced bot недоступен")
            return
        
        chats = enhanced_bot.get_funpay_chats()
        if not chats:
            text = "📋 **Чаты FunPay**\n\n"
            text += "🔍 **Активных чатов не найдено**\n\n"
            text += "Это нормально! Чаты появляются автоматически при:\n"
            text += "• Новых заказах\n"
            text += "• Сообщениях от покупателей\n"
            text += "• Активных продажах\n\n"
            text += "💡 **Статус подключения:** ✅ FunPay подключен\n"
            text += "🔄 **Мониторинг:** Активен\n"
            text += "⏰ **Проверка:** Каждые 10 секунд"
        else:
            text = f"📋 **Чаты FunPay ({len(chats)} шт.)**\n\n"
            for i, chat in enumerate(chats[:10], 1):
                text += f"{i}. **{chat.name}**\n"
                text += f"   ID: `{chat.id}`\n"
                text += f"   Тип: {chat.type}\n"
                if hasattr(chat, 'unread_count') and chat.unread_count > 0:
                    text += f"   Непрочитанных: {chat.unread_count}\n"
                text += "\n"
            
            if len(chats) > 10:
                text += f"... и еще {len(chats) - 10} чатов"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="funpay_menu"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in funpay_chats_callback: {str(e)}")
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "funpay_sync")
def funpay_sync_callback(call):
    """Обработчик синхронизации FunPay."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    try:
        from integration.enhanced_bot import get_enhanced_bot
        
        enhanced_bot = get_enhanced_bot()
        if not enhanced_bot:
            bot.answer_callback_query(call.id, "Enhanced bot недоступен")
            return
        
        bot.answer_callback_query(call.id, "🔄 Синхронизация с FunPay...")
        
        result = enhanced_bot.sync_accounts_with_funpay()
        
        if result['synced'] > 0:
            text = f"✅ **Синхронизация завершена**\n\n"
            text += f"🟢 Успешно: {result['synced']}\n"
            text += f"🔴 Ошибок: {result['errors']}\n\n"
            text += "Аккаунты синхронизированы с чатами FunPay"
        else:
            text = f"❌ **Синхронизация не удалась**\n\n"
            text += f"🔴 Ошибок: {result['errors']}\n\n"
            text += "Проверьте настройки FunPay"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="funpay_menu"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in funpay_sync_callback: {str(e)}")
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "funpay_status")
def funpay_status_callback(call):
    """Обработчик статуса FunPay."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    try:
        from integration.enhanced_bot import get_enhanced_bot
        
        enhanced_bot = get_enhanced_bot()
        if not enhanced_bot or not enhanced_bot.chat_sync:
            text = "❌ **FunPay интеграция недоступна**\n\nChat Sync плагин не инициализирован."
        else:
            chats = enhanced_bot.get_funpay_chats()
            text = f"📊 **Статус FunPay интеграции**\n\n"
            text += f"🔗 **Подключение:** ✅ Активно\n"
            text += f"👤 **Аккаунт:** uuuu989 (ID: 13270924)\n"
            text += f"📋 **Чатов найдено:** {len(chats)}\n"
            text += f"🧩 **Chat Sync:** {'✅ Включен' if enhanced_bot.chat_sync else '❌ Отключен'}\n"
            text += f"🔄 **Мониторинг:** {'✅ Активен' if enhanced_bot.chat_sync and hasattr(enhanced_bot.chat_sync, 'monitoring_active') and enhanced_bot.chat_sync.monitoring_active else '❌ Неактивен'}\n\n"
            if len(chats) == 0:
                text += "💡 **Информация:** Чаты появляются при активных заказах"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="funpay_menu"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in funpay_status_callback: {str(e)}")
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "funpay_help")
def funpay_help_callback(call):
    """Обработчик справки FunPay."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    help_text = """
💬 **FunPay Интеграция - Справка**

**Основные функции:**
• Мониторинг чатов FunPay в реальном времени
• Автоматическая синхронизация с вашими аккаунтами
• Обработка сообщений и уведомлений
• Интеграция с Chat Sync плагином

**Команды:**
• `/funpay_chats` - список чатов FunPay
• `/funpay_sync` - синхронизация с аккаунтами

**Настройка:**
• Golden Key уже настроен в config.py
• Интеграция работает автоматически
• Мониторинг запускается при старте бота

**Возможности:**
• Просмотр всех чатов FunPay
• Синхронизация аккаунтов с чатами
• Отслеживание изменений в реальном времени
• Автоматическая обработка сообщений

**Поддержка:**
При проблемах проверьте логи и убедитесь, что Golden Key корректный.
    """.strip()
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="funpay_menu"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=help_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "autoguard_menu")
def autoguard_menu_callback(call):
    """Меню AutoGuard."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён. Только для администратора.")
        return
    
    try:
        bot.edit_message_text(
            "🔐 **AutoGuard - Автоматическая выдача Steam Guard кодов**\n\n"
            "Выберите действие:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_autoguard_keyboard()
        )
    except Exception as edit_error:
        if "message is not modified" not in str(edit_error):
            bot.send_message(
                call.message.chat.id,
                "🔐 **AutoGuard - Автоматическая выдача Steam Guard кодов**\n\n"
                "Выберите действие:",
                parse_mode="Markdown",
                reply_markup=get_autoguard_keyboard()
            )
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "autoguard_stats")
def autoguard_stats_callback(call):
    """Статистика AutoGuard."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    try:
        from steamHandler.auto_guard import get_auto_guard_stats
        stats = get_auto_guard_stats()
        
        message = (
            f"📊 **Статистика AutoGuard:**\n\n"
            f"🔧 **Состояние:** {'✅ Включен' if stats['enabled'] else '❌ Выключен'}\n"
            f"🛒 **При покупке:** {'✅ Да' if stats['on_purchase'] else '❌ Нет'}\n"
            f"⏰ **Интервал:** {stats['interval']} секунд ({stats['interval'] // 60} минут)\n"
            f"🔄 **Работает:** {'✅ Да' if stats['running'] else '❌ Нет'}\n\n"
            f"📈 **Активность:**\n"
            f"   • Всего задач: {stats['total_tasks']}\n"
            f"   • Успешных: {stats['successful_tasks']}\n"
            f"   • С ошибками: {stats['error_tasks']}\n"
            f"   • Успешность: {stats['success_rate']:.1f}%\n\n"
            f"💡 **Информация:**\n"
            f"   • Коды отправляются автоматически каждые {stats['interval'] // 60} минут\n"
            f"   • При покупке код отправляется сразу\n"
            f"   • При ошибках админ получает уведомления"
        )
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Обновить", callback_data="autoguard_stats"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="autoguard_menu"))
        
        try:
            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                bot.send_message(call.message.chat.id, message, parse_mode="Markdown", reply_markup=keyboard)
                
    except Exception as e:
        logger.error(f"Error in autoguard_stats_callback: {str(e)}")
        try:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:100]}...")
        except:
            pass
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "autoguard_settings")
def autoguard_settings_callback(call):
    """Настройки AutoGuard."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    try:
        from config import (
            AUTO_GUARD_ENABLED, AUTO_GUARD_ON_PURCHASE, AUTO_GUARD_INTERVAL,
            AUTO_GUARD_MAX_ATTEMPTS, AUTO_GUARD_RETRY_DELAY, AUTO_GUARD_NOTIFY_ADMIN
        )
        
        message = (
            f"⚙️ **Настройки AutoGuard:**\n\n"
            f"🔧 **Основные настройки:**\n"
            f"   • Включен: {'✅ Да' if AUTO_GUARD_ENABLED else '❌ Нет'}\n"
            f"   • При покупке: {'✅ Да' if AUTO_GUARD_ON_PURCHASE else '❌ Нет'}\n"
            f"   • Интервал: {AUTO_GUARD_INTERVAL} сек ({AUTO_GUARD_INTERVAL // 60} мин)\n\n"
            f"🔄 **Повторные попытки:**\n"
            f"   • Максимум попыток: {AUTO_GUARD_MAX_ATTEMPTS}\n"
            f"   • Задержка: {AUTO_GUARD_RETRY_DELAY} сек\n\n"
            f"🔔 **Уведомления:**\n"
            f"   • Уведомлять админа: {'✅ Да' if AUTO_GUARD_NOTIFY_ADMIN else '❌ Нет'}\n\n"
            f"💡 **Для изменения настроек отредактируйте config.py**"
        )
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Обновить", callback_data="autoguard_settings"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="autoguard_menu"))
        
        try:
            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                bot.send_message(call.message.chat.id, message, parse_mode="Markdown", reply_markup=keyboard)
                
    except Exception as e:
        logger.error(f"Error in autoguard_settings_callback: {str(e)}")
        try:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:100]}...")
        except:
            pass
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "autoguard_restart")
def autoguard_restart_callback(call):
    """Перезапуск AutoGuard."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    try:
        from steamHandler.auto_guard import stop_auto_guard, start_auto_guard
        
        # Останавливаем и запускаем заново
        stop_auto_guard()
        time.sleep(2)  # Небольшая задержка
        start_auto_guard()
        
        message = "🔄 **AutoGuard перезапущен!**\n\nСистема автоматической выдачи кодов перезапущена успешно."
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📊 Статистика", callback_data="autoguard_stats"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="autoguard_menu"))
        
        try:
            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                bot.send_message(call.message.chat.id, message, parse_mode="Markdown", reply_markup=keyboard)
                
    except Exception as e:
        logger.error(f"Error restarting AutoGuard: {str(e)}")
        try:
            bot.answer_callback_query(call.id, f"Ошибка перезапуска: {str(e)[:100]}...")
        except:
            pass
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "autoguard_stop")
def autoguard_stop_callback(call):
    """Остановка AutoGuard."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    try:
        from steamHandler.auto_guard import stop_auto_guard
        
        stop_auto_guard()
        
        message = "⏹ **AutoGuard остановлен!**\n\nСистема автоматической выдачи кодов остановлена."
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Запустить", callback_data="autoguard_restart"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="autoguard_menu"))
        
        try:
            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                bot.send_message(call.message.chat.id, message, parse_mode="Markdown", reply_markup=keyboard)
                
    except Exception as e:
        logger.error(f"Error stopping AutoGuard: {str(e)}")
        try:
            bot.answer_callback_query(call.id, f"Ошибка остановки: {str(e)[:100]}...")
        except:
            pass
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "autoguard_cleanup")
def autoguard_cleanup_callback(call):
    """Очистка задач AutoGuard."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    try:
        from steamHandler.auto_guard import cleanup_auto_guard_tasks
        
        cleanup_auto_guard_tasks()
        
        message = "🧹 **Задачи AutoGuard очищены!**\n\nСтарые задачи удалены из памяти."
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📊 Статистика", callback_data="autoguard_stats"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="autoguard_menu"))
        
        try:
            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                bot.send_message(call.message.chat.id, message, parse_mode="Markdown", reply_markup=keyboard)
                
    except Exception as e:
        logger.error(f"Error cleaning up AutoGuard tasks: {str(e)}")
        try:
            bot.answer_callback_query(call.id, f"Ошибка очистки: {str(e)[:100]}...")
        except:
            pass
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "autoguard_tasks")
def autoguard_tasks_callback(call):
    """Активные задачи AutoGuard."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    try:
        from steamHandler.auto_guard import auto_guard_manager
        
        tasks = auto_guard_manager.active_tasks
        
        if not tasks:
            message = "📋 **Активные задачи AutoGuard:**\n\nНет активных задач."
        else:
            message = f"📋 **Активные задачи AutoGuard ({len(tasks)}):**\n\n"
            
            for task_key, task_data in list(tasks.items())[:10]:  # Показываем первые 10
                account_name = task_data.get('account_name', 'Unknown')
                owner = task_data.get('owner', 'Unknown')
                success_count = task_data.get('success_count', 0)
                error_count = task_data.get('error_count', 0)
                last_sent = task_data.get('last_sent', 0)
                
                if last_sent:
                    last_sent_time = datetime.fromtimestamp(last_sent).strftime("%H:%M:%S")
                else:
                    last_sent_time = "Никогда"
                
                message += (
                    f"**{account_name}** (владелец: {owner})\n"
                    f"   ✅ Успешно: {success_count}\n"
                    f"   ❌ Ошибок: {error_count}\n"
                    f"   🕐 Последний код: {last_sent_time}\n\n"
                )
            
            if len(tasks) > 10:
                message += f"... и еще {len(tasks) - 10} задач"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Обновить", callback_data="autoguard_tasks"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="autoguard_menu"))
        
        try:
            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                bot.send_message(call.message.chat.id, message, parse_mode="Markdown", reply_markup=keyboard)
                
    except Exception as e:
        logger.error(f"Error in autoguard_tasks_callback: {str(e)}")
        try:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:100]}...")
        except:
            pass
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "autoguard_test")
def autoguard_test_callback(call):
    """Тест генерации Steam Guard кода."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    try:
        # Получаем первый доступный аккаунт для теста
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, account_name, path_to_maFile 
            FROM accounts 
            WHERE path_to_maFile IS NOT NULL 
            LIMIT 1
        """)
        
        test_account = cursor.fetchone()
        conn.close()
        
        if not test_account:
            message = "❌ **Тест AutoGuard:**\n\nНет доступных аккаунтов для тестирования."
        else:
            account_id, account_name, mafile_path = test_account
            
            from steamHandler.SteamGuard import get_steam_guard_code
            
            guard_code = get_steam_guard_code(mafile_path)
            
            if guard_code:
                message = (
                    f"✅ **Тест AutoGuard успешен!**\n\n"
                    f"**Аккаунт:** {account_name}\n"
                    f"**Код:** `{guard_code}`\n\n"
                    f"Система работает корректно."
                )
            else:
                message = (
                    f"❌ **Тест AutoGuard не удался!**\n\n"
                    f"**Аккаунт:** {account_name}\n"
                    f"**Файл:** {mafile_path}\n\n"
                    f"Проверьте .maFile и настройки."
                )
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Повторить тест", callback_data="autoguard_test"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="autoguard_menu"))
        
        try:
            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                bot.send_message(call.message.chat.id, message, parse_mode="Markdown", reply_markup=keyboard)
                
    except Exception as e:
        logger.error(f"Error in autoguard_test_callback: {str(e)}")
        try:
            bot.answer_callback_query(call.id, f"Ошибка теста: {str(e)[:100]}...")
        except:
            pass
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "autoguard_logs")
def autoguard_logs_callback(call):
    """Логи AutoGuard."""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Доступ запрещён.")
        return
    
    try:
        # Читаем последние записи из логов AutoGuard
        log_file = "logs/autoguard.log"
        
        if not os.path.exists(log_file):
            message = "📝 **Логи AutoGuard:**\n\nФайл логов не найден."
        else:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Берем последние 20 строк
                recent_lines = lines[-20:] if len(lines) >= 20 else lines
                
                if recent_lines:
                    message = f"📝 **Последние логи AutoGuard ({len(recent_lines)}):**\n\n"
                    for line in recent_lines[-10:]:  # Показываем последние 10
                        message += f"`{line.strip()}`\n"
                else:
                    message = "📝 **Логи AutoGuard:**\n\nНет записей в логах."
                    
            except Exception as e:
                message = f"❌ **Ошибка чтения логов:**\n\n{str(e)}"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Обновить", callback_data="autoguard_logs"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="autoguard_menu"))
        
        try:
            bot.edit_message_text(
                message,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                bot.send_message(call.message.chat.id, message, parse_mode="Markdown", reply_markup=keyboard)
                
    except Exception as e:
        logger.error(f"Error in autoguard_logs_callback: {str(e)}")
        try:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:100]}...")
        except:
            pass
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

# Обработчики callback-ов для FunPay
@bot.callback_query_handler(func=lambda call: call.data == "funpay_main_menu")
def funpay_main_menu_callback(call):
    """Обработчик главного меню FunPay"""
    if not funpay_integration:
        bot.answer_callback_query(call.id, "❌ FunPay интеграция недоступна")
        return
    
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Доступ запрещён")
        return
    
    try:
        funpay_integration.show_lots_menu(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка показа меню FunPay: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка открытия меню")

@bot.callback_query_handler(func=lambda call: call.data == "funpay_profile_menu")
def funpay_profile_menu_callback(call):
    """Обработчик меню профиля FunPay"""
    if not funpay_integration:
        bot.answer_callback_query(call.id, "❌ FunPay интеграция недоступна")
        return
    
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Доступ запрещён")
        return
    
    try:
        # Получаем расширенную статистику профиля
        profile_text = funpay_integration.get_advanced_profile_stats()
        keyboard = funpay_integration.get_profile_stats_keyboard()
        
        bot.edit_message_text(
            profile_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка показа профиля FunPay: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка загрузки профиля")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main_callback(call):
    """Обработчик кнопки возврата в главное меню"""
    try:
        # Получаем статистику для приветствия
        try:
            stats = db_bot.get_rental_statistics()
            welcome_stats = ""
            if stats:
                welcome_stats = (
                    f"\n📊 **Статистика системы:**\n"
                    f"• Активных аренд: `{stats['active_rentals']}`\n"
                    f"• Свободных аккаунтов: `{stats['available_accounts']}`\n"
                    f"• Загруженность: `{(stats['active_rentals'] / stats['total_accounts'] * 100):.1f}%`"
                )
        except:
            welcome_stats = ""

        welcome_message = (
            "🎮 **Добро пожаловать в Steam Rental by Lini!**\n\n"
            "🚀 **Система автоматической аренды Steam аккаунтов**\n\n"
            "✨ **Возможности:**\n"
            "• Автоматическая обработка заказов с FunPay\n"
            "• Умная система продления аренды\n"
            "• Автоматическая смена паролей\n"
            "• Telegram бот для управления\n"
            "• Статистика и аналитика\n"
            "• 🏪 **Управление лотами FunPay**\n"
            "• 📈 **Расширенная статистика профиля**\n\n"
            "🔐 **Система продления:**\n"
            "• Автоматическое продление на 1 час при отзыве\n"
            "• Ручное продление через бот\n"
            "• Уведомления об истечении срока\n\n"
            "Выберите нужную функцию:" + welcome_stats
        )
        
        bot.edit_message_text(
            welcome_message,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка возврата в главное меню: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка возврата в меню")

@bot.callback_query_handler(func=lambda call: call.data.startswith('profile_stats_'))
def handle_profile_stats_callback(call):
    """Обработчик callback-ов для статистики профиля FunPay"""
    if not funpay_integration:
        bot.answer_callback_query(call.id, "❌ FunPay интеграция недоступна")
        return
    
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Доступ запрещён")
        return
    
    try:
        if call.data == 'profile_stats_refresh':
            # Обновляем статистику профиля
            profile_text = funpay_integration.get_advanced_profile_stats()
            keyboard = funpay_integration.get_profile_stats_keyboard()
            
            bot.edit_message_text(
                profile_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        elif call.data == 'profile_stats_detailed':
            # Показываем детальную статистику (то же самое, что и refresh)
            profile_text = funpay_integration.get_advanced_profile_stats()
            keyboard = funpay_integration.get_profile_stats_keyboard()
            
            bot.edit_message_text(
                profile_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка обработки callback профиля: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка обновления статистики")

def _save_bot_state():
    """Сохраняет состояние бота перед перезапуском"""
    try:
        import json
        import os
        
        # Создаем директорию для состояния если её нет
        state_dir = "bot_state"
        os.makedirs(state_dir, exist_ok=True)
        
        # Сохраняем время последнего перезапуска
        state_data = {
            "last_restart": datetime.now().isoformat(),
            "restart_count": _get_restart_count() + 1,
            "bot_token": API_TOKEN,
            "admin_id": ADMIN_ID
        }
        
        with open(os.path.join(state_dir, "restart_state.json"), "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)
        
        logger.info("Состояние бота сохранено перед перезапуском")
        
    except Exception as e:
        logger.error(f"Ошибка сохранения состояния бота: {e}")

def _get_restart_count():
    """Получает количество перезапусков"""
    try:
        import json
        import os
        
        state_file = os.path.join("bot_state", "restart_state.json")
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("restart_count", 0)
        return 0
    except Exception:
        return 0

def _restart_bot_process():
    """Перезапускает процесс бота"""
    try:
        import time
        import subprocess
        import sys
        
        logger.info("Начинаем процесс перезапуска бота...")
        
        # Небольшая задержка для завершения текущих операций
        time.sleep(3)
        
        # Получаем путь к текущему скрипту
        script_path = sys.argv[0]
        
        # Запускаем новый процесс
        logger.info(f"Запускаем новый процесс: {script_path}")
        subprocess.Popen([sys.executable, script_path] + sys.argv[1:])
        
        # Завершаем текущий процесс
        logger.info("Завершаем текущий процесс бота")
        os._exit(0)
        
    except Exception as e:
        logger.error(f"Ошибка при перезапуске процесса: {e}")
        # Fallback - просто завершаем процесс
        os._exit(1)

def main():
    # Регистрируем обработчики Chat Sync
    try:
        chat_sync_handlers = register_chat_sync_handlers(bot, db_bot)
        if chat_sync_handlers:
            logger.info("Chat Sync handlers registered successfully")
        else:
            logger.warning("Failed to register Chat Sync handlers")
    except Exception as e:
        logger.error(f"Error registering Chat Sync handlers: {str(e)}")
    
    # Проверяем, был ли бот перезапущен
    restart_count = _get_restart_count()
    if restart_count > 0:
        logger.info(f"Бот перезапущен. Количество перезапусков: {restart_count}")
    
    bot.infinity_polling(none_stop=True, timeout=5)

if __name__ == "__main__":
    main()