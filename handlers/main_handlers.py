from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
from keybooards.main_keyboards import reply_phone_number
from config_data.amo_api import AmoCRMWrapper
from lexicon.lexicon_ru import account_info, contact_message, message_in_dev

main_router = Router()


# Хэндлер обрабатывающий команду start
@main_router.message(Command(commands=['start', 'info']))
async def start_handler(message: Message, amo_api: AmoCRMWrapper):
    # Отправка приветственного текста и главной клавиатуры
    tg_id = message.from_user.id

    """Проверка наличия партнёра в бд по tg_id"""

    customer = amo_api.get_customer_by_tg_id(tg_id)
    if customer.get('status_code'):
        if customer.get('tg_id_in_db'):
            customer_params = amo_api.get_customer_params(customer.get('response'))
            await message.answer(text=account_info(customer_params))
        else:
            # Если tg_id нет в бд, то ищем по номеру телефона и добавляем если нашли покупателя
            name = message.from_user.first_name
            await message.answer(text=f'{name}, здравствуйте.\n'
                                      f'Поделитесь своим номером телефона для использования бота.',
                                 reply_markup=await reply_phone_number())
    else:
        await message.answer(text=customer.get('response'))


# Хэндлер обрабатывающий контакт клиента
@main_router.message(F.contact)
async def get_contact(message: Message, amo_api: AmoCRMWrapper):
    contact = message.contact
    response = amo_api.get_customer_by_phone(contact.phone_number)
    if response[0]:
        customer_params = amo_api.get_customer_params(response[1])
        amo_api.put_tg_id_to_customer(customer_params.id, message.from_user.id)

        await message.answer(text=account_info(customer_params),
                             reply_markup=ReplyKeyboardRemove()
                             )
    else:
        await message.answer(text=response[1])


@main_router.message(Command(commands='contacts'))
async def contacts(message: Message):

    await message.answer(text=contact_message)


@main_router.message(Command(commands=['connect', 'support', 'registration', 'education']))
async def in_dev(message: Message):
    await message.answer(text=message_in_dev)



