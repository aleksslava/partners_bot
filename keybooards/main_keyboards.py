from aiogram import Bot
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


async def reply_phone_number():
    first_button = KeyboardButton(text='Поделиться номером телефона', request_contact=True)
    markup = ReplyKeyboardMarkup(keyboard=[[first_button,]], resize_keyboard=True, one_time_keyboard=True)

    return markup


async def set_main_menu(bot: Bot, commands: dict):

    # Главная клавиатура бота
    main_menu_commands = [
        BotCommand(command=command,
                   description=description) for command, description in commands.items()
    ]
    await bot.set_my_commands(main_menu_commands)


async def get_contacts_list(customer_id):
    button = InlineKeyboardButton(text='Список связанных контактов', callback_data=f'contacts_list_{customer_id}')
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])

    return markup


async def hide_contacts_list(customer_id):
    button = InlineKeyboardButton(text='Скрыть список конактов', callback_data=f'hide_contacts_list_{customer_id}')
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])

    return markup


# Главная inline клавиатура
async def get_start_keyboard(commands: dict):
    kb_bl = InlineKeyboardBuilder()
    buttons: list = [
        InlineKeyboardButton(text=text,
                             callback_data=data) for data, text in commands.items() if data != '/start'
    ]
    kb_bl.row(*buttons, width=2)
    return kb_bl.as_markup()


async def forum_button():
    button = InlineKeyboardButton(
        text='Перейти на форум',
        url='https://t.me/+sk6G14Ywu9AzMTBi'
    )

    return InlineKeyboardMarkup(inline_keyboard=[[button]])


async def manager_button():
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

async def support_button():
    button = InlineKeyboardButton(
        text="🟢 WhatsApp",
        url='https://wa.me/79251894560'
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])
    return markup

async def problem_button():
    button = InlineKeyboardButton(
        text='Заполнить форму',
        url='https://forms.gle/wnxcfdTsPpHtNCcy9'
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])
    return markup
