import logging
from pprint import pprint
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject
from redis.asyncio import Redis

from config_data.amo_api import AmoCRMWrapper

logger = logging.getLogger(__name__)


class OuterMiddleware(BaseMiddleware):
    def __init__(self,
                 amo_api: AmoCRMWrapper,
                 fields_id: dict,
                 bot: Bot,
                 redis: Redis
                 ):
        self.amo_api = amo_api
        self.fields_id = fields_id
        self.bot = bot
        self.redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:

        try:
            if event.model_dump().get('callback_query', ''):
                user_id = event.model_dump().get('callback_query').get('from_user').get('id')
                user_name = event.model_dump().get('callback_query').get('from_user').get('username')
            elif event.model_dump().get('message', ''):
                user_id = event.model_dump().get('message').get('from_user').get('id')
                user_name = event.model_dump().get('message').get('from_user').get('username')
            else:
                user_id = 0
                user_name = ''

            if user_id and user_name:
                await self.redis.set(name=str(user_id), value=user_name)
            else:
                logger.error('Не удалось определить telegram_id покупателя')

            response = await self.redis.keys()
            logger.error(response)
        except BaseException as error:
            logger.error(error)

        data['amo_api'] = self.amo_api
        data['fields_id'] = self.fields_id

        result = await handler(event, data)



        return result
