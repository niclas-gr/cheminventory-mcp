from typing import Annotated, Any, TypeAlias

from pydantic import Field

from cheminventory_mcp.app import (
    ADDITIVE,
    DESTRUCTIVE,
    READ,
    CustomFields,
    body,
    client,
    mcp,
)

Size: TypeAlias = Annotated[str, Field(description="Container size, e.g. '500'")]
UnitId: TypeAlias = Annotated[int, Field(description="Unit ID for size (list_units)")]
Destination: TypeAlias = Annotated[
    int, Field(description="Location for the eventual container; 0 for none")
]


@mcp.tool(annotations=READ)
async def list_orders() -> list[dict[str, Any]]:
    """Active order requests."""
    return await client().call("order/load")


@mcp.tool(annotations=ADDITIVE)
async def request_order(
    substance_id: int,
    name: Annotated[str, Field(description="Container name")],
    supplier: str,
    size: Size,
    unit_id: UnitId,
    quantity: Annotated[int, Field(ge=1, description="Identical requests")] = 1,
    comments: str | None = None,
    destination_location_id: Destination = 0,
    status_change_email: bool = False,
    custom_fields: CustomFields = None,
) -> None:
    """Create order requests."""
    await client().call(
        "order/request",
        **body(
            custom_fields,
            substanceid=substance_id,
            name=name,
            supplier=supplier,
            containersize=size,
            units=unit_id,
            quantity=quantity,
            comments=comments,
            destinationlocation=destination_location_id,
            statuschangeemail=status_change_email,
        ),
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def edit_order(
    order_id: int,
    supplier: str,
    size: Size,
    unit_id: UnitId,
    comments: str | None = None,
    destination_location_id: Destination = 0,
    custom_fields: CustomFields = None,
) -> dict[str, Any]:
    """Update an order request. Returns the saved values."""
    return await client().call(
        "order/edit",
        **body(
            custom_fields,
            orderid=order_id,
            containersize=size,
            units=unit_id,
            supplier=supplier,
            comments=comments,
            destinationlocation=destination_location_id,
        ),
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def toggle_order_placed(order_id: int) -> str:
    """Mark an order request as placed, or unmark it. Returns the new order date
    (UTC), or '0' if unmarked."""
    return str(await client().call("order/toggleordered", orderid=order_id))


@mcp.tool(annotations=DESTRUCTIVE)
async def receive_order(
    order_id: int,
    name: Annotated[str, Field(description="Name of the new container")],
    location_id: int,
    comments: str | None = None,
    custom_fields: CustomFields = None,
) -> None:
    """Mark an order as arrived and create its container; size, supplier and
    substance come from the order."""
    await client().call(
        "order/addcontainer",
        **body(
            custom_fields,
            orderid=order_id,
            name=name,
            locationid=location_id,
            comments=comments,
        ),
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def delete_order(order_id: int) -> None:
    """Delete an order request."""
    await client().call("order/delete", orderid=order_id)
