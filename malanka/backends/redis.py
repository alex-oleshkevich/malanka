import aioredis
import asyncio

from malanka.backends._base import BaseBackend, Event


class RedisBackend(BaseBackend):
    _listener_task: asyncio.Task

    def __init__(self, url: str) -> None:
        self._connection = aioredis.from_url(url)
        self._pubsub = self._connection.pubsub()
        self._queue: asyncio.Queue[Event] = asyncio.Queue()

    async def connect(self) -> None:
        await self._connection.__aenter__()

    async def disconnect(self) -> None:
        await self._connection.close()

    async def subscribe(self, channel: str) -> None:
        await self._pubsub.subscribe(channel)
        if not hasattr(self, '_listener_task'):
            self._listener_task = asyncio.create_task(self._listener(self._pubsub))

    async def unsubscribe(self, channel: str) -> None:
        await self._pubsub.unsubscribe(channel)

    async def publish(self, channel: str, message: str) -> None:
        await self._connection.publish(channel, message)

    async def next_item(self) -> Event:
        return await self._queue.get()

    async def _listener(self, pubsub: aioredis.client.PubSub) -> None:
        async for message in pubsub.listen():
            if message is not None and message['type'] == 'message':
                await self._queue.put(
                    Event(channel=message['channel'].decode('utf-8'), message=message['data'].decode('utf-8'))
                )
