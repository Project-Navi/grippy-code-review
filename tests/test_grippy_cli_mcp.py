# SPDX-License-Identifier: MIT
"""Tests for CLI subcommands: serve, install-mcp."""

from __future__ import annotations

import os
import subprocess
import sys


class TestServeSubcommand:
    """Tests for the 'serve' subcommand."""

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
    """Tests for the 'install-mcp' subcommand."""

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
        # Build a minimal env that strips CI-specific variables
        env = {k: v for k, v in os.environ.items() if k == "PATH"}
        # Ensure uv/python can be found
        env["HOME"] = os.environ.get("HOME", "")

        result = subprocess.run(
            [sys.executable, "-m", "grippy"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        assert result.returncode != 0
