import shutil
from typing import Any

import httpx
import pytest
import respx
from mcp import Client, StdioServerParameters
from mcp.types import Tool

from cheminventory_mcp import app, server
from cheminventory_mcp.client import ChemInventoryClient, ChemInventoryError
from tests.test_tools import ADDITIVE, CASES, FILE_TOOLS, READ_ONLY

URL: str = "https://lab.example.org"
ALL_TOOLS: set[str] = {case.tool for case in CASES} | FILE_TOOLS


async def call(response: httpx.Response | Exception) -> Any:
    with respx.mock() as api:
        api.post(f"{URL}/api/order/load").mock(side_effect=[response])

        return await ChemInventoryClient("token", URL).call("order/load")


@pytest.mark.anyio
@pytest.mark.parametrize("base_url", [URL, f"{URL}/"])
async def test_endpoint_url(base_url: str) -> None:
    with respx.mock(assert_all_called=True) as api:
        api.post(f"{URL}/api/general/units").respond(
            json={"status": "success", "data": []}
        )

        assert await ChemInventoryClient("token", base_url).call("general/units") == []


@pytest.mark.parametrize("base_url", ["http://lab.example.org", "lab.example.org", ""])
def test_rejects_non_https_url(base_url: str) -> None:
    with pytest.raises(ValueError, match="must use https"):
        ChemInventoryClient("token", base_url)


def test_default_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHEMINVENTORY_URL")
    app.client.cache_clear()

    try:
        assert (
            str(app.client()._http_client.base_url)
            == "https://app.cheminventory.net/api/"
        )
    finally:
        app.client.cache_clear()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(200, json={"status": "error", "data": []}), r"\[\]"),
        (httpx.Response(200, json={"status": "error"}), "None"),
        (httpx.Response(200, text="<html>Maintenance</html>"), "response is not JSON"),
        (httpx.Response(200, json=[1, 2]), "unexpected response"),
        (httpx.Response(200, json={"data": []}), "unexpected response"),
        (httpx.Response(401, json={"status": "error"}), "HTTP 401"),
        (httpx.ConnectError("connection refused"), "ConnectError: connection refused"),
        (httpx.ReadTimeout("timed out"), "ReadTimeout: timed out"),
    ],
)
async def test_errors(response: httpx.Response | Exception, message: str) -> None:
    with pytest.raises(ChemInventoryError, match=rf"^/order/load: {message}$"):
        await call(response)


@pytest.mark.anyio
async def test_success_without_data() -> None:
    assert await call(httpx.Response(200, json={"status": "success"})) is None


def test_main_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHEMINVENTORY_TOKEN")

    with pytest.raises(SystemExit, match="CHEMINVENTORY_TOKEN is not set"):
        server.main()


def test_main_rejects_http_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHEMINVENTORY_URL", "http://lab.example.org")
    app.client.cache_clear()

    try:
        with pytest.raises(SystemExit, match="must use https"):
            server.main()
    finally:
        app.client.cache_clear()


def test_main_rejects_unknown_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHEMINVENTORY_ACCESS", "readonly")

    with pytest.raises(
        SystemExit,
        match="CHEMINVENTORY_ACCESS must be one of read-only, additive, full: 'readonly'",
    ):
        server.main()


@pytest.mark.parametrize(
    ("access", "available"),
    [
        ("read-only", READ_ONLY | {"save_files"}),
        ("additive", READ_ONLY | ADDITIVE),
        ("full", ALL_TOOLS),
    ],
)
@pytest.mark.anyio
async def test_stdio_entry_point(access: str, available: set[str]) -> None:
    command: str | None = shutil.which("cheminventory-mcp")
    assert command is not None

    parameters: StdioServerParameters = StdioServerParameters(
        command=command,
        env={
            "CHEMINVENTORY_TOKEN": "token",
            "CHEMINVENTORY_ACCESS": access,
            "PATH": "",
        },
    )

    async with Client(parameters) as session:
        tools: list[Tool] = (await session.list_tools()).tools
        version: str | None = (
            session.server_info.version if session.server_info else None
        )

    assert {tool.name for tool in tools} == available
    assert version == "1.0.0"


@pytest.mark.anyio
async def test_access_default_is_full() -> None:
    command: str | None = shutil.which("cheminventory-mcp")
    assert command is not None

    parameters: StdioServerParameters = StdioServerParameters(
        command=command, env={"CHEMINVENTORY_TOKEN": "token", "PATH": ""}
    )

    async with Client(parameters) as session:
        tools: list[Tool] = (await session.list_tools()).tools

    assert {tool.name for tool in tools} == ALL_TOOLS
