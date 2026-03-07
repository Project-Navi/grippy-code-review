# SPDX-License-Identifier: MIT
"""Tests for CLI subcommands: serve, install-mcp, and legacy CI routing."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from grippy.__main__ import _ci_review, _install_mcp, _serve

# ---------------------------------------------------------------------------
# _serve tests (in-process)
# ---------------------------------------------------------------------------


class TestServeInProcess:
    """Tests for the _serve function."""

    def test_serve_calls_main(self) -> None:
        """_serve([]) delegates to mcp_server.main."""
        with patch("grippy.mcp_server.main") as mock_main:
            _serve([])
            mock_main.assert_called_once()

    def test_serve_help_exits_zero(self) -> None:
        """_serve(["--help"]) exits 0."""
        with pytest.raises(SystemExit) as exc_info:
            _serve(["--help"])
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# _install_mcp tests (in-process)
# ---------------------------------------------------------------------------


class TestInstallMcpInProcess:
    """Tests for the _install_mcp function."""

    def test_install_openai_noninteractive(self, tmp_path: Path) -> None:
        """Non-interactive openai install writes config correctly."""
        config_file = tmp_path / ".claude.json"
        config_file.write_text("{}")
        with patch("grippy.mcp_config.get_config_path", return_value=config_file):
            _install_mcp(
                [
                    "--transport",
                    "openai",
                    "--api-key",
                    "test-key-not-real",
                    "--clients",
                    "claude-code",
                    "--profile",
                    "security",
                ]
            )
        data = json.loads(config_file.read_text())
        assert "grippy" in data["mcpServers"]
        entry = data["mcpServers"]["grippy"]
        assert entry["env"]["GRIPPY_TRANSPORT"] == "openai"
        assert entry["env"]["GRIPPY_PROFILE"] == "security"

    def test_install_local_noninteractive(self, tmp_path: Path) -> None:
        """Non-interactive local install writes config correctly."""
        config_file = tmp_path / ".claude.json"
        config_file.write_text("{}")
        with patch("grippy.mcp_config.get_config_path", return_value=config_file):
            _install_mcp(
                [
                    "--transport",
                    "local",
                    "--base-url",
                    "http://localhost:1234/v1",
                    "--model-id",
                    "test-model",
                    "--clients",
                    "claude-code",
                    "--profile",
                    "general",
                ]
            )
        data = json.loads(config_file.read_text())
        entry = data["mcpServers"]["grippy"]
        assert entry["env"]["GRIPPY_TRANSPORT"] == "local"
        assert entry["env"]["GRIPPY_BASE_URL"] == "http://localhost:1234/v1"
        assert entry["env"]["GRIPPY_MODEL_ID"] == "test-model"

    def test_install_local_empty_optional_fields(self, tmp_path: Path) -> None:
        """Empty base-url and model-id are omitted from env."""
        config_file = tmp_path / ".claude.json"
        config_file.write_text("{}")
        with (
            patch("grippy.mcp_config.get_config_path", return_value=config_file),
            patch("builtins.input", return_value=""),
        ):
            _install_mcp(
                [
                    "--transport",
                    "local",
                    "--clients",
                    "claude-code",
                ]
            )
        data = json.loads(config_file.read_text())
        env = data["mcpServers"]["grippy"]["env"]
        assert "GRIPPY_BASE_URL" not in env
        assert "GRIPPY_MODEL_ID" not in env

    def test_install_unknown_client_exits(self) -> None:
        """Unknown client name in --clients exits with code 1."""
        with pytest.raises(SystemExit) as exc_info:
            _install_mcp(
                [
                    "--transport",
                    "openai",
                    "--api-key",
                    "fake",
                    "--clients",
                    "nonexistent",
                ]
            )
        assert exc_info.value.code == 1

    def test_install_interactive_transport(self, tmp_path: Path) -> None:
        """Interactive transport selection (choice=1 → openai)."""
        config_file = tmp_path / ".claude.json"
        config_file.write_text("{}")
        with (
            patch("grippy.mcp_config.get_config_path", return_value=config_file),
            patch("builtins.input", return_value="1"),
            patch("getpass.getpass", return_value="test-key"),
        ):
            _install_mcp(["--clients", "claude-code"])
        data = json.loads(config_file.read_text())
        assert data["mcpServers"]["grippy"]["env"]["GRIPPY_TRANSPORT"] == "openai"

    def test_install_interactive_local_transport(self, tmp_path: Path) -> None:
        """Interactive transport selection (choice=6 → local)."""
        config_file = tmp_path / ".claude.json"
        config_file.write_text("{}")
        with (
            patch("grippy.mcp_config.get_config_path", return_value=config_file),
            patch("builtins.input", side_effect=["6", "http://test:8080/v1", "my-model"]),
        ):
            _install_mcp(["--clients", "claude-code"])
        data = json.loads(config_file.read_text())
        env = data["mcpServers"]["grippy"]["env"]
        assert env["GRIPPY_TRANSPORT"] == "local"
        assert env["GRIPPY_BASE_URL"] == "http://test:8080/v1"
        assert env["GRIPPY_MODEL_ID"] == "my-model"

    def test_install_interactive_client_selection(self, tmp_path: Path) -> None:
        """Interactive client selection with numbered choice."""
        from grippy.mcp_config import MCPClient

        config_file = tmp_path / ".claude.json"
        config_file.write_text("{}")
        with (
            patch("grippy.mcp_config.get_config_path", return_value=config_file),
            patch(
                "grippy.mcp_config.get_available_clients",
                return_value=[MCPClient.CLAUDE_CODE],
            ),
            patch("builtins.input", side_effect=["1"]),
        ):
            _install_mcp(["--transport", "openai", "--api-key", "fake"])
        data = json.loads(config_file.read_text())
        assert "grippy" in data["mcpServers"]

    def test_install_interactive_client_all(self, tmp_path: Path) -> None:
        """Interactive client selection with 'all'."""
        from grippy.mcp_config import MCPClient

        config_file = tmp_path / ".claude.json"
        config_file.write_text("{}")
        with (
            patch("grippy.mcp_config.get_config_path", return_value=config_file),
            patch(
                "grippy.mcp_config.get_available_clients",
                return_value=[MCPClient.CLAUDE_CODE],
            ),
            patch("builtins.input", side_effect=["all"]),
        ):
            _install_mcp(["--transport", "openai", "--api-key", "fake"])
        data = json.loads(config_file.read_text())
        assert "grippy" in data["mcpServers"]

    def test_install_no_available_clients_exits(self) -> None:
        """Exits with code 1 when no clients detected."""
        with (
            patch("grippy.mcp_config.get_available_clients", return_value=[]),
            pytest.raises(SystemExit) as exc_info,
        ):
            _install_mcp(["--transport", "openai", "--api-key", "fake"])
        assert exc_info.value.code == 1

    def test_install_add_failure_prints_fail(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Prints [FAIL] when add_to_client returns False."""
        with (
            patch("grippy.mcp_config.get_config_path", return_value=None),
        ):
            _install_mcp(
                [
                    "--transport",
                    "openai",
                    "--api-key",
                    "fake",
                    "--clients",
                    "claude-code",
                ]
            )
        captured = capsys.readouterr()
        assert "[FAIL]" in captured.out

    def test_install_help_exits_zero(self) -> None:
        """--help exits 0."""
        with pytest.raises(SystemExit) as exc_info:
            _install_mcp(["--help"])
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# _ci_review tests (in-process)
# ---------------------------------------------------------------------------


