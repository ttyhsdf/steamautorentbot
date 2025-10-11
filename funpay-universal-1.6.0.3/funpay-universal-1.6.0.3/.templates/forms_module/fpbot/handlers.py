import re
import traceback
from logging import getLogger
from typing import TYPE_CHECKING
from colorama import Fore
from threading import Thread

from FunPayAPI.updater.events import *
from FunPayAPI.common.enums import *
from FunPayAPI.account import *

from ..meta import PREFIX, NAME
from ..data import Data as data
from ..settings import Settings as sett
from ..settings import DATA
from fpbot.funpaybot import get_funpay_bot

if TYPE_CHECKING:
    from fpbot.funpaybot import FunPayBot


logger = getLogger(f"{NAME}.funpay")
config = sett.get("config")
messages = sett.get("messages")

new_forms = data.get("new_forms")
forms = data.get("forms")


def msg(message_name: str, exclude_watermark: bool = False, **kwargs) -> str | None:
    return get_funpay_bot().msg(message_name, exclude_watermark, "messages", DATA, **kwargs)

def is_fullname_valid(fullname: str) -> bool:
    pattern = r'^[А-Яа-яЁё]+ [А-Яа-яЁё]+ [А-Яа-яЁё]+$'
    return bool(re.match(pattern, fullname.strip()))

def is_age_valid(age: str) -> bool:
    return age.isdigit()

def is_hobby_valid(hobby: str) -> bool:
    pattern = r'^[А-Яа-яЁё\s\-]+$'
    return bool(re.match(pattern, hobby.strip()))

async def handle_cmds(fpbot: 'FunPayBot', event: NewMessageEvent):
    global new_forms
    this_chat = fpbot.funpay_account.get_chat_by_name(event.message.chat_name, True)
    if event.message.text.lower() == "!мояанкета":
        form = forms.get(event.message.author)
        if not form:
            fpbot.send_message(this_chat.id, msg("cmd_myform_error", reason="Ваша анкета не была найдена.\nИспользуйте команду !заполнить, чтобы заполнить анкету."))
            return
        fpbot.send_message(this_chat.id, msg("cmd_myform", fullname=form["fullname"], age=form["age"], hobby=form["hobby"]))
    elif event.message.text.lower() == "!заполнить":
        new_forms[event.message.author] = {
            "fullname": "",
            "age": "",
            "hobby": "",
            "state": "waiting_for_fullname"
        }
        fpbot.send_message(this_chat.id, msg("cmd_writein"))

async def handle_new_form_waiting_for_fullname(fpbot: 'FunPayBot', event: NewMessageEvent):
    global new_forms
    this_chat = fpbot.funpay_account.get_chat_by_name(event.message.chat_name, True)
    fullname = event.message.text.strip()
    if not is_fullname_valid(fullname):
        fpbot.send_message(this_chat.id, msg("entering_fullname_error"))
        return
    fullname = " ".join([f"{part[0].upper()}{part[1:]}" for part in fullname.split(" ")])
    new_forms[event.message.author]["fullname"] = fullname
    new_forms[event.message.author]["state"] = "waiting_for_age"
    if config["funpay"]["bot"]["log_states"]:
        logger.info(f"{PREFIX} {Fore.LIGHTWHITE_EX}{event.message.author} {Fore.WHITE}указал в анкете ФИО: {Fore.LIGHTWHITE_EX}{fullname}")
    fpbot.send_message(this_chat.id, msg("enter_age"))

async def handle_new_form_waiting_for_age(fpbot: 'FunPayBot', event: NewMessageEvent):
    global new_forms
    this_chat = fpbot.funpay_account.get_chat_by_name(event.message.chat_name, True)
    age = event.message.text.strip()
    if not is_age_valid(age):
        fpbot.send_message(this_chat.id, msg("entering_age_error"))
        return
    new_forms[event.message.author]["age"] = int(age)
    new_forms[event.message.author]["state"] = "waiting_for_hobby"
    if config["funpay"]["bot"]["log_states"]:
        logger.info(f"{PREFIX} {Fore.LIGHTWHITE_EX}{event.message.author} {Fore.WHITE}указал в анкете возраст: {Fore.LIGHTWHITE_EX}{age}")
    fpbot.send_message(this_chat.id, msg("enter_hobby"))

async def handle_new_form_waiting_for_hobby(fpbot: 'FunPayBot', event: NewMessageEvent):
    global new_forms, forms
    this_chat = fpbot.funpay_account.get_chat_by_name(event.message.chat_name, True)
    hobby = event.message.text.strip()
    if not is_hobby_valid(hobby):
        fpbot.send_message(this_chat.id, msg("entering_hobby_error"))
        return
    new_forms[event.message.author]["hobby"] = hobby
    forms[event.message.author] = {
        "fullname": new_forms[event.message.author]["fullname"],
        "age": new_forms[event.message.author]["age"],
        "hobby": new_forms[event.message.author]["hobby"]
    }
    del new_forms[event.message.author]
    if config["funpay"]["bot"]["log_states"]:
        logger.info(f"{PREFIX} {Fore.LIGHTWHITE_EX}{event.message.author} {Fore.WHITE}указал в анкете хобби: {Fore.LIGHTWHITE_EX}{hobby}")
    fpbot.send_message(this_chat.id, msg("form_filled_out", fullname=forms[event.message.author]["fullname"], age=forms[event.message.author]["age"], hobby=forms[event.message.author]["hobby"]))
    
async def handle_new_form(fpbot: 'FunPayBot', event: NewMessageEvent):
    this_chat = fpbot.funpay_account.get_chat_by_name(event.message.chat_name, True)
    if this_chat.name not in new_forms:
        return
    if new_forms[this_chat.name]["state"] == "waiting_for_fullname":
        await handle_new_form_waiting_for_fullname(fpbot, event)
    elif new_forms[this_chat.name]["state"] == "waiting_for_age":
        await handle_new_form_waiting_for_age(fpbot, event)
    elif new_forms[this_chat.name]["state"] == "waiting_for_hobby":
        await handle_new_form_waiting_for_hobby(fpbot, event)
    else:
        return

def on_funpay_bot_init(fpbot: 'FunPayBot'):

    def endless_loop(cycle_delay=5):
        global config, messages, new_forms, forms
        while True:
            if sett.get("config") != config: config = sett.get("config")
            if sett.get("messages") != messages: messages = sett.get("messages")
            if data.get("new_forms") != new_forms: data.set("new_forms", new_forms)
            if data.get("forms") != forms: data.set("forms", forms)
            time.sleep(cycle_delay)

    Thread(target=endless_loop, daemon=True).start()

async def on_new_message(fpbot: 'FunPayBot', event: NewMessageEvent):
    try:
        this_chat = fpbot.funpay_account.get_chat_by_name(event.message.chat_name, True)
        if event.message.text is None:
            return
        if event.message.author == this_chat.name:
            await handle_new_form(fpbot, event)
            await handle_cmds(fpbot, event)
    except Exception:
        logger.error(f"{PREFIX} {Fore.LIGHTRED_EX}При обработке ивента новых сообщений произошла ошибка: {Fore.WHITE}")
        traceback.print_exc()