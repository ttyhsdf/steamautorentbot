# Standard library imports
import random
import time
import asyncio
import sqlite3
import threading
import re
from datetime import datetime, timedelta

# Third-party imports
from FunPayAPI import Account, Runner, types, enums, events

# Project-specific imports
from config import FUNPAY_GOLDEN_KEY, ADMIN_ID, HOURS_FOR_REVIEW

from databaseHandler.databaseSetup import SQLiteDB
from steamHandler.SteamGuard import get_steam_guard_code
from steamHandler.changePassword import changeSteamPassword
from steamHandler.auto_guard import start_auto_guard, send_welcome_guard_code, get_auto_guard_stats
from messaging.message_sender import initialize_message_sender, send_message_by_owner
from logger import logger
from pytz import timezone


TOKEN = FUNPAY_GOLDEN_KEY
REFRESH_INTERVAL = 1300  # 30 minutes in seconds

feedbackGiven = []

moscow_tz = timezone("Europe/Moscow")

db = SQLiteDB()


def refresh_session():
    global acc, runner
    logger.info("Refreshing FunPay session...")
    acc = Account(TOKEN).get()
    runner = Runner(acc)
    logger.info("FunPay session refreshed successfully.")


def check_rental_expiration():
    """Checks for expired rentals and changes passwords every minute"""
    while True:
        try:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            
            # Get all accounts with active rentals
            cursor.execute("""
                SELECT id, account_name, login, password, rental_duration, rental_start, owner
                FROM accounts 
                WHERE owner IS NOT NULL AND rental_start IS NOT NULL
            """)
            
            active_rentals = cursor.fetchall()
            
            for rental in active_rentals:
                account_id, account_name, login, password, rental_duration, rental_start, owner = rental
                
                # Check if rental has expired
                start_time = datetime.fromisoformat(rental_start)
                end_time = start_time + timedelta(hours=rental_duration)
                
                if datetime.now() >= end_time:
                    logger.info(f"Rental expired for account {account_name} (owner: {owner})")
                    
                    # Change password
                    try:
                        cursor.execute("SELECT path_to_maFile FROM accounts WHERE id = ?", (account_id,))
                        mafile_result = cursor.fetchone()
                        
                        if mafile_result:
                            mafile_path = mafile_result[0]
                            new_password = asyncio.run(changeSteamPassword(mafile_path, password))
                            
                            # Update password in database
                            cursor.execute(
                                "UPDATE accounts SET password = ? WHERE id = ?",
                                (new_password, account_id)
                            )
                            
                            logger.info(f"Password changed for expired account {account_name}")
                            
                    except Exception as e:
                        logger.error(f"Error changing password for account {account_id}: {str(e)}")
                    
                    # Clear owner and rental_start
                    cursor.execute(
                        "UPDATE accounts SET owner = NULL, rental_start = NULL WHERE id = ?",
                        (account_id,)
                    )
                    
                    # Деактивируем активность покупателя
                    db.deactivate_customer_activity(owner, account_id)
                    
                    logger.info(f"Account {account_name} released from {owner}")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error in rental expiration checker: {str(e)}")

        time.sleep(60)  # Check every 60 seconds (1 minute)


