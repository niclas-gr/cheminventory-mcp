import base64
import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pymupdf
import pytest
import respx
from mcp import Client
from mcp.types import CallToolResult, ImageContent

from cheminventory_mcp import files
from tests.conftest import BASE_URL, TOKEN

API: str = f"{BASE_URL}/api"
FILES: str = "https://files.example.org"


HEADER: str = "Safety Data Sheet - Acme Chemicals"


def pdf(*sections: str, scanned: bool = False) -> bytes:
    """A PDF with one page per section title, each with a header, body and footer;
    an empty title gives a blank page, scanned an image without a text layer."""
    document: pymupdf.Document = pymupdf.open()
    for number, title in enumerate(sections, start=1):
        page: pymupdf.Page = document.new_page()
        if title:
            page.insert_text((72, 40), HEADER, fontsize=9)
            page.insert_text((72, 100), title, fontsize=16)
            page.insert_text((72, 130), "Boiling point: 58 C. Flash point: none.")
            page.insert_text((72, 145), "Density: 1.6 g/cm3 at 20 C.")
            page.insert_text((72, 800), f"Page {number} of {len(sections)}", fontsize=9)

    if not scanned:
        return document.tobytes()

    image: pymupdf.Document = pymupdf.open()
    for page in document:
        target: pymupdf.Page = image.new_page()
        target.insert_image(target.rect, pixmap=page.get_pixmap(dpi=150))

    return image.tobytes()


def body(text: str) -> str:
    """Text with layout whitespace collapsed, for robust comparisons."""
    return " ".join(text.split())


PNG: bytes = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 2, 2), False).tobytes(
    "png"
)


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as router:
        yield router


def serve(
    mock: respx.MockRouter, files: dict[int, httpx.Response | str]
) -> respx.Route:
    """Serve file IDs: a response from the file host, or an API error message."""

    def download(request: httpx.Request) -> httpx.Response:
        file_id: int = json.loads(request.content)["fileid"]
        served: httpx.Response | str = files[file_id]
        if isinstance(served, str):
            return httpx.Response(200, json={"status": "error", "data": served})

        mock.get(f"{FILES}/{file_id}").mock(return_value=served)
        return httpx.Response(
            200, json={"status": "success", "data": f"{FILES}/{file_id}?signed=1"}
        )

    return mock.post(f"{API}/filestore/download").mock(side_effect=download)


def entries(result: CallToolResult) -> list[dict[str, Any]]:
    assert not result.is_error, result.content
    assert result.structured_content is not None

    return result.structured_content["result"]


def pdf_response(data: bytes, name: str = "sds.pdf") -> httpx.Response:
    return httpx.Response(
        200,
        content=data,
        headers={
            "content-type": "application/pdf",
            "content-disposition": f'attachment; filename="{name}"',
        },
    )


@pytest.mark.anyio
async def test_file_content(mock: respx.MockRouter, session: Client) -> None:
    route: respx.Route = serve(
        mock,
        {
            1: pdf_response(
                pdf("Section 1: Identification", "", "Section 9: Properties")
            ),
            2: httpx.Response(
                200,
                content=b"Lot 42\n",
                headers={"content-type": "text/plain; charset=utf-8"},
            ),
            3: httpx.Response(200, content=PNG, headers={"content-type": "image/png"}),
            4: "File not found",
        },
    )

    result: CallToolResult = await session.call_tool(
        "file_content", {"file_ids": [1, 2, 3, 4]}
    )

    assert route.call_count == 4
    assert all(
        json.loads(call.request.content)["authtoken"] == TOKEN for call in route.calls
    )
    assert all(
        TOKEN not in str(call.request.url)
        and TOKEN.encode() not in call.request.content
        for call in mock.calls
        if call.request.url.host == "files.example.org"
    )

    document: dict[str, Any]
    others: list[dict[str, Any]]
    document, *others = entries(result)
    assert document["file_id"] == 1
    assert document["name"] == "sds.pdf"
    assert document["pages"] == 3
    assert document["total_chars"] == len(document["text"])

    pages: list[str] = document["text"].split("--- page ")
    assert [page.split(" ---")[0] for page in pages[1:]] == ["1", "2", "3"]
    assert "# Section 1: Identification" in pages[1]
    assert "Boiling point: 58 C. Flash point: none." in body(pages[1])
    assert body(pages[2]) == "2 ---"
    assert "# Section 9: Properties" in pages[3]
    assert HEADER not in document["text"]
    assert "Page 1 of 3" not in document["text"]

    assert others == [
        {"file_id": 2, "name": "2", "total_chars": 7, "text": "Lot 42\n"},
        {"file_id": 3, "name": "3", "image": "image/png"},
        {"file_id": 4, "error": "/filestore/download: File not found"},
    ]

    image: object = result.content[1]
    assert isinstance(image, ImageContent)
    assert image.mime_type == "image/png"
    assert base64.b64decode(image.data) == PNG


