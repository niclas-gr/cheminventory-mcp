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


def test_bundle_matches_package() -> None:
    project: dict[str, Any] = tomllib.loads((ROOT / "pyproject.toml").read_text())[
        "project"
    ]
    bundle: dict[str, Any] = json.loads((ROOT / "mcpb" / "manifest.json").read_text())
    config: dict[str, Any] = bundle["server"]["mcp_config"]

    assert bundle["version"] == project["version"]
    assert bundle["name"] == project["name"]
    assert bundle["license"] == project["license"]
    assert config["args"][-1] == f"{project['name']}=={project['version']}"
    assert set(config["env"]) == {
        "CHEMINVENTORY_TOKEN",
        "CHEMINVENTORY_URL",
        "CHEMINVENTORY_ACCESS",
    }
