import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
import respx
from mcp import Client
from mcp.types import CallToolResult, ToolAnnotations

from tests.conftest import TOKEN

ENDPOINTS: set[str] = {
    "barcodes/assigned",
    "barcodes/duplicates/check",
    "barcodes/duplicates/getall",
    "barcodes/generator/createvalues",
    "container/add",
    "container/delete",
    "container/getsubstance",
    "container/ghs/delete",
    "container/ghs/save",
    "container/information/gethistory",
    "container/information/load",
    "container/information/save",
    "container/information/togglerecycling",
    "container/move",
    "container/recentlyadded",
    "customfields/delete",
    "customfields/get",
    "customfields/save",
    "filestore/addsubstancelink",
    "filestore/createcategory",
    "filestore/deletecategory",
    "filestore/deletefile",
    "filestore/download",
    "filestore/getlinkedfiles",
    "filestore/getsubstancelinks",
    "filestore/load",
    "filestore/removesubstancelink",
    "filestore/renamecategory",
    "filestore/renamefile",
    "filestore/updatefilecategory",
    "general/exportbyid",
    "general/getdetails",
    "general/retrievesubstanceinfo",
    "general/units",
    "general/updatestructure",
    "inventorymanagement/audithistory/load",
    "inventorymanagement/deletedcontainers/export",
    "inventorymanagement/deletedcontainers/get",
    "inventorymanagement/deletedcontainers/restore",
    "inventorymanagement/export",
    "inventorymanagement/users/add",
    "inventorymanagement/users/disable",
    "inventorymanagement/users/list",
    "inventorymanagement/users/resetpassword",
    "inventorymanagement/users/update",
    "location/containers/delete",
    "location/containers/get",
    "location/containers/move",
    "location/load",
    "mycollection/add",
    "mycollection/addbybarcode",
    "mycollection/deleteall",
    "mycollection/load",
    "mycollection/moveall",
    "mycollection/remove",
    "mycollection/removeall",
    "navbar/switchinventory",
    "order/addcontainer",
    "order/delete",
    "order/edit",
    "order/load",
    "order/request",
    "order/toggleordered",
    "search/execute",
    "search/loadadvancedsearch",
    "watchlist/checksubstance",
    "watchlist/delete",
    "watchlist/generatereport",
    "watchlist/load",
    "watchlist/save",
}

READ_ONLY: set[str] = {
    "advanced_search_options",
    "assigned_barcodes",
    "audit_history",
    "check_barcode",
    "check_watchlists",
    "container_history",
    "duplicate_barcodes",
    "export_containers",
    "export_deleted_containers",
    "file_content",
    "file_download_url",
    "file_substances",
    "get_details",
    "list_custom_fields",
    "list_deleted_containers",
    "list_locations",
    "list_orders",
    "list_units",
    "list_users",
    "list_watchlists",
    "load_collection",
    "load_container",
    "load_file_store",
    "location_containers",
    "recently_added_containers",
    "search",
    "substance_files",
    "watchlist_report",
}

ADDITIVE: set[str] = {
    "add_containers",
    "add_to_collection",
    "add_to_collection_by_barcode",
    "add_user",
    "create_file_category",
    "get_substance",
    "link_file_to_substance",
    "request_order",
    "restore_deleted_container",
    "retrieve_substance_info",
    "save_files",
}

# Tested in test_files.py, as they also download from the file host
FILE_TOOLS: set[str] = {"file_content", "save_files"}

SAME: object = object()

