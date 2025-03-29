from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, Contact
from data.database import database, Partner
from keybooards.main_keyboards import reply_phone_number

main_router = Router()


# Хэндлер обрабатывающий команду start
@main_router.message(Command(commands='start'))
async def start_handler(message: Message):
    # Отправка приветственного текста и главной клавиатуры
    id = message.from_user.id
    last_name = message.from_user.last_name


    # Проверка на наличие tg_id в бд бота, если есть, то запрос в амо на данные для личного кабинета
    if id in database.keys():
        pass
    # Если id в бд нет, то запрашиваем номер телефона партнёра
    else:
        name = message.from_user.first_name

        await message.answer(text=f'{name} '+'Привет новый пользовать, отправь свой номер телефона.',
                             reply_markup=await reply_phone_number())


@main_router.message(F.contact)
async def get_contact(message: Message):
    contact = message.contact
    await message.answer(
        text=f'Твоё имя - {contact.first_name}\nТвой телефон-{contact.phone_number}')