import os.path
import typing as t
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from malanka.channels import TextSocket
from malanka.streams import RedisStream


def index_view(request):
    template_file = os.path.join(os.path.dirname(__file__), 'template.html')
    with open(template_file, 'r') as f:
        return HTMLResponse(f.read())


class MySocket(TextSocket):
    channel_name = 'office'

    async def received(self, websocket: WebSocket, data: t.Any) -> None:
        await self.broadcast(data)


routes = [
    Route('/', index_view),
    WebSocketRoute('/ws', MySocket.as_asgi(RedisStream('redis://'))),
    WebSocketRoute('/ws2', MySocket.as_asgi(RedisStream('redis://'))),
]

app = Starlette(debug=True, routes=routes)
