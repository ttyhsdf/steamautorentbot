# FunPay Universal
Современный бот-помощник для FunPay 🤖🟦

## 🧭 Навигация:
- [Функционал бота](#-функционал)
- [Установка бота](#%EF%B8%8F-установка)
- [Полезные ссылки](#-полезные-ссылки)
- [Для разработчиков](#-для-разработчиков)

## ⚡ Функционал
- Система модулей
- Удобный Telegram бот для настройки бота (используется aiogram 3.10.0):
  - Удобная настройка всех конфигов бота
- Функционал:
  - Вечный онлайн на сайте
  - Автоматическое поднятие лотов
  - Приветственное сообщение
  - Возможность добавления пользовательских команд
  - Возможность добавления пользовательской автовыдачи на лоты
  - Автоматические ответы на отзывы
  - Команда `!продавец` для вызова продавца (уведомляет вас в Telegram боте, что покупателю требуется помощь)
  - Авто-создание тикетов в тех. поддержку на закрытие заказов (бот каждые 24 часа создвёт тикеты на закрытие неподтверждённых заказов)
  - Логгирование ивентов FunPay в Telegram чат (новые сообщения, новые заказы, новые отзывы и т.д.)

## ⬇️ Установка
1. Скачайте [последнюю Release версию](https://github.com/alleexxeeyy/funpay-universal/releases/latest) и распакуйте в любое удобное для вас место
2. Убедитесь, что у вас установлен **Python версии 3.x.x - 3.12.x** (**ни в коем случае не устанавливайте версию 3.13.x**, на ней работать не будет). Если не установлен, сделайте это, перейдя по ссылке https://www.python.org/downloads/release/python-31210/ (при установке нажмите на пункт `Add to PATH`)
3. Откройте `install_requirements.bat` и дождитесь установки всех необходимых для работы библиотек, а после закройте окно
4. Чтобы запустить бота, откройте запускатор `start.bat`
5. После первого запуска вас попрсят настроить бота для работы

Если при установке у вас возникла проблема, попробуйте найти её решение [здесь](https://telegra.ph/FunPay-Universal--chastye-oshibki-i-ih-resheniya-08-26)

## 📚 Для разработчиков

Модульная система помогает внедрять в бота дополнительный функционал, сделанный энтузиастами. По сути, это же, что и плагины, но в более удобном формате.

<details>
  <summary><strong>📌 Основные ивенты</strong></summary>

  ### Ивенты бота (BOT_EVENT_HANDLERS)

  Ивенты, которые выполняются при определённом действии бота.

  | Ивент | Когда вызывается | Передающиеся аргументы |
  |-------|------------------|------------------------|
  | `ON_MODULE_CONNECTED` | При подключении модуля | `Module` |
  | `ON_MODULE_ENABLED` | При включении модуля | `Module` |
  | `ON_MODULE_DISABLED` | При выключении модуля | `Module` |
  | `ON_MODULE_RELOADED` | При перезагрузке модуля | `Module` |
  | `ON_INIT` | При инициализации бота | `-` |
  | `ON_FUNPAY_BOT_INIT` | При инициализации (запуске) FunPay бота | `FunPayBot` |
  | `ON_TELEGRAM_BOT_INIT` | При инициализации (запуске) Telegram бота | `TelegramBot` |

  ### Ивенты FunPay (FUNPAY_EVENT_HANDLERS)

  Ивенты, которые выполняются при получении ивента в раннере FunPay бота.

  | Ивент | Когда вызывается | Передающиеся аргументы |
  |-------|------------------|------------------------|
  | `EventTypes.CHATS_LIST_CHANGED` | Список чатов и/или последнее сообщение одного/нескольких чатов изменилось | `FunPayBot`, `ChatsListChangedEvent` |
  | `EventTypes.INITIAL_CHAT` | Обнаружен чат (при первом запросе Runner'а) | `FunPayBot`, `InitialChatEvent` |
  | `EventTypes.INITIAL_ORDER` | Обнаружен заказ (при первом запросе Runner'а) | `FunPayBot`, `InitialOrderEvent` |
  | `EventTypes.LAST_CHAT_MESSAGE_CHANGED` | В чате изменилось последнее сообщение. | `FunPayBot`, `LastChatMessageChangedEvent` |
  | `EventTypes.NEW_MESSAGE` | Обнаружено новое сообщение в истории чата | `FunPayBot`, `NewMessageEvent` |
  | `EventTypes.NEW_ORDER` | Обнаружен новый заказ | `FunPayBot`, `NewOrderEvent` |
  | `EventTypes.ORDER_STATUS_CHANGED` | Статус заказа изменился | `FunPayBot`, `OrderStatusChangedEvent` |
  | `EventTypes.ORDERS_LIST_CHANGED` | Список заказов и/или статус одного/нескольких заказов изменился | `FunPayBot`, `OrdersListChangedEvent` |

</details>

<details>
  <summary><strong>📁 Строение модуля</strong></summary>  
  
  </br>Модуль - это папка, внутри которой находятся важные компоненты. Вы можете изучить строение модуля, опираясь на [шаблонный модуль](.templates/forms_module), но стоит понимать, что это лишь пример, сделанный нами.

  Строение модуля может быть абсолютно любым на ваше усмотрение, но всё же в каждом модуля должен быть обязательный файл инициализации **`__init__.py`**, в котором задаются все основные параметры для корректной
  работы модуля.

  Обязательные константы хендлеров:
  | Константа | Тип | Описание |
  |-----------|-----|----------|
  | `BOT_EVENT_HANDLERS` | `dict[str, list[Any]]` | В этом словаре задаются хендлеры ивентов бота |
  | `FUNPAY_EVENT_HANDLERS` | `dict[EventTypes, list[Any]` | В этом словаре задаются хендлеры ивентов FunPay |
  | `TELEGRAM_BOT_ROUTERS` | `list[Router]` | В этом массиве задаются роутеры модульного Telegram бота  |

  Обязательные константы метаданных:
  | Константа | Тип | Описание |
  |-----------|-----|----------|
  | `PREFIX` | `str` | Префикс |
  | `VERSION` | `str` | Версия |
  | `NAME` | `str` | Название |
  | `DESCRIPTION` | `str` | Описание |
  | `AUTHORS` | `str` | Авторы |
  | `LINKS` | `str` | Ссылки на авторов |

  Также, если модуль требует дополнительных зависимостей, в нём должен быть файл зависимостей **requirements.txt**, которые будут сами скачиваться при загрузке всех модулей бота.

  #### 🔧 Пример содержимого:
  Обратите внимание, что метаданные были вынесены в отдельный файл `meta.py`, но импортируются в `__init__.py`.
  Это сделано для избежания конфликтов импорта в дальнейшей части кода модуля.

  `meta.py`:
  ```python
  from colorama import Fore, Style

  PREFIX = f"{Fore.LIGHTCYAN_EX}[test module]{Fore.WHITE}"
  VERSION = "1.0"
  NAME = "test_module"
  DESCRIPTION = "Тестовый модуль. /test_module в Telegram боте для управле!мояанкетания"
  AUTHORS = "@alleexxeeyy"
  LINKS = "https://t.me/alleexxeeyy, https://t.me/alexeyproduction"
  ```

  `__init__.py`:
  ```python
  from .fpbot.handlers import on_funpay_bot_init, on_new_message, on_new_order
  from .tgbot._handlers import on_telegram_bot_init
  from .tgbot import router
  from .meta import *
  from FunPayAPI.updater.events import EventTypes
  from core.modules_manager import disable_module, Module
  

  _module: Module = None

  def set_module(new: Module):
      global _module
      _module = new

  def get_module():
      return _module
  
  def on_module_connected():
      try:
          set_module(module)
          print(f"{PREFIX} Модуль подключен и активен")
      except:
          disable_module(_module.uuid)
  
  BOT_EVENT_HANDLERS = {
      "ON_MODULE_CONNECTED": [on_module_connected],
      "ON_FUNPAY_BOT_INIT": [on_funpay_bot_init],
      "ON_TELEGRAM_BOT_INIT": [on_telegram_bot_init]
  }
  FUNPAY_EVENT_HANDLERS = {
      EventTypes.NEW_MESSAGE: [on_new_message],
      EventTypes.NEW_ORDER: [on_new_order]
  }
  TELEGRAM_BOT_ROUTERS = [router]
  ```

</details>

<details>
  <summary><strong>❗ Примечания</strong></summary>

  </br>Функционал Telegram бота написан на библиотеке aiogram 3, система внедрения пользовательского функционала Telegram бота работает на основе роутеров, которые сливаются с основным, главным роутером бота.
  И так, как они сливаются воедино, могут возникнуть осложнения, если, например Callback данные имеют идентичное название. Поэтому, после написания функционала Telegram бота для модуля, лучше переименуйте
  эти данные уникальным образом, чтобы они не совпадали с названиями основного бота или дополнительных подключаемых модулей.

</details>


## 🔗 Полезные ссылки
- Разработчик: https://github.com/alleexxeeyy (в профиле есть актуальные ссылки на все контакты для связи)
- Telegram канал: https://t.me/alexeyproduction
- Telegram бот для покупки официальных модулей: https://t.me/alexey_production_bot

## ПРИМЕЧАНИЯ
Бот написан на основе библиотеки https://github.com/LIMBODS/FunPayAPI, которая была сделана **не мной**, а другими энтузиастами.