@pytest.mark.anyio
async def test_pages_and_max_chars(mock: respx.MockRouter, session: Client) -> None:
    serve(mock, {1: pdf_response(pdf("One", "Two", "Three", "Four"))})

    full: dict[str, Any] = entries(
        await session.call_tool("file_content", {"file_ids": [1], "pages": "2-3"})
    )[0]
    cut: dict[str, Any] = entries(
        await session.call_tool(
            "file_content", {"file_ids": [1], "pages": "2-3", "max_chars": 20}
        )
    )[0]

    assert full["pages"] == 4
    assert full["text"].startswith("--- page 2 ---\n# Two")
    assert "--- page 3 ---\n# Three" in full["text"]
    assert "One" not in full["text"]
    assert "Four" not in full["text"]
    assert cut == full | {"text": full["text"][:20]}


@pytest.mark.anyio
async def test_headers_footers_and_text_format(
    mock: respx.MockRouter, session: Client
) -> None:
    serve(
        mock, {1: pdf_response(pdf("Section 9: Properties", "Section 10: Stability"))}
    )

    kept: str = entries(
        await session.call_tool(
            "file_content", {"file_ids": [1], "headers_footers": True}
        )
    )[0]["text"]
    plain: str = entries(
        await session.call_tool(
            "file_content", {"file_ids": [1], "text_format": "text"}
        )
    )[0]["text"]

    assert HEADER in kept
    assert "Page 2 of 2" in kept
    assert "Section 9: Properties" in plain
    assert "#" not in plain
    assert HEADER not in plain


@pytest.mark.anyio
async def test_ocr(mock: respx.MockRouter, session: Client) -> None:
    serve(mock, {1: pdf_response(pdf("Section 9: Properties", scanned=True))})

    recognized: dict[str, Any] = entries(
        await session.call_tool("file_content", {"file_ids": [1]})
    )[0]
    skipped: dict[str, Any] = entries(
        await session.call_tool("file_content", {"file_ids": [1], "ocr": "never"})
    )[0]

    assert "Boiling point: 58 C" in body(recognized["text"])
    assert skipped["error"].startswith("sds.pdf: no text found")
    assert "try ocr='auto'" in skipped["error"]


@pytest.mark.anyio
async def test_documents_are_parsed_one_at_a_time(
    mock: respx.MockRouter, session: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    running: int = 0
    peak: int = 0
    lock: threading.Lock = threading.Lock()

    def parse(*_: object) -> tuple[int, list[str]]:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.02)
        with lock:
            running -= 1

        return 1, ["--- page 1 ---\nx"]

    monkeypatch.setattr(files, "document_text", parse)
    serve(mock, {number: pdf_response(pdf("x")) for number in range(1, 5)})

    result: CallToolResult = await session.call_tool(
        "file_content", {"file_ids": [1, 2, 3, 4]}
    )

    assert [entry["text"] for entry in entries(result)] == ["--- page 1 ---\nx"] * 4
    assert peak == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "pages", "message"),
    [
        (pdf_response(pdf("One", "Two")), "2-3", "Pages 2-3 are outside 1-2"),
        (
            pdf_response(pdf("", "")),
            None,
            "sds.pdf: no text found (scanned document, or only page headers and footers?); use save_files, or set headers_footers",
        ),
        (
            httpx.Response(
                200,
                content=b"PK\x03\x04",
                headers={
                    "content-type": "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document",
                    "content-disposition": "attachment; filename=coa.docx",
                },
            ),
            None,
            "coa.docx: unsupported file type; use save_files",
        ),
        (httpx.Response(404), None, "file 1: HTTP 404"),
        (
            httpx.Response(302, headers={"location": "http://files.example.org/x"}),
            None,
            "Refusing to download over http: files.example.org",
        ),
    ],
)
async def test_file_content_errors(
    response: httpx.Response,
    pages: str | None,
    message: str,
    mock: respx.MockRouter,
    session: Client,
) -> None:
    serve(mock, {1: response})
    plain: respx.Route = mock.get("http://files.example.org/x").respond(200)
    arguments: dict[str, Any] = {"file_ids": [1]} | ({"pages": pages} if pages else {})

    result: CallToolResult = await session.call_tool("file_content", arguments)

    assert entries(result) == [{"file_id": 1, "error": message}]
    assert not plain.called


