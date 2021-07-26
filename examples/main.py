import os.path
import typing as t
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from malanka.backends.postgres import PostgresBackend
from malanka.backends.redis import RedisBackend
from malanka.pubsub import PubSub
from malanka.sockets import TextSocket


def index_view(request):
    template_file = os.path.join(os.path.dirname(__file__), 'template.html')
    with open(template_file, 'r') as f:
        return HTMLResponse(f.read())


class MySocket(TextSocket):
    channel_name = 'office'

    async def received(self, websocket: WebSocket, data: t.Any) -> None:
        await self.broadcast(data)


stream = PubSub(RedisBackend('redis://'))
# stream = PubSub(PostgresBackend('postgresql://app:app@localhost/kamai'))

routes = [
    Route('/', index_view),
    WebSocketRoute('/ws', MySocket.as_asgi(stream)),
    WebSocketRoute('/ws2', MySocket.as_asgi(stream)),
]

app = Starlette(debug=True, routes=routes)
