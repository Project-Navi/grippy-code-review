# SPDX-License-Identifier: MIT
"""MCP client detection and registration.

Detects installed MCP clients (Claude Code, Claude Desktop, Cursor),
generates grippy server entries, and manages client config files.
"""

from __future__ import annotations

import json
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Any


class MCPClient(Enum):
    """Supported MCP clients."""

    CLAUDE_CODE = "Claude Code"
    CLAUDE_DESKTOP = "Claude Desktop"
    CURSOR = "Cursor"


def get_config_path(client: MCPClient) -> Path | None:
    """Return the config file path for the given MCP client.

    Returns None if the platform is unsupported for the given client.
    """
    home = Path.home()

    if client == MCPClient.CLAUDE_CODE:
        return home / ".claude.json"

    if client == MCPClient.CURSOR:
        return home / ".cursor" / "mcp.json"

    if client == MCPClient.CLAUDE_DESKTOP:
        if sys.platform == "darwin":
            return (
                home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
            )
        if sys.platform == "win32":
            appdata = Path.home() / "AppData" / "Roaming"
            return appdata / "Claude" / "claude_desktop_config.json"
        # Linux / other Unix
        xdg = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
        return xdg / "Claude" / "claude_desktop_config.json"

    return None  # pragma: no cover


def get_available_clients() -> list[MCPClient]:
    """Return clients where the config file exists OR its parent dir exists."""
    available: list[MCPClient] = []
    for client in MCPClient:
        config_path = get_config_path(client)
        if config_path is None:
            continue
        if config_path.exists() or config_path.parent.exists():
            available.append(client)
    return available


def generate_server_entry(
    project_root: Path | None, env: dict[str, str]
) -> dict[str, Any]:
    """Generate a grippy MCP server entry for client config files.

    If *project_root* is provided, generates a dev-mode entry using
    ``uv run --directory``.  If *project_root* is None, generates a
    published-package entry using ``uvx grippy-mcp``.

    Returns:
        Dict with command, args, and env suitable for mcpServers config.
    """
    if project_root is not None:
        return {
            "command": "uv",
            "args": ["run", "--directory", str(project_root), "grippy", "serve"],
            "env": env,
        }
    return {
        "command": "uvx",
        "args": ["grippy-mcp", "serve"],
        "env": env,
    }


def add_to_client(client: MCPClient, server_entry: dict[str, Any]) -> bool:
    """Add grippy to the given client's MCP config.

    Loads the config JSON, sets ``config["mcpServers"]["grippy"]`` to
    *server_entry*, and saves. Creates the file if it doesn't exist.

    Returns True on success, False on OSError or if config path is None.
    """
    config_path = get_config_path(client)
    if config_path is None:
        return False
    try:
        config = _load_config(config_path)
        mcp_servers: dict[str, Any] = config.setdefault("mcpServers", {})
        mcp_servers["grippy"] = server_entry
        _save_config(config_path, config)
        return True
    except OSError:
        return False


def remove_from_client(client: MCPClient) -> bool:
    """Remove grippy from the given client's MCP config.

    Returns True if grippy was present and removed, False otherwise.
    """
    config_path = get_config_path(client)
    if config_path is None:
        return False
    try:
        config = _load_config(config_path)
        mcp_servers: dict[str, Any] = config.get("mcpServers", {})
        if "grippy" not in mcp_servers:
            return False
        del mcp_servers["grippy"]
        _save_config(config_path, config)
        return True
    except OSError:
        return False


def is_configured(client: MCPClient) -> bool:
    """Check if grippy is registered in the given client's config."""
    config_path = get_config_path(client)
    if config_path is None or not config_path.exists():
        return False
    try:
        config = _load_config(config_path)
        servers = config.get("mcpServers", {})
        return "grippy" in servers
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_config(config_path: Path) -> dict[str, Any]:
    """Load JSON config from *config_path*.

    Returns an empty dict if the file is missing or contains invalid JSON.
    """
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _save_config(config_path: Path, config: dict[str, Any]) -> None:
    """Write *config* as pretty-printed JSON to *config_path*.

    Creates parent directories if they don't exist.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
