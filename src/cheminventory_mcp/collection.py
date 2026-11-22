from typing import Annotated, Any

from pydantic import Field

from cheminventory_mcp.app import ADDITIVE, DESTRUCTIVE, READ, Ids, client, mcp


@mcp.tool(annotations=READ)
async def load_collection() -> list[dict[str, Any]]:
    """Containers in the user's 'My Collection'; sid is the substance ID."""
    return await client().call("mycollection/load")


@mcp.tool(annotations=ADDITIVE)
async def add_to_collection(container_ids: Ids) -> None:
    """Add containers to 'My Collection'."""
    await client().call("mycollection/add", containerid=container_ids)


@mcp.tool(annotations=ADDITIVE)
async def add_to_collection_by_barcode(
    barcodes: Annotated[list[str], Field(min_length=1)],
) -> list[str]:
    """Add containers to 'My Collection' by barcode (case-insensitive). Returns the
    barcodes that matched no container."""
    return (await client().call("mycollection/addbybarcode", barcode=barcodes))[
        "errorBarcodes"
    ]


@mcp.tool(annotations=DESTRUCTIVE)
async def remove_from_collection(container_id: int) -> None:
    """Remove a container from 'My Collection'."""
    await client().call("mycollection/remove", containerid=container_id)


@mcp.tool(annotations=DESTRUCTIVE)
async def clear_collection() -> None:
    """Remove all containers from 'My Collection'; the containers are kept."""
    await client().call("mycollection/removeall")


@mcp.tool(annotations=DESTRUCTIVE)
async def move_collection(destination_id: int) -> None:
    """Move all containers in 'My Collection' to a location."""
    await client().call("mycollection/moveall", destinationid=destination_id)


@mcp.tool(annotations=DESTRUCTIVE)
async def delete_collection_containers() -> None:
    """Delete every container in 'My Collection' from the inventory."""
    await client().call("mycollection/deleteall")
