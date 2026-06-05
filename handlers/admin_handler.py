import logging
import re
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from openpyxl import load_workbook

from keybooards.main_keyboards import get_start_keyboard
from lexicon.lexicon_ru import spam_message, spam_url, start_menu

admin_router = Router()
logger = logging.getLogger(__name__)

CUSTOMERS_XLSX_PATH = Path('media/xls_files/customers.xlsx')
SPAM_VIDEO_PATH = Path('media/video/video.mp4')
SPAM_NAME_MASK = '[Имя]'
SPAM_STATUS_SUCCESS = 'Успешно'
SPAM_STATUS_ERROR = 'Ошибка отправки'
SPAM_STATUS_SKIP = 'Пропуск'


class AdminSpamStates(StatesGroup):
    waiting_range = State()
    waiting_single_tg_id = State()
    waiting_single_name = State()


def is_admin(user_id: int, admin_id: str) -> bool:
    try:
        return int(user_id) == int(admin_id)
    except (TypeError, ValueError):
        return False


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Сделать рассылку', callback_data='admin_broadcast')],
        [InlineKeyboardButton(text='Отправить пользователю по telegram_id', callback_data='admin_single')],
        [InlineKeyboardButton(text='Назад в главное меню', callback_data='admin_back_main')],
    ])


def spam_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Записаться на интервью', url=spam_url)]
    ])


def spam_text(name: str) -> str:
    return spam_message.replace(SPAM_NAME_MASK, name.strip())


def parse_spam_range(text: str) -> tuple[int, int] | None:
    match = re.fullmatch(r'\s*(\d+)\s*-\s*(\d+)\s*', text or '')
    if not match:
        return None
    start, end = int(match.group(1)), int(match.group(2))
    if start < 1 or end < start:
        return None
    return start, end


def normalize_telegram_id(value) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    value = str(value).strip()
    if value.isdigit():
        return int(value)
    raise ValueError('Некорректный telegram_id')


def get_xlsx_columns(sheet) -> dict[str, int]:
    columns = {}
    for cell in sheet[1]:
        if cell.value is not None:
            columns[str(cell.value).strip()] = cell.column
    return columns


async def send_interview_spam(bot: Bot, chat_id: int, name: str) -> None:
    await bot.send_video(
        chat_id=chat_id,
        video=FSInputFile(SPAM_VIDEO_PATH),
        caption=spam_text(name),
        reply_markup=spam_keyboard(),
        width=1080,
        height=1920,
        supports_streaming=True
    )


