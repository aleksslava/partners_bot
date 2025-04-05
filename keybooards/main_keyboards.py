from aiogram import Bot
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand


async def reply_phone_number():
    first_button = KeyboardButton(text='Поделиться номером телефона', request_contact=True)
    markup = ReplyKeyboardMarkup(keyboard=[[first_button,]], resize_keyboard=True)

    return markup


async def set_main_menu(bot: Bot):

    # Создаем список с командами и их описанием для кнопки menu
    main_menu_commands = [
        BotCommand(command='/info',
                   description='Получить информацию об аккаунте партнёра'),
        BotCommand(command='/connect',
                   description='Написать персональному менеджеру'),
        BotCommand(command='/support',
                   description='Поддержка'),
        BotCommand(command='/education',
                   description='Обучающие материалы компании HITE PRO!'),
        BotCommand(command='/registration',
                   description='Регистрация в партнёрской программе HITE PRO!'),
        BotCommand(command='/contacts',
                   description='Другие способы связи с нами'),

    ]

    await bot.set_my_commands(main_menu_commands)
