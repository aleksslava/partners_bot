import asyncio
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import httpx
from fastapi.testclient import TestClient
from openpyxl import Workbook

from config_data.config import AdminWebConfig
from web_admin.max_client import MaxBroadcastClient, MaxServiceUnavailable
from web_admin.service import (
    BroadcastService,
    UploadValidationError,
    message_limit,
    parse_recipients,
)
from web_admin.storage import BroadcastStorage
from webhooks.app import create_webhooks_app


def make_xlsx(
    rows: list[tuple],
    headers=('telegram_id', 'max_id', 'Имя'),
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        if headers == ('telegram_id', 'max_id', 'Имя') and len(row) == 2:
            sheet.append((row[0], None, row[1]))
        else:
            sheet.append(row)
    content = BytesIO()
    workbook.save(content)
    workbook.close()
    return content.getvalue()


def get_csrf(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


def login(client: TestClient, password: str = 'admin-password') -> str:
    response = client.post(
        '/tg_partners/admin/login',
        data={'password': password},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return get_csrf(client.get('/tg_partners/admin/new'))


class FakeMaxClient:
    def __init__(self, send_error: Exception | None = None) -> None:
        self.send_error = send_error
        self.uploads: list[str] = []
        self.messages: list[dict] = []
        self.closed = False

    async def upload_media(self, media_path: str) -> dict[str, str]:
        self.uploads.append(media_path)
        return {'media_type': 'image', 'token': 'max-media-token'}

    async def send_message(self, **kwargs) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.messages.append(kwargs)

    async def close(self) -> None:
        self.closed = True


def test_parse_recipients_validates_and_deduplicates() -> None:
    content = make_xlsx(
        [
            (123, 'Анна'),
            (123, 'Дубль'),
            ('bad-id', 'Ошибка'),
            (456, ''),
        ]
    )

    recipients, stats = parse_recipients(
        content,
        'Здравствуйте, [Имя]!',
    )

    assert [item['deliveries'][0]['status'] for item in recipients] == [
        'pending',
        'skipped',
        'skipped',
        'skipped',
    ]
    assert stats['telegram']['duplicates'] == 1
    assert stats['telegram']['invalid'] == 2


def test_parse_recipients_requires_telegram_id_column() -> None:
    content = make_xlsx([(123, 456, 'Анна')], headers=('id', 'max_id', 'Имя'))

    with pytest.raises(UploadValidationError, match='telegram_id'):
        parse_recipients(content, 'Сообщение')


def test_parse_recipients_validates_each_platform_independently() -> None:
    content = make_xlsx(
        [
            (100, 200, 'Анна'),
            (100, 201, 'Борис'),
            (102, 201, 'Вера'),
            (None, 203, 'Галина'),
            (104, None, 'Денис'),
        ]
    )

    recipients, stats = parse_recipients(
        content,
        'Здравствуйте, [Имя]!',
        targets={'telegram', 'max'},
    )

    assert stats['telegram'] == {
        'ready': 3,
        'skipped': 2,
        'duplicates': 1,
        'invalid': 1,
    }
    assert stats['max'] == {
        'ready': 3,
        'skipped': 2,
        'duplicates': 1,
        'invalid': 1,
    }
    second_row = {
        delivery['platform']: delivery for delivery in recipients[1]['deliveries']
    }
    assert second_row['telegram']['status'] == 'skipped'
    assert second_row['max']['status'] == 'pending'


def test_message_limit_uses_strictest_selected_platform() -> None:
    assert message_limit({'telegram'}, False) == 4096
    assert message_limit({'max'}, True) == 4000
    assert message_limit({'telegram', 'max'}, True) == 1024


def test_admin_login_session_and_csrf(tmp_path: Path) -> None:
    bot = AsyncMock()
    config = AdminWebConfig('admin-password', 'session-secret' * 3, tmp_path)
    app = create_webhooks_app(bot, 'webhook-secret', config)

    with TestClient(app, base_url='https://testserver') as client:
        unauthorized = client.get('/tg_partners/admin', follow_redirects=False)
        assert unauthorized.status_code == 303
        assert unauthorized.headers['location'].endswith('/login')

        bad_login = client.post(
            '/tg_partners/admin/login',
            data={'password': 'wrong'},
        )
        assert bad_login.status_code == 401
        assert 'Неверный пароль' in bad_login.text

        response = client.post(
            '/tg_partners/admin/login',
            data={'password': 'admin-password'},
            follow_redirects=False,
        )
        assert response.status_code == 303
        cookie = response.headers['set-cookie'].lower()
        assert 'httponly' in cookie
        assert 'secure' in cookie
        assert 'samesite=strict' in cookie

        csrf_response = client.post(
            '/tg_partners/admin/logout',
            data={'csrf_token': 'wrong'},
        )
        assert csrf_response.status_code == 403


def test_preview_confirm_and_cancel_scheduled_broadcast(tmp_path: Path) -> None:
    bot = AsyncMock()
    config = AdminWebConfig('admin-password', 'session-secret' * 3, tmp_path)
    app = create_webhooks_app(bot, 'webhook-secret', config)

    with TestClient(app, base_url='https://testserver') as client:
        csrf_token = login(client)
        response = client.post(
            '/tg_partners/admin/preview',
            data={
                'csrf_token': csrf_token,
                'message': 'Здравствуйте, [Имя]!',
                'send_telegram': '1',
                'scheduled_at': '2099-01-01T12:00',
                'button_text': 'Подробнее',
                'button_url': 'https://example.com',
            },
            files={
                'recipients_file': (
                    'recipients.xlsx',
                    make_xlsx([(123, 'Анна'), (456, 'Иван')]),
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                ),
            },
        )
        assert response.status_code == 200
        assert 'Telegram' in response.text
        assert '2 готово' in response.text
        assert 'Здравствуйте, Анна!' in response.text

        drafts = app.state.admin_service.storage.list_broadcasts(include_drafts=True)
        assert len(drafts) == 1
        broadcast_id = drafts[0]['id']

        confirm = client.post(
            f'/tg_partners/admin/broadcasts/{broadcast_id}/confirm',
            data={'csrf_token': csrf_token},
            follow_redirects=False,
        )
        assert confirm.status_code == 303
        assert app.state.admin_service.storage.get_broadcast(broadcast_id)['status'] == 'scheduled'

        detail = client.get(f'/tg_partners/admin/broadcasts/{broadcast_id}')
        assert detail.status_code == 200
        assert 'Здравствуйте, [Имя]!' in detail.text

        cancel = client.post(
            f'/tg_partners/admin/broadcasts/{broadcast_id}/cancel',
            data={'csrf_token': csrf_token},
            follow_redirects=False,
        )
        assert cancel.status_code == 303
        assert app.state.admin_service.storage.get_broadcast(broadcast_id)['status'] == 'cancelled'


def test_new_broadcast_defaults_to_both_configured_bots(tmp_path: Path) -> None:
    bot = AsyncMock()
    config = AdminWebConfig(
        'admin-password',
        'session-secret' * 3,
        tmp_path,
        max_bot_api_secret='max-secret',
    )
    app = create_webhooks_app(bot, 'webhook-secret', config)

    with TestClient(app, base_url='https://testserver') as client:
        login(client)
        response = client.get('/tg_partners/admin/new')

    assert response.status_code == 200
    assert re.search(r'name="send_telegram"[^>]+checked', response.text)
    assert re.search(r'name="send_max"[^>]+checked', response.text)


def test_preview_creates_deliveries_for_both_bots(tmp_path: Path) -> None:
    bot = AsyncMock()
    config = AdminWebConfig(
        'admin-password',
        'session-secret' * 3,
        tmp_path,
        max_bot_api_secret='max-secret',
    )
    app = create_webhooks_app(bot, 'webhook-secret', config)

    with TestClient(app, base_url='https://testserver') as client:
        csrf_token = login(client)
        response = client.post(
            '/tg_partners/admin/preview',
            data={
                'csrf_token': csrf_token,
                'message': 'Здравствуйте, [Имя]!',
                'send_telegram': '1',
                'send_max': '1',
                'scheduled_at': '2099-01-01T12:00',
            },
            files={
                'recipients_file': (
                    'recipients.xlsx',
                    make_xlsx([(123, 923, 'Анна'), (456, 956, 'Иван')]),
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                ),
            },
        )

        assert response.status_code == 200
        assert '2 готово' in response.text
        broadcast = app.state.admin_service.storage.list_broadcasts(
            include_drafts=True
        )[0]
        recipients = app.state.admin_service.storage.get_recipients(broadcast['id'])
        assert broadcast['send_telegram'] == 1
        assert broadcast['send_max'] == 1
        assert all(item['telegram_delivery'] for item in recipients)
        assert all(item['max_delivery'] for item in recipients)
        status_response = client.get(
            f"/tg_partners/admin/broadcasts/{broadcast['id']}/status"
        )
        assert status_response.status_code == 200
        assert status_response.json()['platforms']['telegram']['valid_count'] == 2
        assert status_response.json()['platforms']['max']['valid_count'] == 2
        confirm = client.post(
            f"/tg_partners/admin/broadcasts/{broadcast['id']}/confirm",
            data={'csrf_token': csrf_token},
            follow_redirects=False,
        )
        assert confirm.status_code == 303
        detail = client.get(f"/tg_partners/admin/broadcasts/{broadcast['id']}")
        assert detail.status_code == 200
        assert '923' in detail.text
        assert 'Telegram' in detail.text
        assert 'MAX' in detail.text


def test_preview_rejects_max_when_integration_is_not_configured(tmp_path: Path) -> None:
    bot = AsyncMock()
    app = create_webhooks_app(
        bot,
        'webhook-secret',
        AdminWebConfig('admin-password', 'session-secret' * 3, tmp_path),
    )

    with TestClient(app, base_url='https://testserver') as client:
        csrf_token = login(client)
        response = client.post(
            '/tg_partners/admin/preview',
            data={
                'csrf_token': csrf_token,
                'message': 'Сообщение',
                'send_max': '1',
            },
            files={
                'recipients_file': (
                    'recipients.xlsx',
                    make_xlsx([(123, 923, 'Анна')]),
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                ),
            },
        )

    assert response.status_code == 422
    assert 'Интеграция MAX не настроена' in response.text


def test_worker_sends_personalized_message_and_records_result(tmp_path: Path) -> None:
    bot = AsyncMock()
    storage = BroadcastStorage(tmp_path)
    service = BroadcastService(storage, bot)
    service.initialize()
    recipients, stats = parse_recipients(
        make_xlsx([(123, 'Анна'), (456, 'Иван')]),
        'Привет, [Имя]!',
    )
    broadcast_id = storage.create_draft(
        message='Привет, [Имя]!',
        source_filename='recipients.xlsx',
        media_path=None,
        media_kind=None,
        media_original_name=None,
        button_text=None,
        button_url=None,
        scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        recipients=recipients,
        targets={'telegram'},
        validation_stats=stats,
    )
    assert storage.confirm_draft(broadcast_id)

    processed = asyncio.run(service.process_next_due())

    assert processed is True
    assert bot.send_message.await_count == 2
    sent_texts = [call.kwargs['text'] for call in bot.send_message.await_args_list]
    assert sent_texts == ['Привет, Анна!', 'Привет, Иван!']
    broadcast = storage.get_broadcast(broadcast_id)
    assert broadcast['status'] == 'completed'
    assert broadcast['success_count'] == 2


@pytest.mark.parametrize(
    ('media_kind', 'suffix', 'bot_method'),
    [('photo', '.jpg', 'send_photo'), ('video', '.mp4', 'send_video')],
)
def test_worker_sends_media_and_removes_file(
    tmp_path: Path,
    media_kind: str,
    suffix: str,
    bot_method: str,
) -> None:
    bot = AsyncMock()
    storage = BroadcastStorage(tmp_path)
    service = BroadcastService(storage, bot)
    service.initialize()
    media_path = service.media_dir / f'attachment{suffix}'
    media_path.write_bytes(b'test-media')
    recipients, stats = parse_recipients(
        make_xlsx([(123, 'Анна')]),
        'Сообщение',
    )
    broadcast_id = storage.create_draft(
        message='Сообщение',
        source_filename='recipients.xlsx',
        media_path=str(media_path),
        media_kind=media_kind,
        media_original_name=f'attachment{suffix}',
        button_text='Подробнее',
        button_url='https://example.com',
        scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        recipients=recipients,
        targets={'telegram'},
        validation_stats=stats,
    )
    storage.confirm_draft(broadcast_id)

    asyncio.run(service.process_next_due())

    getattr(bot, bot_method).assert_awaited_once()
    assert not media_path.exists()
    assert storage.get_broadcast(broadcast_id)['status'] == 'completed'


def test_worker_records_partial_telegram_error(tmp_path: Path) -> None:
    bot = AsyncMock()
    bot.send_message.side_effect = [None, RuntimeError('telegram unavailable')]
    storage = BroadcastStorage(tmp_path)
    service = BroadcastService(storage, bot)
    service.initialize()
    recipients, stats = parse_recipients(
        make_xlsx([(123, 'Анна'), (456, 'Иван')]),
        'Сообщение',
    )
    broadcast_id = storage.create_draft(
        message='Сообщение',
        source_filename='recipients.xlsx',
        media_path=None,
        media_kind=None,
        media_original_name=None,
        button_text=None,
        button_url=None,
        scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        recipients=recipients,
        targets={'telegram'},
        validation_stats=stats,
    )
    storage.confirm_draft(broadcast_id)

    asyncio.run(service.process_next_due())

    broadcast = storage.get_broadcast(broadcast_id)
    assert broadcast['status'] == 'completed_with_errors'
    assert broadcast['success_count'] == 1
    assert broadcast['error_count'] == 1


def test_worker_sends_to_both_bots_and_uploads_max_media_once(tmp_path: Path) -> None:
    bot = AsyncMock()
    max_client = FakeMaxClient()
    storage = BroadcastStorage(tmp_path)
    service = BroadcastService(storage, bot, max_client=max_client)
    service.initialize()
    media_path = service.media_dir / 'photo.jpg'
    media_path.write_bytes(b'image')
    recipients, stats = parse_recipients(
        make_xlsx([(123, 923, 'Анна'), (456, 956, 'Иван')]),
        'Привет, [Имя]!',
        targets={'telegram', 'max'},
        message_limit_value=1024,
    )
    broadcast_id = storage.create_draft(
        message='Привет, [Имя]!',
        source_filename='recipients.xlsx',
        media_path=str(media_path),
        media_kind='photo',
        media_original_name='photo.jpg',
        button_text='Подробнее',
        button_url='https://example.com',
        scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        recipients=recipients,
        targets={'telegram', 'max'},
        validation_stats=stats,
    )
    storage.confirm_draft(broadcast_id)

    asyncio.run(service.process_next_due())

    assert bot.send_photo.await_count == 2
    assert len(max_client.uploads) == 1
    assert len(max_client.messages) == 2
    assert [item['text'] for item in max_client.messages] == [
        'Привет, Анна!',
        'Привет, Иван!',
    ]
    broadcast = storage.get_broadcast(broadcast_id)
    assert broadcast['status'] == 'completed'
    assert broadcast['platform_stats']['telegram']['success_count'] == 2
    assert broadcast['platform_stats']['max']['success_count'] == 2


def test_max_outage_does_not_block_telegram(tmp_path: Path) -> None:
    bot = AsyncMock()
    max_client = FakeMaxClient(MaxServiceUnavailable('MAX offline'))
    storage = BroadcastStorage(tmp_path)
    service = BroadcastService(storage, bot, max_client=max_client)
    service.initialize()
    recipients, stats = parse_recipients(
        make_xlsx([(123, 923, 'Анна'), (456, 956, 'Иван')]),
        'Сообщение',
        targets={'telegram', 'max'},
    )
    broadcast_id = storage.create_draft(
        message='Сообщение',
        source_filename='recipients.xlsx',
        media_path=None,
        media_kind=None,
        media_original_name=None,
        button_text=None,
        button_url=None,
        scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        recipients=recipients,
        targets={'telegram', 'max'},
        validation_stats=stats,
    )
    storage.confirm_draft(broadcast_id)

    asyncio.run(service.process_next_due())

    assert bot.send_message.await_count == 2
    assert len(max_client.messages) == 0
    broadcast = storage.get_broadcast(broadcast_id)
    assert broadcast['platform_stats']['telegram']['success_count'] == 2
    assert broadcast['platform_stats']['max']['error_count'] == 2


def test_max_http_client_uses_internal_api(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == '/broadcast/media':
            return httpx.Response(
                200,
                json={'media_type': 'image', 'token': 'token'},
            )
        return httpx.Response(200, json={'ok': True})

    media_path = tmp_path / 'photo.jpg'
    media_path.write_bytes(b'image')
    client = MaxBroadcastClient(
        'http://max-service',
        'secret',
        transport=httpx.MockTransport(handler),
    )

    async def scenario() -> None:
        media = await client.upload_media(str(media_path))
        await client.send_message(
            max_id=123,
            text='Сообщение',
            button_text=None,
            button_url=None,
            media_type=media['media_type'],
            media_token=media['token'],
        )
        await client.close()

    asyncio.run(scenario())

    assert [request.url.path for request in requests] == [
        '/broadcast/media',
        '/broadcast/send',
    ]
    assert all(request.headers['X-Webhook-Secret'] == 'secret' for request in requests)


def test_max_http_client_retries_temporary_service_error() -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503, json={'detail': 'unavailable'})
        return httpx.Response(200, json={'ok': True})

    client = MaxBroadcastClient(
        'http://max-service',
        'secret',
        transport=httpx.MockTransport(handler),
    )

    async def scenario() -> None:
        await client.send_message(
            max_id=123,
            text='Сообщение',
            button_text=None,
            button_url=None,
            media_type=None,
            media_token=None,
        )
        await client.close()

    with patch('web_admin.max_client.asyncio.sleep', new=AsyncMock()) as sleep:
        asyncio.run(scenario())

    assert attempts == 3
    assert sleep.await_count == 2


def test_recovery_does_not_resend_ambiguous_recipient(tmp_path: Path) -> None:
    storage = BroadcastStorage(tmp_path)
    storage.initialize()
    recipients, stats = parse_recipients(
        make_xlsx([(123, 'Анна'), (456, 'Иван')]),
        'Сообщение',
    )
    broadcast_id = storage.create_draft(
        message='Сообщение',
        source_filename='recipients.xlsx',
        media_path=None,
        media_kind=None,
        media_original_name=None,
        button_text=None,
        button_url=None,
        scheduled_at=datetime.now(timezone.utc),
        recipients=recipients,
        targets={'telegram'},
        validation_stats=stats,
    )
    storage.confirm_draft(broadcast_id)
    storage.mark_running(broadcast_id)
    first_delivery = storage.pending_deliveries(broadcast_id)[0]
    storage.mark_delivery_sending(first_delivery['id'])

    storage.recover_interrupted()

    broadcast = storage.get_broadcast(broadcast_id)
    recovered_recipients = storage.get_recipients(broadcast_id)
    assert broadcast['status'] == 'scheduled'
    assert recovered_recipients[0]['telegram_delivery']['status'] == 'error'
    assert recovered_recipients[1]['telegram_delivery']['status'] == 'pending'


def test_storage_migrates_legacy_telegram_history(tmp_path: Path) -> None:
    database_path = tmp_path / 'broadcasts.sqlite3'
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL, source_filename TEXT NOT NULL,
            media_path TEXT, media_kind TEXT, media_original_name TEXT,
            button_text TEXT, button_url TEXT, status TEXT NOT NULL,
            scheduled_at TEXT NOT NULL, created_at TEXT NOT NULL,
            started_at TEXT, finished_at TEXT,
            total_count INTEGER NOT NULL DEFAULT 0,
            valid_count INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            skipped_count INTEGER NOT NULL DEFAULT 0,
            duplicate_count INTEGER NOT NULL DEFAULT 0,
            invalid_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
        );
        CREATE TABLE broadcast_recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broadcast_id INTEGER NOT NULL, row_number INTEGER NOT NULL,
            telegram_id INTEGER, raw_telegram_id TEXT,
            name TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, error TEXT
        );
        INSERT INTO broadcasts (
            id, message, source_filename, status, scheduled_at, created_at,
            total_count, valid_count, success_count
        ) VALUES (1, 'Old', 'old.xlsx', 'completed',
                  '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00',
                  1, 1, 1);
        INSERT INTO broadcast_recipients (
            broadcast_id, row_number, telegram_id, raw_telegram_id,
            name, status, error
        ) VALUES (1, 2, 123, '123', 'Анна', 'success', NULL);
        """
    )
    connection.commit()
    connection.close()

    storage = BroadcastStorage(tmp_path)
    storage.initialize()

    broadcast = storage.get_broadcast(1)
    recipients = storage.get_recipients(1)
    assert broadcast['send_telegram'] == 1
    assert broadcast['send_max'] == 0
    assert broadcast['platform_stats']['telegram']['success_count'] == 1
    assert recipients[0]['telegram_delivery']['status'] == 'success'
    assert recipients[0]['max_delivery'] is None
