import asyncio
import functools
import os
import pytest
from starlette.testclient import TestClient

from malanka import PubSub
from malanka.backends.postgres import PostgresBackend
from malanka.backends.redis import RedisBackend


@pytest.fixture
def test_client_factory(anyio_backend_name, anyio_backend_options):
    return functools.partial(
        TestClient,
        backend=anyio_backend_name,
        backend_options=anyio_backend_options,
    )


redis_pubsub = PubSub(RedisBackend(os.environ.get('REDIS_URL', 'redis://')))
postgres_pubsub = PubSub(
    PostgresBackend(os.environ.get('POSTGRES_URL', 'postgresql://postgres:postgres@localhost/postgres'))
)
