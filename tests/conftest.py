import os
from collections.abc import AsyncIterator, Iterator

import pytest
import respx
from mcp import Client

TOKEN: str = "00000000-0000-0000-0000-000000000000"
BASE_URL: str = "https://inventory.example.org"

os.environ["CHEMINVENTORY_TOKEN"] = TOKEN
os.environ["CHEMINVENTORY_URL"] = BASE_URL

import cheminventory_mcp.server  # noqa: E402, F401  (registers the tools)
from cheminventory_mcp.app import client, mcp  # noqa: E402


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=f"{BASE_URL}/api/", assert_all_called=False) as router:
        yield router


@pytest.fixture
async def session() -> AsyncIterator[Client]:
    client.cache_clear()

    async with Client(mcp) as connected:
        yield connected
