import asyncio
import logging
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, WebAppInfo, InlineKeyboardMarkup
from keybooards.main_keyboards import (reply_phone_number, get_contacts_list, hide_contacts_list, get_start_keyboard,
                                       forum_button, manager_button, support_button, problem_button,
                                       helpfull_materials_keyboard, back_button)
from config_data.amo_api import AmoCRMWrapper, Contact
from lexicon.lexicon_ru import account_info, Lexicon_RU, start_menu, helpfull_materials_menu

main_router = Router()
logger = logging.getLogger(__name__)


@main_router.message(CommandStart())  # Хэндлер для обработки команды /start
async def command_start_process(message: Message):

    await message.answer(text='<b>Основное меню чат-бота HiTE PRO!</b>',
                         reply_markup=await get_start_keyboard(start_menu))


@main_router.message(Command(commands=['info']))  # Хэндлер для обработки команды /info
async def info_handler(message: Message, amo_api: AmoCRMWrapper, fields_id: dict):

    tg_id = message.from_user.id

    # Проверка наличия партнёра в бд по tg_id

    customer = amo_api.get_customer_by_tg_id(tg_id)
    if customer.get('status_code'):
        if customer.get('tg_id_in_db'):
            customer = customer.get('response')
            responsible_manager = amo_api.get_responsible_user_by_id(int(customer.get('responsible_user_id')))
            customer['manager'] = responsible_manager
            customer_params = amo_api.get_customer_params(customer, fields_id=fields_id)
            await message.answer(text=account_info(customer_params),
                                 reply_markup=await get_contacts_list(customer_params.id))
        else:
            # Если tg_id нет в бд, то ищем по номеру телефона
            name = message.from_user.first_name
            await message.answer(text=f'{name}, здравствуйте.\n'
                                      f'Поделитесь своим номером телефона для использования бота.',
                                 reply_markup=await reply_phone_number())
    else:
        await message.answer(text='Ошибка! Помогите нам её исправить. Сообщите об этой ошибке в онлайн-форме:',
                             reply_markup=await problem_button())


@main_router.callback_query(F.data == '/info')  # Обработка инлайн кнопки "Мой профиль"
async def info_handler_cl(callback: CallbackQuery, amo_api: AmoCRMWrapper, fields_id: dict):
    await callback.answer()
    tg_id = callback.message.chat.id

    # Проверка наличия партнёра в амо по tg_id

    customer = amo_api.get_customer_by_tg_id(tg_id)
    if customer.get('status_code'):  # Проверка корректности ответа от амо
        if customer.get('tg_id_in_db'):  # Проверка наличия tg_id в базе амо
            customer = customer.get('response')
            responsible_manager = amo_api.get_responsible_user_by_id(int(customer.get('responsible_user_id')))
            customer['manager'] = responsible_manager
            customer_params = amo_api.get_customer_params(customer, fields_id=fields_id)
            await callback.message.edit_text(text=account_info(customer_params),
                                             reply_markup=await get_contacts_list(customer_params.id))
        else:
            # Если tg_id нет в бд, то ищем по номеру телефона
            name = callback.message.chat.first_name
            await callback.message.answer(text=f'{name}, здравствуйте.\n'
                                                  f'Поделитесь своим номером телефона для использования бота.',
                                          reply_markup=await reply_phone_number())
    else:
        await callback.message.edit_text(text='Ошибка! Помогите нам её исправить. '
                                              '👇 Сообщите об этой ошибке в онлайн-форме.',
                                         reply_markup=await problem_button())


@main_router.message(F.contact)  # Хэндлер для обработки отправленного пользователем контакта
async def get_contact(message: Message, amo_api: AmoCRMWrapper, fields_id: dict):
    contact = message.contact
    customer = amo_api.get_customer_by_phone(contact.phone_number)
    if customer[0]:
        responsible_manager = amo_api.get_responsible_user_by_id(int(customer[1].get('responsible_user_id')))
        customer[1]['manager'] = responsible_manager
        customer_params = amo_api.get_customer_params(customer[1], fields_id=fields_id)
        amo_api.put_tg_id_to_customer(customer_params.id, message.from_user.id)

        await message.answer(text=account_info(customer_params),
                             reply_markup=await get_contacts_list(customer_params.id)
                             )
    else:
        await message.answer(text=f'{customer[1]}\n\n'
                                  f'👇 Сообщите об этой ошибке в онлайн-форме.',
                             reply_markup=await problem_button())


