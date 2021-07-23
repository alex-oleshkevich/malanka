import json
import typing as t
from starlette import status
from starlette.concurrency import run_until_first_complete
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket

from malanka.streams import Stream


class Socket:
    stream: Stream
    channel_name: str
    websocket: WebSocket
    encoding: t.Optional[str] = None

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope['type'] == 'websocket'

        self.scope = scope
        self.receive = receive
        self.send = send

    async def dispatch(self) -> None:
        """Handles client connection.
        This method doesn't return while the connection is up."""

        assert self.stream, 'No event stream defined.'

        self.websocket = WebSocket(self.scope, self.receive, self.send)
        async with self.stream.subscribe(self.get_channel_name()):  # type: ignore
            # typing is ignored because I don't know how to properly type decorator-based async context managers
            # without cognitive overhead.
            await self.connected(self.websocket)

            # connection closes if at least one of these functions returns
            await run_until_first_complete(
                (self._receive_from_client, dict(ws=self.websocket)),
                (self._receive_from_stream, dict(ws=self.websocket)),
            )

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

        return self.decode_fallback(ws, data)

    def decode_fallback(self, ws: WebSocket, data: t.Mapping) -> t.Any:
        """Handle unsupported encoding by overriding this method.
        Override this method to support custom data encodings.

        Example:
            import msgpack

            class MsgpackSocket:
                def decode_fallback(self, ws, data):
                    return msgpack.loads(data["text"])
        """
        return data["text"] if data.get("text") else data["bytes"]

    async def broadcast(self, data: t.Any) -> None:
        """Send message to all channel members including this connection."""
        await self.stream.publish(self.get_channel_name(), data)

    def get_channel_name(self) -> str:
        """Return current name. Override this function to set a dynamic channel name.

        Example:
            def get_channel_name(self) -> str:
                return 'user.%s' % self.scope['user_id']
        """
        assert self.channel_name, 'Channel name is not set.'
        return self.channel_name

    def load_json(self, raw_data: str) -> t.Any:
        """Parse JSON encoded raw data. Override this method to customize JSON parsing.

        Example:
            import ujson
            def load_json(self, raw_data):
                return ujson.loads(raw_data)
        """
        return json.loads(raw_data)

    @classmethod
    def as_asgi(cls, stream: Stream, channel_name: str = None) -> t.Callable:
        """Create a new ASGI compatible class with stream and channel name properly set up.
        This is the primary way to use Socket class.

        Example:
            from starlette.routes import WebsocketRoute
            from malanka.streams import RedisStream

            routes = [
                WebSocketRoute('/ws', MySocket.as_asgi(RedisStream('redis://'))),
            ]
        """
        return type(
            'Inner' + cls.__name__,
            (cls,),
            dict(
                stream=stream or cls.stream,
                channel_name=channel_name or cls.channel_name,
            ),
        )

    async def _receive_from_client(self, ws: WebSocket) -> None:
        """Listens socket for client generated events."""
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

    async def _receive_from_stream(self, ws: WebSocket) -> None:
        """Listens stream for data generated by another members."""
        async for data in self.stream.stream():
            if self.encoding == 'text':
                await ws.send_text(data)
            elif self.encoding == 'bytes':
                await ws.send_bytes(data)
            elif self.encoding == 'json':
                await ws.send_json(data)

    def __await__(self) -> t.Any:
        return self.dispatch().__await__()


class TextSocket(Socket):
    encoding = 'text'


class BinarySocket(Socket):
    encoding = 'bytes'


class JSONSocket(Socket):
    encoding = 'json'
