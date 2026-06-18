import logging
from typing import Annotated

from aiogram import Bot
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from lexicon.lexicon_ru import site_order_webhook_message
from webhooks.dependencies import get_bot, verify_webhook_secret

logger = logging.getLogger(__name__)
router = APIRouter()


class SiteOrderItem(BaseModel):
    """Одна товарная позиция из заказа, полученного от сайта."""

    name: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    total: float = Field(ge=0)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Убирает пробелы по краям и запрещает пустое название товара."""

        value = value.strip()
        if not value:
            raise ValueError('name is required')
        return value


class SiteOrderWebhook(BaseModel):
    """Payload webhook-а о заказе, который сайт отправляет боту."""

    telegram_id: int = Field(gt=0)
    order_id: str = Field(min_length=1)
    total: float = Field(ge=0)
    items: list[SiteOrderItem] = Field(min_length=1)

    @field_validator('order_id')
    @classmethod
    def validate_order_id(cls, value: str) -> str:
        """Убирает пробелы по краям и запрещает пустой номер заказа."""

        value = value.strip()
        if not value:
            raise ValueError('order_id is required')
        return value


def format_money(value: float) -> str:
    """Форматирует сумму для сообщения пользователю: 12500 -> 12 500."""

    if float(value).is_integer():
        return f'{int(value):,}'.replace(',', ' ')
    return f'{value:,.2f}'.replace(',', ' ').replace('.', ',')


def format_site_order_message(order: SiteOrderWebhook) -> str:
    """Собирает Telegram-сообщение о заказе по шаблону из лексикона."""

    items = '\n'.join(
        f'- {item.name}, {item.quantity} шт. = {format_money(item.total)} ₽'
        for item in order.items
    )
    return site_order_webhook_message.format(
        order_id=order.order_id,
        total=format_money(order.total),
        items=items,
    )


@router.post('/site-order', dependencies=[Depends(verify_webhook_secret)])
async def site_order_webhook(
    payload: SiteOrderWebhook,
    bot: Annotated[Bot, Depends(get_bot)],
) -> dict[str, bool]:
    """Отправляет пользователю Telegram-сообщение о заказе с сайта."""

    try:
        await bot.send_message(
            chat_id=payload.telegram_id,
            text=format_site_order_message(payload),
        )
    except Exception:
        logger.exception(
            'Не удалось отправить webhook-сообщение пользователю %s',
            payload.telegram_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='telegram_send_failed',
        )

    return {'ok': True}