# Хэндлер для обработки инлайн кнопки "Показать контакты"
@main_router.callback_query(F.data.startswith('contacts_list'))
async def open_contacts_list(callback: CallbackQuery, amo_api: AmoCRMWrapper):
    last_message = callback.message.text
    customer_id = callback.data.split('_')[2]
    customer = amo_api.get_customer_by_id(customer_id, with_contacts=True)
    contacts_list_id = [contact.get('id') for contact in customer[1]['_embedded']['contacts']]
    last_message = last_message + '\n\n<b>Привязанные контакты к профилю</b>\n'

    for contact_id in contacts_list_id:
        contact_data = Contact(**amo_api.get_contact_by_id(contact_id))
        last_message = last_message + str(contact_data)

    await callback.message.edit_text(text=last_message, reply_markup=await hide_contacts_list(customer_id))


# Хэндлер для обработки инлайн кнопки "Скрыть контакты"
@main_router.callback_query(F.data.startswith('hide_contacts_list'))
async def hide_contact_list(callback: CallbackQuery, amo_api: AmoCRMWrapper):
    customer_id = callback.data.split('_')[3]
    last_text = callback.message.text
    hide_index = last_text.find('Привязанные')
    new_text = last_text[:hide_index]
    await callback.message.edit_text(text=new_text, reply_markup=await get_contacts_list(customer_id))


@main_router.message(Command(commands='contacts'))  # Хэндлер для обработки команды /contacts
async def contacts(message: Message):
    await message.answer(text=Lexicon_RU.get('contact_message'))


@main_router.callback_query(F.data == '/contacts')  # Хэндлер для обработки inline кнопки "contacts"
async def command_contacts_process_cl(callback: CallbackQuery):
    await callback.message.edit_text(text=Lexicon_RU.get('contact_message'))


@main_router.message(Command(commands='shop'))  # Хэндлер для обработки команды /shop
async def command_shop_process(message: Message):
    button = InlineKeyboardButton(text='Перейти в магазин', url='https://profi.hite-pro.ru/shop')
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])
    await message.answer(text=Lexicon_RU.get('shop_message'), reply_markup=markup)


@main_router.callback_query(F.data == '/shop')  # Хэндлер для обработки inline кнопки "shop"
async def command_shop_process_cl(callback: CallbackQuery):
    button = InlineKeyboardButton(text='Перейти в магазин', url='https://profi.hite-pro.ru/shop')
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])
    await callback.message.edit_text(text=Lexicon_RU.get('shop_message'), reply_markup=markup)


@main_router.message(Command(commands='forum'))  # Хэндлер для обработки команды /forum
async def command_forum_process(message: Message):
    await message.answer(text=Lexicon_RU.get('forum_message'), reply_markup=await forum_button())


@main_router.callback_query(F.data == '/forum')  # Хэндлер для обработки inline кнопки "forum"
async def command_forum_process_cl(callback: CallbackQuery):
    await callback.message.edit_text(text=Lexicon_RU.get('forum_message'), reply_markup=await forum_button())


@main_router.message(Command(commands='materials'))  # Хэндлер для обработки команды /materials
async def command_materials_process(message: Message):

    await message.answer(text='<b>Полезные материалы HiTE PRO.</b>\n\n'
                              '👇 Используйте кнопки ниже, чтобы выбрать раздел.',
                         reply_markup=await helpfull_materials_keyboard(helpfull_materials_menu))
    # await message.answer(text=Lexicon_RU.get('helpful_materials').get('first_message'))
    # await asyncio.sleep(1)
    # await message.answer(text=Lexicon_RU.get('helpful_materials').get('second_message'))
    # await asyncio.sleep(1)
    # await message.answer(text=Lexicon_RU.get('helpful_materials').get('third_message'))
    # await asyncio.sleep(1)
    # await message.answer(text=Lexicon_RU.get('helpful_materials').get('forth_message'))
    # await asyncio.sleep(1)
    # await message.answer(text=Lexicon_RU.get('helpful_materials').get('five_message'))


