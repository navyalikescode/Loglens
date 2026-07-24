import os

os.environ["SKIP_PHOENIX"] = "true"
os.environ["GROQ_API_KEY"] = ""

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture
async def client():
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c
