from typing import Annotated, Any, Literal

from pydantic import Field

from cheminventory_mcp.app import DESTRUCTIVE, READ, FieldKind, body, client, mcp


@mcp.tool(annotations=READ)
async def list_custom_fields() -> dict[str, Any]:
    """Container and substance custom fields with IDs, data types and allowed
    values."""
    return await client().call("customfields/get")


@mcp.tool(annotations=DESTRUCTIVE)
async def save_custom_field(
    field_kind: FieldKind,
    name: str,
    data_type: Literal[
        "text", "multilinetext", "number", "date", "url", "dropdown", "tags"
    ],
    field_id: Annotated[
        int, Field(description="Custom field to update; 0 creates a new field")
    ] = 0,
    searchable: bool | None = None,
    admin_edit_only: Annotated[
        bool | None,
        Field(description="Only administrators may edit (initial value still free)"),
    ] = None,
    allowed_values: Annotated[
        list[str] | None, Field(description="Options for dropdown and tags fields")
    ] = None,
    show_for_orders: Annotated[
        bool | None, Field(description="Container fields: available on order requests")
    ] = None,
) -> int:
    """Create or update a container or substance custom field. Returns the field
    ID."""
    return await client().call(
        "customfields/save",
        **body(
            id=field_id,
            fieldtype=field_kind,
            name=name,
            type=data_type,
            searchable=searchable,
            admineditonly=admin_edit_only,
            allowedvalues=allowed_values,
            showfororders=show_for_orders,
        ),
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def delete_custom_field(field_id: int, field_kind: FieldKind) -> None:
    """Delete a custom field and its values."""
    await client().call("customfields/delete", id=field_id, fieldtype=field_kind)
