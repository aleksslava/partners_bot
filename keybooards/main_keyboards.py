from aiogram import Bot
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


async def reply_phone_number():  # Формирование инлайн клавиатуры запроса контакта пользователя
    first_button = KeyboardButton(text='Поделиться номером телефона', request_contact=True)
    markup = ReplyKeyboardMarkup(keyboard=[[first_button,]], resize_keyboard=True, one_time_keyboard=True)

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
                             callback_data=data) for data, text in commands.items() if data != '/start'
    ]
    kb_bl.row(*buttons, width=2)
    return kb_bl.as_markup()


async def forum_button(): # Формирование клавиатуры перехода на форум
    button = InlineKeyboardButton(
        text='Перейти на форум',
        url='https://t.me/+T7LVt_YYHDYwMzQy'
    )

    return InlineKeyboardMarkup(inline_keyboard=[[button]])


async def manager_button():  # Формирование клавиатуры для связи с менеджером
    button_whatsapp = InlineKeyboardButton(
        text="🟢 WhatsApp",
        url='https://wa.me/79251930861'
    )
    button_telegram = InlineKeyboardButton(
        text='🔵 Telegram',
        url='https://t.me/+79251930861'
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[button_whatsapp], [button_telegram]])
    return markup

async def support_button(): # Формирование клавиатуры для связи с тех. поддержкой
    button = InlineKeyboardButton(
        text="🟢 WhatsApp",
        url='https://wa.me/79251894560'
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])
    return markup

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