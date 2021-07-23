import json
import typing as t
from starlette import status
from starlette.concurrency import run_until_first_complete
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket

from malanka.streams import Stream


class Socket:
    channel_name: str
    event_stream: Stream
    encoding: t.Optional[str] = None

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope['type'] == 'websocket'
        self.scope = scope
        self.receive = receive
        self.send = send

    async def dispatch(self) -> None:
        assert self.event_stream, 'No event stream defined.'
        try:
            await self.event_stream.subscribe(self.get_channel_name())

            ws = WebSocket(self.scope, self.receive, self.send)
            await self.connected(ws)

            await run_until_first_complete(
                (self._receive_from_client, dict(ws=ws)),
                (self._receive_from_channel, dict(ws=ws)),
            )
        finally:
            await self.event_stream.unsubscribe()

    async def connected(self, ws: WebSocket) -> None:
        """Called on successful connection."""
        await ws.accept()

    async def disconnected(self, ws: WebSocket, close_code: int) -> None:
        """Called after disconnection."""

    async def received(self, websocket: WebSocket, data: t.Any) -> None:
        """Called when a message from client has been received."""

    async def decode(self, ws: WebSocket, data: t.Mapping) -> t.Any:
        if self.encoding == 'text':
            if 'text' not in data:
                await ws.close(status.WS_1003_UNSUPPORTED_DATA)
                raise RuntimeError("Expected text websocket messages, but got bytes.")
            return data['text']
        elif self.encoding == 'bytes':
            if 'bytes' not in data:
                await ws.close(status.WS_1003_UNSUPPORTED_DATA)
                raise RuntimeError("Expected bytes websocket messages, but got text.")
        elif self.encoding == 'json':
            text = data['text'] if data.get('text') is not None else data['bytes'].decode('utf-8')
            try:
                return self.load_json(text)
            except json.decoder.JSONDecodeError:
                await ws.close(status.WS_1003_UNSUPPORTED_DATA)
                raise RuntimeError('Malformed JSON data received.')

        assert self.encoding is None, f"Unsupported 'encoding' attribute {self.encoding}"
        return data["text"] if data.get("text") else data["bytes"]

    async def broadcast(self, data: t.Any) -> None:
        """Send message to all channel members including myself."""
        await self.event_stream.publish(self.get_channel_name(), data)

    def get_channel_name(self) -> str:
        assert self.channel_name, 'Channel name is not set.'
        return self.channel_name

    def load_json(self, raw_data: str) -> t.Any:
        return json.loads(raw_data)

    @classmethod
    def as_asgi(cls, stream: Stream, channel_name: str = None) -> t.Callable:
        return type(
            'Inner' + cls.__name__,
            (cls,),
            dict(
                event_stream=stream or cls.event_stream,
                channel_name=channel_name or cls.channel_name,
            ),
        )

    async def _receive_from_client(self, ws: WebSocket) -> None:
        close_code = status.WS_1000_NORMAL_CLOSURE
        try:
            while True:
                message = await ws.receive()
                if message['type'] == 'websocket.receive':
                    data = await self.decode(ws, message)
                    await self.received(ws, data)
                elif message['type'] == 'websocket.disconnect':
                    close_code = int(message.get('code', status.WS_1000_NORMAL_CLOSURE))
                    break
        except Exception:
            close_code = status.WS_1011_INTERNAL_ERROR
            raise
        finally:
            await self.disconnected(ws, close_code)

    async def _receive_from_channel(self, ws: WebSocket) -> None:
        async for message in self.event_stream.stream():
            if self.encoding == 'text':
                await ws.send_text(message)
            elif self.encoding == 'bytes':
                await ws.send_bytes(message)
            elif self.encoding == 'json':
                await ws.send_json(message)

    def __await__(self) -> t.Any:
        return self.dispatch().__await__()


class TextSocket(Socket):
    encoding = 'text'


class JSONSocket(Socket):
    encoding = 'json'
