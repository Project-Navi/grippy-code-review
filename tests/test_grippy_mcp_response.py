# SPDX-License-Identifier: MIT
"""Tests for MCP response serializers."""

from __future__ import annotations

from typing import Any

from grippy.mcp_response import _serialize_rule_finding, serialize_audit, serialize_scan
from grippy.rules.base import ResultEnrichment, RuleResult, RuleSeverity
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


def _make_review(**overrides: Any) -> GrippyReview:
    """Build a minimal GrippyReview, merging *overrides* on top of defaults."""
    defaults: dict[str, Any] = {
        "version": "1.0",
        "audit_type": "pr_review",
        "timestamp": "2026-03-06T00:00:00Z",
        "model": "test-model-v1",
        "pr": PRMetadata(
            title="fix: patch bug",
            author="dev",
            branch="fix/bug -> main",
            complexity_tier=ComplexityTier.STANDARD,
        ),
        "scope": ReviewScope(
            files_in_diff=3,
            files_reviewed=3,
            coverage_percentage=100.0,
            governance_rules_applied=["G-001"],
            modes_active=["pr_review"],
        ),
        "findings": [
            Finding(
                id="F-001",
                severity=Severity.HIGH,
                confidence=85,
                category=FindingCategory.SECURITY,
                file="src/app.py",
                line_start=42,
                line_end=42,
                title="SQL injection risk",
                description="Unsanitized input reaches query builder.",
                suggestion="Use parameterized queries.",
                evidence="cursor.execute(f'SELECT {user_input}')",
                grippy_note="Grumble... this is bad.",
            ),
        ],
        "escalations": [],
        "score": Score(
            overall=72,
            breakdown=ScoreBreakdown(
                security=60, logic=80, governance=75, reliability=85, observability=90
            ),
            deductions=ScoreDeductions(
                critical_count=0, high_count=1, medium_count=0, low_count=0, total_deduction=28
            ),
        ),
        "verdict": Verdict(
            status=VerdictStatus.PROVISIONAL,
            threshold_applied=70,
            merge_blocking=False,
            summary="Hard hat required in this zone.",
        ),
        "personality": Personality(
            tone_register=ToneRegister.GRUMPY,
            opening_catchphrase="*adjusts hard hat* Let me inspect this building site...",
            closing_line="Grumble out.",
            disguise_used="building inspector",
            ascii_art_key=AsciiArtKey.WARNING,
        ),
        "meta": ReviewMeta(
            review_duration_ms=1500,
            tokens_used=4000,
            context_files_loaded=2,
            confidence_filter_suppressed=0,
            duplicate_filter_suppressed=0,
        ),
    }
    defaults.update(overrides)
    return GrippyReview(**defaults)


# ---------------------------------------------------------------------------
# serialize_audit tests
# ---------------------------------------------------------------------------


class TestSerializeAudit:
    """Tests for serialize_audit."""

    def test_required_keys(self) -> None:
        review = _make_review()
        result = serialize_audit(review, profile="security", diff_stats={"files": 3})
        assert set(result.keys()) == {
            "findings",
            "summary_only_findings",
            "score",
            "verdict",
            "rule_findings",
            "metadata",
        }

    def test_strips_personality(self) -> None:
        review = _make_review()
        result = serialize_audit(review, profile="security", diff_stats={"files": 3})
        result_str = str(result)
        assert "hard hat" not in result_str.lower()
        assert "Grumble" not in result_str
        assert "building inspector" not in result_str

    def test_finding_fields(self) -> None:
        review = _make_review()
        result = serialize_audit(review, profile="security", diff_stats={"files": 3})
        f = result["findings"][0]
        assert f["id"] == "F-001"
        assert f["file"] == "src/app.py"
        assert f["line"] == 42
        assert f["severity"] == "HIGH"
        assert f["category"] == "security"
        assert f["title"] == "SQL injection risk"
        assert f["description"] == "Unsanitized input reaches query builder."
        assert f["confidence"] == 85

    def test_score_shape(self) -> None:
        review = _make_review()
        result = serialize_audit(review, profile="security", diff_stats={"files": 3})
        score = result["score"]
        assert score["overall"] == 72
        assert score["security"] == 60
        assert score["logic"] == 80
        assert score["governance"] == 75
        assert score["reliability"] == 85
        assert score["observability"] == 90

    def test_verdict_shape(self) -> None:
        review = _make_review()
        result = serialize_audit(review, profile="security", diff_stats={"files": 3})
        verdict = result["verdict"]
        assert verdict["status"] == "PROVISIONAL"
        assert verdict["merge_blocking"] is False

    def test_metadata_includes_model_profile_files_reviewed(self) -> None:
        review = _make_review()
        result = serialize_audit(review, profile="security", diff_stats={"files": 3})
        meta = result["metadata"]
        assert meta["model"] == "test-model-v1"
        assert meta["profile"] == "security"
        assert meta["files_reviewed"] == 3
        assert meta["diff_stats"] == {"files": 3}

    def test_rule_findings_included(self) -> None:
        review = _make_review()
        rule_findings = [
            RuleResult(
                rule_id="SEC-001",
                severity=RuleSeverity.ERROR,
                message="Hardcoded secret",
                file="config.py",
                line=10,
                evidence="TOKEN = 'redacted'",
            ),
        ]
        result = serialize_audit(
            review, profile="security", diff_stats={"files": 3}, rule_findings=rule_findings
        )
        assert len(result["rule_findings"]) == 1
        rf = result["rule_findings"][0]
        assert rf["rule_id"] == "SEC-001"
        assert rf["severity"] == "ERROR"
        assert rf["message"] == "Hardcoded secret"
        assert rf["file"] == "config.py"
        assert rf["line"] == 10
        assert rf["evidence"] == "TOKEN = 'redacted'"

    def test_rule_findings_empty_by_default(self) -> None:
        review = _make_review()
        result = serialize_audit(review, profile="general", diff_stats={})
        assert result["rule_findings"] == []

    def test_diff_truncated_flag(self) -> None:
        review = _make_review()
        result = serialize_audit(
            review, profile="security", diff_stats={"files": 3}, diff_truncated=True
        )
        assert result["metadata"]["diff_truncated"] is True

    def test_diff_truncated_default_false(self) -> None:
        review = _make_review()
        result = serialize_audit(review, profile="security", diff_stats={"files": 3})
        assert result["metadata"]["diff_truncated"] is False


