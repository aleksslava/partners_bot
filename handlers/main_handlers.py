from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from data.database import database, Partner
from keybooards.main_keyboards import reply_phone_number
from config_data.amo_api import AmoCRMWrapper



main_router = Router()


# Хэндлер обрабатывающий команду start
@main_router.message(Command(commands='start'))
async def start_handler(message: Message, amo_api:AmoCRMWrapper):
    # Отправка приветственного текста и главной клавиатуры
    tg_id = message.from_user.id

    # Проверка на наличие tg_id в бд бота, если есть, то запрос в амо на данные для личного кабинета
    if str(tg_id) in database.keys():
        partner: Partner = database[str(id)]
        customer_id = partner.customer_id
        response = amo_api.get_customer_by_id(customer_id)
        customer_params = amo_api.get_customer_params(response)
        await message.answer(text=f'Имя - {customer_params.name}\n'
                                  f'Квалифицирован - {customer_params.kval}\n'
                                  f'Менеджжер - {customer_params.manager}\n'
                                  f'Статус партнёра - {customer_params.status}'
                                  f'Покупок после 1 апреля 2025 года - {customer_params.bye_after_first_april}\n'
                                  f'Накопленные бонусы - {customer_params.bonuses}\n'
                                  f'Количество выведенных бонусов - {customer_params.payout}\n'
                                  f'Город работы - {customer_params.town}'
                             )

    # Если id в бд нет, то запрашиваем номер телефона партнёра, для запроса в амо по номеру телефона
    else:
        name = message.from_user.first_name

        await message.answer(text=f'{name}, здравствуйте.\n'
                                  f'Поделитесь своим номером телефона для пользования ботом.',
                             reply_markup=await reply_phone_number())


@main_router.message(F.contact)
async def get_contact(message: Message, amo_api: AmoCRMWrapper):
    contact = message.contact
    response = amo_api.get_customer_by_phone(contact.phone_number)
    customer_params = amo_api.get_customer_params(response)
    partner_obj = Partner(
        customer_id=customer_params.id,
        last_name=customer_params.name.split()[1],
        first_name=customer_params.name.split()[0],
        phone_number=contact.phone_number,
        is_partner=customer_params.kval
    )
    database[str(message.from_user.id)] = partner_obj
    await message.answer(text=f'Имя - {customer_params.name}\n'
                              f'Квалифицирован - {customer_params.kval}\n'
                              f'Менеджер - {customer_params.manager}\n'
                              f'Статус партнёра - {customer_params.status}\n'
                              f'Покупок после 1 апреля 2025 года - {customer_params.bye_after_first_april}\n'
                              f'Накопленные бонусы - {customer_params.bonuses}\n'
                              f'Количество выведенных бонусов - {customer_params.payout}\n'
                              f'Город работы - {customer_params.town}'
                         )
