import asyncio
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from config_data.config import AdminWebConfig
from web_admin.service import BroadcastService, UploadValidationError, parse_recipients
from web_admin.storage import BroadcastStorage
from webhooks.app import create_webhooks_app


def make_xlsx(rows: list[tuple[object, object]], headers=('telegram_id', 'Имя')) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
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


def test_parse_recipients_validates_and_deduplicates() -> None:
    content = make_xlsx(
        [
            (123, 'Анна'),
            (123, 'Дубль'),
            ('bad-id', 'Ошибка'),
            (456, ''),
        ]
    )

    recipients, duplicate_count, invalid_count = parse_recipients(
        content,
        'Здравствуйте, [Имя]!',
    )

    assert [item['status'] for item in recipients] == [
        'pending',
        'skipped',
        'skipped',
        'skipped',
    ]
    assert duplicate_count == 1
    assert invalid_count == 2


def test_parse_recipients_requires_telegram_id_column() -> None:
    content = make_xlsx([(123, 'Анна')], headers=('id', 'Имя'))

    with pytest.raises(UploadValidationError, match='telegram_id'):
        parse_recipients(content, 'Сообщение')


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
        assert 'Корректных получателей' in response.text
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


def test_worker_sends_personalized_message_and_records_result(tmp_path: Path) -> None:
    bot = AsyncMock()
    storage = BroadcastStorage(tmp_path)
    service = BroadcastService(storage, bot)
    service.initialize()
    recipients, duplicates, invalid = parse_recipients(
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
        duplicate_count=duplicates,
        invalid_count=invalid,
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
    recipients, duplicates, invalid = parse_recipients(
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
        duplicate_count=duplicates,
        invalid_count=invalid,
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
    recipients, duplicates, invalid = parse_recipients(
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
        duplicate_count=duplicates,
        invalid_count=invalid,
    )
    storage.confirm_draft(broadcast_id)

    asyncio.run(service.process_next_due())

    broadcast = storage.get_broadcast(broadcast_id)
    assert broadcast['status'] == 'completed_with_errors'
    assert broadcast['success_count'] == 1
    assert broadcast['error_count'] == 1


def test_recovery_does_not_resend_ambiguous_recipient(tmp_path: Path) -> None:
    storage = BroadcastStorage(tmp_path)
    storage.initialize()
    recipients, duplicates, invalid = parse_recipients(
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
        duplicate_count=duplicates,
        invalid_count=invalid,
    )
    storage.confirm_draft(broadcast_id)
    storage.mark_running(broadcast_id)
    first_recipient = storage.pending_recipients(broadcast_id)[0]
    storage.mark_recipient_sending(first_recipient['id'])

    storage.recover_interrupted()

    broadcast = storage.get_broadcast(broadcast_id)
    recovered_recipients = storage.get_recipients(broadcast_id)
    assert broadcast['status'] == 'scheduled'
    assert recovered_recipients[0]['status'] == 'error'
    assert recovered_recipients[1]['status'] == 'pending'
