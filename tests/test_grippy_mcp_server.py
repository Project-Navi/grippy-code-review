# SPDX-License-Identifier: MIT
"""Tests for Grippy MCP server tools."""

from __future__ import annotations

import json
from unittest.mock import patch

from grippy.mcp_server import _run_audit, _run_scan

# ---------------------------------------------------------------------------
# _run_scan tests
# ---------------------------------------------------------------------------


class TestRunScan:
    """Tests for the _run_scan helper."""

    def test_scan_empty_diff(self) -> None:
        """Empty diff yields no findings and gate=passed."""
        with patch("grippy.mcp_server.get_local_diff", return_value=""):
            result = json.loads(_run_scan(scope="staged", profile="security"))
        assert result["findings"] == []
        assert result["gate"] == "passed"

    def test_scan_with_findings(self) -> None:
        """Diff containing a hardcoded AWS secret triggers findings."""
        secret_diff = (
            "diff --git a/config.py b/config.py\n"
            "index 0000000..1111111 100644\n"
            "--- a/config.py\n"
            "+++ b/config.py\n"
            "@@ -0,0 +1,1 @@\n"
            "+AWS_KEY = 'AKIAIOSFODNN7ABCDEFG'\n"
        )
        with patch("grippy.mcp_server.get_local_diff", return_value=secret_diff):
            result = json.loads(_run_scan(scope="staged", profile="security"))
        assert len(result["findings"]) > 0

    def test_scan_invalid_scope(self) -> None:
        """Invalid scope string returns a JSON error."""
        result = json.loads(_run_scan(scope="invalid", profile="security"))
        assert "error" in result

    def test_scan_invalid_profile(self) -> None:
        """Unknown profile name returns a JSON error."""
        result = json.loads(_run_scan(scope="staged", profile="nonexistent"))
        assert "error" in result

    def test_scan_default_scope(self) -> None:
        """Default scope is 'staged'."""
        with patch("grippy.mcp_server.get_local_diff", return_value="") as mock_diff:
            _run_scan()
            mock_diff.assert_called_once_with("staged")


# ---------------------------------------------------------------------------
# _run_audit tests
# ---------------------------------------------------------------------------


class TestRunAudit:
    """Tests for the _run_audit helper."""

    def test_audit_empty_diff(self) -> None:
        """Empty diff returns an error about nothing to review."""
        with patch("grippy.mcp_server.get_local_diff", return_value=""):
            result = json.loads(_run_audit(scope="staged", profile="general"))
        assert "error" in result
        assert "empty" in result["error"].lower()

    def test_audit_invalid_scope(self) -> None:
        """Invalid scope string returns a JSON error."""
        result = json.loads(_run_audit(scope="bad!", profile="general"))
        assert "error" in result

    def test_audit_default_scope(self) -> None:
        """Default scope is 'staged'."""
        with patch("grippy.mcp_server.get_local_diff", return_value="") as mock_diff:
            _run_audit()
            mock_diff.assert_called_once_with("staged")
