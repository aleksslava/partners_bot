import asyncio
import logging
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from openpyxl import load_workbook

from web_admin.storage import BroadcastStorage

logger = logging.getLogger(__name__)

NAME_MASK = '[Имя]'
MAX_XLSX_SIZE = 10 * 1024 * 1024
MAX_MEDIA_SIZE = 20 * 1024 * 1024
TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024
ALLOWED_MEDIA = {
    '.jpg': 'photo',
    '.jpeg': 'photo',
    '.png': 'photo',
    '.mp4': 'video',
}


class UploadValidationError(ValueError):
    pass


def normalize_telegram_id(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError
    if isinstance(value, int):
        telegram_id = value
    elif isinstance(value, float) and value.is_integer():
        telegram_id = int(value)
    else:
        text = str(value or '').strip()
        if not text.isdigit():
            raise ValueError
        telegram_id = int(text)
    if telegram_id <= 0:
        raise ValueError
    return telegram_id


def parse_recipients(
    file_content: bytes,
    message: str,
    *,
    message_limit: int = TEXT_LIMIT,
) -> tuple[list[dict[str, Any]], int, int]:
    if not file_content:
        raise UploadValidationError('Excel-файл пуст.')
    if len(file_content) > MAX_XLSX_SIZE:
        raise UploadValidationError('Excel-файл должен быть не больше 10 МБ.')

    try:
        workbook = load_workbook(BytesIO(file_content), read_only=True, data_only=True)
    except Exception as error:
        raise UploadValidationError('Не удалось открыть Excel-файл.') from error

    try:
        sheet = workbook.active
        iter_rows = getattr(sheet, 'iter_rows', None)
        if iter_rows is None:
            raise UploadValidationError('В Excel-файле нет активного листа.')
        header_cells = next(iter_rows(min_row=1, max_row=1), None)
        if header_cells is None:
            raise UploadValidationError('В Excel-файле нет заголовков.')

        columns = {
            str(cell.value).strip().casefold(): index
            for index, cell in enumerate(header_cells)
            if cell.value is not None
        }
        telegram_column = columns.get('telegram_id')
        if telegram_column is None:
            raise UploadValidationError('Не найдена обязательная колонка telegram_id.')
        name_column = columns.get('имя')
        if name_column is None:
            name_column = columns.get('название')

        recipients: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        duplicate_count = 0
        invalid_count = 0
        needs_name = NAME_MASK in message
        for row_number, row in enumerate(iter_rows(min_row=2, values_only=True), start=2):
            if all(value in (None, '') for value in row):
                continue
            raw_id = row[telegram_column] if telegram_column < len(row) else None
            name_value = row[name_column] if name_column is not None and name_column < len(row) else None
            name = str(name_value or '').strip()
            item: dict[str, Any] = {
                'row_number': row_number,
                'raw_telegram_id': str(raw_id or '').strip(),
                'name': name,
                'status': 'pending',
                'error': None,
            }
            try:
                telegram_id = normalize_telegram_id(raw_id)
            except ValueError:
                item.update(status='skipped', error='Некорректный telegram_id')
                invalid_count += 1
                recipients.append(item)
                continue

            item['telegram_id'] = telegram_id
            if telegram_id in seen_ids:
                item.update(status='skipped', error='Повторный telegram_id')
                duplicate_count += 1
            elif needs_name and not name:
                item.update(status='skipped', error='Не указано имя для подстановки [Имя]')
                invalid_count += 1
            elif len(render_message(message, name)) > message_limit:
                item.update(status='skipped', error='Сообщение после подстановки слишком длинное')
                invalid_count += 1
            else:
                seen_ids.add(telegram_id)
            recipients.append(item)
    finally:
        workbook.close()

    if not recipients:
        raise UploadValidationError('В Excel-файле нет получателей.')
    if not any(item['status'] == 'pending' for item in recipients):
        raise UploadValidationError('В Excel-файле нет корректных получателей.')
    return recipients, duplicate_count, invalid_count


def render_message(message: str, name: str) -> str:
    return message.replace(NAME_MASK, name)


def build_button(text: str | None, url: str | None) -> InlineKeyboardMarkup | None:
    if not text or not url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, url=url)]],
    )


