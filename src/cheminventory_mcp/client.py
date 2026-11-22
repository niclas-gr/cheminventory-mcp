from dataclasses import dataclass
from email.message import Message
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote

import httpx
from mcp.server.mcpserver.exceptions import ToolError


class ChemInventoryError(ToolError):
    pass


@dataclass(frozen=True)
class Download:
    name: str
    content_type: str
    data: bytes


async def require_https(request: httpx.Request) -> None:
    if request.url.scheme != "https":
        raise ChemInventoryError(
            f"Refusing to download over {request.url.scheme}: {request.url.host}"
        )


def file_name(response: httpx.Response, fallback: str) -> str:
    """File name from Content-Disposition or the URL path, without directories."""
    header: Message = Message()
    header["content-disposition"] = response.headers.get("content-disposition", "")
    raw: str = header.get_filename() or unquote(response.url.path.rsplit("/", 1)[-1])

    name: str = PurePosixPath(raw.replace("\\", "/")).name

    return name if name not in ("", ".", "..") else fallback


class ChemInventoryClient:
    def __init__(self, token: str, base_url: str) -> None:
        if not base_url.startswith("https://"):
            raise ValueError(f"ChemInventory URL must use https: {base_url!r}")

        self._token: str = token
        self._http_client: httpx.AsyncClient = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/api/", timeout=60.0
        )
        # Separate client for file storage that doesn't see the API token
        self._files_client: httpx.AsyncClient = httpx.AsyncClient(
            follow_redirects=True,
            timeout=120.0,
            event_hooks={"request": [require_https]},
        )

    async def call(self, endpoint: str, **params: Any) -> Any:
        try:
            response: httpx.Response = await self._http_client.post(
                endpoint, json={"authtoken": self._token, **params}
            )
        except httpx.HTTPError as error:
            raise ChemInventoryError(
                f"/{endpoint}: {type(error).__name__}: {error}"
            ) from error

        if response.is_error:
            raise ChemInventoryError(f"/{endpoint}: HTTP {response.status_code}")

        try:
            payload: Any = response.json()
        except ValueError as error:
            raise ChemInventoryError(f"/{endpoint}: response is not JSON") from error

        if not isinstance(payload, dict) or "status" not in payload:
            raise ChemInventoryError(f"/{endpoint}: unexpected response")
        if payload["status"] != "success":
            raise ChemInventoryError(f"/{endpoint}: {payload.get('data')}")

        return payload.get("data")

    async def table(self, endpoint: str, **params: Any) -> list[dict[str, Any]]:
        """Rows of a columns/rows table response, keyed by column header."""
        data: dict[str, Any] = await self.call(endpoint, **params)

        headers: dict[str, str] = {
            column["key"]: column["header"] for column in data["columns"]
        }

        return [
            {headers.get(key, key): value for key, value in row.items()}
            for row in data["rows"]
        ]

    async def download(self, file_id: int) -> Download:
        """Download a file from the file store."""
        url: str = await self.call("filestore/download", fileid=file_id)

        try:
            response: httpx.Response = await self._files_client.get(url)
        except httpx.HTTPError as error:
            raise ChemInventoryError(
                f"file {file_id}: {type(error).__name__}: {error}"
            ) from error

        if response.is_error:
            raise ChemInventoryError(f"file {file_id}: HTTP {response.status_code}")

        content_type: str = response.headers.get("content-type", "").split(";")[0]

        return Download(
            name=file_name(response, fallback=str(file_id)),
            content_type=content_type.strip().lower(),
            data=response.content,
        )
