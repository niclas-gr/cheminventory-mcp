import asyncio
import os
from collections.abc import Awaitable, Callable
from datetime import date
from functools import cache
from importlib.metadata import version
from typing import Annotated, Any, Literal, TypeAlias

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from cheminventory_mcp.client import ChemInventoryClient

READ: ToolAnnotations = ToolAnnotations(read_only_hint=True, open_world_hint=False)
ADDITIVE: ToolAnnotations = ToolAnnotations(
    destructive_hint=False, open_world_hint=False
)
DESTRUCTIVE: ToolAnnotations = ToolAnnotations(
    destructive_hint=True, open_world_hint=False
)

Scope: TypeAlias = Literal["inventory", "site", "enterprise"]
FieldKind: TypeAlias = Literal["container", "substance"]
AccountType: TypeAlias = Annotated[
    Literal[2, 3, 4, 6],
    Field(description="2 group administrator, 3 order handler, 4 user, 6 read-only"),
]
CustomFields: TypeAlias = Annotated[
    dict[int, str] | None,
    Field(description="Container custom field values by custom field ID"),
]
Ids: TypeAlias = Annotated[list[int], Field(min_length=1)]

PARALLEL_REQUESTS: int = 3

mcp: MCPServer[Any] = MCPServer(
    "ChemInventory",
    version=version("cheminventory-mcp"),
    instructions=(
        "Tools for a ChemInventory chemical inventory. Call get_details first: it "
        "returns the inventory ID, location IDs, unit IDs, custom field IDs and the "
        "user's date format, which the other tools need. Container lists from search, "
        "location and collection tools are summaries; use load_container or "
        "export_containers for all fields. Name search is often exact-match; use "
        "advanced search with 'contains' for partial names. If a substance has "
        "needsretrieval = 1 and a CAS number, call retrieve_substance_info for it "
        "if available. Scope parameters should stay 'inventory' unless the user is a "
        "site or enterprise administrator."
    ),
)


@cache
def client() -> ChemInventoryClient:
    return ChemInventoryClient(
        token=os.environ["CHEMINVENTORY_TOKEN"],
        base_url=os.environ.get("CHEMINVENTORY_URL", "https://app.cheminventory.net"),
    )


def body(custom_fields: dict[int, str] | None = None, **params: Any) -> dict[str, Any]:
    """Request parameters without unset values, with dates as YYYY-MM-DD and custom
    fields as cf-<id>."""
    fields: dict[str, str] = {
        f"cf-{field_id}": value for field_id, value in (custom_fields or {}).items()
    }

    values: dict[str, Any] = {
        key: value.isoformat() if isinstance(value, date) else value
        for key, value in params.items()
        if value is not None
    }

    return values | fields


async def gather_limited[T, R](
    items: list[T], run: Callable[[T], Awaitable[R]]
) -> list[R]:
    """Results of run for every item in order, with PARALLEL_REQUESTS at a time."""
    slots: asyncio.Semaphore = asyncio.Semaphore(PARALLEL_REQUESTS)

    async def limited(item: T) -> R:
        async with slots:
            return await run(item)

    return list(await asyncio.gather(*(limited(item) for item in items)))
