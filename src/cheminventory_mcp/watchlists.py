from typing import Annotated, Any

from pydantic import Field

from cheminventory_mcp.app import DESTRUCTIVE, READ, Scope, client, mcp


@mcp.tool(annotations=READ)
async def list_watchlists() -> dict[str, Any]:
    """Global and custom (inventory, site, enterprise) watchlists with their search
    terms."""
    return await client().call_object("watchlist/load")


@mcp.tool(annotations=READ)
async def check_watchlists(substance_id: int) -> list[dict[str, Any]]:
    """Watchlists that contain a substance."""
    return await client().call("watchlist/checksubstance", substanceid=substance_id)


@mcp.tool(annotations=READ)
async def watchlist_report(
    watchlist_id: int, scope: Scope = "inventory"
) -> list[dict[str, Any]]:
    """Containers that match a watchlist."""
    return await client().table(
        "watchlist/generatereport", id=watchlist_id, scope=scope
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def save_watchlist(
    name: str,
    terms: Annotated[list[str], Field(description="Search terms, e.g. CAS numbers")],
    watchlist_id: Annotated[
        int, Field(description="Watchlist to update; 0 creates a new watchlist")
    ] = 0,
    scope: Scope = "inventory",
) -> None:
    """Create or update a custom watchlist."""
    await client().call(
        "watchlist/save", id=watchlist_id, scope=scope, name=name, terms=terms
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def delete_watchlist(watchlist_id: int) -> None:
    """Delete a custom watchlist."""
    await client().call("watchlist/delete", id=watchlist_id)
