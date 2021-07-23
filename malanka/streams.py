import aioredis
import async_timeout
import asyncio
import typing as t
from contextlib import asynccontextmanager


class Stream(t.Protocol):
    def stream(self) -> t.AsyncIterator:
        ...

    async def publish(self, channel: str, data: t.Any) -> None:
        ...

    async def subscribe(self, channel: str) -> t.AsyncIterator[None]:
        ...


class RedisStream:
    def __init__(self, url: str, *, redis_client: t.Union[str, aioredis.Redis] = None):
        if url:
            self.client = aioredis.from_url(url)
        elif redis_client:
            self.client = redis_client
        else:
            raise ValueError('RedisStream needs either url argument or redis_client.')
        self.pubsub = self.client.pubsub()

    async def stream(self) -> t.AsyncGenerator:
        while True:
            try:
                async with async_timeout.timeout(1):
                    message = await self.pubsub.get_message(ignore_subscribe_messages=True)
                    if message is not None:
                        yield message['data'].decode('utf-8')
                    await asyncio.sleep(0.01)
            except asyncio.TimeoutError:
                pass

    async def publish(self, channel: str, data: t.Any) -> None:
        await self.client.publish(channel, data)

    @asynccontextmanager
    async def subscribe(self, channel: str) -> t.AsyncIterator[None]:
        try:
            await self.pubsub.subscribe(channel)
            yield
        finally:
            await self.pubsub.unsubscribe()

    async def unsubscribe(self) -> None:
        await self.pubsub.unsubscribe()
