# SPDX-License-Identifier: MIT
"""Tests for MCP client config detection and registration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from grippy.mcp_config import (
    MCPClient,
    add_to_client,
    generate_server_entry,
    get_available_clients,
    get_config_path,
    is_configured,
    remove_from_client,
)

# ---------------------------------------------------------------------------
# get_config_path tests
# ---------------------------------------------------------------------------


class TestGetConfigPath:
    """Tests for get_config_path."""

    def test_claude_code_returns_claude_json(self) -> None:
        """Claude Code config path ends with .claude.json."""
        path = get_config_path(MCPClient.CLAUDE_CODE)
        assert path is not None
        assert path.name == ".claude.json"

    def test_cursor_returns_mcp_json(self) -> None:
        """Cursor config path ends with mcp.json."""
        path = get_config_path(MCPClient.CURSOR)
        assert path is not None
        assert path.name == "mcp.json"
        assert "cursor" in str(path).lower()

    def test_claude_desktop_returns_desktop_config(self) -> None:
        """Claude Desktop config path ends with claude_desktop_config.json on Linux."""
        with patch("grippy.mcp_config.sys") as mock_sys:
            mock_sys.platform = "linux"
            path = get_config_path(MCPClient.CLAUDE_DESKTOP)
        assert path is not None
        assert path.name == "claude_desktop_config.json"


# ---------------------------------------------------------------------------
# generate_server_entry tests
# ---------------------------------------------------------------------------


class TestGenerateServerEntry:
    """Tests for generate_server_entry."""

    def test_entry_shape(self) -> None:
        """Entry has command=uv, serve in args, --directory in args."""
        entry = generate_server_entry(Path("/some/project"), {"FOO": "bar"})
        assert entry["command"] == "uv"
        assert "serve" in entry["args"]
        assert "--directory" in entry["args"]

    def test_entry_has_project_path(self) -> None:
        """Entry args contain the project root path."""
        root = Path("/my/project")
        entry = generate_server_entry(root, {})
        assert str(root) in entry["args"]

    def test_entry_has_env(self) -> None:
        """Entry includes the provided env dict."""
        env = {"OPENAI_API_KEY": "sk-test"}
        entry = generate_server_entry(Path("/p"), env)
        assert entry["env"] == env


# ---------------------------------------------------------------------------
# add / remove / is_configured tests
# ---------------------------------------------------------------------------


class TestAddRemove:
    """Tests for add_to_client, remove_from_client, is_configured."""

    def test_add_creates_config(self, tmp_path: Path) -> None:
        """add_to_client creates a new config file if it doesn't exist."""
        config_file = tmp_path / "config.json"
        entry = {"command": "uv", "args": ["run", "grippy", "serve"], "env": {}}
        with patch("grippy.mcp_config.get_config_path", return_value=config_file):
            result = add_to_client(MCPClient.CLAUDE_CODE, entry)
        assert result is True
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["mcpServers"]["grippy"] == entry

    def test_add_preserves_existing(self, tmp_path: Path) -> None:
        """add_to_client preserves existing mcpServers entries."""
        config_file = tmp_path / "config.json"
        existing = {"mcpServers": {"other-server": {"command": "node"}}}
        config_file.write_text(json.dumps(existing))
        entry = {"command": "uv", "args": ["run", "grippy", "serve"], "env": {}}
        with patch("grippy.mcp_config.get_config_path", return_value=config_file):
            result = add_to_client(MCPClient.CLAUDE_CODE, entry)
        assert result is True
        data = json.loads(config_file.read_text())
        assert data["mcpServers"]["other-server"] == {"command": "node"}
        assert data["mcpServers"]["grippy"] == entry

    def test_remove_works(self, tmp_path: Path) -> None:
        """remove_from_client removes grippy entry."""
        config_file = tmp_path / "config.json"
        existing = {"mcpServers": {"grippy": {"command": "uv"}, "other": {"command": "node"}}}
        config_file.write_text(json.dumps(existing))
        with patch("grippy.mcp_config.get_config_path", return_value=config_file):
            result = remove_from_client(MCPClient.CLAUDE_CODE)
        assert result is True
        data = json.loads(config_file.read_text())
        assert "grippy" not in data["mcpServers"]
        assert "other" in data["mcpServers"]

    def test_remove_not_present(self, tmp_path: Path) -> None:
        """remove_from_client returns False when grippy is not configured."""
        config_file = tmp_path / "config.json"
        existing = {"mcpServers": {"other": {"command": "node"}}}
        config_file.write_text(json.dumps(existing))
        with patch("grippy.mcp_config.get_config_path", return_value=config_file):
            result = remove_from_client(MCPClient.CLAUDE_CODE)
        assert result is False

    def test_is_configured_true(self, tmp_path: Path) -> None:
        """is_configured returns True when grippy is in mcpServers."""
        config_file = tmp_path / "config.json"
        existing = {"mcpServers": {"grippy": {"command": "uv"}}}
        config_file.write_text(json.dumps(existing))
        with patch("grippy.mcp_config.get_config_path", return_value=config_file):
            assert is_configured(MCPClient.CLAUDE_CODE) is True

    def test_is_configured_false(self, tmp_path: Path) -> None:
        """is_configured returns False when grippy is not in mcpServers."""
        config_file = tmp_path / "config.json"
        existing = {"mcpServers": {"other": {"command": "node"}}}
        config_file.write_text(json.dumps(existing))
        with patch("grippy.mcp_config.get_config_path", return_value=config_file):
            assert is_configured(MCPClient.CLAUDE_CODE) is False

    def test_is_configured_no_file(self, tmp_path: Path) -> None:
        """is_configured returns False when config file doesn't exist."""
        config_file = tmp_path / "nonexistent.json"
        with patch("grippy.mcp_config.get_config_path", return_value=config_file):
            assert is_configured(MCPClient.CLAUDE_CODE) is False

    def test_add_returns_false_on_none_path(self) -> None:
        """add_to_client returns False when config path is None."""
        with patch("grippy.mcp_config.get_config_path", return_value=None):
            result = add_to_client(MCPClient.CLAUDE_CODE, {"command": "uv"})
        assert result is False

    def test_remove_returns_false_on_none_path(self) -> None:
        """remove_from_client returns False when config path is None."""
        with patch("grippy.mcp_config.get_config_path", return_value=None):
            result = remove_from_client(MCPClient.CLAUDE_CODE)
        assert result is False


