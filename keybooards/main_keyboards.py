from aiogram import Bot
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


async def reply_phone_number():  # Формирование инлайн клавиатуры запроса контакта пользователя
    first_button = KeyboardButton(text='Отправить номер телефона', request_contact=True)
    markup = ReplyKeyboardMarkup(is_persistent=True, keyboard=[[first_button,]], resize_keyboard=True,
                                 one_time_keyboard=False, )

    return markup


async def set_main_menu(bot: Bot, commands: dict):  # Главная клавиатура бота

    main_menu_commands = [
        BotCommand(command=command,
                   description=description) for command, description in commands.items()
    ]
    await bot.set_my_commands(main_menu_commands)



async def get_contacts_list(customer_id): # Формирование кнопки раскрытия списка контактов партнёра
    button = InlineKeyboardButton(text='Список связанных контактов', callback_data=f'contacts_list_{customer_id}')
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])

    return markup


async def hide_contacts_list(customer_id): # Формирование кнопки скрытия списка контактов партнёра
    button = InlineKeyboardButton(text='Скрыть список конактов', callback_data=f'hide_contacts_list_{customer_id}')
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])

    return markup


# Главная inline клавиатура
async def get_start_keyboard(commands: dict): # Формирование главной инлайн клавиатуры
    kb_bl = InlineKeyboardBuilder()
    buttons: list = [
        InlineKeyboardButton(text=text,
                             callback_data=data) for data, text in commands.items() if data not in ['/start', '/new_shop']
    ]
    kb_bl.row(*buttons, width=2)
    return kb_bl.as_markup()

async def authorized_client(commands: dict):
    kb_bl = InlineKeyboardBuilder()
    buttons: list = [
        InlineKeyboardButton(text=text,
                             callback_data=data) for data, text in commands.items() if data in ['/shop', '/info']
    ]
    kb_bl.row(*buttons, width=2)
    return kb_bl.as_markup()

async def link_to_opt_button(lead_id):
    button_telegram = InlineKeyboardButton(
        text='🔵 Сообщить о заказе в telegram',
        url=f'https://t.me/+79251930861?text=%D0%97%D0%B4%D1%80%D0%B0%D0%B2%D1%81%D1%82%D0%B2%D1%83%D0%B9%D1%82%D0%B5!%20%D0%AF%20%D0%BE%D1%84%D0%BE%D1%80%D0%BC%D0%B8%D0%BB%20%D0%B7%D0%B0%D0%BA%D0%B0%D0%B7%20%E2%84%96%7B{lead_id}%7D%20%D1%87%D0%B5%D1%80%D0%B5%D0%B7%20%D0%9A%D0%B0%D0%B1%D0%B8%D0%BD%D0%B5%D1%82%20%D0%BF%D0%B0%D1%80%D1%82%D0%BD%D0%B5%D1%80%D0%B0%20%D0%B2%20%D0%A2%D0%93.%20%D0%92%D1%8B%20%D0%B2%D0%B8%D0%B4%D0%B8%D1%82%D0%B5%20%D0%B7%D0%B0%D0%BA%D0%B0%D0%B7?'
    )

    return InlineKeyboardMarkup(inline_keyboard=[[button_telegram]])

async def forum_button(): # Формирование клавиатуры перехода на форум
    button_telegram = InlineKeyboardButton(
        text='Перейти на форум в telegram',
        url='https://t.me/+rZKO37Sn33NlNDdi'
    )
    button_max = InlineKeyboardButton(
        text='Перейти на форум в max',
        url='https://max.ru/join/woDgvK-CGSe5x9DKQ_rZLMGwf9mT_DvvLA6Cv__iq6U'
    )

    return InlineKeyboardMarkup(inline_keyboard=[[button_telegram], [button_max]])


async def manager_button():  # Формирование клавиатуры для связи с менеджером
    button_whatsapp = InlineKeyboardButton(
        text="🟢 WhatsApp",
        url='https://wa.me/79251930861'
    )
    button_telegram = InlineKeyboardButton(
        text='🔵 Telegram',
        url='https://t.me/+79251930861'
    )
    button_max = InlineKeyboardButton(
        text='🟣 MAX',
        url='https://max.ru/u/f9LHodD0cOLRJPZ-Vm5lXdFA6YvPYESWoU7_n6imsgqQorxD9nvTdH9pXxU'
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[button_whatsapp], [button_telegram], [button_max]])
    return markup

async def support_button(): # Формирование клавиатуры для связи с тех. поддержкой
    kb_bl = InlineKeyboardBuilder()
    button_whatsapp = InlineKeyboardButton(
        text="🟢 WhatsApp",
        url='https://wa.me/79251894560'
    )
    button_telegram = InlineKeyboardButton(
        text="🔵 Telegram",
        url='https://t.me/+79251894560'
    )
    button_MAX = InlineKeyboardButton(
        text="🟣 MAX",
        url='https://max.ru/u/f9LHodD0cOLgkmm1pw0Fy8nY2N3E9npARi6-3lC_qZ_FVzXQu8WdfUF0rGs'
    )
    buttons = [button_whatsapp, button_telegram, button_MAX]
    kb_bl.row(*buttons, width=1)
    return kb_bl.as_markup()

async def problem_button():  # Формирование клавиатуры для заполнения формы отзыва на бота
    button = InlineKeyboardButton(
        text='Заполнить форму',
        url='https://forms.gle/wnxcfdTsPpHtNCcy9'
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])
    return markup

async def helpfull_materials_keyboard(texts: dict):
    kb_bl = InlineKeyboardBuilder()
    buttons: list = [
        InlineKeyboardButton(text=text,
                             callback_data=data) for text, data in texts.items()
    ]
    kb_bl.row(*buttons, width=1)
    return kb_bl.as_markup()

async def back_button():
    button = InlineKeyboardButton(text='Назад',
                                  callback_data='back')
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])
    return markup

async def answer_for_user():  # Формирование клавиатуры для ответа на произвольное сообщение
    button_whatsapp_tp = InlineKeyboardButton(
        text="🟢 WhatsApp тех. поддержки",
        url='https://wa.me/79251894560'
    )
    button_telegram_opt = InlineKeyboardButton(
        text='🔵 Telegram партнёрский отдел',
        url='https://t.me/+79251930861'
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[button_whatsapp_tp], [button_telegram_opt]])
    return markup

async def confirm_spam(message_id: int):
    kb_bl = InlineKeyboardBuilder()
    buttons: list = [
        InlineKeyboardButton(text='Да',
                             callback_data=f'spamyes_{message_id}'),
        InlineKeyboardButton(text='Нет',
                             callback_data=f'spamno_{message_id}')
    ]
    kb_bl.row(*buttons, width=2)
    return kb_bl.as_markup()