class BroadcastService:
    def __init__(self, storage: BroadcastStorage, bot: Bot):
        self.storage = storage
        self.bot = bot
        self.media_dir = storage.data_dir / 'media'
        self._worker_task: asyncio.Task | None = None
        self._wake_event = asyncio.Event()

    def initialize(self) -> None:
        self.storage.initialize()
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.storage.recover_interrupted()
        for media_path in self.storage.stale_draft_media():
            self.delete_media(media_path)

    def start(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker_task is None:
            return
        self._worker_task.cancel()
        try:
            await self._worker_task
        except asyncio.CancelledError:
            pass
        self._worker_task = None

    def wake(self) -> None:
        self._wake_event.set()

    async def _worker_loop(self) -> None:
        while True:
            processed = await self.process_next_due()
            if processed:
                continue
            self._wake_event.clear()
            try:
                await asyncio.wait_for(self._wake_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    async def process_next_due(self) -> bool:
        broadcast = self.storage.next_due(datetime.now(timezone.utc))
        if broadcast is None:
            return False
        broadcast_id = int(broadcast['id'])
        if not self.storage.mark_running(broadcast_id):
            return True

        try:
            recipients = self.storage.pending_recipients(broadcast_id)
            for recipient in recipients:
                recipient_id = int(recipient['id'])
                if not self.storage.mark_recipient_sending(recipient_id):
                    continue
                try:
                    await self._send(broadcast, recipient)
                except Exception as error:
                    logger.exception(
                        'Ошибка веб-рассылки %s для telegram_id=%s',
                        broadcast_id,
                        recipient['telegram_id'],
                    )
                    self.storage.mark_recipient_result(
                        recipient_id,
                        success=False,
                        error=str(error)[:500],
                    )
                else:
                    self.storage.mark_recipient_result(recipient_id, success=True)
                await asyncio.sleep(0.05)
            self.storage.finish_broadcast(broadcast_id)
        except Exception as error:
            logger.exception('Не удалось выполнить веб-рассылку %s', broadcast_id)
            self.storage.fail_broadcast(broadcast_id, str(error)[:500])
        finally:
            self.delete_media(broadcast.get('media_path'))
        return True

    async def _send(self, broadcast: dict[str, Any], recipient: dict[str, Any]) -> None:
        message = render_message(broadcast['message'], recipient.get('name', ''))
        keyboard = build_button(broadcast.get('button_text'), broadcast.get('button_url'))

        async def send() -> None:
            if broadcast.get('media_kind') == 'photo':
                await self.bot.send_photo(
                    chat_id=int(recipient['telegram_id']),
                    photo=FSInputFile(broadcast['media_path']),
                    caption=message,
                    reply_markup=keyboard,
                    parse_mode=None,
                )
            elif broadcast.get('media_kind') == 'video':
                await self.bot.send_video(
                    chat_id=int(recipient['telegram_id']),
                    video=FSInputFile(broadcast['media_path']),
                    caption=message,
                    reply_markup=keyboard,
                    parse_mode=None,
                    supports_streaming=True,
                )
            else:
                await self.bot.send_message(
                    chat_id=int(recipient['telegram_id']),
                    text=message,
                    reply_markup=keyboard,
                    parse_mode=None,
                )

        try:
            await send()
        except TelegramRetryAfter as error:
            await asyncio.sleep(float(error.retry_after))
            await send()

    @staticmethod
    def delete_media(media_path: str | None) -> None:
        if not media_path:
            return
        try:
            Path(media_path).unlink(missing_ok=True)
        except OSError:
            logger.exception('Не удалось удалить медиафайл %s', media_path)
