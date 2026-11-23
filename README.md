# ChemInventory MCP Server

An [MCP](https://modelcontextprotocol.io) server for the [ChemInventory API](https://www.cheminventory.net/support/api/). It lets AI assistants such as Claude search a chemical inventory, read and update containers, substances, orders, files, users and watchlists. Every documented API endpoint is available as a tool.

> This project is not affiliated with, endorsed by or supported by ChemInventory or Antipodes Scientific Ltd. "ChemInventory" is used only to name the service this server connects to.

<!-- mcp-name: io.github.niclas-gr/cheminventory-mcp -->

## Installation

The server is published on [PyPI](https://pypi.org/project/cheminventory-mcp/) as `cheminventory-mcp` and needs Python 3.13 or later on macOS 14+ with Apple silicon, Windows on x64 or Linux on x86-64 or ARM64 (glibc 2.28+). The recommended way to run it is with [uv](https://docs.astral.sh/uv/), which also downloads a suitable Python version when none is installed. Install uv as described in [Astral's documentation](https://docs.astral.sh/uv/getting-started/installation/), then open a new terminal so that `uv` and `uvx` are on the `PATH`.

### 1. Get the server

**Run on demand (recommended).** MCP clients start the server with `uvx cheminventory-mcp`, which downloads the package into an isolated, cached environment on first use. Nothing else needs to be installed; continue with [Connect an MCP client](https://github.com/niclas-gr/cheminventory-mcp#connect-an-mcp-client).

- Pin a version with `uvx cheminventory-mcp@1.0.0`
- Get the newest release with `uvx cheminventory-mcp@latest`

**Install permanently.** To put a `cheminventory-mcp` command on the `PATH` instead:

```bash
uv tool install cheminventory-mcp   # upgrade later with: uv tool upgrade cheminventory-mcp
```

or, without uv, into a Python 3.13+ environment:

```bash
pip install cheminventory-mcp
```

Then use `cheminventory-mcp` as the client command in place of `uvx cheminventory-mcp`, with the absolute path from `which cheminventory-mcp` (`where cheminventory-mcp` on Windows) if the client cannot find it.

### 2. Check that it starts

```bash
CHEMINVENTORY_TOKEN=<token> uvx cheminventory-mcp
```

The server prints nothing and waits for an MCP client on standard input; stop it with <kbd>Ctrl</kbd>+<kbd>C</kbd>. If the token is missing or `CHEMINVENTORY_URL` is not an `https://` URL, it exits with an error message instead.

## API token

A user with _Group Administrator_ privileges creates tokens on the _Inventory Management_ page under _Inventory Tools > API Tokens_. Each token is tied to one user account and has exactly that user's privileges, so a token tied to a read-only account gives read-only access. The token is shown only once; revoke it and create a new one if it is lost. Tie it to the least-privileged account that suffices, such as a read-only account for lookups (see [Security](https://github.com/niclas-gr/cheminventory-mcp#security)).

## Connect an MCP client

All clients start the server with the same command. Replace `<token>` with your [API token](https://github.com/niclas-gr/cheminventory-mcp#api-token).

### Claude Code

```bash
claude mcp add --env CHEMINVENTORY_TOKEN=<token> --transport stdio cheminventory \
  -- uvx cheminventory-mcp
```

Add `--scope user` to make the server available in all projects.

### Claude Desktop

Download [`cheminventory-mcp.mcpb`](https://github.com/niclas-gr/cheminventory-mcp/releases/latest/download/cheminventory-mcp.mcpb) from the latest release and open it, or drag it into the Claude Desktop window. Claude Desktop shows an installation dialog that asks for the API token and, optionally, the installation URL and [access level](https://github.com/niclas-gr/cheminventory-mcp#configuration); the token is stored as a secret. uv must be installed (see [Installation](https://github.com/niclas-gr/cheminventory-mcp#installation)).

To configure it by hand instead, open _Settings > Developer > Edit Config_ and add the server to `claude_desktop_config.json`, then restart Claude Desktop:

```json
{
  "mcpServers": {
    "cheminventory": {
      "command": "uvx",
      "args": ["cheminventory-mcp"],
      "env": { "CHEMINVENTORY_TOKEN": "<token>" }
    }
  }
}
```

If Claude Desktop cannot find `uvx`, set `command` to its absolute path (`which uvx`).

### OpenAI Codex CLI

```bash
codex mcp add cheminventory --env CHEMINVENTORY_TOKEN=<token> -- uvx cheminventory-mcp
```

### Gemini CLI

Add the server to `~/.gemini/settings.json` (all projects) or `.gemini/settings.json` (one project), using the same `mcpServers` entry as for Claude Desktop.

### Other clients and versions

With Node.js installed, [add-mcp](https://www.npmjs.com/package/add-mcp) writes the configuration for many other clients, such as Cursor, VS Code, Windsurf, Cline or Zed, and asks which ones to set up:

```bash
npx add-mcp "uvx cheminventory-mcp" --env "CHEMINVENTORY_TOKEN=<token>" -g
```

Any MCP client that starts stdio servers works with `uvx cheminventory-mcp`. To run the latest unreleased code, use `uvx --from git+https://github.com/niclas-gr/cheminventory-mcp cheminventory-mcp`; for a local checkout, use `uv run --directory /path/to/cheminventory-mcp cheminventory-mcp`.

## Configuration

| Variable | Required | Description |
| --- | --- | --- |
| `CHEMINVENTORY_TOKEN` | yes | API token |
| `CHEMINVENTORY_URL` | no | Installation URL for dedicated or self-hosted servers; must use `https://` |
| `CHEMINVENTORY_ACCESS` | no | Which tools are available: `read-only`, `additive` or `full` |

`CHEMINVENTORY_URL` defaults to `https://app.cheminventory.net`. Use the address you open ChemInventory at in the browser, without `/api`.

`CHEMINVENTORY_ACCESS` defaults to `full`. With `read-only`, only the read-only tools in the table below and `save_files` are available; with `additive`, the additive tools are added, but nothing existing can be changed or deleted. Tools outside the level are not offered to the AI client at all. `get_substance` and `retrieve_substance_info` need `additive`, because they create substances or store structures. To set it, add it next to the token, e.g. `--env CHEMINVENTORY_ACCESS=read-only` for Claude Code or `"CHEMINVENTORY_ACCESS": "read-only"` in the `env` of a JSON configuration.

## Tools

The server provides 71 tools for the 70 API endpoints; `export_containers` covers both export endpoints. Each tool is annotated so that clients can ask before running it: read-only tools change nothing, additive tools only create records or files, and destructive tools may change or delete existing data.

| Group | Read-only | Additive | Destructive |
| --- | --- | --- | --- |
| Inventory, search | `get_details`, `list_units`, `list_locations`, `location_containers`, `search`, `advanced_search_options`, `export_containers`, `audit_history` |  | `move_location_containers`, `delete_location_containers`, `switch_inventory` |
| Containers | `load_container`, `container_history`, `recently_added_containers`, `list_deleted_containers`, `export_deleted_containers` | `add_containers`, `restore_deleted_container` | `update_container`, `toggle_container_recycling`, `move_containers`, `delete_containers` |
| Substances |  | `get_substance`, `retrieve_substance_info` | `update_substance_structure`, `save_ghs_entry`, `delete_ghs_entry` |
| Custom fields | `list_custom_fields` |  | `save_custom_field`, `delete_custom_field` |
| Barcodes | `assigned_barcodes`, `check_barcode`, `duplicate_barcodes` |  | `generate_barcodes` |
| Files | `load_file_store`, `substance_files`, `file_substances`, `file_download_url`, `file_content` | `create_file_category`, `link_file_to_substance`, `save_files` | `rename_file`, `set_file_category`, `unlink_file_from_substance`, `delete_file`, `rename_file_category`, `delete_file_category` |
| Orders | `list_orders` | `request_order` | `edit_order`, `toggle_order_placed`, `receive_order`, `delete_order` |
| My Collection | `load_collection` | `add_to_collection`, `add_to_collection_by_barcode` | `remove_from_collection`, `clear_collection`, `move_collection`, `delete_collection_containers` |
| Watchlists | `list_watchlists`, `check_watchlists`, `watchlist_report` |  | `save_watchlist`, `delete_watchlist` |
| Users | `list_users` | `add_user` | `update_user`, `disable_user`, `reset_user_password` |

`get_substance` creates the substance if it does not exist yet, and `generate_barcodes` can change the inventory's barcode prefix. Some tools need administrator privileges or a site or enterprise license; the API rejects them otherwise.

`file_content` and `save_files` download files from the file store on the computer that runs the server, so they also work where the AI client itself has no network access. `file_content` returns PDFs and other documents as Markdown or plain text, using PyMuPDF's layout analysis for reading order, headings and tables, with page headers and footers removed unless requested; scanned pages are read with OCR ([RapidOCR](https://github.com/RapidAI/RapidOCR), included). Pages and a character limit can be selected. Text files are returned as text and images as images; other formats such as Word files can only be saved. `save_files` writes files to a local folder and never overwrites existing files.

## Security

The token gives the MCP client the full privileges of its user, so tie it to the least-privileged account that suffices, such as a read-only account for lookups. Inventory data that tools return is passed to the AI model and its provider, and text stored in the inventory (names, comments, custom fields, file contents) can contain instructions that the model might follow. Keep confirmation prompts on for destructive tools, and set `CHEMINVENTORY_ACCESS` (see [Configuration](https://github.com/niclas-gr/cheminventory-mcp#configuration)) to hide the tools you do not need. That setting is a second layer on top of the account's privileges: it limits what the AI client can do, but the token itself can still do everything its account can.

## Privacy

The server runs on your computer and keeps no data. It sends requests only to your ChemInventory installation and, for `file_content` and `save_files`, to the file host that ChemInventory's download links point to. Whatever a tool returns goes to your AI client and from there to its model provider, under that provider's terms. There is no telemetry or analytics.

## Development

```bash
uv sync
uv run prek install
uv run pytest
```

The tests run every tool through an MCP client against a mocked API; they need no token or network access.

## License

[GNU AGPL v3.0 or later](https://github.com/niclas-gr/cheminventory-mcp/blob/main/LICENSE). Text extraction uses [PyMuPDF](https://github.com/pymupdf/PyMuPDF), which is licensed under the AGPL.
