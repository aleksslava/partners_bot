from aiogram import Bot
from fastapi import FastAPI

from webhooks import pass_notification, site_order

WEBHOOKS_PREFIX = '/tg_partners'


def create_webhooks_app(bot: Bot, webhook_secret: str) -> FastAPI:
    """Создаёт общее FastAPI-приложение и подключает webhook-роутеры."""

    app = FastAPI(title='partners_bot webhooks')
    app.state.bot = bot
    app.state.webhook_secret = webhook_secret
    app.include_router(pass_notification.router, prefix=WEBHOOKS_PREFIX)
    app.include_router(site_order.router, prefix=WEBHOOKS_PREFIX)
    return app