CONTAINER_SUMMARY: dict[str, Any] = {
    "id": 856461,
    "name": "N,N-diisopropyl ethylamine 99%",
    "location": 40032,
    "size": "50",
    "unitid": 1,
    "unit": "mL",
    "substance": 4454,
    "cas": "7087-68-5",
    "isomericsmiles": "CCN(C(C)C)C(C)C",
    "needsretrieval": 0,
    "barcode": "AEF01028",
    "inventory": 9,
    "locationtext": "Cupboards > Cupboard 1",
}
SEARCH_RESULT: dict[str, Any] = {"orders": [], "containers": [CONTAINER_SUMMARY]}
TABLE: dict[str, Any] = {
    "columns": [
        {"header": "Container Name", "key": "name"},
        {"header": "Barcode", "key": "barcode"},
    ],
    "rows": [
        {"name": "Acetone", "barcode": "ABC123"},
        {"name": "Toluene", "barcode": "ABC124", "extra": 1},
    ],
}
TABLE_ROWS: list[dict[str, Any]] = [
    {"Container Name": "Acetone", "Barcode": "ABC123"},
    {"Container Name": "Toluene", "Barcode": "ABC124", "extra": 1},
]
DUPLICATES: dict[str, list[dict[str, Any]]] = {
    "AEF01028": [
        {"type": "container", "id": 856461, "name": "DIPEA", "description": 9},
        {"type": "location", "id": 40032, "name": "Cupboard 1", "description": 9},
    ]
}
SUBSTANCE: dict[str, Any] = {
    "id": 382144,
    "name": "Triphenylphosphine",
    "cas": "603-35-0",
    "needsretrieval": 0,
    "ghs": [{"id": 1190, "hazardstatements": "H302|H317|H373"}],
}
FILE: dict[str, Any] = {
    "id": 186451,
    "name": "sds.pdf",
    "categoryid": 480,
    "size": 104550,
}
HISTORY: list[list[str]] = [
    ["2020-01-29 19:57:54", "Smith, Andrew", "Creation", "Container added"],
    ["2020-04-02 13:47:55", "Mayfair, John", "Edit", "Product Code changed"],
]


@dataclass
class Case:
    tool: str
    arguments: dict[str, Any]
    endpoint: str
    params: dict[str, Any] = field(default_factory=dict)
    data: Any = field(default_factory=list)
    result: Any = None

    @property
    def id(self) -> str:
        return f"{self.tool}->{self.endpoint}"


