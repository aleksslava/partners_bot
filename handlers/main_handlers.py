from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
from data.database import database, Partner
from keybooards.main_keyboards import reply_phone_number
from config_data.amo_api import AmoCRMWrapper

main_router = Router()


# Хэндлер обрабатывающий команду start
@main_router.message(Command(commands=['start', 'info']))
async def start_handler(message: Message, amo_api: AmoCRMWrapper):
    # Отправка приветственного текста и главной клавиатуры
    tg_id = message.from_user.id

    # Проверка на наличие tg_id в бд бота, если есть, то запрос в амо на данные для личного кабинета
    if str(tg_id) in database.keys():
        partner: Partner = database[str(tg_id)]
        phone_number = partner.phone_number
        response = amo_api.get_customer_by_phone(phone_number)
        if response[0]:
            customer_params = amo_api.get_customer_params(response[1])
            await message.answer(text=f'<b><u>Данные Вашей учетной записи партнёра:</u></b>\n\n'
                                      f'👤 Имя - {customer_params.name}\n\n'
                                      f'✅ Квалифицирован - {customer_params.kval}\n\n'
                                      f'👥 Персональный менеджер - {customer_params.manager}\n\n'
                                      f'🌟 Категория партнёра - {customer_params.status}\n\n'
                                      f'📆 Покупок после 1 апреля 2025 года - {customer_params.bye_after_first_april}\n\n'
                                      f'🎁 Накопленные бонусы - {customer_params.bonuses}\n\n'
                                      f'📤 Количество выведенных бонусов - {customer_params.payout}\n\n'
                                      f'🌆 Город работы - {customer_params.town}'
                                 )
        else:
            await message.answer(text=response[1])

    # Если id в бд нет, то запрашиваем номер телефона партнёра, для запроса в амо по номеру телефона
    else:
        name = message.from_user.first_name
        await message.answer(text=f'{name}, здравствуйте.\n'
                                  f'Поделитесь своим номером телефона для использования бота.',
                             reply_markup=await reply_phone_number())


# Хэндлер обрабатывающий контакт клиента
@main_router.message(F.contact)
async def get_contact(message: Message, amo_api: AmoCRMWrapper):
    contact = message.contact
    response = amo_api.get_customer_by_phone(contact.phone_number)
    if response[0]:
        customer_params = amo_api.get_customer_params(response[1])
        partner_obj = Partner(
            customer_id=customer_params.id,
            last_name=customer_params.name.split()[1],
            first_name=customer_params.name.split()[0],
            phone_number=contact.phone_number,
            is_partner=customer_params.kval
        )
        database[str(message.from_user.id)] = partner_obj
        await message.answer(text=f'<b><u>Данные Вашей учетной записи партнёра:</u></b>\n\n'
                                  f'👤 Имя - {customer_params.name}\n\n'
                                  f'✅ Квалифицирован - {customer_params.kval}\n\n'
                                  f'👥 Персональный менеджер - {customer_params.manager}\n\n'
                                  f'🌟 Категория партнёра - {customer_params.status}\n\n'
                                  f'📆 Покупок после 1 апреля 2025 года - {customer_params.bye_after_first_april}\n\n'
                                  f'🎁 Накопленные бонусы - {customer_params.bonuses}\n\n'
                                  f'📤 Количество выведенных бонусов - {customer_params.payout}\n\n'
                                  f'🌆 Город работы - {customer_params.town}',
                             reply_markup=ReplyKeyboardRemove()
                             )
    else:
        await message.answer(text=response[1])


@main_router.message(Command(commands='contacts'))
async def contacts(message: Message):

    await message.answer(text=f'<b>Связаться с нами можно</b>:\n\n'
                              f'📞 <b>Телефон</b> :\n'
                              f'+7 (495) 256-33-00\n\n'
                              f'📧 <b>Электронная почта</b> :\n'
                              f'<a href="sales@hite-pro.ru">sales@hite-pro.ru</a>\n\n'
                              f'📱 <b>WhatsApp</b> :\n'
                              f'<a href="https://wa.me/79251930861">Ссылка на whatsapp</a>')


@main_router.message(Command(commands=['connect', 'support', 'registration', 'education']))
async def in_dev(message: Message):
    await message.answer(text='Данный раздел  находится в разработке.\n'
                              'Приносим извинения за предоставленные неудобства!')



