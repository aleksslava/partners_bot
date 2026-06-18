from typing import Annotated

from aiogram import Bot
from fastapi import Header, HTTPException, Request, status


def get_bot(request: Request) -> Bot:
    """Возвращает экземпляр Telegram-бота из состояния FastAPI-приложения."""

    return request.app.state.bot


def verify_webhook_secret(
    request: Request,
    x_webhook_secret: Annotated[str | None, Header()] = None,
) -> None:
    """Проверяет общий секрет webhook-а из заголовка X-Webhook-Secret."""

    if x_webhook_secret != request.app.state.webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='unauthorized',
        )