CASES: list[Case] = [
    # Barcodes
    Case("assigned_barcodes", {}, "barcodes/assigned", data=TABLE, result=TABLE_ROWS),
    Case(
        "check_barcode",
        {"barcode": "AEF01028"},
        "barcodes/duplicates/check",
        {"barcode": "AEF01028"},
        DUPLICATES,
        SAME,
    ),
    Case("duplicate_barcodes", {}, "barcodes/duplicates/getall", {}, DUPLICATES, SAME),
    Case(
        "generate_barcodes",
        {"prefix": "ABC", "count": 2, "starting_number": 1},
        "barcodes/generator/createvalues",
        {"prefix": "ABC", "count": 2, "startingnumber": 1, "duplicatecheck": True},
        ["ABC001", "ABC002"],
        SAME,
    ),
    # Containers
    Case(
        "add_containers",
        {
            "location_id": 40032,
            "substance_id": 537219,
            "containers": [
                {
                    "name": "Acetone",
                    "supplier": "Sigma Aldrich",
                    "barcode": "ABC123",
                    "size": "250",
                    "unit_id": 1,
                    "comments": "",
                    "date_acquired": "2022-04-25",
                    "custom_fields": {"362": "Sigma: 179124", "363": "2024-04-25"},
                },
                {"name": "Acetone"},
            ],
        },
        "container/add",
        {
            "data": [
                {
                    "name": "Acetone",
                    "locationid": 40032,
                    "substanceid": 537219,
                    "supplier": "Sigma Aldrich",
                    "barcode": "ABC123",
                    "containersize": "250",
                    "units": 1,
                    "comments": "",
                    "dateacquired": "2022-04-25",
                    "cf-362": "Sigma: 179124",
                    "cf-363": "2024-04-25",
                },
                {"name": "Acetone", "locationid": 40032, "substanceid": 537219},
            ]
        },
        [101, 102],
        SAME,
    ),
    Case(
        "delete_containers",
        {"container_ids": [1, 2]},
        "container/delete",
        {"containerid": [1, 2]},
    ),
    Case(
        "load_container",
        {"container_id": 856461},
        "container/information/load",
        {"containerid": 856461},
        CONTAINER_SUMMARY | {"cf-362": "UPG159-05", "files": []},
        SAME,
    ),
    Case(
        "container_history",
        {"container_id": 856461},
        "container/information/gethistory",
        {"containerid": 856461},
        HISTORY,
        SAME,
    ),
    Case(
        "update_container",
        {"container_id": 5, "field": "comments", "value": "Red label"},
        "container/information/save",
        {"containerid": 5, "field": "comments", "newvalue": "Red label"},
    ),
    Case(
        "update_container",
        {"container_id": 5, "field": "containersize", "value": "250", "unit": "g"},
        "container/information/save",
        {
            "containerid": 5,
            "field": "containersize",
            "newvalue": {"size": "250", "unit": "g"},
        },
    ),
    Case(
        "toggle_container_recycling",
        {"container_id": 5},
        "container/information/togglerecycling",
        {"containerid": 5},
    ),
    Case(
        "move_containers",
        {"container_ids": [1, 2, 3], "destination_id": 40032},
        "container/move",
        {"containerid": [1, 2, 3], "destinationid": 40032},
        [1, 2],
        SAME,
    ),
    Case(
        "recently_added_containers",
        {},
        "container/recentlyadded",
        data=TABLE,
        result=TABLE_ROWS,
    ),
    Case(
        "list_deleted_containers",
        {},
        "inventorymanagement/deletedcontainers/get",
        data=[{"id": 855552, "containername": "Gold (I) chloride"}],
        result=SAME,
    ),
    Case(
        "export_deleted_containers",
        {},
        "inventorymanagement/deletedcontainers/export",
        data=TABLE,
        result=TABLE_ROWS,
    ),
    Case(
        "restore_deleted_container",
        {"container_id": 855552},
        "inventorymanagement/deletedcontainers/restore",
        {"id": 855552},
    ),
    # Substances
    Case(
        "get_substance",
        {"name": "Triphenylphosphine", "cas": "603-35-0"},
        "container/getsubstance",
        {"name": "Triphenylphosphine", "cas": "603-35-0"},
        [SUBSTANCE],
        SAME,
    ),
    Case(
        "get_substance",
        {"name": "Triphenylphosphine", "cas": "N/A", "substance_id": 382144},
        "container/getsubstance",
        {"name": "Triphenylphosphine", "cas": "N/A", "substanceid": 382144},
        [SUBSTANCE],
        SAME,
    ),
    Case(
        "retrieve_substance_info",
        {"substance_id": 4454},
        "general/retrievesubstanceinfo",
        {"substance": 4454},
        "C1C=CC=CC=1",
        SAME,
    ),
    Case(
        "update_substance_structure",
        {"substance_id": 4454, "structure": "CCO"},
        "general/updatestructure",
        {"substanceid": 4454, "newmolfile": "CCO"},
        459193,
        SAME,
    ),
    Case(
        "save_ghs_entry",
        {"substance_id": 4454, "hazard_codes": ["H225", "H410"], "source": "Sigma"},
        "container/ghs/save",
        {
            "entryid": 0,
            "hcodes": ["H225", "H410"],
            "source": "Sigma",
            "substance": 4454,
        },
        {"id": 8226},
        8226,
    ),
    Case(
        "delete_ghs_entry",
        {"entry_id": 8226},
        "container/ghs/delete",
        {"entryid": 8226},
    ),
    # Custom fields
    Case(
        "list_custom_fields",
        {},
        "customfields/get",
        data={"container": [{"id": 363, "name": "Expiry Date"}], "substance": []},
        result=SAME,
    ),
    Case(
        "save_custom_field",
        {
            "field_kind": "substance",
            "name": "Storage class",
            "data_type": "dropdown",
            "allowed_values": ["3", "6.1"],
            "searchable": True,
        },
        "customfields/save",
        {
            "id": 0,
            "fieldtype": "substance",
            "name": "Storage class",
            "type": "dropdown",
            "searchable": True,
            "allowedvalues": ["3", "6.1"],
        },
        5361,
        SAME,
    ),
    Case(
        "delete_custom_field",
        {"field_id": 5361, "field_kind": "container"},
        "customfields/delete",
        {"id": 5361, "fieldtype": "container"},
    ),
    # File store
    Case(
        "link_file_to_substance",
        {"file_id": 186451, "substance_id": 5421},
        "filestore/addsubstancelink",
        {"fileid": 186451, "substanceid": 5421},
    ),
    Case(
        "create_file_category",
        {"name": "SDS"},
        "filestore/createcategory",
        {"name": "SDS", "scope": "inventory"},
        480,
        SAME,
    ),
    Case(
        "delete_file_category",
        {"category_id": 480},
        "filestore/deletecategory",
        {"id": 480},
    ),
    Case("delete_file", {"file_id": 1}, "filestore/deletefile", {"fileid": 1}),
    Case(
        "file_download_url",
        {"file_id": 1},
        "filestore/download",
        {"fileid": 1},
        "https://files.example.org/abc",
        SAME,
    ),
    Case(
        "substance_files",
        {"substance_id": 5421},
        "filestore/getlinkedfiles",
        {"substanceid": 5421},
        [FILE],
        SAME,
    ),
    Case(
        "file_substances",
        {"file_id": 186451},
        "filestore/getsubstancelinks",
        {"fileid": 186451},
        [{"id": 5421, "name": "Pyrrolidine", "cas": "123-75-1"}],
        SAME,
    ),
    Case(
        "load_file_store",
        {"scope": "site"},
        "filestore/load",
        {"scope": "site"},
        {"categories": [{"id": 480, "name": "SDS"}], "files": [FILE]},
        SAME,
    ),
    Case(
        "unlink_file_from_substance",
        {"file_id": 186451, "substance_id": 5421},
        "filestore/removesubstancelink",
        {"fileid": 186451, "substanceid": 5421},
    ),
    Case(
        "rename_file_category",
        {"category_id": 480, "name": "Safety data sheets"},
        "filestore/renamecategory",
        {"id": 480, "name": "Safety data sheets"},
    ),
    Case(
        "rename_file",
        {"file_id": 1, "file_name": "acetone.pdf"},
        "filestore/renamefile",
        {"fileid": 1, "filename": "acetone.pdf"},
    ),
    Case(
        "set_file_category",
        {"file_id": 1, "category_id": 0},
        "filestore/updatefilecategory",
        {"fileid": 1, "newcategoryid": 0},
    ),
    # Inventory, locations, search
    Case(
        "export_containers",
        {"container_ids": [1, 2]},
        "general/exportbyid",
        {"containerids": [1, 2]},
        TABLE,
        TABLE_ROWS,
    ),
    Case(
        "export_containers",
        {},
        "inventorymanagement/export",
        data=TABLE,
        result=TABLE_ROWS,
    ),
    Case(
        "get_details",
        {},
        "general/getdetails",
        data={"user": {"id": 178, "inventory": 9}, "inventory": {"id": 9}},
        result=SAME,
    ),
    Case(
        "list_units",
        {},
        "general/units",
        data=[{"id": 5, "unit": "g"}, {"id": 1, "unit": "mL"}],
        result=SAME,
    ),
    Case(
        "audit_history",
        {"start_date": "2022-03-01", "end_date": "2022-03-31"},
        "inventorymanagement/audithistory/load",
        {"startdate": "2022-03-01", "enddate": "2022-03-31"},
        [
            [
                "2022-03-16 01:51:20",
                "Smith, Andrew",
                "Container",
                "Movement",
                "moved",
                {"containerid": 855558, "event": "move"},
            ]
        ],
        SAME,
    ),
    Case(
        "switch_inventory",
        {"inventory_id": 10},
        "navbar/switchinventory",
        {"newinventory": 10},
    ),
    Case(
        "list_locations",
        {},
        "location/load",
        data=[{"id": 381572, "name": "Cupboard 1", "parent": 381555}],
        result=SAME,
    ),
    Case(
        "location_containers",
        {"location_id": 381572},
        "location/containers/get",
        {"locationid": 381572},
        SEARCH_RESULT,
        SAME,
    ),
    Case(
        "move_location_containers",
        {"origin_id": 1, "destination_id": 2},
        "location/containers/move",
        {"origin": 1, "destination": 2},
    ),
    Case(
        "delete_location_containers",
        {"location_id": 1},
        "location/containers/delete",
        {"locationid": 1},
    ),
    Case(
        "search",
        {"inventory": 9, "search_type": "name", "terms": ["dipea"]},
        "search/execute",
        {"inventory": 9, "type": "name", "contents": "dipea"},
        SEARCH_RESULT,
        [{"term": "dipea", **SEARCH_RESULT}],
    ),
    Case(
        "search",
        {
            "inventory": "site",
            "search_type": "ghs",
            "terms": [{"searchtype": "or", "items": ["H200", "H201"]}],
        },
        "search/execute",
        {
            "inventory": "site",
            "type": "ghs",
            "contents": {"searchtype": "or", "items": ["H200", "H201"]},
        },
        SEARCH_RESULT,
        [{"term": {"searchtype": "or", "items": ["H200", "H201"]}, **SEARCH_RESULT}],
    ),
    Case(
        "search",
        {"inventory": 9, "search_type": "cf-date-363", "terms": ["2027-01-01"]},
        "search/execute",
        {"inventory": 9, "type": "cf-date-363", "contents": "2027-01-01"},
        SEARCH_RESULT,
        [{"term": "2027-01-01", **SEARCH_RESULT}],
    ),
    Case(
        "search",
        {"inventory": 9, "search_type": "cas", "terms": [" 7087-68-5 "]},
        "search/execute",
        {"inventory": 9, "type": "cas", "contents": " 7087-68-5 "},
        SEARCH_RESULT,
        [{"term": " 7087-68-5 ", **SEARCH_RESULT}],
    ),
    Case(
        "export_containers",
        {"columns": ["barcode", "Container Name"]},
        "inventorymanagement/export",
        data=TABLE,
        result=[
            {"Barcode": "ABC123", "Container Name": "Acetone"},
            {"Barcode": "ABC124", "Container Name": "Toluene"},
        ],
    ),
    Case(
        "export_containers",
        {"container_ids": [1], "columns": ["Barcode"]},
        "general/exportbyid",
        {"containerids": [1]},
        {"columns": TABLE["columns"], "rows": []},
        [],
    ),
    Case(
        "advanced_search_options",
        {},
        "search/loadadvancedsearch",
        data=[{"id": "name", "label": "Name", "type": "string"}],
        result=SAME,
    ),
    # Users
    Case(
        "add_user",
        {
            "inventory_id": 9,
            "email": "a@example.org",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "account_type": 4,
        },
        "inventorymanagement/users/add",
        {
            "inventory": 9,
            "email": "a@example.org",
            "firstname": "Ada",
            "lastname": "Lovelace",
            "accounttype": 4,
        },
        23425,
        SAME,
    ),
    Case(
        "disable_user",
        {"user_id": 23425, "inventory_id": 9},
        "inventorymanagement/users/disable",
        {"id": 23425, "inventory": 9},
    ),
    Case(
        "list_users",
        {"inventory_id": 9},
        "inventorymanagement/users/list",
        {"inventory": 9},
        [{"id": 2254, "email": "d@example.org", "accounttype": 4}],
        SAME,
    ),
    Case(
        "reset_user_password",
        {"user_id": 2254, "password": "correct horse"},
        "inventorymanagement/users/resetpassword",
        {"id": 2254, "password": "correct horse"},
    ),
    Case(
        "update_user",
        {
            "user_id": 2254,
            "email": "d@example.org",
            "first_name": "David",
            "last_name": "Matthews",
            "account_type": 6,
            "inventory_id": 9,
        },
        "inventorymanagement/users/update",
        {
            "id": 2254,
            "email": "d@example.org",
            "firstname": "David",
            "lastname": "Matthews",
            "accounttype": 6,
            "inventory": 9,
        },
    ),
    # My Collection
    Case(
        "add_to_collection",
        {"container_ids": [1, 2]},
        "mycollection/add",
        {"containerid": [1, 2]},
    ),
    Case(
        "add_to_collection_by_barcode",
        {"barcodes": ["AEF01220", "ABC123"]},
        "mycollection/addbybarcode",
        {"barcode": ["AEF01220", "ABC123"]},
        {"errorBarcodes": ["ABC123"]},
        ["ABC123"],
    ),
    Case("delete_collection_containers", {}, "mycollection/deleteall"),
    Case(
        "load_collection",
        {},
        "mycollection/load",
        data=[{"id": 6280879, "name": "1-adamantanol 99%", "sid": 8303}],
        result=SAME,
    ),
    Case(
        "move_collection",
        {"destination_id": 40032},
        "mycollection/moveall",
        {"destinationid": 40032},
    ),
    Case(
        "remove_from_collection",
        {"container_id": 1},
        "mycollection/remove",
        {"containerid": 1},
    ),
    Case("clear_collection", {}, "mycollection/removeall"),
    # Orders
    Case(
        "receive_order",
        {
            "order_id": 817,
            "name": "PPh3",
            "location_id": 40032,
            "custom_fields": {425: "x"},
        },
        "order/addcontainer",
        {"orderid": 817, "name": "PPh3", "locationid": 40032, "cf-425": "x"},
    ),
    Case("delete_order", {"order_id": 817}, "order/delete", {"orderid": 817}),
    Case(
        "edit_order",
        {"order_id": 817, "supplier": "Sigma Aldrich", "size": "1000", "unit_id": 5},
        "order/edit",
        {
            "orderid": 817,
            "containersize": "1000",
            "units": 5,
            "supplier": "Sigma Aldrich",
            "destinationlocation": 0,
        },
        {"suppliername": "Sigma Aldrich", "size": "1000", "unitid": "5"},
        SAME,
    ),
    Case(
        "list_orders",
        {},
        "order/load",
        data=[{"id": 817, "name": "Triphenylphosphine", "substanceid": 382144}],
        result=SAME,
    ),
    Case(
        "request_order",
        {
            "substance_id": 382144,
            "name": "Triphenylphosphine",
            "supplier": "Sigma Aldrich",
            "size": "1000",
            "unit_id": 5,
            "quantity": 2,
            "comments": "Purity: 99%",
            "status_change_email": True,
        },
        "order/request",
        {
            "substanceid": 382144,
            "name": "Triphenylphosphine",
            "supplier": "Sigma Aldrich",
            "containersize": "1000",
            "units": 5,
            "quantity": 2,
            "comments": "Purity: 99%",
            "destinationlocation": 0,
            "statuschangeemail": True,
        },
    ),
    Case(
        "toggle_order_placed",
        {"order_id": 817},
        "order/toggleordered",
        {"orderid": 817},
        "2022-04-22 03:20:59",
        SAME,
    ),
    Case(
        "toggle_order_placed",
        {"order_id": 817},
        "order/toggleordered",
        {"orderid": 817},
        0,
        "0",
    ),
    # Watchlists
    Case(
        "check_watchlists",
        {"substance_id": 4454},
        "watchlist/checksubstance",
        {"substanceid": 4454},
        [{"watchlistid": 1, "watchlistname": "DHS Appendix A", "hassubstance": True}],
        SAME,
    ),
    Case(
        "delete_watchlist",
        {"watchlist_id": 3},
        "watchlist/delete",
        {"id": 3},
    ),
    Case(
        "watchlist_report",
        {"watchlist_id": 117},
        "watchlist/generatereport",
        {"id": 117, "scope": "inventory"},
        TABLE,
        TABLE_ROWS,
    ),
    Case(
        "list_watchlists",
        {},
        "watchlist/load",
        data={"global": [{"id": 117, "terms": ["100-35-6"]}], "inventory": []},
        result=SAME,
    ),
    Case(
        "save_watchlist",
        {"name": "Peroxide formers", "terms": ["60-29-7"]},
        "watchlist/save",
        {
            "id": 0,
            "scope": "inventory",
            "name": "Peroxide formers",
            "terms": ["60-29-7"],
        },
    ),
]


