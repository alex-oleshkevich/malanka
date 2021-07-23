import asyncio
import os.path
import typing as t
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from malanka.channels import TextChannel


def index_view(request):
    template_file = os.path.join(os.path.dirname(__file__), 'template.html')
    with open(template_file, 'r') as f:
        return HTMLResponse(f.read())


async def data_stream():
    while True:
        yield 'message'
        await asyncio.sleep(1)


class MyChannel(TextChannel):
    async def received(self, websocket: WebSocket, data: t.Any) -> None:
        print('received "%s"' % data)


routes = [
    Route('/', index_view),
    WebSocketRoute('/ws', MyChannel.as_asgi(data_stream())),
]

app = Starlette(debug=True, routes=routes)
