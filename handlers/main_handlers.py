from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, Contact
from data.database import database, Partner
from keybooards.main_keyboards import reply_phone_number
from config_data.amo_api import AmoCRMWrapper

main_router = Router()


# Хэндлер обрабатывающий команду start
@main_router.message(Command(commands='start'))
async def start_handler(message: Message):
    # Отправка приветственного текста и главной клавиатуры
    id = message.from_user.id
    last_name = message.from_user.last_name


    # Проверка на наличие tg_id в бд бота, если есть, то запрос в амо на данные для личного кабинета
    if id in database.keys():
        partner = database[id]
        phone = partner.phone_number
        response = AmoCRMWrapper().get_user_by_phone(phone)
        await message.answer(text=str(response))

    # Если id в бд нет, то запрашиваем номер телефона партнёра, для запроса в амо по номеру телефона
    else:
        name = message.from_user.first_name

        await message.answer(text=f'Привет {name}\nОтправь свой номер телефона для пользоввания ботом.',
                             reply_markup=await reply_phone_number())


@main_router.message(F.contact)
async def get_contact(message: Message):
    contact = message.contact

    response = AmoCRMWrapper().get_user_by_phone(contact.phone_number)
    await message.answer(text=str(response))
