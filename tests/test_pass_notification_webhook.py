from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from webhooks.app import create_webhooks_app
from webhooks.pass_notification import (
    PassNotificationWebhook,
    format_pass_notification_message,
)


def valid_payload() -> dict:
    return {
        'telegram_id': 123456789,
        'username': 'partner-login',
        'pass': 'secret-pass',
    }


def test_pass_notification_payload_valid() -> None:
    payload = PassNotificationWebhook.model_validate(valid_payload())

    assert payload.telegram_id == 123456789
    assert payload.username == 'partner-login'
    assert payload.password == 'secret-pass'


@pytest.mark.parametrize('field_name', ['telegram_id', 'username', 'pass'])
def test_pass_notification_payload_required_fields(field_name: str) -> None:
    payload = valid_payload()
    payload.pop(field_name)

    with pytest.raises(ValidationError):
        PassNotificationWebhook.model_validate(payload)


@pytest.mark.parametrize('telegram_id', [0, -1, 'abc'])
def test_pass_notification_payload_invalid_telegram_id(telegram_id: object) -> None:
    payload = valid_payload()
    payload['telegram_id'] = telegram_id

    with pytest.raises(ValidationError):
        PassNotificationWebhook.model_validate(payload)


@pytest.mark.parametrize(
    ('field_name', 'value'),
    [
        ('username', ''),
        ('username', '   '),
        ('pass', ''),
        ('pass', '   '),
    ],
)
def test_pass_notification_payload_empty_strings(
    field_name: str,
    value: str,
) -> None:
    payload = valid_payload()
    payload[field_name] = value

    with pytest.raises(ValidationError):
        PassNotificationWebhook.model_validate(payload)


def test_format_pass_notification_message_contains_credentials() -> None:
    payload = PassNotificationWebhook.model_validate(valid_payload())

    message = format_pass_notification_message(payload)

    assert 'partner-login' in message
    assert 'secret-pass' in message


def test_pass_notification_webhook_unauthorized() -> None:
    bot = AsyncMock()
    app = create_webhooks_app(bot=bot, webhook_secret='secret')
    client = TestClient(app)

    response = client.post('/tg_partners/pass_notification', json=valid_payload())

    assert response.status_code == 401
    assert response.json() == {'detail': 'unauthorized'}
    bot.send_message.assert_not_called()


def test_pass_notification_webhook_sends_message() -> None:
    bot = AsyncMock()
    app = create_webhooks_app(bot=bot, webhook_secret='secret')
    client = TestClient(app)

    response = client.post(
        '/tg_partners/pass_notification',
        json=valid_payload(),
        headers={'X-Webhook-Secret': 'secret'},
    )

    assert response.status_code == 200
    assert response.json() == {'ok': True}
    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.kwargs['chat_id'] == 123456789
    assert 'partner-login' in bot.send_message.await_args.kwargs['text']
    assert 'secret-pass' in bot.send_message.await_args.kwargs['text']


def test_pass_notification_webhook_telegram_send_failed() -> None:
    bot = AsyncMock()
    bot.send_message.side_effect = RuntimeError('telegram error')
    app = create_webhooks_app(bot=bot, webhook_secret='secret')
    client = TestClient(app)

    response = client.post(
        '/tg_partners/pass_notification',
        json=valid_payload(),
        headers={'X-Webhook-Secret': 'secret'},
    )

    assert response.status_code == 502
    assert response.json() == {'detail': 'telegram_send_failed'}


def test_webhooks_app_includes_pass_notification_route() -> None:
    bot = AsyncMock()
    app = create_webhooks_app(bot=bot, webhook_secret='secret')

    routes = {getattr(route, 'path', '') for route in app.routes}

    assert '/tg_partners/pass_notification' in routes
