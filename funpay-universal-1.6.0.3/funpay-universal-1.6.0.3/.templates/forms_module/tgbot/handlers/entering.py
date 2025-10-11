from aiogram import F, types, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext

from .. import templates as templ
from tgbot import templates as main_templ
from .. import states
from settings import Settings as main_sett
from ...settings import Settings as sett
from .. import callback_datas as calls

from fpbot.funpaybot import get_funpay_bot
from tgbot.helpful import throw_float_message

router = Router()



def is_int(txt) -> bool:
    try:
        int(txt)
        return True
    except ValueError:
        return False


@router.message(states.FORMS_MessagePageStates.entering_message_text, F.text)
async def handler_entering_message_text(message: types.Message, state: FSMContext):
    try:
        await state.set_state(None)
        if len(message.text.strip()) <= 0:
            raise Exception("❌ Слишком короткий текст")

        data = await state.get_data()
        messages = sett.get("messages")
        message_split_lines = message.text.strip().split('\n')
        messages[data["message_id"]]["text"] = message_split_lines
        sett.set("messages", messages)
        await throw_float_message(state=state,
                                  message=message,
                                  text=templ.settings_mess_page_float_text(f"✅ <b>Текст сообщения</b> <code>{data['message_id']}</code> был успешно изменён на <blockquote>{message.text.strip()}</blockquote>"),
                                  reply_markup=main_templ.back_kb(calls.FORMS_MessagePage(message_id=data.get("message_id")).pack()))
    except Exception as e:
        if e is not TelegramAPIError:
            data = await state.get_data()
            await throw_float_message(state=state,
                                      message=message,
                                      text=templ.settings_mess_page_float_text(e), 
                                      reply_markup=main_templ.back_kb(calls.FORMS_MessagePage(message_id=data.get("message_id")).pack()))

@router.message(states.FORMS_MessagesStates.entering_page, F.text)
async def handler_entering_messages_page(message: types.Message, state: FSMContext):
    try: 
        await state.set_state(None)
        if not is_int(message.text.strip()):
            raise Exception("❌ Вы должны ввести числовое значение")
        
        await state.update_data(last_page=int(message.text.strip())-1)
        await throw_float_message(state=state,
                                  message=message,
                                  text=templ.settings_mess_text(),
                                  reply_markup=main_templ.settings_mess_kb(int(message.text.strip())-1))
    except Exception as e:
        if e is not TelegramAPIError:
            data = await state.get_data()
            last_page = data.get("last_page") or 0
            await throw_float_message(state=state,
                                      message=message,
                                      text=main_templ.settings_mess_float_text(e),
                                      reply_markup=main_templ.back_kb(calls.FORMS_MessagesPagination(page=last_page).pack()))