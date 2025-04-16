import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from config_data.amo_api import AmoCRMWrapper

logger = logging.getLogger(__name__)


class OuterMiddleware(BaseMiddleware):
    def __init__(self,
                 amo_api: AmoCRMWrapper,
                 fields_id: dict):
        self.amo_api = amo_api
        self.fields_id = fields_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:

        logger.info(
            'Вошли в миддлварь %s, тип события %s',
            __class__.__name__,
            event.__class__.__name__
        )

        data['amo_api'] = self.amo_api
        data['fields_id'] = self.fields_id

        result = await handler(event, data)

        logger.info('Выходим из миддлвари  %s', __class__.__name__)

        return result