@main_router.callback_query(F.data == '/materials')  # Хэндлер для обработки inline кнопки "materials"
async def command_materials_process_cl(callback: CallbackQuery):
    await callback.message.edit_text(text='<b>Полезные материалы HiTE PRO.</b>\n\n'
                                    '👇 Используйте кнопки ниже, чтобы выбрать раздел.',
                                     reply_markup=await helpfull_materials_keyboard(helpfull_materials_menu))
    # await callback.message.edit_text(text=Lexicon_RU.get('helpful_materials').get('first_message'))
    # await asyncio.sleep(1)
    # await callback.message.answer(text=Lexicon_RU.get('helpful_materials').get('second_message'))
    # await asyncio.sleep(1)
    # await callback.message.answer(text=Lexicon_RU.get('helpful_materials').get('third_message'))
    # await asyncio.sleep(1)
    # await callback.message.answer(text=Lexicon_RU.get('helpful_materials').get('forth_message'))
    # await asyncio.sleep(1)
    # await callback.message.answer(text=Lexicon_RU.get('helpful_materials').get('five_message'))

@main_router.callback_query(F.data == 'first_message')
async def command_materials_process_cl(callback: CallbackQuery):
    await callback.message.edit_text(text=Lexicon_RU.get('helpful_materials').get('first_message'),
                                     reply_markup=await back_button())

@main_router.callback_query(F.data == 'second_message')
async def command_materials_process_cl(callback: CallbackQuery):
    await callback.message.edit_text(text=Lexicon_RU.get('helpful_materials').get('second_message'),
                                     reply_markup=await back_button())

@main_router.callback_query(F.data == 'third_message')
async def command_materials_process_cl(callback: CallbackQuery):
    await callback.message.edit_text(text=Lexicon_RU.get('helpful_materials').get('third_message'),
                                     reply_markup=await back_button())

@main_router.callback_query(F.data == 'forth_message')
async def command_materials_process_cl(callback: CallbackQuery):
    await callback.message.edit_text(text=Lexicon_RU.get('helpful_materials').get('forth_message'),
                                     reply_markup=await back_button())

@main_router.callback_query(F.data == 'five_message')
async def command_materials_process_cl(callback: CallbackQuery):
    await callback.message.edit_text(text=Lexicon_RU.get('helpful_materials').get('five_message'),
                                     reply_markup=await back_button())

@main_router.callback_query(F.data == 'back')
async def command_materials_process_cl(callback: CallbackQuery):
    await callback.message.edit_text(text='<b>Полезные материалы HiTE PRO.</b>\n\n'
                                          '👇 Используйте кнопки ниже, чтобы выбрать раздел.',
                                     reply_markup=await helpfull_materials_keyboard(helpfull_materials_menu))

@main_router.message(Command(commands='manager'))  # Хэндлер для обработки команды /manager
async def command_manager_process(message: Message):
    await message.answer(text=Lexicon_RU.get('manager'), reply_markup=await manager_button())


@main_router.callback_query(F.data == '/manager')  # Хэндлер для обработки inline кнопки "manager"
async def command_manager_process_cl(callback: CallbackQuery):
    await callback.message.edit_text(text=Lexicon_RU.get('manager'), reply_markup=await manager_button())


@main_router.message(Command(commands='support'))  # Хэндлер для обработки команды /support
async def command_support_process(message: Message):
    await message.answer(text=Lexicon_RU.get('support'), reply_markup=await support_button())

@main_router.callback_query(F.data == '/support')  # Хэндлер для обработки inline кнопки "support"
async def command_support_process_cl(callback: CallbackQuery):
    await callback.message.edit_text(text=Lexicon_RU.get('support'), reply_markup=await support_button())


@main_router.message(Command(commands='problem'))  # Хэндлер для обработки команды /problem
async def command_problem_process(message: Message):
    await message.answer(text=Lexicon_RU.get('problem'), reply_markup=await problem_button())


@main_router.callback_query(F.data == '/problem')  # Хэндлер для обработки inline кнопки "problem"
async def command_problem_process_cl(callback: CallbackQuery):
    await callback.message.edit_text(text=Lexicon_RU.get('problem'), reply_markup=await problem_button())


@main_router.message()  # Хэндлер для обработки произвольных сообщений пользователя
async def answer_message(message: Message):
    await message.answer(text=Lexicon_RU.get('answer_for_user'))
