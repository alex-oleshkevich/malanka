import dataclasses

import abc
import typing as t


@dataclasses.dataclass
class Event:
    channel: str
    message: str


class BaseBackend(abc.ABC):
    @abc.abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    async def disconnect(self) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    async def subscribe(self, channel: str) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    async def unsubscribe(self, channel: str) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    async def publish(self, channel: str, message: str) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    async def next_item(self) -> Event:
        raise NotImplementedError

    async def __aenter__(self) -> None:
        await self.connect()

    async def __aexit__(self, *args: t.Any) -> None:
        await self.disconnect()
