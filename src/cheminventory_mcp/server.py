import asyncio
import os
import sys
from typing import Literal, TypeAlias, get_args

from mcp.types import Tool

from cheminventory_mcp import (  # noqa: F401  (modules register their tools)
    barcodes,
    collection,
    containers,
    fields,
    files,
    inventory,
    orders,
    substances,
    users,
    watchlists,
)
from cheminventory_mcp.app import client, mcp

Access: TypeAlias = Literal["read-only", "additive", "full"]
ACCESS_LEVELS: dict[str, Access] = {level: level for level in get_args(Access)}

# Allowed at every access level: writes local files, but changes nothing in
# ChemInventory
LOCAL_WRITES: frozenset[str] = frozenset({"save_files"})


def permitted(tool: Tool, access: Access) -> bool:
    """Whether a tool is available at an access level, from its annotations."""
    if access == "full" or tool.name in LOCAL_WRITES:
        return True

    read_only: bool = bool(tool.annotations and tool.annotations.read_only_hint)
    destructive: bool = bool(tool.annotations and tool.annotations.destructive_hint)

    return read_only or (access == "additive" and not destructive)


def restrict_tools(access: Access) -> None:
    """Remove the tools that the access level does not permit."""
    for tool in asyncio.run(mcp.list_tools()):
        if not permitted(tool, access):
            mcp.remove_tool(tool.name)


def main() -> None:
    if not os.environ.get("CHEMINVENTORY_TOKEN"):
        sys.exit("CHEMINVENTORY_TOKEN is not set; create a token under Inventory Tools")

    setting: str = os.environ.get("CHEMINVENTORY_ACCESS", "full")
    access: Access | None = ACCESS_LEVELS.get(setting)
    if access is None:
        sys.exit(
            f"CHEMINVENTORY_ACCESS must be one of {', '.join(ACCESS_LEVELS)}: "
            f"{setting!r}"
        )

    try:
        client()
    except ValueError as error:
        sys.exit(str(error))

    restrict_tools(access)
    mcp.run()