def startFunpay():
    global acc, runner

    try:
        logger.info("Starting FunPay bot...")
        
        # Проверяем токен
        if not TOKEN or TOKEN.strip() == "":
            logger.error("FunPay Golden Key не задан!")
            print("❌ Ошибка: FUNPAY_GOLDEN_KEY не задан в config.py")
            return
        
        acc = Account(TOKEN).get()
        runner = Runner(acc)
        logger.info("FunPay account and runner initialized.")
        
        # Инициализируем отправитель сообщений
        initialize_message_sender(acc)
        logger.info("Message sender initialized.")
        
        last_refresh = time.time()

        logger.info("Starting rental expiration checker thread...")

        timerChecker_thread = threading.Thread(target=check_rental_expiration, daemon=True)
        timerChecker_thread.start()

        # Запускаем автоматическую систему выдачи Steam Guard кодов
        logger.info("Starting AutoGuard system...")
        start_auto_guard()

        logger.info("FunPay bot started successfully. Listening for events...")

        for event in runner.listen(requests_delay=8):
            try:
                global send_message_by_owner
                current_time = time.time()
                if current_time - last_refresh >= REFRESH_INTERVAL:
                    logger.info("Refreshing session due to interval timeout...")
                    refresh_session()
                    last_refresh = current_time

                def send_message_by_owner(owner, message):
                    try:
                        chat = acc.get_chat_by_name(owner, True)
                        acc.send_message(chat.id, message)
                    except Exception as e:
                        logger.error(f"Failed to send message to {owner}: {str(e)}")

                # Отладочная информация о типе события
                logger.debug(f"Получено событие: {event.type}", extra_info=f"Event type: {event.type}")
                
                # Обработка различных типов событий
                if hasattr(events.EventTypes, 'INITIAL_CHAT') and event.type is events.EventTypes.INITIAL_CHAT:
                    logger.debug("🔄 Инициализация чата", extra_info="Initializing chat connection")
                    # Это нормальное событие при подключении к FunPay
                    
                elif hasattr(events.EventTypes, 'NEW_ORDER') and event.type is events.EventTypes.NEW_ORDER:
                    logger.info("🛒 Обработка нового заказа", extra_info=f"Order ID: {event.order.id}")
                    
                    # Логируем детали заказа
                    logger.new_order(
                        event.order.id, 
                        event.order.buyer_username, 
                        event.order.amount, 
                        event.order.price
                    )

                    accounts = db.get_unowned_accounts()

                    acc = Account(TOKEN).get()
                    chat = acc.get_chat_by_name(event.order.buyer_username, True)

                    all_accounts = db.get_all_account_names()

                    order_name = event.order.description
                    number_of_orders = event.order.amount

                    logger.debug(f"Название заказа: {order_name}", extra_info="Original order name")

                    cleaned_order_name = re.sub(r"[^\w\s]", " ", order_name)
                    cleaned_order_name = " ".join(cleaned_order_name.split())
                    logger.debug(f"Очищенное название: {cleaned_order_name}", extra_info="Cleaned order name")

                    matched_account = None
                    max_similarity = 0

                    for account in all_accounts:
                        cleaned_account = re.sub(r"[^\w\s]", " ", account)
                        cleaned_account = " ".join(cleaned_account.split())

                        if cleaned_account.lower() in cleaned_order_name.lower():
                            similarity = len(cleaned_account)
                            if similarity > max_similarity:
                                max_similarity = similarity
                                matched_account = account

                    if matched_account:
                        logger.info(f"✅ Найден подходящий аккаунт: {matched_account}", extra_info="Account matched successfully")

                        available_accounts = [
                            acc for acc in accounts if acc["account_name"] == matched_account
                        ]

                        if len(available_accounts) >= number_of_orders:
                            logger.info(f"📦 Найдено {len(available_accounts)} доступных аккаунтов для {matched_account}", 
                                      extra_info=f"Available: {len(available_accounts)}, Required: {number_of_orders}")

                            selected_accounts = available_accounts[:number_of_orders]

                            for i, account in enumerate(selected_accounts):
                                try:
                                    # Set owner and rental start time
                                    db.set_account_owner(account["id"], event.order.buyer_username)
                                    
                                    # Логируем выдачу аккаунта
                                    logger.account_assigned(account["id"], event.order.buyer_username, account['account_name'])
                                    
                                    # Логируем покупку покупателя
                                    db.log_customer_purchase(
                                        event.order.buyer_username,
                                        account["id"],
                                        account['account_name'],
                                        account['rental_duration']
                                    )

                                    # Send account confirmation to buyer (without credentials)
                                    message = (
                                        f"✅ **Аккаунт #{i+1} успешно зарезервирован!**\n\n"
                                        f"📝 **Уникальный ID:** `{account['id']}`\n"
                                        f"🔑 **Название:** `{account['account_name']}`\n"
                                        f"⏱ **Срок аренды:** {account['rental_duration']} часов\n\n"
                                        f"🔐 **Для получения данных аккаунта отправьте команду:**\n"
                                        f"`/get_account {account['id']}`\n\n"
                                        f"📋 **Доступные команды:**\n"
                                        f"• `/get_account {account['id']}` - получить данные аккаунта (максимум 3 раза)\n"
                                        f"• `/code` - запросить код подтверждения\n"
                                        f"• `/question` - задать вопрос\n\n"
                                        f"⚠️ **ВАЖНО:**\n"
                                        f"• Данные аккаунта можно получить только 3 раза за аренду\n"
                                        f"• После истечения аренды доступ будет заблокирован\n"
                                        f"• За отзыв получите +{HOURS_FOR_REVIEW} час аренды\n\n"
                                        f"------------------------------------------------------------------------------"
                                    )

                                    send_message_by_owner(event.order.buyer_username, message)
                                    logger.debug(f"Сообщение отправлено пользователю {event.order.buyer_username}", 
                                               extra_info=f"Account ID: {account['id']}")
                                    
                                    # Автоматически отправляем Steam Guard код при покупке
                                    try:
                                        success = send_welcome_guard_code(
                                            account['id'], 
                                            account['account_name'], 
                                            event.order.buyer_username, 
                                            account['path_to_maFile']
                                        )
                                        if success:
                                            logger.info(f"Welcome guard code sent to {event.order.buyer_username} for {account['account_name']}")
                                        else:
                                            logger.warning(f"Failed to send welcome guard code to {event.order.buyer_username} for {account['account_name']}")
                                    except Exception as guard_error:
                                        logger.error(f"Error sending welcome guard code: {str(guard_error)}")

                                except Exception as e:
                                    logger.log_error("Account Assignment", f"Error assigning account {account['id']}: {str(e)}", 
                                                   f"Buyer: {event.order.buyer_username}, Account: {account['account_name']}")

                        else:
                            logger.warning(f"Not enough available accounts for {matched_account}")
                            send_message_by_owner(
                                event.order.buyer_username,
                                f"Извините, в данный момент нет доступных аккаунтов для '{matched_account}'. Попробуйте позже."
                            )
                    else:
                        logger.warning(f"No matching account found for order: {order_name}")
                        send_message_by_owner(
                            event.order.buyer_username,
                            f"Извините, не удалось найти подходящий аккаунт для заказа '{order_name}'. Обратитесь к администратору."
                        )

                elif hasattr(events.EventTypes, 'ORDER_PAID') and event.type is events.EventTypes.ORDER_PAID:
                    logger.log_order_paid(event.order.id, event.order.buyer_username, event.order.amount, event.order.price)
                    # Заказ оплачен - можно выдавать аккаунт
                    
                elif hasattr(events.EventTypes, 'ORDER_CONFIRMED') and event.type is events.EventTypes.ORDER_CONFIRMED:
                    logger.log_order_confirmed(event.order.id, event.order.buyer_username)
                    # Заказ подтвержден - аккаунт выдан
                    
                elif hasattr(events.EventTypes, 'ORDER_REFUNDED') and event.type is events.EventTypes.ORDER_REFUNDED:
                    reason = getattr(event, 'reason', 'Unknown')
                    logger.log_order_refunded(event.order.id, event.order.buyer_username, reason)
                    # Заказ возвращен - нужно освободить аккаунт
                    
                elif hasattr(events.EventTypes, 'NEW_MESSAGE') and event.type is events.EventTypes.NEW_MESSAGE:
                    logger.info("Processing new message event...")

                    conn = sqlite3.connect("database.db")
                    cursor = conn.cursor()

                    try:
                        sender_username = event.message.chat.name
                        message_text = event.message.text

                        logger.info(f"Message from {sender_username}: {message_text}")

                        # Check if user has active rentals
                        cursor.execute(
                            """
                            SELECT id, account_name, login, password, rental_duration, rental_start
                            FROM accounts 
                            WHERE owner = ? AND rental_start IS NOT NULL
                            """,
                            (sender_username,)
                        )

                        user_accounts = cursor.fetchall()

                        if user_accounts:
                            if message_text == "/code":
                                # Send Steam Guard code
                                for account in user_accounts:
                                    account_id, account_name, login, password, rental_duration, rental_start = account
                                    
                                    try:
                                        # Get maFile path
                                        cursor.execute(
                                            "SELECT path_to_maFile FROM accounts WHERE id = ?",
                                            (account_id,)
                                        )
                                        mafile_result = cursor.fetchone()
                                        
                                        if mafile_result:
                                            mafile_path = mafile_result[0]
                                            guard_code = get_steam_guard_code(mafile_path)
                                            
                                            if guard_code:
                                                send_message_by_owner(
                                                    sender_username,
                                                    f"🔐 Код подтверждения для аккаунта {account_name}:\n`{guard_code}`"
                                                )
                                            else:
                                                send_message_by_owner(
                                                    sender_username,
                                                    f"❌ Не удалось получить код подтверждения для аккаунта {account_name}"
                                                )
                                    except Exception as e:
                                        logger.error(f"Error getting guard code for account {account_id}: {str(e)}")
                                        send_message_by_owner(
                                            sender_username,
                                            f"❌ Ошибка при получении кода подтверждения для аккаунта {account_name}"
                                        )

                            elif message_text.startswith("/get_account "):
                                # Handle get_account command
                                try:
                                    account_id_str = message_text.split()[1]
                                    account_id = int(account_id_str)
                                    
                                    # Check if user can access this account
                                    access_check = db.can_access_account(account_id, sender_username)
                                    
                                    if not access_check["can_access"]:
                                        reason = access_check["reason"]
                                        send_message_by_owner(
                                            sender_username,
                                            f"❌ **Доступ к аккаунту {account_id} запрещен**\n\n"
                                            f"**Причина:** {reason}\n\n"
                                            f"💡 Проверьте правильность ID аккаунта или обратитесь к администратору."
                                        )
                                    else:
                                        # Get account details
                                        cursor.execute(
                                            """
                                            SELECT account_name, login, password, rental_duration, access_count, max_access_count
                                            FROM accounts 
                                            WHERE id = ? AND owner = ?
                                            """,
                                            (account_id, sender_username)
                                        )
                                        account_data = cursor.fetchone()
                                        
                                        if account_data:
                                            account_name, login, password, rental_duration, access_count, max_access_count = account_data
                                            
                                            # Increment access count
                                            increment_result = db.increment_access_count(account_id, sender_username)
                                            
                                            if increment_result["success"]:
                                                new_access_count = increment_result["access_count"]
                                                remaining_access = max_access_count - new_access_count
                                                
                                                # Send account details
                                                message = (
                                                    f"🔐 **Данные аккаунта {account_name}**\n\n"
                                                    f"📝 **ID:** `{account_id}`\n"
                                                    f"👤 **Логин:** `{login}`\n"
                                                    f"🔑 **Пароль:** `{password}`\n"
                                                    f"⏱ **Срок аренды:** {rental_duration} часов\n\n"
                                                    f"📊 **Статистика доступа:**\n"
                                                    f"• Использовано: {new_access_count}/{max_access_count}\n"
                                                    f"• Осталось попыток: {remaining_access}\n\n"
                                                    f"⚠️ **Внимание:** Данные можно получить только {max_access_count} раз за аренду!\n"
                                                    f"🔄 Для получения кода подтверждения отправьте `/code`"
                                                )
                                                
                                                send_message_by_owner(sender_username, message)
                                                
                                                # Логируем доступ к данным аккаунта
                                                db.log_customer_access(sender_username, account_id)
                                                
                                                logger.info(f"Account data sent to {sender_username} for account {account_id} (access {new_access_count}/{max_access_count})")
                                            else:
                                                send_message_by_owner(
                                                    sender_username,
                                                    f"❌ Ошибка при обновлении счетчика доступа для аккаунта {account_id}"
                                                )
                                        else:
                                            send_message_by_owner(
                                                sender_username,
                                                f"❌ Аккаунт с ID {account_id} не найден или не принадлежит вам"
                                            )
                                            
                                except (ValueError, IndexError):
                                    send_message_by_owner(
                                        sender_username,
                                        "❌ **Неверный формат команды**\n\n"
                                        "Используйте: `/get_account <ID_аккаунта>`\n"
                                        "Пример: `/get_account 123`"
                                    )
                                except Exception as e:
                                    logger.error(f"Error processing get_account command: {str(e)}")
                                    send_message_by_owner(
                                        sender_username,
                                        f"❌ Ошибка при обработке команды: {str(e)}"
                                    )

                            elif message_text == "/my_accounts":
                                # Show user's accounts with access info
                                try:
                                    accounts_info = []
                                    for account in user_accounts:
                                        account_id, account_name, login, password, rental_duration, rental_start = account
                                        
                                        # Get access info
                                        access_info = db.get_account_access_info(account_id)
                                        if access_info:
                                            access_count = access_info["access_count"]
                                            max_access_count = access_info["max_access_count"]
                                            remaining = max_access_count - access_count
                                            
                                            accounts_info.append(
                                                f"🔑 **{account_name}** (ID: {account_id})\n"
                                                f"⏱ Аренда: {rental_duration}ч | 📊 Доступ: {access_count}/{max_access_count} (осталось: {remaining})\n"
                                                f"💡 Команда: `/get_account {account_id}`\n"
                                            )
                                    
                                    if accounts_info:
                                        message = (
                                            f"📋 **Ваши аккаунты** ({len(accounts_info)} шт.)\n\n" +
                                            "\n".join(accounts_info) +
                                            f"\n💡 **Используйте команду `/get_account <ID>` для получения данных**"
                                        )
                                    else:
                                        message = "❌ У вас нет активных аккаунтов"
                                    
                                    send_message_by_owner(sender_username, message)
                                    
                                except Exception as e:
                                    logger.error(f"Error showing user accounts: {str(e)}")
                                    send_message_by_owner(
                                        sender_username,
                                        f"❌ Ошибка при получении списка аккаунтов: {str(e)}"
                                    )

                            elif message_text == "/question":
                                # Forward question to admin
                                admin_message = f"❓ Вопрос от {sender_username}:\n\n{message_text}"
                                # You can implement admin notification here
                                logger.info(f"Question from {sender_username}: {message_text}")

                            else:
                                # Regular message - forward to admin
                                admin_message = f"💬 Сообщение от {sender_username}:\n\n{message_text}"
                                # You can implement admin notification here
                                logger.info(f"Message from {sender_username}: {message_text}")

                        else:
                            # User has no active rentals
                            send_message_by_owner(
                                sender_username,
                                "❌ **У вас нет активных аренд**\n\n"
                                "💡 **Доступные команды:**\n"
                                "• `/my_accounts` - показать ваши аккаунты\n"
                                "• `/get_account <ID>` - получить данные аккаунта\n"
                                "• `/code` - запросить код подтверждения\n"
                                "• `/question` - задать вопрос\n\n"
                                "🛒 **Для получения аккаунта сначала совершите покупку на FunPay**"
                            )

                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}")
                    finally:
                        conn.close()

                elif hasattr(events.EventTypes, 'CHAT_OPENED') and event.type is events.EventTypes.CHAT_OPENED:
                    logger.log_chat_opened(event.chat.name)
                    # Чат открыт - пользователь начал общение
                    
                elif hasattr(events.EventTypes, 'CHAT_CLOSED') and event.type is events.EventTypes.CHAT_CLOSED:
                    logger.log_chat_closed(event.chat.name)
                    # Чат закрыт - общение завершено
                    
                elif hasattr(events.EventTypes, 'LOT_UPDATE') and event.type is events.EventTypes.LOT_UPDATE:
                    logger.log_lot_updated(event.lot.name, "Updated")
                    # Лот обновлен - обновляем информацию о доступности
                    
                elif hasattr(events.EventTypes, 'NEW_FEEDBACK') and event.type is events.EventTypes.NEW_FEEDBACK:
                    logger.log_feedback_received(event.feedback.author, event.feedback.rating, event.feedback.text)
                    # Новый отзыв - продлеваем аренду на +1 час
                    
                    try:
                        # Получаем информацию об отзыве
                        reviewer_username = event.feedback.author
                        rating = event.feedback.rating
                        review_text = event.feedback.text
                        
                        logger.info(f"Processing feedback from {reviewer_username}, rating: {rating}")
                        
                        # Ищем активную аренду для этого пользователя
                        cursor = db.conn.cursor()
                        cursor.execute(
                            """
                            SELECT id, account_name, rental_duration, rental_start
                            FROM accounts 
                            WHERE owner = ? AND rental_start IS NOT NULL
                            ORDER BY rental_start DESC
                            LIMIT 1
                            """,
                            (reviewer_username,)
                        )
                        
                        active_rental = cursor.fetchone()
                        
                        if active_rental:
                            account_id, account_name, current_duration, rental_start = active_rental
                            
                            # Продлеваем аренду на HOURS_FOR_REVIEW часов
                            success = db.extend_rental_duration(account_id, HOURS_FOR_REVIEW)
                            
                            if success:
                                # Логируем отзыв покупателя
                                db.log_customer_feedback(
                                    reviewer_username,
                                    account_id,
                                    rating,
                                    review_text
                                )
                                
                                # Логируем продление аренды
                                db.log_rental_extension(
                                    reviewer_username,
                                    account_id,
                                    HOURS_FOR_REVIEW
                                )
                                
                                # Получаем обновленную информацию об аккаунте
                                cursor.execute(
                                    "SELECT rental_duration FROM accounts WHERE id = ?",
                                    (account_id,)
                                )
                                new_duration = cursor.fetchone()[0]
                                
                                # Отправляем уведомление пользователю
                                message = (
                                    f"🎉 **Спасибо за отзыв!**\n\n"
                                    f"✅ **Ваша аренда продлена на +{HOURS_FOR_REVIEW} час!**\n\n"
                                    f"📝 **Аккаунт:** {account_name}\n"
                                    f"⏱ **Новый срок аренды:** {new_duration} часов\n"
                                    f"⭐ **Рейтинг отзыва:** {rating}/5\n\n"
                                    f"💡 **Ваш отзыв:** {review_text}\n\n"
                                    f"🎮 **Удачной игры!**"
                                )
                                
                                send_message_by_owner(reviewer_username, message)
                                
                                logger.info(f"Rental extended for {reviewer_username} by {HOURS_FOR_REVIEW} hours", 
                                          extra_info=f"Account: {account_name}, New duration: {new_duration}")
                                
                                # Уведомляем администратора
                                admin_message = (
                                    f"📝 **Новый отзыв получен!**\n\n"
                                    f"👤 **Пользователь:** {reviewer_username}\n"
                                    f"⭐ **Рейтинг:** {rating}/5\n"
                                    f"💬 **Отзыв:** {review_text}\n"
                                    f"🎯 **Аккаунт:** {account_name}\n"
                                    f"⏱ **Продлено на:** +{HOURS_FOR_REVIEW} час\n"
                                    f"📊 **Новый срок:** {new_duration} часов"
                                )
                                
                                send_message_by_owner("admin", admin_message)
                                
                            else:
                                logger.warning(f"Failed to extend rental for {reviewer_username}")
                                send_message_by_owner(
                                    reviewer_username,
                                    f"❌ **Ошибка при продлении аренды**\n\n"
                                    f"Спасибо за отзыв, но произошла ошибка при продлении аренды. "
                                    f"Обратитесь к администратору."
                                )
                        else:
                            logger.info(f"No active rental found for reviewer {reviewer_username}")
                            send_message_by_owner(
                                reviewer_username,
                                f"📝 **Спасибо за отзыв!**\n\n"
                                f"⭐ **Рейтинг:** {rating}/5\n"
                                f"💬 **Отзыв:** {review_text}\n\n"
                                f"ℹ️ **Примечание:** У вас нет активной аренды для продления, "
                                f"но мы ценим ваш отзыв!"
                            )
                        
                        cursor.close()
                        
                    except Exception as e:
                        logger.error(f"Error processing feedback: {str(e)}")
                        # Отправляем уведомление об ошибке администратору
                        try:
                            send_message_by_owner(
                                "admin",
                                f"❌ **Ошибка обработки отзыва**\n\n"
                                f"**Автор:** {event.feedback.author}\n"
                                f"**Рейтинг:** {event.feedback.rating}\n"
                                f"**Ошибка:** {str(e)}"
                            )
                        except:
                            pass
                    
                else:
                    # Неизвестный или необрабатываемый тип события
                    event_name = str(event.type).split('.')[-1] if '.' in str(event.type) else str(event.type)
                    
                    # Логируем только важные неизвестные события
                    if event_name not in ['INITIAL_CHAT', 'HEARTBEAT', 'PING', 'PONG']:
                        logger.debug(f"Неизвестное событие: {event_name}", extra_info=f"Event type: {event.type}")
                    else:
                        # Для служебных событий используем более низкий уровень логирования
                        logger.debug(f"Служебное событие: {event_name}", extra_info="Service event")

                logger.info("Event processed successfully.")

            except Exception as e:
                logger.error(f"An error occurred while processing event: {str(e)}")
    
    except Exception as e:
        logger.error(f"Critical error in startFunpay: {str(e)}")
        print(f"❌ Критическая ошибка FunPay: {str(e)}")
        raise