@pytest.mark.anyio
async def test_refuses_http_download_url(
    mock: respx.MockRouter, session: Client
) -> None:
    mock.post(f"{API}/filestore/download").respond(
        json={"status": "success", "data": "http://files.example.org/1"}
    )
    plain: respx.Route = mock.get("http://files.example.org/1").respond(200)

    result: CallToolResult = await session.call_tool("file_content", {"file_ids": [1]})

    assert entries(result) == [
        {"file_id": 1, "error": "Refusing to download over http: files.example.org"}
    ]
    assert not plain.called


@pytest.mark.anyio
@pytest.mark.parametrize(
    "arguments",
    [
        {"file_ids": []},
        {"file_ids": [1], "pages": "1-"},
        {"file_ids": [1], "pages": "a"},
        {"file_ids": [1], "max_chars": 0},
        {"file_ids": [1], "text_format": "html"},
        {"file_ids": [1], "ocr": "sometimes"},
    ],
)
async def test_file_content_invalid_arguments(
    arguments: dict[str, Any], mock: respx.MockRouter, session: Client
) -> None:
    route: respx.Route = mock.post(f"{API}/filestore/download").respond(200)

    result: CallToolResult = await session.call_tool("file_content", arguments)

    assert result.is_error
    assert not route.called


@pytest.mark.anyio
async def test_save_files(
    tmp_path: Path, mock: respx.MockRouter, session: Client
) -> None:
    folder: Path = tmp_path / "new" / "folder"
    folder.mkdir(parents=True)
    (folder / "old.pdf").write_bytes(b"%PDF-old")
    serve(
        mock,
        {
            1: pdf_response(b"%PDF-1", name="../../sds.pdf"),
            2: pdf_response(b"%PDF-2", name="old.pdf"),
            3: httpx.Response(
                200, content=b"x", headers={"content-type": "text/plain"}
            ),
            4: "File not found",
        },
    )

    result: CallToolResult = await session.call_tool(
        "save_files", {"file_ids": [1, 2, 3, 4], "directory": str(folder)}
    )

    saved: list[dict[str, Any]] = entries(result)
    assert saved[0] == {"file_id": 1, "path": str(folder / "sds.pdf")}
    assert saved[1] == {"file_id": 2, "error": f"{folder / 'old.pdf'} already exists"}
    assert saved[2] == {"file_id": 3, "path": str(folder / "3")}
    assert saved[3] == {"file_id": 4, "error": "/filestore/download: File not found"}
    assert (folder / "sds.pdf").read_bytes() == b"%PDF-1"
    assert (folder / "old.pdf").read_bytes() == b"%PDF-old"
    assert (folder / "3").read_bytes() == b"x"
    assert sorted(path.name for path in folder.iterdir()) == ["3", "old.pdf", "sds.pdf"]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["new"]


@pytest.mark.anyio
async def test_save_files_needs_absolute_path(
    mock: respx.MockRouter, session: Client
) -> None:
    route: respx.Route = mock.post(f"{API}/filestore/download").respond(200)

    result: CallToolResult = await session.call_tool(
        "save_files", {"file_ids": [1], "directory": "downloads"}
    )

    assert result.is_error
    assert "directory must be an absolute path: 'downloads'" in str(result.content)
    assert not route.called