# ---------------------------------------------------------------------------
# serialize_scan tests
# ---------------------------------------------------------------------------


class TestSerializeScan:
    """Tests for serialize_scan."""

    def test_required_keys(self) -> None:
        result = serialize_scan([], gate=False, profile="security", diff_stats={"files": 1})
        assert set(result.keys()) == {"findings", "gate", "profile", "diff_stats"}

    def test_gate_failed(self) -> None:
        result = serialize_scan([], gate=True, profile="security", diff_stats={})
        assert result["gate"] == "failed"

    def test_gate_passed(self) -> None:
        result = serialize_scan([], gate=False, profile="security", diff_stats={})
        assert result["gate"] == "passed"

    def test_finding_serialization(self) -> None:
        findings = [
            RuleResult(
                rule_id="SEC-002",
                severity=RuleSeverity.WARN,
                message="Loose permissions",
                file="deploy.yml",
                line=5,
                evidence="permissions: write-all",
            ),
            RuleResult(
                rule_id="SEC-003",
                severity=RuleSeverity.INFO,
                message="No issue",
                file="readme.md",
            ),
        ]
        result = serialize_scan(
            findings, gate=False, profile="strict-security", diff_stats={"files": 2}
        )
        assert len(result["findings"]) == 2

        f0 = result["findings"][0]
        assert f0["rule_id"] == "SEC-002"
        assert f0["severity"] == "WARN"
        assert f0["message"] == "Loose permissions"
        assert f0["file"] == "deploy.yml"
        assert f0["line"] == 5
        assert f0["evidence"] == "permissions: write-all"

        f1 = result["findings"][1]
        assert f1["rule_id"] == "SEC-003"
        assert f1["severity"] == "INFO"
        assert f1["message"] == "No issue"
        assert f1["file"] == "readme.md"
        assert f1["line"] is None
        assert "evidence" not in f1

    def test_profile_passthrough(self) -> None:
        result = serialize_scan([], gate=False, profile="general", diff_stats={})
        assert result["profile"] == "general"

    def test_diff_stats_passthrough(self) -> None:
        stats = {"files": 5, "additions": 100, "deletions": 20}
        result = serialize_scan([], gate=False, profile="security", diff_stats=stats)
        assert result["diff_stats"] == stats


# ---------------------------------------------------------------------------
# _serialize_rule_finding tests
# ---------------------------------------------------------------------------


class TestSerializeRuleFinding:
    """Tests for _serialize_rule_finding edge cases."""

    def test_enrichment_serialized_when_present(self) -> None:
        enrichment = ResultEnrichment(
            blast_radius=5,
            is_recurring=True,
            prior_count=3,
            suppressed=False,
            suppression_reason="",
            velocity="increasing",
        )
        result = _serialize_rule_finding(
            RuleResult(
                rule_id="SEC-010",
                severity=RuleSeverity.WARN,
                message="Test finding",
                file="app.py",
                line=42,
                enrichment=enrichment,
            ),
        )
        assert "enrichment" in result
        e = result["enrichment"]
        assert e["blast_radius"] == 5
        assert e["is_recurring"] is True
        assert e["prior_count"] == 3
        assert e["suppressed"] is False
        assert e["suppression_reason"] == ""
        assert e["velocity"] == "increasing"

    def test_personality_fields_absent_from_audit(self) -> None:
        """Verify every Personality model field is stripped from serialized output."""
        review = _make_review()
        result = serialize_audit(review, profile="security", diff_stats={"files": 3})
        flat = str(result)
        # Every field from schema.Personality must be absent
        for field in (
            "tone_register",
            "opening_catchphrase",
            "closing_line",
            "disguise_used",
            "ascii_art_key",
        ):
            assert field not in flat, f"Personality field '{field}' leaked into serialized output"
