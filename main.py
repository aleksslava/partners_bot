import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config_data.config import load_config, Config
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from handlers.main_handlers import main_router

# Инициализация логера
logger = logging.getLogger(__name__)

async def main(storage: MemoryStorage | None = MemoryStorage()):
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

    dp = Dispatcher(storage=storage)

    dp.include_router(main_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

    logger.info("partners_bot started succesful")

if __name__ == "__main__":
    asyncio.run(main())