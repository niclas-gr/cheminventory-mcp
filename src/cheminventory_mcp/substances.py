from typing import Annotated, Any

from pydantic import Field

from cheminventory_mcp.app import ADDITIVE, DESTRUCTIVE, body, client, mcp
from cheminventory_mcp.client import ChemInventoryError


@mcp.tool(annotations=ADDITIVE)
async def get_substance(
    name: Annotated[
        str, Field(description="Substance name; not needed with substance_id")
    ] = "",
    cas: Annotated[
        str,
        Field(description="CAS number, or 'N/A' if none; not needed with substance_id"),
    ] = "",
    substance_id: Annotated[
        int | None, Field(description="ID of a known substance")
    ] = None,
) -> list[dict[str, Any]]:
    """Substance records matching name and CAS number, or the substance with
    substance_id. Creates the substance if it does not exist yet."""
    if substance_id is None and not (name and cas):
        raise ChemInventoryError("name and cas are required without substance_id")

    return await client().call(
        "container/getsubstance", **body(name=name, cas=cas, substanceid=substance_id)
    )


@mcp.tool(annotations=ADDITIVE)
async def retrieve_substance_info(substance_id: int) -> str:
    """Fetch structure and synonyms for a substance with a CAS number. Returns the
    isomeric SMILES."""
    return await client().call("general/retrievesubstanceinfo", substance=substance_id)


@mcp.tool(annotations=DESTRUCTIVE)
async def update_substance_structure(
    substance_id: int,
    structure: Annotated[str, Field(description="Molfile or SMILES")],
) -> int:
    """Set the structure of a substance. Returns the substance ID, which is an
    existing substance's ID if the structure matches one."""
    return await client().call(
        "general/updatestructure", substanceid=substance_id, newmolfile=structure
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def save_ghs_entry(
    substance_id: int,
    hazard_codes: Annotated[list[str], Field(description="e.g. ['H225', 'H410']")],
    source: Annotated[str, Field(description="Shown to users, e.g. 'Sigma Aldrich'")],
    entry_id: Annotated[
        int, Field(description="GHS entry to update; 0 creates a new entry")
    ] = 0,
) -> int:
    """Create or update a GHS hazard entry of a substance. Returns the entry ID."""
    return (
        await client().call(
            "container/ghs/save",
            entryid=entry_id,
            hcodes=hazard_codes,
            source=source,
            substance=substance_id,
        )
    )["id"]


@mcp.tool(annotations=DESTRUCTIVE)
async def delete_ghs_entry(entry_id: int) -> None:
    """Delete a GHS hazard entry."""
    await client().call("container/ghs/delete", entryid=entry_id)
