import asyncio
import pytest
import typing as t
from starlette.testclient import TestClient
from unittest import mock

from malanka import TextSocket, WebSocket
from tests.conftest import postgres_pubsub, redis_pubsub


@pytest.mark.parametrize('pubsub', [redis_pubsub, postgres_pubsub])
def test_text_socket(pubsub):
    spy = mock.MagicMock()

    class Socket(TextSocket):
        async def received(self, websocket: WebSocket, data: t.Any) -> None:
            spy(data)

    app = Socket(pubsub=pubsub, channel_name='demo')
    client = TestClient(app)
    with client.websocket_connect("/demo") as websocket:
        websocket.send_text('hello')
        assert spy.assert_called_once_with('hello')