def respond(api: respx.MockRouter, endpoint: str, data: Any) -> respx.Route:
    return api.post(endpoint).respond(json={"status": "success", "data": data})


def sent(route: respx.Route) -> Any:
    return json.loads(route.calls.last.request.content)


def value(result: CallToolResult) -> Any:
    content: dict[str, Any] | None = result.structured_content
    assert content is not None

    return content["result"] if set(content) == {"result"} else content


def text(result: CallToolResult) -> str:
    return " ".join(getattr(block, "text", "") for block in result.content)


@pytest.mark.anyio
@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
async def test_tool_request_and_result(
    case: Case, api: respx.MockRouter, session: Client
) -> None:
    route: respx.Route = respond(api, case.endpoint, case.data)

    result: CallToolResult = await session.call_tool(case.tool, case.arguments)

    assert not result.is_error, text(result)
    assert route.call_count == 1
    assert sent(route) == {"authtoken": TOKEN, **case.params}
    assert value(result) == (case.data if case.result is SAME else case.result)


@pytest.mark.anyio
async def test_every_tool_and_endpoint_covered(session: Client) -> None:
    tools: set[str] = {tool.name for tool in (await session.list_tools()).tools}

    assert tools == {case.tool for case in CASES} | FILE_TOOLS
    assert ENDPOINTS == {case.endpoint for case in CASES}


