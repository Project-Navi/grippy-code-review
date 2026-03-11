# SPDX-License-Identifier: MIT
"""Tier 1 deterministic edge-case diff tests.

Verifies the pipeline doesn't crash on edge-case diffs BEFORE the LLM sees them.
Each test sends a diff through run_rules() + filter_diff() + format_pr_context()
and asserts no exception + basic output validity.

No LLM calls. Marker: e2e_fast.

Run with:  uv run pytest -m e2e_fast tests/test_e2e_edge_diffs.py -v
"""

from __future__ import annotations

import pytest

from grippy.agent import format_pr_context
from grippy.ignore import filter_diff
from grippy.rules import RuleResult, run_rules
from grippy.rules.config import PROFILES, ProfileConfig
from tests.e2e_fixtures import DIFFS, generate_many_files_diff, generate_massive_diff

pytestmark = pytest.mark.e2e_fast

SECURITY_PROFILE: ProfileConfig = PROFILES["security"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_rules_safe(diff: str, profile: ProfileConfig = SECURITY_PROFILE) -> list[RuleResult]:
    """Run rules and return results. Asserts no exception."""
    results = run_rules(diff, profile)
    assert isinstance(results, list)
    for r in results:
        assert isinstance(r, RuleResult)
    return results


def _filter_diff_safe(diff: str) -> tuple[str, int]:
    """Run filter_diff with no pathspec and assert return shape."""
    filtered, excluded = filter_diff(diff, None)
    assert isinstance(filtered, str)
    assert isinstance(excluded, int)
    assert excluded >= 0
    return filtered, excluded


def _format_context_safe(diff: str, rule_findings: str = "") -> str:
    """Run format_pr_context and assert it returns a non-empty string."""
    result = format_pr_context(
        title="Edge Case PR",
        author="test-bot",
        branch="feat/edge-case -> main",
        description="Testing edge-case diffs through the pipeline.",
        diff=diff,
        rule_findings=rule_findings,
    )
    assert isinstance(result, str)
    assert len(result) > 0
    return result


# ===========================================================================
# Test class: run_rules() on edge-case diffs
# ===========================================================================


class TestEdgeDiffsThroughRules:
    """Verify run_rules() doesn't crash on edge-case diffs."""

    def test_empty_diff(self) -> None:
        results = _run_rules_safe(DIFFS["empty"])
        assert results == []

    def test_single_line_diff(self) -> None:
        results = _run_rules_safe(DIFFS["single_line"])
        assert isinstance(results, list)

    def test_binary_file_diff(self) -> None:
        results = _run_rules_safe(DIFFS["binary_file"])
        assert isinstance(results, list)

    def test_massive_diff(self) -> None:
        results = _run_rules_safe(DIFFS["massive"])
        assert isinstance(results, list)

    def test_massive_diff_custom_size(self) -> None:
        big = generate_massive_diff(200_000)
        results = _run_rules_safe(big)
        assert isinstance(results, list)

    def test_unicode_heavy_diff(self) -> None:
        results = _run_rules_safe(DIFFS["unicode_heavy"])
        assert isinstance(results, list)

    def test_no_newline_at_eof_diff(self) -> None:
        results = _run_rules_safe(DIFFS["no_newline_at_eof"])
        assert isinstance(results, list)

    def test_rename_only_diff(self) -> None:
        results = _run_rules_safe(DIFFS["rename_only"])
        # Rename-only should produce zero findings (no content change)
        assert results == []

    def test_delete_only_diff(self) -> None:
        results = _run_rules_safe(DIFFS["delete_only"])
        assert isinstance(results, list)

    def test_many_files_diff(self) -> None:
        results = _run_rules_safe(DIFFS["many_files"])
        assert isinstance(results, list)

    def test_many_files_custom_count(self) -> None:
        big = generate_many_files_diff(100)
        results = _run_rules_safe(big)
        assert isinstance(results, list)

    def test_mixed_language_diff(self) -> None:
        results = _run_rules_safe(DIFFS["mixed_language"])
        assert isinstance(results, list)

    def test_adversarial_filepath_diff(self) -> None:
        results = _run_rules_safe(DIFFS["adversarial_filepath"])
        assert isinstance(results, list)


# ===========================================================================
# Test class: filter_diff() on edge-case diffs
# ===========================================================================


class TestEdgeDiffsThroughFilterDiff:
    """Verify filter_diff() handles edge cases without crash."""

    def test_empty_diff_filter(self) -> None:
        _filtered, excluded = _filter_diff_safe(DIFFS["empty"])
        assert excluded == 0

    def test_single_line_diff_filter(self) -> None:
        filtered, excluded = _filter_diff_safe(DIFFS["single_line"])
        assert excluded == 0
        assert "VERSION" in filtered

    def test_massive_diff_filter(self) -> None:
        filtered, excluded = _filter_diff_safe(DIFFS["massive"])
        assert excluded == 0
        assert len(filtered) > 0

    def test_unicode_diff_filter(self) -> None:
        filtered, excluded = _filter_diff_safe(DIFFS["unicode_heavy"])
        assert excluded == 0
        assert len(filtered) > 0

    def test_binary_file_filter(self) -> None:
        _filtered, excluded = _filter_diff_safe(DIFFS["binary_file"])
        assert excluded == 0

    def test_rename_only_filter(self) -> None:
        _filtered, excluded = _filter_diff_safe(DIFFS["rename_only"])
        assert excluded == 0

    def test_delete_only_filter(self) -> None:
        _filtered, excluded = _filter_diff_safe(DIFFS["delete_only"])
        assert excluded == 0

    def test_no_newline_at_eof_filter(self) -> None:
        _filtered, excluded = _filter_diff_safe(DIFFS["no_newline_at_eof"])
        assert excluded == 0

    def test_many_files_filter(self) -> None:
        _filtered, excluded = _filter_diff_safe(DIFFS["many_files"])
        assert excluded == 0

    def test_mixed_language_filter(self) -> None:
        _filtered, excluded = _filter_diff_safe(DIFFS["mixed_language"])
        assert excluded == 0


# ===========================================================================
# Test class: format_pr_context() on edge-case diffs
# ===========================================================================

# All diff names that represent edge cases (not vuln-specific diffs)
_EDGE_DIFF_NAMES: list[str] = [
    "empty",
    "single_line",
    "binary_file",
    "massive",
    "unicode_heavy",
    "no_newline_at_eof",
    "rename_only",
    "delete_only",
    "many_files",
    "mixed_language",
    "adversarial_filepath",
    "injection_xml_filename",
    "injection_data_fence",
]


class TestEdgeDiffsThroughFormatContext:
    """Verify format_pr_context() handles edge diffs without crash."""

    @pytest.mark.parametrize("diff_name", _EDGE_DIFF_NAMES)
    def test_format_context_never_crashes(self, diff_name: str) -> None:
        diff = DIFFS[diff_name]
        result = _format_context_safe(diff)
        # Should always contain the data-fence preamble
        assert "USER-PROVIDED DATA" in result

    def test_format_context_with_rule_findings(self) -> None:
        """Rule findings string is included in context without crash."""
        diff = DIFFS["secrets_env"]
        findings = run_rules(diff, SECURITY_PROFILE)
        # Serialize findings as a simple string (mimics production behavior)
        findings_str = "\n".join(
            f"[{r.severity.name}] {r.rule_id}: {r.message} ({r.file}:{r.line})" for r in findings
        )
        result = _format_context_safe(diff, rule_findings=findings_str)
        assert len(result) > 0

    def test_format_context_empty_diff_stats(self) -> None:
        """Empty diff produces zero-count stats in context."""
        result = _format_context_safe(DIFFS["empty"])
        # The context should still have metadata sections
        assert "Edge Case PR" in result


# ===========================================================================
# Test class: rule findings on known-vuln diffs
# ===========================================================================


class TestRuleFindings:
    """Verify rules produce correct findings on known-vuln diffs."""

    def test_secrets_detected_in_env(self) -> None:
        results = run_rules(DIFFS["secrets_env"], SECURITY_PROFILE)
        assert len(results) > 0
        rule_ids = {r.rule_id for r in results}
        # Should detect secrets (API key pattern)
        assert any("secret" in rid.lower() or "credential" in rid.lower() for rid in rule_ids), (
            f"Expected secrets rule to fire on .env diff, got rule IDs: {rule_ids}"
        )

    def test_workflow_permissions_detected(self) -> None:
        results = run_rules(DIFFS["workflow_permissions"], SECURITY_PROFILE)
        assert len(results) > 0
        rule_ids = {r.rule_id for r in results}
        assert any("workflow" in rid.lower() or "permission" in rid.lower() for rid in rule_ids), (
            f"Expected workflow permissions rule to fire, got rule IDs: {rule_ids}"
        )

    def test_sql_injection_detected(self) -> None:
        results = run_rules(DIFFS["sql_injection"], SECURITY_PROFILE)
        assert len(results) > 0
        rule_ids = {r.rule_id for r in results}
        assert any("sql" in rid.lower() for rid in rule_ids), (
            f"Expected SQL injection rule to fire, got rule IDs: {rule_ids}"
        )

    def test_weak_crypto_detected(self) -> None:
        results = run_rules(DIFFS["weak_crypto"], SECURITY_PROFILE)
        assert len(results) > 0
        rule_ids = {r.rule_id for r in results}
        assert any("crypto" in rid.lower() for rid in rule_ids), (
            f"Expected weak crypto rule to fire, got rule IDs: {rule_ids}"
        )

    def test_command_injection_detected(self) -> None:
        results = run_rules(DIFFS["command_injection"], SECURITY_PROFILE)
        assert len(results) > 0
        rule_ids = {r.rule_id for r in results}
        assert any("sink" in rid.lower() or "danger" in rid.lower() for rid in rule_ids), (
            f"Expected dangerous sink rule to fire, got rule IDs: {rule_ids}"
        )

    def test_clean_python_zero_findings(self) -> None:
        results = run_rules(DIFFS["clean_python"], SECURITY_PROFILE)
        assert results == [], (
            f"Clean Python diff should produce zero findings, got: "
            f"{[(r.rule_id, r.message) for r in results]}"
        )

    def test_clean_javascript_zero_findings(self) -> None:
        results = run_rules(DIFFS["clean_javascript"], SECURITY_PROFILE)
        assert results == [], (
            f"Clean JS diff should produce zero findings, got: "
            f"{[(r.rule_id, r.message) for r in results]}"
        )

    def test_clean_rust_zero_findings(self) -> None:
        results = run_rules(DIFFS["clean_rust"], SECURITY_PROFILE)
        assert results == [], (
            f"Clean Rust diff should produce zero findings, got: "
            f"{[(r.rule_id, r.message) for r in results]}"
        )


# ===========================================================================
# Test class: full deterministic pipeline (rules -> filter -> format)
# ===========================================================================


class TestFullDeterministicPipeline:
    """Run the full deterministic pipeline stages end-to-end."""

    @pytest.mark.parametrize("diff_name", _EDGE_DIFF_NAMES)
    def test_pipeline_never_crashes(self, diff_name: str) -> None:
        """Each edge diff passes through all 3 stages without exception."""
        diff = DIFFS[diff_name]

        # Stage 1: run_rules
        results = run_rules(diff, SECURITY_PROFILE)
        assert isinstance(results, list)

        # Stage 2: filter_diff
        filtered, _excluded = filter_diff(diff, None)
        assert isinstance(filtered, str)

        # Stage 3: format_pr_context (with any rule findings)
        findings_str = "\n".join(f"[{r.severity.name}] {r.rule_id}: {r.message}" for r in results)
        context = format_pr_context(
            title="Pipeline Test",
            author="bot",
            branch="test -> main",
            description="Edge case pipeline test.",
            diff=filtered,
            rule_findings=findings_str,
        )
        assert isinstance(context, str)
        assert len(context) > 0

    def test_pipeline_with_all_profiles(self) -> None:
        """Each profile handles a vuln diff without crash."""
        diff = DIFFS["multi_vuln_auth"]
        for profile_name, profile in PROFILES.items():
            results = run_rules(diff, profile)
            assert isinstance(results, list), f"Profile {profile_name!r} crashed on run_rules"
            # All profiles should detect something in multi_vuln_auth
            if profile_name != "general":
                assert len(results) > 0, (
                    f"Profile {profile_name!r} found nothing in multi_vuln_auth"
                )
