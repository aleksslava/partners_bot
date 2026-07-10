import asyncio
from pathlib import Path
from typing import Any

import httpx


class MaxServiceUnavailable(RuntimeError):
    pass


class MaxDeliveryError(RuntimeError):
    pass


class MaxBroadcastClient:
    def __init__(
        self,
        base_url: str,
        secret: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip('/'),
            headers={'X-Webhook-Secret': secret},
            timeout=httpx.Timeout(30, connect=5),
            transport=transport,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def upload_media(self, media_path: str) -> dict[str, str]:
        path = Path(media_path)
        content = await asyncio.to_thread(path.read_bytes)
        response = await self._request(
            'POST',
            '/broadcast/media',
            files={'file': (path.name, content, 'application/octet-stream')},
        )
        payload = response.json()
        try:
            media_type = str(payload['media_type'])
            token = str(payload['token'])
        except (KeyError, TypeError) as error:
            raise MaxDeliveryError('Сервис MAX вернул некорректный ответ') from error
        if media_type not in {'image', 'video'} or not token:
            raise MaxDeliveryError('Сервис MAX вернул некорректный ответ')
        return {'media_type': media_type, 'token': token}

    async def send_message(
        self,
        *,
        max_id: int,
        text: str,
        button_text: str | None,
        button_url: str | None,
        media_type: str | None,
        media_token: str | None,
    ) -> None:
        payload: dict[str, Any] = {'max_id': max_id, 'text': text}
        if button_text and button_url:
            payload['button'] = {'text': button_text, 'url': button_url}
        if media_type and media_token:
            payload['media'] = {'media_type': media_type, 'token': media_token}
        await self._request('POST', '/broadcast/send', json=payload)

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        delays = (0, 1, 2)
        last_transport_error: Exception | None = None
        for attempt, delay in enumerate(delays):
            if delay:
                await asyncio.sleep(delay)
            try:
                response = await self.client.request(method, url, **kwargs)
            except (httpx.ConnectError, httpx.TimeoutException) as error:
                last_transport_error = error
                if attempt < len(delays) - 1:
                    continue
                raise MaxServiceUnavailable('Сервис MAX недоступен') from error

            if response.status_code in {429, 503} and attempt < len(delays) - 1:
                continue
            if response.status_code in {429, 503}:
                raise MaxServiceUnavailable(
                    f'Сервис MAX временно недоступен: HTTP {response.status_code}'
                )
            if response.status_code in {401, 403, 404}:
                raise MaxServiceUnavailable(
                    f'Интеграция MAX недоступна: HTTP {response.status_code}'
                )
            if response.is_error:
                detail = response.text[:300]
                raise MaxDeliveryError(
                    f'Ошибка сервиса MAX: HTTP {response.status_code}: {detail}'
                )
            return response

        raise MaxServiceUnavailable('Сервис MAX недоступен') from last_transport_error
