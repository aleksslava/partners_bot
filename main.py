import asyncio
import logging
import time
from pprint import pprint

import requests
from redis.asyncio.client import Redis
from aiogram import Bot, Dispatcher
from config_data.config import load_config, Config, fields_id
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from handlers.main_handlers import main_router
from config_data.amo_api import AmoCRMWrapper
from outer_middleware.outer_middleware import OuterMiddleware
from keybooards.main_keyboards import set_main_menu
from lexicon.lexicon_ru import start_menu


redis = Redis(decode_responses=True, host='localhost')


# Инициализация логера
logger = logging.getLogger(__name__)


async def main():
    # Конфигурируем логгер
    logging.basicConfig(
        level=logging.INFO,
        format='%(filename)s:%(lineno)d #%(levelname)-8s '
               '[%(asctime)s] - %(name)s - %(message)s')
    logger.info("Starting partners_bot")

    # Загружаем конфиг в переменную config
    config: Config = load_config()

    # Инициализируем бот и диспетчер
    bot: Bot = Bot(
        token=config.tg_bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    await set_main_menu(bot, start_menu)


    # Создаём объект связи с API AMOCRM
    amo_api = AmoCRMWrapper(
        path=config.amo_config.path_to_env,
        amocrm_subdomain=config.amo_config.amocrm_subdomain,
        amocrm_client_id=config.amo_config.amocrm_client_id,
        amocrm_redirect_url=config.amo_config.amocrm_redirect_url,
        amocrm_client_secret=config.amo_config.amocrm_client_secret,
        amocrm_secret_code=config.amo_config.amocrm_secret_code,
        amocrm_access_token=config.amo_config.amocrm_access_token,
        amocrm_refresh_token=config.amo_config.amocrm_refresh_token
    )


    # response = amo_api.get_customer_by_phone(phone_number='79670215847')
    # pprint(response, indent=4)

    dp = Dispatcher()

    dp.include_router(main_router)
    dp.update.middleware(OuterMiddleware(amo_api, fields_id, bot, redis))
    logger.info("partners_bot started succesful")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
