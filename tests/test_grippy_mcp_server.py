# SPDX-License-Identifier: MIT
"""Tests for Grippy MCP server tools."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from grippy.mcp_server import _run_audit, _run_scan, audit_diff, main, scan_diff
from grippy.retry import ReviewParseError
from grippy.schema import (
    AsciiArtKey,
    ComplexityTier,
    Finding,
    FindingCategory,
    GrippyReview,
    Personality,
    PRMetadata,
    ReviewMeta,
    ReviewScope,
    Score,
    ScoreBreakdown,
    ScoreDeductions,
    Severity,
    ToneRegister,
    Verdict,
    VerdictStatus,
)

_SIMPLE_DIFF = (
    "diff --git a/foo.py b/foo.py\n"
    "index 0000000..1111111 100644\n"
    "--- a/foo.py\n"
    "+++ b/foo.py\n"
    "@@ -0,0 +1,1 @@\n"
    "+print('hello')\n"
)

_SECRET_DIFF = (
    "diff --git a/config.py b/config.py\n"
    "index 0000000..1111111 100644\n"
    "--- a/config.py\n"
    "+++ b/config.py\n"
    "@@ -0,0 +1,1 @@\n"
    "+AWS_KEY = 'AKIAIOSFODNN7ABCDEFG'\n"
)


def _make_review(**overrides: Any) -> GrippyReview:
    """Build a minimal GrippyReview for testing."""
    defaults: dict[str, Any] = {
        "version": "1.0",
        "audit_type": "pr_review",
        "timestamp": "2026-03-06T00:00:00Z",
        "model": "test-model",
        "pr": PRMetadata(
            title="test",
            author="dev",
            branch="test -> main",
            complexity_tier=ComplexityTier.STANDARD,
        ),
        "scope": ReviewScope(
            files_in_diff=1,
            files_reviewed=1,
            coverage_percentage=100.0,
            governance_rules_applied=[],
            modes_active=["pr_review"],
        ),
        "findings": [
            Finding(
                id="F-001",
                severity=Severity.LOW,
                confidence=80,
                category=FindingCategory.LOGIC,
                file="foo.py",
                line_start=1,
                line_end=1,
                title="Test finding",
                description="Test desc",
                suggestion="Fix it",
                evidence="print('hello')",
                grippy_note="Grumble",
            ),
        ],
        "escalations": [],
        "score": Score(
            overall=90,
            breakdown=ScoreBreakdown(
                security=90, logic=90, governance=90, reliability=90, observability=90
            ),
            deductions=ScoreDeductions(
                critical_count=0, high_count=0, medium_count=0, low_count=1, total_deduction=10
            ),
        ),
        "verdict": Verdict(
            status=VerdictStatus.PASS,
            threshold_applied=70,
            merge_blocking=False,
            summary="Looks fine.",
        ),
        "personality": Personality(
            tone_register=ToneRegister.GRUMPY,
            opening_catchphrase="Grumble...",
            closing_line="Out.",
            disguise_used="inspector",
            ascii_art_key=AsciiArtKey.ALL_CLEAR,
        ),
        "meta": ReviewMeta(
            review_duration_ms=500,
            tokens_used=1000,
            context_files_loaded=0,
            confidence_filter_suppressed=0,
            duplicate_filter_suppressed=0,
        ),
    }
    defaults.update(overrides)
    return GrippyReview(**defaults)


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
        with patch("grippy.mcp_server.get_local_diff", return_value=_SECRET_DIFF):
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

    def test_audit_invalid_profile(self) -> None:
        """Invalid profile returns a JSON error."""
        result = json.loads(_run_audit(scope="staged", profile="nonexistent"))
        assert "error" in result

    def test_audit_default_scope(self) -> None:
        """Default scope is 'staged'."""
        with patch("grippy.mcp_server.get_local_diff", return_value="") as mock_diff:
            _run_audit()
            mock_diff.assert_called_once_with("staged")

    def test_audit_happy_path(self) -> None:
        """Full audit path with mocked agent returns serialized review."""
        review = _make_review()
        mock_agent = MagicMock()
        with (
            patch("grippy.mcp_server.get_local_diff", return_value=_SIMPLE_DIFF),
            patch("grippy.agent.create_reviewer", return_value=mock_agent),
            patch("grippy.retry.run_review", return_value=review),
        ):
            result = json.loads(_run_audit(scope="staged", profile="general"))
        assert "findings" in result
        assert "score" in result
        assert "verdict" in result
        assert result["score"]["overall"] == 90

    def test_audit_security_profile_runs_rules(self) -> None:
        """Security profile triggers rule engine and mode=security_audit."""
        review = _make_review()
        mock_agent = MagicMock()
        with (
            patch("grippy.mcp_server.get_local_diff", return_value=_SIMPLE_DIFF),
            patch("grippy.agent.create_reviewer", return_value=mock_agent) as mock_create,
            patch("grippy.retry.run_review", return_value=review),
        ):
            result = json.loads(_run_audit(scope="staged", profile="security"))
        assert "findings" in result
        # Verify security mode was used
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs.get("mode") == "security_audit"

    def test_audit_create_reviewer_value_error(self) -> None:
        """ValueError from create_reviewer returns config error."""
        with (
            patch("grippy.mcp_server.get_local_diff", return_value=_SIMPLE_DIFF),
            patch("grippy.agent.create_reviewer", side_effect=ValueError("bad config")),
        ):
            result = json.loads(_run_audit(scope="staged", profile="general"))
        assert "error" in result
        assert "Config error" in result["error"]

    def test_audit_create_reviewer_generic_error(self) -> None:
        """Generic exception from create_reviewer returns safe error."""
        with (
            patch("grippy.mcp_server.get_local_diff", return_value=_SIMPLE_DIFF),
            patch("grippy.agent.create_reviewer", side_effect=RuntimeError("boom")),
        ):
            result = json.loads(_run_audit(scope="staged", profile="general"))
        assert "error" in result
        assert "Failed to initialize" in result["error"]

    def test_audit_review_parse_error(self) -> None:
        """ReviewParseError returns error with attempt count."""
        mock_agent = MagicMock()
        with (
            patch("grippy.mcp_server.get_local_diff", return_value=_SIMPLE_DIFF),
            patch("grippy.agent.create_reviewer", return_value=mock_agent),
            patch(
                "grippy.retry.run_review",
                side_effect=ReviewParseError(attempts=3, last_raw="", errors=["failed"]),
            ),
        ):
            result = json.loads(_run_audit(scope="staged", profile="general"))
        assert "error" in result
        assert "3 attempts" in result["error"]

    def test_audit_generic_review_error(self) -> None:
        """Generic exception from run_review returns safe error."""
        mock_agent = MagicMock()
        with (
            patch("grippy.mcp_server.get_local_diff", return_value=_SIMPLE_DIFF),
            patch("grippy.agent.create_reviewer", return_value=mock_agent),
            patch("grippy.retry.run_review", side_effect=ConnectionError("timeout")),
        ):
            result = json.loads(_run_audit(scope="staged", profile="general"))
        assert "error" in result
        assert "ConnectionError" in result["error"]


# ---------------------------------------------------------------------------
# MCP tool wrapper tests
# ---------------------------------------------------------------------------


class TestToolAnnotations:
    """Tests that MCP tool annotations are correctly set."""

    def test_scan_diff_read_only_hint(self) -> None:
        """scan_diff is annotated as readOnly (no file writes)."""
        from grippy.mcp_server import mcp

        tool = mcp._tool_manager._tools["scan_diff"]
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True

    def test_scan_diff_not_destructive(self) -> None:
        """scan_diff is annotated as non-destructive."""
        from grippy.mcp_server import mcp

        tool = mcp._tool_manager._tools["scan_diff"]
        assert tool.annotations is not None
        assert tool.annotations.destructiveHint is False

    def test_audit_diff_read_only_hint(self) -> None:
        """audit_diff is annotated as readOnly (no file writes)."""
        from grippy.mcp_server import mcp

        tool = mcp._tool_manager._tools["audit_diff"]
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True

    def test_audit_diff_not_destructive(self) -> None:
        """audit_diff is annotated as non-destructive."""
        from grippy.mcp_server import mcp

        tool = mcp._tool_manager._tools["audit_diff"]
        assert tool.annotations is not None
        assert tool.annotations.destructiveHint is False


class TestToolWrappers:
    """Tests for the @mcp.tool() decorated wrappers."""

    def test_scan_diff_delegates(self) -> None:
        """scan_diff delegates to _run_scan."""
        with patch("grippy.mcp_server.get_local_diff", return_value=""):
            result = json.loads(scan_diff(scope="staged", profile="security"))
        assert result["gate"] == "passed"

    def test_audit_diff_delegates(self) -> None:
        """audit_diff delegates to _run_audit."""
        with patch("grippy.mcp_server.get_local_diff", return_value=""):
            result = json.loads(audit_diff(scope="staged", profile="general"))
        assert "error" in result


# ---------------------------------------------------------------------------
# main() test
# ---------------------------------------------------------------------------


class TestMain:
    """Tests for the main() entry point."""

    def test_main_calls_mcp_run(self) -> None:
        """main() calls mcp.run(transport='stdio')."""
        with patch("grippy.mcp_server.mcp") as mock_mcp:
            main()
            mock_mcp.run.assert_called_once_with(transport="stdio")


# ---------------------------------------------------------------------------
# .grippyignore integration tests
# ---------------------------------------------------------------------------


class TestGrippyignoreIntegration:
    """Tests for .grippyignore integration in MCP tools."""

    def test_scan_filters_ignored_files(self, monkeypatch: Any, tmp_path: Any) -> None:
        """Files matching .grippyignore should not produce findings."""
        (tmp_path / ".grippyignore").write_text("tests/\n")

        diff = (
            "diff --git a/tests/test_rule.py b/tests/test_rule.py\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/tests/test_rule.py\n"
            "@@ -0,0 +1,1 @@\n"
            '+PASSWORD = "hunter2"\n'  # pragma: allowlist secret
        )
        monkeypatch.setattr("grippy.mcp_server.get_local_diff", lambda _: diff)
        monkeypatch.setattr("grippy.mcp_server.get_repo_root", lambda: tmp_path)

        result = json.loads(_run_scan(scope="staged", profile="security"))
        assert result["findings"] == []

    def test_scan_stats_reflect_filtered_diff(self, monkeypatch: Any, tmp_path: Any) -> None:
        """diff_stats must be computed from the filtered diff, not the raw diff."""
        (tmp_path / ".grippyignore").write_text("tests/\n")

        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/src/app.py\n"
            "@@ -0,0 +1,1 @@\n"
            "+x = 1\n"
            "diff --git a/tests/test_rule.py b/tests/test_rule.py\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/tests/test_rule.py\n"
            "@@ -0,0 +1,1 @@\n"
            '+PASSWORD = "hunter2"\n'  # pragma: allowlist secret
        )
        monkeypatch.setattr("grippy.mcp_server.get_local_diff", lambda _: diff)
        monkeypatch.setattr("grippy.mcp_server.get_repo_root", lambda: tmp_path)

        result = json.loads(_run_scan(scope="staged", profile="security"))
        # Stats should show 1 file (src/app.py), not 2
        assert result["diff_stats"]["files"] == 1

    def test_audit_all_excluded_returns_error(self, monkeypatch: Any, tmp_path: Any) -> None:
        """All files excluded should return an error, not proceed to LLM."""
        (tmp_path / ".grippyignore").write_text("*\n")

        diff = (
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1 +1 @@\n"
            "+x = 1\n"
        )
        monkeypatch.setattr("grippy.mcp_server.get_local_diff", lambda _: diff)
        monkeypatch.setattr("grippy.mcp_server.get_repo_root", lambda: tmp_path)

        result = json.loads(_run_audit(scope="staged", profile="security"))
        assert "error" in result