@admin_router.callback_query(F.data == 'start_admin')
async def start_admin_menu(callback: CallbackQuery, admin_id: str, state: FSMContext):
    if not is_admin(callback.from_user.id, admin_id):
        await callback.answer(text='Нет доступа', show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(text='<b>Меню администратора</b>', reply_markup=admin_menu_keyboard())
    await callback.answer()


@admin_router.callback_query(F.data == 'admin_back_main')
async def admin_back_main(callback: CallbackQuery, admin_id: str, state: FSMContext):
    if not is_admin(callback.from_user.id, admin_id):
        await callback.answer(text='Нет доступа', show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(text='<b>Основное меню чат-бота HiTE PRO!</b>',
                                     reply_markup=await get_start_keyboard(start_menu, is_admin=True))
    await callback.answer()


@admin_router.callback_query(F.data == 'admin_broadcast')
async def start_admin_broadcast(callback: CallbackQuery, admin_id: str, state: FSMContext):
    if not is_admin(callback.from_user.id, admin_id):
        await callback.answer(text='Нет доступа', show_alert=True)
        return

    await state.set_state(AdminSpamStates.waiting_range)
    await callback.message.edit_text(text='Введите диапазон пользователей для рассылки в формате N-N.')
    await callback.answer()


@admin_router.message(StateFilter(AdminSpamStates.waiting_range), F.text)
async def process_admin_broadcast_range(message: Message, bot: Bot, admin_id: str, state: FSMContext):
    if not is_admin(message.from_user.id, admin_id):
        await state.clear()
        await message.answer(text='Нет доступа')
        return

    spam_range = parse_spam_range(message.text)
    if spam_range is None:
        await message.answer(text='Некорректный диапазон. Введите диапазон в формате N-N, например: 1-10.')
        return

    if not CUSTOMERS_XLSX_PATH.exists():
        await state.clear()
        await message.answer(text=f'Файл {CUSTOMERS_XLSX_PATH} не найден.')
        return

    if not SPAM_VIDEO_PATH.exists():
        await state.clear()
        await message.answer(text=f'Файл {SPAM_VIDEO_PATH} не найден.')
        return

    try:
        workbook = load_workbook(CUSTOMERS_XLSX_PATH)
    except BaseException as error:
        logger.exception('Не удалось открыть Excel-файл для рассылки')
        await state.clear()
        await message.answer(text=f'Не удалось открыть Excel-файл: {error}')
        return

    sheet = workbook.active
    columns = get_xlsx_columns(sheet)
    required_columns = ['Название', 'telegram_id', 'Отправлено в ТГ']
    missed_columns = [column for column in required_columns if column not in columns]
    if missed_columns:
        await state.clear()
        await message.answer(text=f'В Excel-файле не найдены колонки: {", ".join(missed_columns)}.')
        return

    start_client, end_client = spam_range
    max_client_number = max(sheet.max_row - 1, 0)
    if end_client > max_client_number:
        await state.clear()
        await message.answer(text=f'В Excel-файле только {max_client_number} строк с клиентами.')
        return

    await message.answer(text='Рассылка запущена.')

    total = 0
    success = 0
    errors = 0
    name_column = columns['Название']
    telegram_id_column = columns['telegram_id']
    status_column = columns['Отправлено в ТГ']

    for row_number in range(start_client + 1, end_client + 2):
        telegram_id_cell = sheet.cell(row=row_number, column=telegram_id_column)
        status_cell = sheet.cell(row=row_number, column=status_column)

        if telegram_id_cell.value is None or str(telegram_id_cell.value).strip() == '':
            status_cell.value = SPAM_STATUS_SKIP
            continue

        total += 1
        full_name = str(sheet.cell(row=row_number, column=name_column).value or '').strip()
        name = full_name.split(maxsplit=1)[0] if full_name else ''

        try:
            telegram_id = normalize_telegram_id(telegram_id_cell.value)
            await send_interview_spam(bot=bot, chat_id=telegram_id, name=name)
            status_cell.value = SPAM_STATUS_SUCCESS
            success += 1
        except BaseException:
            status_cell.value = SPAM_STATUS_ERROR
            errors += 1
            logger.exception('Ошибка отправки рассылки пользователю %s', telegram_id_cell.value)

    save_error = None
    try:
        workbook.save(CUSTOMERS_XLSX_PATH)
    except BaseException as error:
        save_error = error
        logger.exception('Не удалось сохранить Excel-файл после рассылки')

    await state.clear()
    stats_message = (f'Всего отправок: {total}\n'
                     f'Успешных: {success}\n'
                     f'Отправок с ошибкой: {errors}')
    if save_error is not None:
        stats_message += f'\n\nНе удалось сохранить Excel-файл: {save_error}'
    await message.answer(text=stats_message)


@admin_router.callback_query(F.data == 'admin_single')
async def start_admin_single_send(callback: CallbackQuery, admin_id: str, state: FSMContext):
    if not is_admin(callback.from_user.id, admin_id):
        await callback.answer(text='Нет доступа', show_alert=True)
        return

    await state.set_state(AdminSpamStates.waiting_single_tg_id)
    await callback.message.edit_text(text='Введите telegram_id пользователя.')
    await callback.answer()


@admin_router.message(StateFilter(AdminSpamStates.waiting_single_tg_id), F.text)
async def process_admin_single_tg_id(message: Message, admin_id: str, state: FSMContext):
    if not is_admin(message.from_user.id, admin_id):
        await state.clear()
        await message.answer(text='Нет доступа')
        return

    try:
        telegram_id = normalize_telegram_id(message.text)
    except ValueError:
        await message.answer(text='Некорректный telegram_id. Введите только числовой telegram_id.')
        return

    await state.update_data(telegram_id=telegram_id)
    await state.set_state(AdminSpamStates.waiting_single_name)
    await message.answer(text='Введите имя получателя для подстановки в сообщение.')


@admin_router.message(StateFilter(AdminSpamStates.waiting_single_name), F.text)
async def process_admin_single_name(message: Message, bot: Bot, admin_id: str, state: FSMContext):
    if not is_admin(message.from_user.id, admin_id):
        await state.clear()
        await message.answer(text='Нет доступа')
        return

    if not SPAM_VIDEO_PATH.exists():
        await state.clear()
        await message.answer(text=f'Файл {SPAM_VIDEO_PATH} не найден.')
        return

    state_data = await state.get_data()
    telegram_id = state_data.get('telegram_id')
    name = message.text.strip()

    try:
        await send_interview_spam(bot=bot, chat_id=telegram_id, name=name)
    except BaseException as error:
        logger.exception('Ошибка отправки сообщения пользователю %s', telegram_id)
        await state.clear()
        await message.answer(text=f'Ошибка отправки: {error}')
        return

    await state.clear()
    await message.answer(text='Сообщение успешно отправлено.')
