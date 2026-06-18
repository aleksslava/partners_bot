from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from webhooks.app import create_webhooks_app
from webhooks.site_order import (
    SiteOrderWebhook,
    format_site_order_message,
)


def valid_payload() -> dict:
    return {
        'telegram_id': 123456789,
        'order_id': 'A-100500',
        'total': 12500,
        'items': [
            {
                'name': 'Терморегулятор',
                'quantity': 2,
                'total': 5000,
            },
        ],
    }


def test_site_order_payload_valid() -> None:
    payload = SiteOrderWebhook.model_validate(valid_payload())

    assert payload.telegram_id == 123456789
    assert payload.order_id == 'A-100500'
    assert len(payload.items) == 1


@pytest.mark.parametrize('field_name', ['telegram_id', 'order_id', 'total', 'items'])
def test_site_order_payload_required_fields(field_name: str) -> None:
    payload = valid_payload()
    payload.pop(field_name)

    with pytest.raises(ValidationError):
        SiteOrderWebhook.model_validate(payload)


@pytest.mark.parametrize('telegram_id', [0, -1, 'abc'])
def test_site_order_payload_invalid_telegram_id(telegram_id: object) -> None:
    payload = valid_payload()
    payload['telegram_id'] = telegram_id

    with pytest.raises(ValidationError):
        SiteOrderWebhook.model_validate(payload)


@pytest.mark.parametrize(
    'items',
    [
        [],
        [{'name': '', 'quantity': 1, 'total': 100}],
        [{'name': 'Товар', 'quantity': 0, 'total': 100}],
        [{'name': 'Товар', 'quantity': 1, 'total': -1}],
    ],
)
def test_site_order_payload_invalid_items(items: list[dict]) -> None:
    payload = valid_payload()
    payload['items'] = items

    with pytest.raises(ValidationError):
        SiteOrderWebhook.model_validate(payload)


def test_format_site_order_message_contains_order_data() -> None:
    payload = SiteOrderWebhook.model_validate(valid_payload())

    message = format_site_order_message(payload)

    assert 'A-100500' in message
    assert '12 500 ₽' in message
    assert 'Терморегулятор' in message
    assert '2 шт.' in message


def test_site_order_webhook_unauthorized() -> None:
    bot = AsyncMock()
    app = create_webhooks_app(bot=bot, webhook_secret='secret')
    client = TestClient(app)

    response = client.post('/tg_partners/site-order', json=valid_payload())

    assert response.status_code == 401
    assert response.json() == {'detail': 'unauthorized'}
    bot.send_message.assert_not_called()


def test_site_order_webhook_sends_message() -> None:
    bot = AsyncMock()
    app = create_webhooks_app(bot=bot, webhook_secret='secret')
    client = TestClient(app)

    response = client.post(
        '/tg_partners/site-order',
        json=valid_payload(),
        headers={'X-Webhook-Secret': 'secret'},
    )

    assert response.status_code == 200
    assert response.json() == {'ok': True}
    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.kwargs['chat_id'] == 123456789
    assert 'A-100500' in bot.send_message.await_args.kwargs['text']


def test_site_order_webhook_telegram_send_failed() -> None:
    bot = AsyncMock()
    bot.send_message.side_effect = RuntimeError('telegram error')
    app = create_webhooks_app(bot=bot, webhook_secret='secret')
    client = TestClient(app)

    response = client.post(
        '/tg_partners/site-order',
        json=valid_payload(),
        headers={'X-Webhook-Secret': 'secret'},
    )

    assert response.status_code == 502
    assert response.json() == {'detail': 'telegram_send_failed'}


def test_webhooks_app_includes_site_order_route() -> None:
    bot = AsyncMock()
    app = create_webhooks_app(bot=bot, webhook_secret='secret')

    routes = {getattr(route, 'path', '') for route in app.routes}

    assert '/tg_partners/site-order' in routes
