from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Bot
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from config_data.config import AdminWebConfig
from web_admin.auth import LoginRateLimiter
from web_admin.routes import ADMIN_PREFIX, router as admin_web_router
from web_admin.service import BroadcastService
from web_admin.storage import BroadcastStorage
from webhooks import pass_notification, site_order

WEBHOOKS_PREFIX = '/tg_partners'


def create_webhooks_app(
    bot: Bot,
    webhook_secret: str,
    admin_config: AdminWebConfig | None = None,
) -> FastAPI:
    """Создаёт общее FastAPI-приложение и подключает webhook-роутеры."""

    admin_service = None
    if admin_config is not None and admin_config.enabled:
        admin_service = BroadcastService(
            storage=BroadcastStorage(admin_config.data_dir),
            bot=bot,
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if admin_service is not None:
            admin_service.initialize()
            admin_service.start()
        yield
        if admin_service is not None:
            await admin_service.stop()

    app = FastAPI(title='partners_bot webhooks', lifespan=lifespan)
    app.state.bot = bot
    app.state.webhook_secret = webhook_secret
    app.include_router(pass_notification.router, prefix=WEBHOOKS_PREFIX)
    app.include_router(site_order.router, prefix=WEBHOOKS_PREFIX)
    if admin_service is not None and admin_config is not None:
        app.state.admin_service = admin_service
        app.state.admin_config = admin_config
        app.state.admin_rate_limiter = LoginRateLimiter()
        app.add_middleware(
            SessionMiddleware,
            secret_key=admin_config.session_secret,
            session_cookie='partners_admin_session',
            max_age=12 * 60 * 60,
            path=ADMIN_PREFIX,
            same_site='strict',
            https_only=True,
        )
        static_dir = Path(__file__).resolve().parent.parent / 'web_admin' / 'static'
        app.mount(f'{ADMIN_PREFIX}/static', StaticFiles(directory=static_dir), name='admin-static')
        app.include_router(admin_web_router)
    return app
