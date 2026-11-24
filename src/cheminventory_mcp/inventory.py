import re
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import Field

from cheminventory_mcp.app import DESTRUCTIVE, READ, Ids, client, gather_limited, mcp
from cheminventory_mcp.client import ChemInventoryError

SEARCH_TYPE: str = (
    r"^(name|cas|barcode|ghs|advanced|exactstructure|substructure|substanceid"
    r"|containerid|[cs]f-(text|multilinetext|number|date|url|dropdown|tags)-\d+)$"
)
CAS_NUMBER: re.Pattern[str] = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")


def check_cas(term: str | dict[str, Any]) -> None:
    """Reject a CAS number with the wrong format or check digit."""
    match: re.Match[str] | None = (
        CAS_NUMBER.match(term.strip()) if isinstance(term, str) else None
    )
    if match is None:
        raise ChemInventoryError(f"{term!r} is not a CAS number (e.g. 7087-68-5)")

    digits: str = match[1] + match[2]
    checksum: int = sum(
        position * int(digit)
        for position, digit in enumerate(reversed(digits), start=1)
    )

    if checksum % 10 != int(match[3]):
        raise ChemInventoryError(f"{term} has a wrong check digit; check the number")


def select_columns(
    rows: list[dict[str, Any]], columns: list[str]
) -> list[dict[str, Any]]:
    """Keep only the named columns, matched case-insensitively."""
    if not rows:
        return rows

    available: dict[str, str] = {
        header.casefold(): header for row in rows for header in row
    }

    unknown: list[str] = [
        column for column in columns if column.casefold() not in available
    ]
    if unknown:
        raise ChemInventoryError(
            f"Unknown columns {unknown}; available: {sorted(available.values())}"
        )

    keep: list[str] = [available[column.casefold()] for column in columns]

    return [{header: row.get(header) for header in keep} for row in rows]


@mcp.tool(annotations=READ)
async def get_details() -> dict[str, Any]:
    """Account and inventory details: user and inventory IDs, date format, units,
    suppliers, custom fields and the location hierarchy."""
    return await client().call_object("general/getdetails")


@mcp.tool(annotations=READ)
async def list_units() -> list[dict[str, Any]]:
    """Container size units with their IDs."""
    return await client().call("general/units")


@mcp.tool(annotations=READ)
async def export_containers(
    container_ids: Annotated[
        Ids | None,
        Field(description="Containers to export; omit to export the whole inventory"),
    ] = None,
    columns: Annotated[
        list[str] | None,
        Field(
            min_length=1,
            description=(
                "Column headers to keep, case-insensitive, e.g. a container's name, "
                "CAS, size, unit and location; omit for all columns. An unknown "
                "header returns the available ones"
            ),
        ),
    ] = None,
) -> list[dict[str, Any]]:
    """Full records of containers, including custom fields. A whole-inventory export
    is large (about 1 KB per container); select columns for overviews."""
    rows: list[dict[str, Any]] = (
        await client().table("inventorymanagement/export")
        if container_ids is None
        else await client().table("general/exportbyid", containerids=container_ids)
    )

    return rows if columns is None else select_columns(rows, columns)


@mcp.tool(annotations=READ)
async def audit_history(start_date: date, end_date: date) -> list[list[Any]]:
    """Inventory activity logs in a date range as [timestamp (UTC), user, subject,
    event, description, details]."""
    return await client().call(
        "inventorymanagement/audithistory/load",
        startdate=start_date.isoformat(),
        enddate=end_date.isoformat(),
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def switch_inventory(inventory_id: int) -> None:
    """Switch the token user's active inventory everywhere, including the web
    interface (site and enterprise licenses only). Rarely needed."""
    await client().call("navbar/switchinventory", newinventory=inventory_id)


@mcp.tool(annotations=READ)
async def list_locations() -> list[dict[str, Any]]:
    """All locations with ID, name, barcode, parent ID (0 at root) and container
    count."""
    return await client().call("location/load")


@mcp.tool(annotations=READ)
async def location_containers(location_id: int) -> dict[str, Any]:
    """Container summaries in a location."""
    return await client().call_object("location/containers/get", locationid=location_id)


@mcp.tool(annotations=DESTRUCTIVE)
async def move_location_containers(origin_id: int, destination_id: int) -> None:
    """Move all containers from one location to another."""
    await client().call(
        "location/containers/move", origin=origin_id, destination=destination_id
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def delete_location_containers(location_id: int) -> None:
    """Delete all containers in a location."""
    await client().call("location/containers/delete", locationid=location_id)


@mcp.tool(annotations=READ)
async def search(
    inventory: Annotated[
        int | Literal["site", "enterprise", "recycling"],
        Field(description="Inventory ID, or a site, enterprise or recycling scope"),
    ],
    search_type: Annotated[
        str,
        Field(
            pattern=SEARCH_TYPE,
            description=(
                "One of name (includes synonyms), cas, barcode, ghs, advanced, "
                "exactstructure, substructure, substanceid, containerid, or a custom "
                "field as cf-<datatype>-<id> / sf-<datatype>-<id>, e.g. cf-date-363"
            ),
        ),
    ],
    terms: Annotated[
        list[str | dict[str, Any]],
        Field(
            min_length=1,
            description=(
                "Search terms, each searched separately. name: matching follows the "
                "account's name search preference (user.preferences.ns in "
                "get_details) and is often exact; for partial names use advanced "
                "with operator 'contains' on the name field. cas: checked for a "
                "valid check digit before searching. Structure searches: molfile or "
                "SMILES (stereocenters may be ignored); substances without a stored "
                "structure are not found. ghs: {searchtype: 'or'|'and', items: "
                "['H225', ...]}. advanced: QueryBuilder rules {condition, rules: "
                "[{id, field, type, input, operator, value}]} with fields from "
                "advanced_search_options and operators such as 'contains' or "
                "'between'; dates in the user's date format from get_details"
            ),
        ),
    ],
) -> list[dict[str, Any]]:
    """Search containers for one or more terms, e.g. a whole list of names, CAS
    numbers or SMILES at once. Returns, per term, the container summaries and
    matching orders, or an error. Results are filtered by the user's 'limit search
    to' setting."""

    async def run(term: str | dict[str, Any]) -> dict[str, Any]:
        try:
            if search_type == "cas":
                check_cas(term)

            found: dict[str, Any] = await client().call_object(
                "search/execute", inventory=inventory, type=search_type, contents=term
            )
        except ChemInventoryError as error:
            return {"term": term, "error": str(error)}

        return {"term": term, **found}

    return await gather_limited(terms, run)


@mcp.tool(annotations=READ)
async def advanced_search_options() -> list[dict[str, Any]]:
    """Fields and types available for advanced search rules."""
    return await client().call("search/loadadvancedsearch")
