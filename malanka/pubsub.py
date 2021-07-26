import asyncio
import typing as t
from contextlib import asynccontextmanager

from malanka.backends._base import BaseBackend, Event


class Unsubscribed(Exception):
    """Abort async iteration on unsubscription."""


class Subscriber:
    def __init__(self, queue: asyncio.Queue[t.Union[Event, None]]) -> None:
        self._queue = queue

    async def __aiter__(self) -> t.Optional[t.AsyncGenerator[Event, None]]:
        try:
            while True:
                yield await self.get()
        except Unsubscribed:
            pass

    async def get(self) -> Event:
        item = await self._queue.get()
        if item is None:
            raise Unsubscribed()
        return item


class PubSub:
    _listener_task: asyncio.Task

    def __init__(self, backend: BaseBackend) -> None:
        self._backend = backend
        self._subscribers: dict[str, set[asyncio.Queue[t.Union[Event, None]]]] = {}

    async def connect(self) -> None:
        await self._backend.connect()
        self._listener_task = asyncio.create_task(self._listen_for_events())

    async def disconnect(self) -> None:
        if self._listener_task.done():
            self._listener_task.result()
        else:
            self._listener_task.cancel()
        await self._backend.disconnect()

    @asynccontextmanager
    async def subscribe(self, channel: str) -> t.AsyncIterator[Subscriber]:
        queue: asyncio.Queue[t.Union[Event, None]] = asyncio.Queue()
        try:
            if not self._subscribers.get(channel):
                await self._backend.subscribe(channel)
                self._subscribers[channel] = {queue}
            else:
                self._subscribers[channel].add(queue)
            yield Subscriber(queue)
            self._subscribers[channel].remove(queue)

            if not self._subscribers.get(channel):
                # delete key from subscribers when it has zero listeners
                # also, unsubscribe from the backend service
                del self._subscribers[channel]
                await self._backend.unsubscribe(channel)
        finally:
            await queue.put(None)

    async def publish(self, channel: str, message: str) -> None:
        await self._backend.publish(channel, message)

    async def __aenter__(self) -> None:
        await self.connect()

    async def __aexit__(self, *args: t.Any) -> None:
        await self.disconnect()

    async def _listen_for_events(self) -> None:
        while True:
            event = await self._backend.next_item()
            for queue in self._subscribers.get(event.channel, []):
                await queue.put(event)