class TestCiReviewInProcess:
    """Tests for the _ci_review function."""

    def test_ci_review_calls_main(self) -> None:
        """_ci_review([]) calls review.main(profile=None)."""
        with patch("grippy.review.main") as mock_main:
            _ci_review([])
            mock_main.assert_called_once_with(profile=None)

    def test_ci_review_with_profile(self) -> None:
        """_ci_review(["--profile", "security"]) passes profile through."""
        with patch("grippy.review.main") as mock_main:
            _ci_review(["--profile", "security"])
            mock_main.assert_called_once_with(profile="security")

    def test_ci_review_help_exits_zero(self) -> None:
        """--help exits 0."""
        with pytest.raises(SystemExit) as exc_info:
            _ci_review(["--help"])
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Subprocess integration tests (kept for real end-to-end coverage)
# ---------------------------------------------------------------------------


class TestServeSubcommand:
    """Tests for the 'serve' subcommand via subprocess."""

    def test_serve_help(self) -> None:
        """serve --help exits 0 and mentions MCP or serve."""
        result = subprocess.run(
            [sys.executable, "-m", "grippy", "serve", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        output = result.stdout.lower()
        assert "mcp" in output or "serve" in output


class TestInstallMcpSubcommand:
    """Tests for the 'install-mcp' subcommand via subprocess."""

    def test_install_mcp_help(self) -> None:
        """install-mcp --help exits 0 and mentions transport or mcp."""
        result = subprocess.run(
            [sys.executable, "-m", "grippy", "install-mcp", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        output = result.stdout.lower()
        assert "transport" in output or "mcp" in output


class TestLegacyCIEntryPoint:
    """Tests for the legacy CI entry point (no subcommand)."""

    def test_no_subcommand_requires_github_env(self) -> None:
        """Running without subcommand fails when GITHUB_TOKEN/EVENT_PATH are absent."""
        env = {k: v for k, v in os.environ.items() if k == "PATH"}
        env["HOME"] = os.environ.get("HOME", "")
        result = subprocess.run(
            [sys.executable, "-m", "grippy"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        assert result.returncode != 0
