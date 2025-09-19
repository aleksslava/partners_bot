import logging
import json
from pprint import pprint

from service.service import order_note

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, WebAppInfo, \
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from keybooards.main_keyboards import (reply_phone_number, get_contacts_list, hide_contacts_list, get_start_keyboard,
                                       forum_button, manager_button, support_button, problem_button,
                                       helpfull_materials_keyboard, back_button, answer_for_user, authorized_client,
                                       link_to_opt_button,
                                       )
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

        await message.answer(text=f'Вы успешно авторизовались в чат боте HiTE PRO!\n\n'
                                  f'Можете посмотреть информацию из Вашего профиля и воспользоваться '
                                  f'магазином HiTE PRO👇', reply_markup=await authorized_client(start_menu))
    else:
        await message.answer(text=f'{customer[1]}\n\n'
                                  f'Воспользоваться чат-ботом могут только авторизованные партнёры.\n'
                                  f'👇 Если вы действующий партнёр компании HiTE PRO, '
                                  f'сообщите об этой ошибке в онлайн-форме.',
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
async def hide_contact_list(callback: CallbackQuery):
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
async def command_shop_process(message: Message, amo_api: AmoCRMWrapper, fields_id: dict):
    tg_id = message.from_user.id
    customer = amo_api.get_customer_by_tg_id(tg_id)
    if customer.get('status_code'):  # Проверка корректности ответа от амо
        if customer.get('tg_id_in_db'):  # Проверка наличия tg_id в базе амо
            customer = customer.get('response')
            customer['manager'] = {'name': None}
            customer_params = amo_api.get_customer_params(customer, fields_id=fields_id)
            customer_id = customer_params.id
            bonus = str(customer_params.bonuses).replace(' ', '')
            discont = ''.join(list(filter(lambda x: x.isdigit(), customer_params.status)))

            kb_1 = KeyboardButton(text='Открыть магазин',
                                  web_app=WebAppInfo(
                                      url=f'https://aleksslava.github.io/testwebapp.github.io/?bonus={bonus}&'
                                          f'id={customer_id}&discont={discont}'))
            webapp_keyboard_1 = ReplyKeyboardMarkup(keyboard=[[kb_1, ]], resize_keyboard=True)

            await message.answer(text='Для перехода в магазин воспользуйтесь кнопкой клавиатуры👇',
                                 reply_markup=webapp_keyboard_1)
        else:
            # Если tg_id нет в бд, то ищем по номеру телефона
            name = message.from_user.first_name
            await message.answer(text=f'{name}, здравствуйте.\n'
                                      f'Поделитесь своим номером телефона для использования бота.',
                                 reply_markup=await reply_phone_number())
    else:
        response = customer.get('response')
        await message.answer(text=f'{response}\n\n'
                                  f'👇 Сообщите об этой ошибке в онлайн-форме.',
                             reply_markup=await problem_button())


@main_router.callback_query(F.data == '/shop')  # Хэндлер для обработки inline кнопки "shop"
async def command_shop_process_cl(callback: CallbackQuery, amo_api: AmoCRMWrapper, fields_id: dict):
    tg_id = callback.from_user.id

    customer = amo_api.get_customer_by_tg_id(tg_id)
    if customer.get('status_code'):  # Проверка корректности ответа от амо
        if customer.get('tg_id_in_db'):  # Проверка наличия tg_id в базе амо
            customer = customer.get('response')
            customer['manager'] = {'name': None}
            customer_params = amo_api.get_customer_params(customer, fields_id=fields_id)
            customer_id = customer_params.id
            bonus = str(customer_params.bonuses).replace(' ', '')
            discont = ''.join(list(filter(lambda x: x.isdigit(), customer_params.status)))

            kb_1 = KeyboardButton(text='Открыть магазин',
                                  web_app=WebAppInfo(
                                      url=f'https://aleksslava.github.io/testwebapp.github.io/?bonus={bonus}&'
                                          f'id={customer_id}&discont={discont}'))
            webapp_keyboard_1 = ReplyKeyboardMarkup(keyboard=[[kb_1, ]], resize_keyboard=True)

            await callback.message.answer(text='Для перехода в магазин воспользуйтесь кнопкой клавиатуры👇',
                                          reply_markup=webapp_keyboard_1)
        else:
            # Если tg_id нет в бд, то ищем по номеру телефона
            name = callback.from_user.first_name
            await callback.message.answer(text=f'{name}, здравствуйте.\n'
                                               f'Поделитесь своим номером телефона для использования бота.',
                                          reply_markup=await reply_phone_number())
    else:
        response = customer.get('response')
        await callback.message.answer(text=f'{response}\n\n'
                                           f'👇 Сообщите об этой ошибке в онлайн-форме.',
                                      reply_markup=await problem_button())

    await callback.answer()


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


@main_router.callback_query(F.data == '/materials')  # Хэндлер для обработки inline кнопки "materials"
async def command_materials_process_cl(callback: CallbackQuery):
    await callback.message.edit_text(text='<b>Полезные материалы HiTE PRO.</b>\n\n'
                                          '👇 Используйте кнопки ниже, чтобы выбрать раздел.',
                                     reply_markup=await helpfull_materials_keyboard(helpfull_materials_menu))


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


@main_router.message(F.text != None)  # Хэндлер для обработки произвольных сообщений пользователя
async def answer_message(message: Message):
    await message.answer(text=Lexicon_RU.get('answer_for_user'), reply_markup=await answer_for_user())
    print(message.chat.id)


@main_router.message(F.web_app_data.data != None)  # Хэндлер для обработки заказа из webapp
async def web_app_order(message: Message, amo_api: AmoCRMWrapper, fields_id: dict, bot: Bot):
    raw_json = message.web_app_data.data
    raw_json = json.loads(raw_json)
    full_price = raw_json.get('total')


    try:
        customer_id = raw_json.get('userId')
        if customer_id is None:
            raise ValueError('Нет id покупателя к которому привязать заказ')
        customer = amo_api.get_customer_by_id(customer_id, with_contacts=True)
        contacts_list_id = [contact.get('id') for contact in customer[1]['_embedded']['contacts']]
        contact_id = contacts_list_id[0]

        # Создание новой сделки в АМО
        response = amo_api.send_lead_to_amo(pipeline_id=fields_id.get('pipeline_id'),
                                            status_id=fields_id.get('status_id'),
                                            tag_id=fields_id.get('tag_id'),
                                            contact_id=int(contact_id),
                                            price=int(full_price))

        lead_id = response.get('_embedded').get('leads')[0].get('id')

        # Добавление примечания в сделку
        response_add_note = amo_api.add_new_note_to_lead(lead_id=lead_id, text=order_note(raw_json, lead_id=lead_id))

        items = raw_json.get('items')

        # Добавление товаров в сделку
        response = amo_api.add_catalog_elements_to_lead(lead_id=lead_id,
                                                        catalog_id=fields_id.get('catalog_id'),
                                                        elements=items)

        await message.answer(text=order_note(raw_json, lead_id=lead_id, service=False),
                             reply_markup=ReplyKeyboardRemove())

        link_to_opt = ('👉 Если хотите общаться с сотрудниками HiTE PRO в Телеграм — '
                       'нажмите на кнопку ниже и напишите любое сообщение.')

        await message.answer(text=link_to_opt, reply_markup=await link_to_opt_button(lead_id=lead_id))

        await bot.send_message(chat_id=fields_id.get('chat_id'),
                               text=f'Оформлен заказ:\n\n{order_note(raw_json, lead_id=lead_id)}\n'
                                    f'Создана сделка:\n'
                                    f'<a href="https://hite.amocrm.ru/leads/detail/{lead_id}">{lead_id}</a>')

    except BaseException as error:
        logger.error(error)

        await message.answer(text='Произошла ошибка при отправке заказа, обратитесь к менеджеру.',
                             reply_markup=ReplyKeyboardRemove())

        await bot.send_message(chat_id=fields_id.get('chat_id'),
                               text=f'Произошла ошибка при оформлении заказа.\n\n{error}')
