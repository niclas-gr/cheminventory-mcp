from datetime import date
from typing import Annotated, Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from cheminventory_mcp.app import (
    ADDITIVE,
    DESTRUCTIVE,
    READ,
    CustomFields,
    Ids,
    body,
    client,
    mcp,
)
from cheminventory_mcp.client import ChemInventoryError

CONTAINER_FIELD: str = (
    r"^(containername|cas|containersize|barcode|supplier|dateacquired|comments"
    r"|[cs]f-\d+)$"
)


class NewContainer(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    name: str
    supplier: str | None = None
    barcode: str | None = None
    size: str | None = Field(None, description="Container size, e.g. '250'")
    unit_id: int | None = Field(None, description="Unit ID for size (list_units)")
    comments: str | None = None
    date_acquired: date | None = None
    custom_fields: CustomFields = None


@mcp.tool(annotations=READ)
async def load_container(container_id: int) -> dict[str, Any]:
    """All information for one container, including substance, GHS hazard
    statements, custom fields and files."""
    return await client().call_object(
        "container/information/load", containerid=container_id
    )


@mcp.tool(annotations=READ)
async def container_history(container_id: int) -> list[list[Any]]:
    """Audit log of one container as [timestamp (UTC), user, event, description]."""
    return await client().call(
        "container/information/gethistory", containerid=container_id
    )


@mcp.tool(annotations=READ)
async def recently_added_containers() -> list[dict[str, Any]]:
    """Containers added in the last 30 days (group administrators only)."""
    return await client().table("container/recentlyadded")


@mcp.tool(annotations=ADDITIVE)
async def add_containers(
    location_id: int,
    substance_id: int,
    containers: Annotated[list[NewContainer], Field(min_length=1)],
) -> list[int]:
    """Add containers of one substance to one location. Returns the new container
    IDs."""
    data: list[dict[str, Any]] = [
        body(
            container.custom_fields,
            name=container.name,
            locationid=location_id,
            substanceid=substance_id,
            supplier=container.supplier,
            barcode=container.barcode,
            containersize=container.size,
            units=container.unit_id,
            comments=container.comments,
            dateacquired=container.date_acquired,
        )
        for container in containers
    ]

    return await client().call("container/add", data=data)


@mcp.tool(annotations=DESTRUCTIVE)
async def update_container(
    container_id: int,
    field: Annotated[
        str,
        Field(
            pattern=CONTAINER_FIELD,
            description=(
                "containername, cas, containersize, barcode, supplier, dateacquired, "
                "comments, cf-<id> (container custom field) or sf-<id> (substance "
                "custom field)"
            ),
        ),
    ],
    value: Annotated[
        str,
        Field(
            description=(
                "New value; for containersize the size, e.g. '250'. Custom fields: "
                "dates as YYYY-MM-DD, tags as '|value 1|value 2|'"
            )
        ),
    ],
    unit: Annotated[
        str | None, Field(description="Unit name for containersize, e.g. 'g'")
    ] = None,
) -> None:
    """Change one field of a container."""
    new_value: str | dict[str, str] = value

    if field == "containersize":
        if unit is None:
            raise ChemInventoryError("containersize needs a unit")
        new_value = {"size": value, "unit": unit}

    await client().call(
        "container/information/save",
        containerid=container_id,
        field=field,
        newvalue=new_value,
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def toggle_container_recycling(container_id: int) -> None:
    """Toggle whether a container is offered for recycling (site and enterprise
    licenses with recycling enabled)."""
    await client().call(
        "container/information/togglerecycling", containerid=container_id
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def move_containers(container_ids: Ids, destination_id: int) -> list[int]:
    """Move containers to a location. Returns the IDs that were moved."""
    return await client().call(
        "container/move", containerid=container_ids, destinationid=destination_id
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def delete_containers(container_ids: Ids) -> None:
    """Delete containers. restore_deleted_container undoes this."""
    await client().call("container/delete", containerid=container_ids)


@mcp.tool(annotations=READ)
async def list_deleted_containers() -> list[dict[str, Any]]:
    """Deleted containers with ID, deletion date (UTC), name, barcode and user."""
    return await client().call("inventorymanagement/deletedcontainers/get")


@mcp.tool(annotations=READ)
async def export_deleted_containers() -> list[dict[str, Any]]:
    """Full records of all deleted containers, including custom fields."""
    return await client().table("inventorymanagement/deletedcontainers/export")


@mcp.tool(annotations=ADDITIVE)
async def restore_deleted_container(container_id: int) -> None:
    """Restore a deleted container, including its parent locations."""
    await client().call(
        "inventorymanagement/deletedcontainers/restore", id=container_id
    )
