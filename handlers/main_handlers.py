import pprint

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery
from keybooards.main_keyboards import reply_phone_number, get_contacts_list
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
            await message.answer(text=account_info(customer_params),
                                 reply_markup=get_contacts_list(customer_params.id))
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
        pprint.pprint(response[1])
        customer_params = amo_api.get_customer_params(response[1])
        amo_api.put_tg_id_to_customer(customer_params.id, message.from_user.id)

        await message.answer(text=account_info(customer_params),
                             reply_markup=get_contacts_list(customer_params.id)
                             )
    else:
        await message.answer(text=response[1])


@main_router.message(Command(commands='contacts'))
async def contacts(message: Message):

    await message.answer(text=contact_message)


@main_router.message(Command(commands=['connect', 'support', 'registration', 'education']))
async def in_dev(message: Message):
    await message.answer(text=message_in_dev)


@main_router.callback_query(F.data.startswith('contacts_list'))
async def open_contacts_list(callback: CallbackQuery, amo_api: AmoCRMWrapper):
    last_message = callback.message.text
    customer_id = callback.data.split('_')[2]
    customer = amo_api.get_customer_by_id(customer_id, with_contacts=True)
    contacts_list = [contact.get('id') for contact in customer[1]['_embedded']['contacts']]
    for contact_id in contacts_list:
        contact_data = amo_api.get_contact_by_id(contact_id)
        pprint.pprint(contact_data, indent=4)







