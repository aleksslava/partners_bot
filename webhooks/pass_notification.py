import logging
from typing import Annotated

from aiogram import Bot
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from lexicon.lexicon_ru import new_password_message
from webhooks.dependencies import get_bot, verify_webhook_secret

logger = logging.getLogger(__name__)
router = APIRouter()


class PassNotificationWebhook(BaseModel):
    """Payload for sending new site credentials to a Telegram user."""

    telegram_id: int = Field(gt=0)
    username: str = Field(min_length=1)
    password: str = Field(alias='pass', min_length=1)

    @field_validator('username', 'password')
    @classmethod
    def validate_not_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('field is required')
        return value


def format_pass_notification_message(payload: PassNotificationWebhook) -> str:
    """Builds a Telegram message with new site credentials."""

    return new_password_message.format(
        login=payload.username,
        password=payload.password,
    )


@router.post('/pass_notification', dependencies=[Depends(verify_webhook_secret)])
async def pass_notification_webhook(
    payload: PassNotificationWebhook,
    bot: Annotated[Bot, Depends(get_bot)],
) -> dict[str, bool]:
    """Sends new site credentials to a Telegram user."""

    try:
        await bot.send_message(
            chat_id=payload.telegram_id,
            text=format_pass_notification_message(payload),
        )
    except Exception:
        logger.exception(
            'Failed to send pass notification webhook message to user %s',
            payload.telegram_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='telegram_send_failed',
        )

    return {'ok': True}
