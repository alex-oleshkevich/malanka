import json
import typing as t
from starlette import status
from starlette.concurrency import run_until_first_complete
from starlette.websockets import WebSocket


class Channel:
    encoding: t.Optional[str] = None
    event_stream: t.Optional[t.AsyncIterator] = None

    def __init__(self, scope, receive, send):
        assert scope['type'] == 'websocket'
        self.scope = scope
        self.receive = receive
        self.send = send

    @classmethod
    def as_asgi(cls, stream: t.AsyncIterator) -> t.Callable:
        cls.event_stream = stream
        return cls

    async def dispatch(self) -> None:
        websocket = WebSocket(self.scope, self.receive, self.send)
        await self.connected(websocket)

        await run_until_first_complete(
            (self._receive_from_client, dict(ws=websocket)),
            (self._receive_from_channel, dict(ws=websocket)),
        )

    async def connected(self, ws: WebSocket) -> None:
        """Called on successful connection."""
        await ws.accept()

    async def disconnected(self, ws: WebSocket, close_code: int) -> None:
        """Called after disconnection."""

    async def received(self, websocket: WebSocket, data: t.Any) -> None:
        """Called when a message from client has been received."""

    async def decode(self, ws: WebSocket, message: t.Mapping) -> t.Any:
        if self.encoding == 'text':
            if 'text' not in message:
                await ws.close(status.WS_1003_UNSUPPORTED_DATA)
                raise RuntimeError("Expected text websocket messages, but got bytes.")
            return message['text']
        elif self.encoding == 'bytes':
            if 'bytes' not in message:
                await ws.close(status.WS_1003_UNSUPPORTED_DATA)
                raise RuntimeError("Expected bytes websocket messages, but got text.")
        elif self.encoding == 'json':
            text = message['text'] if message.get('text') is not None else message['bytes'].decode('utf-8')
            try:
                return self.load_json(text)
            except json.decoder.JSONDecodeError:
                await ws.close(status.WS_1003_UNSUPPORTED_DATA)
                raise RuntimeError('Malformed JSON data received.')

        assert self.encoding is None, f"Unsupported 'encoding' attribute {self.encoding}"
        return message["text"] if message.get("text") else message["bytes"]

    def load_json(self, raw_data: str) -> t.Any:
        return json.loads(raw_data)

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
        assert self.event_stream, 'No event stream defined.'

        async for message in self.event_stream:
            if self.encoding == 'text':
                await ws.send_text(message)
            elif self.encoding == 'bytes':
                await ws.send_bytes(message)
            elif self.encoding == 'json':
                await ws.send_json(message)

    def __await__(self) -> t.Any:
        return self.dispatch().__await__()


class TextChannel(Channel):
    encoding = 'text'


class JSONChannel(Channel):
    encoding = 'json'
