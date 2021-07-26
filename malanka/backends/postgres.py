import asyncio
import asyncpg
import typing as t

from malanka.backends._base import BaseBackend, Event


class PostgresBackend(BaseBackend):
    _connection: asyncpg.Connection

    def __init__(self, url: str) -> None:
        self._url = url
        self._queue: asyncio.Queue[Event] = asyncio.Queue()

    async def connect(self) -> None:
        self._connection = await asyncpg.connect(self._url)

    async def disconnect(self) -> None:
        await self._connection.close()

    async def subscribe(self, channel: str) -> None:
        await self._connection.add_listener(channel, self._listener)

    async def unsubscribe(self, channel: str) -> None:
        await self._connection.remove_listener(channel, self._listener)

    async def publish(self, channel: str, message: str) -> None:
        await self._connection.execute('select pg_notify($1, $2);', channel, message)

    def _listener(self, *args: t.Any) -> None:
        connection, pid, channel, payload = args
        self._queue.put_nowait(Event(channel=channel, message=payload))

    async def next_item(self) -> Event:
        return await self._queue.get()
