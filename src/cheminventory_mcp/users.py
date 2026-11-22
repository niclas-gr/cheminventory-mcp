from typing import Annotated, Any

from pydantic import Field

from cheminventory_mcp.app import (
    ADDITIVE,
    DESTRUCTIVE,
    READ,
    AccountType,
    body,
    client,
    mcp,
)


@mcp.tool(annotations=READ)
async def list_users(inventory_id: int) -> list[dict[str, Any]]:
    """User accounts of an inventory (administrators only)."""
    return await client().call("inventorymanagement/users/list", inventory=inventory_id)


@mcp.tool(annotations=ADDITIVE)
async def add_user(
    inventory_id: int,
    email: str,
    first_name: str,
    last_name: str,
    account_type: AccountType,
    barcode: str | None = None,
    sso: Annotated[
        bool | None, Field(description="Sign in with SSO, if the license enables it")
    ] = None,
) -> int:
    """Create a user account in an inventory. Returns the user ID."""
    return await client().call(
        "inventorymanagement/users/add",
        **body(
            inventory=inventory_id,
            email=email,
            firstname=first_name,
            lastname=last_name,
            accounttype=account_type,
            barcode=barcode,
            sso=sso,
        ),
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def update_user(
    user_id: int,
    email: str,
    first_name: str,
    last_name: str,
    account_type: AccountType,
    inventory_id: Annotated[
        int | None,
        Field(description="Inventory the account type applies to, if several"),
    ] = None,
) -> None:
    """Update a user account. All of email, names and account type are set."""
    await client().call(
        "inventorymanagement/users/update",
        **body(
            id=user_id,
            email=email,
            firstname=first_name,
            lastname=last_name,
            accounttype=account_type,
            inventory=inventory_id,
        ),
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def disable_user(user_id: int, inventory_id: int) -> None:
    """Remove a user's access to an inventory."""
    await client().call(
        "inventorymanagement/users/disable", id=user_id, inventory=inventory_id
    )


@mcp.tool(annotations=DESTRUCTIVE)
async def reset_user_password(
    user_id: int, password: Annotated[str, Field(min_length=8)]
) -> None:
    """Set a new password for a user (not for SSO accounts)."""
    await client().call(
        "inventorymanagement/users/resetpassword", id=user_id, password=password
    )
