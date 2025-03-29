from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


async def reply_phone_number():
    first_button = KeyboardButton(text='Отправить', request_contact=True)
    markup = ReplyKeyboardMarkup(keyboard=[[first_button,]], resize_keyboard=True)


    return markup
