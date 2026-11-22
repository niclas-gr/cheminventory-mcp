from typing import Annotated, Any

from pydantic import Field

from cheminventory_mcp.app import DESTRUCTIVE, READ, client, mcp


@mcp.tool(annotations=READ)
async def assigned_barcodes() -> list[dict[str, Any]]:
    """All assigned barcodes (group administrators only)."""
    return await client().table("barcodes/assigned")


@mcp.tool(annotations=READ)
async def check_barcode(barcode: str) -> dict[str, Any]:
    """Containers, locations and users that already carry a barcode, keyed by
    barcode value."""
    return await client().call("barcodes/duplicates/check", barcode=barcode)


@mcp.tool(annotations=READ)
async def duplicate_barcodes() -> dict[str, Any]:
    """All barcodes assigned more than once, keyed by barcode value
    (administrators only)."""
    return await client().call("barcodes/duplicates/getall")


@mcp.tool(annotations=DESTRUCTIVE)
async def generate_barcodes(
    prefix: Annotated[str, Field(max_length=6)],
    count: Annotated[int, Field(ge=1)],
    starting_number: int,
) -> list[str]:
    """Unused barcode values. Saves prefix as the inventory's barcode prefix if
    permitted."""
    return await client().call(
        "barcodes/generator/createvalues",
        prefix=prefix,
        count=count,
        startingnumber=starting_number,
        duplicatecheck=True,
    )