@pytest.mark.anyio
async def test_annotations(session: Client) -> None:
    for tool in (await session.list_tools()).tools:
        hints: ToolAnnotations | None = tool.annotations
        assert hints is not None, tool.name
        assert hints.open_world_hint is False, tool.name
        assert bool(hints.read_only_hint) == (tool.name in READ_ONLY), tool.name
        if not hints.read_only_hint:
            assert hints.destructive_hint == (tool.name not in ADDITIVE), tool.name
        assert tool.description, tool.name


@pytest.mark.anyio
async def test_instructions(session: Client) -> None:
    assert session.instructions is not None
    assert "get_details" in session.instructions


@pytest.mark.anyio
async def test_api_error_is_reported(api: respx.MockRouter, session: Client) -> None:
    api.post("order/load").respond(json={"status": "error", "data": "Invalid token"})

    result: CallToolResult = await session.call_tool("list_orders", {})

    assert result.is_error
    assert "/order/load: Invalid token" in text(result)
    assert TOKEN not in text(result)


@pytest.mark.anyio
async def test_http_error_is_reported(api: respx.MockRouter, session: Client) -> None:
    api.post("location/load").respond(status_code=502)

    result: CallToolResult = await session.call_tool("list_locations", {})

    assert result.is_error
    assert "/location/load: HTTP 502" in text(result)
    assert TOKEN not in text(result)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("list_users", {}),
        ("generate_barcodes", {"prefix": "TOOLONG", "count": 1, "starting_number": 1}),
        ("generate_barcodes", {"prefix": "AB", "count": 0, "starting_number": 1}),
        ("reset_user_password", {"user_id": 1, "password": "short"}),
        (
            "add_user",
            {
                "inventory_id": 9,
                "email": "a",
                "first_name": "a",
                "last_name": "b",
                "account_type": 1,
            },
        ),
        ("save_custom_field", {"field_kind": "user", "name": "x", "data_type": "text"}),
        (
            "save_custom_field",
            {"field_kind": "container", "name": "x", "data_type": "bool"},
        ),
        (
            "request_order",
            {
                "substance_id": 1,
                "name": "x",
                "supplier": "s",
                "size": "1",
                "unit_id": 1,
                "quantity": 0,
            },
        ),
        ("load_file_store", {"scope": "world"}),
        ("search", {"inventory": 9, "search_type": "name", "terms": []}),
        ("search", {"inventory": 9, "search_type": "smiles", "terms": ["CCO"]}),
        ("search", {"inventory": 9, "search_type": "name", "contents": "x"}),
        ("export_containers", {"columns": []}),
        ("add_containers", {"location_id": 1, "substance_id": 1, "containers": [{}]}),
        (
            "update_container",
            {"container_id": 1, "field": "containersize", "value": "5"},
        ),
    ],
)
async def test_invalid_arguments_send_no_request(
    tool: str, arguments: dict[str, Any], api: respx.MockRouter, session: Client
) -> None:
    route: respx.Route = api.post(url__regex=".*").respond(
        json={"status": "success", "data": []}
    )

    result: CallToolResult = await session.call_tool(tool, arguments)

    assert result.is_error
    assert not route.called


