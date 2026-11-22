import json
import tomllib
from pathlib import Path
from typing import Any

ROOT: Path = Path(__file__).parent.parent


def test_versions_and_names_match() -> None:
    project: dict[str, Any] = tomllib.loads((ROOT / "pyproject.toml").read_text())[
        "project"
    ]
    server: dict[str, Any] = json.loads((ROOT / "server.json").read_text())
    package: dict[str, Any] = server["packages"][0]

    assert server["version"] == package["version"] == project["version"]
    assert package["identifier"] == project["name"]
    assert f"<!-- mcp-name: {server['name']} -->" in (ROOT / "README.md").read_text()
    assert len(server["description"]) <= 100