# ---------------------------------------------------------------------------
# get_available_clients tests
# ---------------------------------------------------------------------------


class TestGetAvailableClients:
    """Tests for get_available_clients."""

    def test_returns_clients_with_existing_config(self, tmp_path: Path) -> None:
        """Returns clients where the config file exists."""
        config_file = tmp_path / ".claude.json"
        config_file.write_text("{}")

        def fake_config_path(client: MCPClient) -> Path | None:
            if client == MCPClient.CLAUDE_CODE:
                return config_file
            return tmp_path / "nonexistent" / "deep" / "config.json"

        with patch("grippy.mcp_config.get_config_path", side_effect=fake_config_path):
            clients = get_available_clients()
        assert MCPClient.CLAUDE_CODE in clients

    def test_returns_clients_with_existing_parent(self, tmp_path: Path) -> None:
        """Returns clients where config parent dir exists even if config doesn't."""
        config_file = tmp_path / "mcp.json"  # parent (tmp_path) exists, file does not

        def fake_config_path(client: MCPClient) -> Path | None:
            if client == MCPClient.CURSOR:
                return config_file
            return tmp_path / "nonexistent" / "deep" / "config.json"

        with patch("grippy.mcp_config.get_config_path", side_effect=fake_config_path):
            clients = get_available_clients()
        assert MCPClient.CURSOR in clients