@pytest.mark.anyio
async def test_export_unknown_column(api: respx.MockRouter, session: Client) -> None:
    respond(api, "inventorymanagement/export", TABLE)

    result: CallToolResult = await session.call_tool(
        "export_containers", {"columns": ["Barcode", "Remaining"]}
    )

    assert result.is_error
    assert (
        "Unknown columns ['Remaining']; available: "
        "['Barcode', 'Container Name', 'extra']" in text(result)
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("term", "message"),
    [
        ("7087-68-4", "7087-68-4 has a wrong check digit"),
        ("7087685", "'7087685' is not a CAS number"),
        ("1-11-1", "'1-11-1' is not a CAS number"),
        ({"cas": "7087-68-5"}, "is not a CAS number"),
    ],
)
async def test_invalid_cas_is_not_searched(
    term: str | dict[str, str],
    message: str,
    api: respx.MockRouter,
    session: Client,
) -> None:
    route: respx.Route = respond(api, "search/execute", SEARCH_RESULT)

    result: CallToolResult = await session.call_tool(
        "search", {"inventory": 9, "search_type": "cas", "terms": [term, "64-17-5"]}
    )

    assert not result.is_error, text(result)
    assert route.call_count == 1
    assert sent(route)["contents"] == "64-17-5"

    errors: list[dict[str, Any]] = value(result)
    assert errors[0]["term"] == term
    assert message in errors[0]["error"]
    assert errors[1] == {"term": "64-17-5", **SEARCH_RESULT}


@pytest.mark.anyio
async def test_search_runs_three_at_a_time_in_order(
    api: respx.MockRouter, session: Client
) -> None:
    running: int = 0
    peak: int = 0

    async def reply(request: httpx.Request) -> httpx.Response:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1

        term: str = json.loads(request.content)["contents"]
        if term == "fail":
            return httpx.Response(200, json={"status": "error", "data": "Bad term"})

        return httpx.Response(
            200,
            json={"status": "success", "data": {"orders": [], "containers": [term]}},
        )

    route: respx.Route = api.post("search/execute").mock(side_effect=reply)
    terms: list[str] = [f"term {number}" for number in range(10)] + ["fail"]

    result: CallToolResult = await session.call_tool(
        "search", {"inventory": 9, "search_type": "name", "terms": terms}
    )

    assert not result.is_error, text(result)
    assert route.call_count == 11
    assert peak == 3
    assert value(result) == [
        {"term": term, "orders": [], "containers": [term]} for term in terms[:-1]
    ] + [{"term": "fail", "error": "/search/execute: Bad term"}]
