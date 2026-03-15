# SPDX-License-Identifier: MIT
"""Tests for Grippy output policy — 34 tests covering all P0 invariants."""

from __future__ import annotations

from unittest.mock import patch

from grippy.output_policy import (
    _below_confidence_threshold,
    _derive_verdict,
    _get_added_lines_by_file,
    _is_narration,
    _recompute_score,
    filter_review,
)
from grippy.schema import (
    Finding,
    GrippyReview,
    Personality,
    PRMetadata,
    ReviewMeta,
    ReviewScope,
    Score,
    ScoreBreakdown,
    ScoreDeductions,
    Verdict,
    VerdictStatus,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _f(**kw: object) -> Finding:
    """Build a Finding with sensible defaults, overridable by keyword."""
    defaults: dict = {
        "id": "F-001",
        "severity": "HIGH",
        "confidence": 85,
        "category": "security",
        "file": "src/main.py",
        "line_start": 10,
        "line_end": 15,
        "title": "SQL injection risk",
        "description": "User input interpolated into query.",
        "suggestion": "Use parameterized queries.",
        "evidence": 'f"SELECT * FROM {user_input}"',
        "grippy_note": "Fix this.",
    }
    defaults.update(kw)
    return Finding(**defaults)


def _review(findings: list[Finding] | None = None, **kw: object) -> GrippyReview:
    """Build a GrippyReview with sensible defaults."""
    defaults: dict = {
        "audit_type": "pr_review",
        "timestamp": "2026-03-15T12:00:00Z",
        "model": "test-model",
        "pr": PRMetadata(
            title="test", author="dev", branch="feat > main", complexity_tier="STANDARD"
        ),
        "scope": ReviewScope(
            files_in_diff=3,
            files_reviewed=3,
            coverage_percentage=100.0,
            governance_rules_applied=[],
            modes_active=["pr_review"],
        ),
        "findings": findings if findings is not None else [],
        "escalations": [],
        "score": Score(
            overall=95,
            breakdown=ScoreBreakdown(
                security=100, logic=90, governance=95, reliability=90, observability=100
            ),
            deductions=ScoreDeductions(
                critical_count=0, high_count=0, medium_count=0, low_count=0, total_deduction=5
            ),
        ),
        "verdict": Verdict(
            status="PASS", threshold_applied=70, merge_blocking=False, summary="Clean."
        ),
        "personality": Personality(
            tone_register="grudging_respect",
            opening_catchphrase="Not bad.",
            closing_line="Carry on.",
            ascii_art_key="all_clear",
        ),
        "meta": ReviewMeta(
            review_duration_ms=30000,
            tokens_used=5000,
            context_files_loaded=3,
            confidence_filter_suppressed=0,
            duplicate_filter_suppressed=0,
        ),
    }
    defaults.update(kw)
    return GrippyReview(**defaults)


_DIFF_WITH_MAIN = """\
diff --git a/src/main.py b/src/main.py
index abc..def 100644
--- a/src/main.py
+++ b/src/main.py
@@ -10,3 +10,5 @@ def handle_request():
     user_input = request.args.get("q")
-    old_code()
+    query = f"SELECT * FROM {user_input}"
+    result = db.execute(query)
+    return result
"""


# ---------------------------------------------------------------------------
# 0a. Narration tests (1-3)
# ---------------------------------------------------------------------------


class TestNarrationSuppression:
    def test_no_action_needed_suppressed(self) -> None:
        """1. Finding with 'no action needed' in description -> suppressed."""
        f = _f(description="The code is fine. No action needed.", suggestion="Keep as-is.")
        assert _is_narration(f) is True

    def test_empty_suggestion_suppressed(self) -> None:
        """2. Finding with empty suggestion -> suppressed."""
        f = _f(suggestion="   ")
        assert _is_narration(f) is True

    def test_actionable_finding_not_suppressed(self) -> None:
        """3. Actionable finding with concrete suggestion -> not suppressed."""
        f = _f(
            description="User input concatenated into SQL query.",
            suggestion="Use parameterized queries with cursor.execute(sql, params).",
        )
        assert _is_narration(f) is False


# ---------------------------------------------------------------------------
# 0b. Confidence threshold tests (4-8)
# ---------------------------------------------------------------------------


class TestConfidenceThreshold:
    def test_low_at_60_suppressed(self) -> None:
        """4. LOW at 60 -> suppressed (below 65 minimum)."""
        f = _f(severity="LOW", confidence=60)
        assert _below_confidence_threshold(f) is True

    def test_critical_at_80_passes(self) -> None:
        """5. CRITICAL at 80 -> passes (meets 80 minimum)."""
        f = _f(severity="CRITICAL", confidence=80)
        assert _below_confidence_threshold(f) is False

    def test_critical_at_79_suppressed(self) -> None:
        """6. CRITICAL at 79 -> suppressed (below 80 minimum)."""
        f = _f(severity="CRITICAL", confidence=79)
        assert _below_confidence_threshold(f) is True

    def test_medium_governance_penalized(self) -> None:
        """7. MEDIUM governance at raw 80 -> effective 65 -> suppressed (below 75)."""
        f = _f(severity="MEDIUM", confidence=80, category="governance")
        assert _below_confidence_threshold(f) is True

    def test_high_governance_passes(self) -> None:
        """8. HIGH governance at raw 95 -> effective 80 -> passes (above 75)."""
        f = _f(severity="HIGH", confidence=95, category="governance")
        assert _below_confidence_threshold(f) is False


# ---------------------------------------------------------------------------
# 0c. Evidence tests (9-12)
# ---------------------------------------------------------------------------


class TestEvidenceGrounding:
    def test_empty_evidence_suppressed(self) -> None:
        """9. Empty evidence -> suppressed, not scored."""
        findings = [_f(evidence="")]
        review = _review(findings)
        result = filter_review(review, diff=_DIFF_WITH_MAIN)
        assert len(result.findings) == 0
        assert len(result.summary_only_findings) == 0
        # Empty evidence counted in threshold_suppressed
        assert result.meta.threshold_suppressed_count == 1

    def test_grounded_evidence_inline(self) -> None:
        """10. Grounded evidence -> inline-eligible, no penalty."""
        f = _f(evidence='query = f"SELECT * FROM {user_input}"')
        review = _review([f])
        result = filter_review(review, diff=_DIFF_WITH_MAIN)
        assert len(result.findings) == 1
        assert len(result.summary_only_findings) == 0

    def test_ungrounded_evidence_summary_only(self) -> None:
        """11. Ungrounded evidence (no matching tokens) -> summary-only, still scored."""
        f = _f(evidence="completely_unrelated_token_xyz fabricated_evidence_abc")
        review = _review([f])
        result = filter_review(review, diff=_DIFF_WITH_MAIN)
        assert len(result.findings) == 0
        assert len(result.summary_only_findings) == 1
        # Scored: score should reflect this finding
        assert result.score.overall < 100

    def test_no_diff_skips_evidence_check(self) -> None:
        """12. diff=None -> evidence check skipped, all inline-eligible."""
        f = _f(evidence="anything at all")
        review = _review([f])
        result = filter_review(review, diff=None)
        assert len(result.findings) == 1
        assert len(result.summary_only_findings) == 0


# ---------------------------------------------------------------------------
# Three-set invariant tests (13-14)
# ---------------------------------------------------------------------------


class TestThreeSetInvariant:
    def test_display_caps_dont_inflate_score(self) -> None:
        """13. 8 LOWs -> all 8 in scoring set -> display caps to 3 -> score unchanged."""
        findings = [
            _f(id=f"F-{i:03d}", severity="LOW", confidence=70, evidence="query user_input SELECT")
            for i in range(8)
        ]
        review = _review(findings)
        result = filter_review(review, diff=_DIFF_WITH_MAIN)
        # Display: capped to 3 LOW
        assert len(result.findings) == 3
        # Score: all 8 LOW in scoring set (8 * 2 = 16 deduction)
        assert result.score.overall == 100 - 16
        assert result.score.deductions.low_count == 8

    def test_summary_only_scored_not_posted(self) -> None:
        """14. Summary-only findings contribute to score but not inline posting."""
        grounded = _f(id="F-001", evidence='query = f"SELECT * FROM {user_input}"')
        ungrounded = _f(id="F-002", evidence="completely_unrelated_fabricated_token_xyz dummy_text")
        review = _review([grounded, ungrounded])
        result = filter_review(review, diff=_DIFF_WITH_MAIN)
        assert len(result.findings) == 1  # only grounded is inline
        assert len(result.summary_only_findings) == 1  # ungrounded is summary-only
        # Both contribute to score (2 HIGH = -30)
        assert result.score.overall == 100 - 30


# ---------------------------------------------------------------------------
# 0d. Score recomputation tests (15-17)
# ---------------------------------------------------------------------------


class TestScoreRecomputation:
    def test_two_high_findings(self) -> None:
        """15. 2 HIGH findings -> score = 100 - 30 = 70."""
        findings = [_f(id="F-001", severity="HIGH"), _f(id="F-002", severity="HIGH")]
        score = _recompute_score(findings)
        assert score.overall == 70

    def test_critical_security_capped(self) -> None:
        """16. 5 CRITICAL security -> capped at -50, not -125 -> score = 50."""
        findings = [_f(id=f"F-{i:03d}", severity="CRITICAL", category="security") for i in range(5)]
        score = _recompute_score(findings)
        assert score.overall == 50
        assert score.deductions.total_deduction == 50

    def test_breakdown_per_category(self) -> None:
        """17. Score breakdown reflects per-category deductions."""
        findings = [
            _f(id="F-001", severity="HIGH", category="security"),
            _f(id="F-002", severity="MEDIUM", category="logic"),
        ]
        score = _recompute_score(findings)
        assert score.breakdown.security == 85  # 100 - 15
        assert score.breakdown.logic == 95  # 100 - 5
        assert score.breakdown.governance == 100  # untouched
        assert score.overall == 80  # 100 - 15 - 5


# ---------------------------------------------------------------------------
# 0e. Verdict derivation tests (18-21)
# ---------------------------------------------------------------------------


class TestVerdictDerivation:
    def test_low_score_fails(self) -> None:
        """18. Score 65 in pr_review mode -> FAIL, merge_blocking=True."""
        verdict = _derive_verdict(65, [], "pr_review")
        assert verdict.status == VerdictStatus.FAIL
        assert verdict.merge_blocking is True

    def test_critical_forces_fail(self) -> None:
        """19. CRITICAL forces FAIL regardless of score."""
        findings = [_f(severity="CRITICAL")]
        verdict = _derive_verdict(100, findings, "pr_review")
        assert verdict.status == VerdictStatus.FAIL
        assert verdict.merge_blocking is True

    def test_two_high_forces_fail(self) -> None:
        """20. 2+ HIGH forces FAIL regardless of score."""
        findings = [_f(id="F-001", severity="HIGH"), _f(id="F-002", severity="HIGH")]
        verdict = _derive_verdict(100, findings, "pr_review")
        assert verdict.status == VerdictStatus.FAIL
        assert verdict.merge_blocking is True

    def test_mode_is_verdict_authority(self) -> None:
        """21. mode parameter is verdict authority (not review.audit_type)."""
        # Score 80 passes pr_review (threshold 70) but fails security_audit (threshold 85)
        verdict_pr = _derive_verdict(80, [], "pr_review")
        verdict_sec = _derive_verdict(80, [], "security_audit")
        assert verdict_pr.status == VerdictStatus.PASS
        assert verdict_sec.status == VerdictStatus.FAIL


# ---------------------------------------------------------------------------
# 0f. Display cap tests (22-23)
# ---------------------------------------------------------------------------


class TestDisplayCaps:
    def test_per_file_cap(self) -> None:
        """22. 6 findings same file -> display set has 5, scoring set has 6."""
        findings = [
            _f(
                id=f"F-{i:03d}",
                severity="MEDIUM",
                confidence=85,
                evidence='query = f"SELECT * FROM {user_input}"',
            )
            for i in range(6)
        ]
        review = _review(findings)
        result = filter_review(review, diff=_DIFF_WITH_MAIN)
        assert len(result.findings) == 5
        # Score from scoring set (all 6): 100 - 6*5 = 70
        assert result.score.overall == 70
        assert result.meta.display_capped_count == 1

    def test_low_cap(self) -> None:
        """23. 4 LOW findings -> display set has 3, scoring set has 4."""
        findings = [
            _f(
                id=f"F-{i:03d}",
                severity="LOW",
                confidence=70,
                evidence='query = f"SELECT * FROM {user_input}"',
            )
            for i in range(4)
        ]
        review = _review(findings)
        result = filter_review(review, diff=_DIFF_WITH_MAIN)
        assert len(result.findings) == 3
        # Score from all 4 LOW: 100 - 4*2 = 92
        assert result.score.overall == 92
        assert result.meta.display_capped_count == 1


# ---------------------------------------------------------------------------
# Summary-only persistence tests (24-25)
# ---------------------------------------------------------------------------


class TestSummaryOnlyPersistence:
    def test_ungrounded_in_summary_only(self) -> None:
        """24. Ungrounded finding -> in summary_only_findings, not in findings."""
        f = _f(evidence="completely_unrelated_fabricated_token_xyz dummy_text")
        review = _review([f])
        result = filter_review(review, diff=_DIFF_WITH_MAIN)
        assert len(result.findings) == 0
        assert len(result.summary_only_findings) == 1
        assert result.summary_only_findings[0].id == "F-001"

    def test_summary_only_contributes_to_score(self) -> None:
        """25. Summary-only findings contribute to score (scoring set includes them)."""
        f = _f(
            severity="CRITICAL",
            confidence=90,
            evidence="completely_unrelated_fabricated_token_xyz dummy_text",
        )
        review = _review([f])
        result = filter_review(review, diff=_DIFF_WITH_MAIN)
        assert len(result.summary_only_findings) == 1
        # 1 CRITICAL = -25 -> score = 75
        assert result.score.overall == 75


# ---------------------------------------------------------------------------
# 0g. Telemetry tests (26-30)
# ---------------------------------------------------------------------------


class TestTelemetry:
    def test_before_policy_snapshot(self) -> None:
        """26. score_before_policy and verdict_before_policy populated."""
        review = _review([])
        result = filter_review(review)
        assert result.meta.score_before_policy == 95  # original fixture score
        assert result.meta.verdict_before_policy == "PASS"

    def test_narration_count(self) -> None:
        """27. narration_suppressed_count = narration-specific count."""
        findings = [
            _f(id="F-001", description="No action needed.", suggestion="Keep."),
            _f(id="F-002", suggestion=""),
            _f(id="F-003"),  # real finding
        ]
        review = _review(findings)
        result = filter_review(review, diff=_DIFF_WITH_MAIN)
        assert result.meta.narration_suppressed_count == 2

    def test_threshold_count(self) -> None:
        """28. threshold_suppressed_count = threshold + empty-evidence count."""
        findings = [
            _f(id="F-001", severity="LOW", confidence=50),  # below threshold
            _f(id="F-002", evidence=""),  # empty evidence
            _f(id="F-003"),  # real finding
        ]
        review = _review(findings)
        result = filter_review(review, diff=_DIFF_WITH_MAIN)
        assert result.meta.threshold_suppressed_count == 2

    def test_total_suppressed_is_sum(self) -> None:
        """29. confidence_filter_suppressed = narration + threshold (backward compat total)."""
        findings = [
            _f(id="F-001", description="No action needed.", suggestion="Keep."),  # narration
            _f(id="F-002", severity="LOW", confidence=50),  # threshold
            _f(id="F-003"),  # survives
        ]
        review = _review(findings)
        result = filter_review(review, diff=_DIFF_WITH_MAIN)
        assert result.meta.confidence_filter_suppressed == (
            result.meta.narration_suppressed_count + result.meta.threshold_suppressed_count
        )

    def test_display_capped_count(self) -> None:
        """30. display_capped_count = exact cap count."""
        findings = [
            _f(
                id=f"F-{i:03d}",
                severity="LOW",
                confidence=70,
                evidence='query = f"SELECT * FROM {user_input}"',
            )
            for i in range(5)
        ]
        review = _review(findings)
        result = filter_review(review, diff=_DIFF_WITH_MAIN)
        # 5 LOW -> 3 displayed, 2 capped
        assert result.meta.display_capped_count == 2


# ---------------------------------------------------------------------------
# 0h. Fail-open test (31)
# ---------------------------------------------------------------------------


class TestFailOpen:
    def test_policy_error_returns_unfiltered(self) -> None:
        """31. Injected exception -> unfiltered review, policy_bypassed=True."""
        import json
        from unittest.mock import MagicMock

        from grippy.retry import run_review

        review_dict = _review([_f()]).model_dump(mode="json")
        mock_response = MagicMock()
        mock_response.content = json.dumps(review_dict)
        mock_response.reasoning_content = None
        mock_agent = MagicMock()
        mock_agent.run.return_value = mock_response
        mock_agent.model = None

        with patch("grippy.retry.filter_review", side_effect=RuntimeError("boom")):
            result = run_review(mock_agent, "test message")

        assert result.meta.policy_bypassed is True
        assert result.meta.policy_bypass_reason == "boom"


# ---------------------------------------------------------------------------
# Diff helper tests (32-33)
# ---------------------------------------------------------------------------


class TestDiffHelper:
    def test_correct_file_line_mapping(self) -> None:
        """32. _get_added_lines_by_file returns correct file -> lines mapping."""
        result = _get_added_lines_by_file(_DIFF_WITH_MAIN)
        assert "src/main.py" in result
        lines = result["src/main.py"]
        assert any("SELECT" in line for line in lines)
        assert any("db.execute" in line for line in lines)

    def test_handles_empty_and_binary(self) -> None:
        """33. Handles empty diff, binary files, renamed files."""
        # Empty diff
        assert _get_added_lines_by_file("") == {}

        # Binary file (no hunks)
        binary_diff = (
            "diff --git a/img.png b/img.png\n"
            "new file mode 100644\n"
            "Binary files /dev/null and b/img.png differ\n"
        )
        result = _get_added_lines_by_file(binary_diff)
        assert "img.png" not in result or result.get("img.png") == []

        # Rename with no content change
        rename_diff = (
            "diff --git a/old.py b/new.py\n"
            "similarity index 100%\n"
            "rename from old.py\n"
            "rename to new.py\n"
        )
        result = _get_added_lines_by_file(rename_diff)
        assert result.get("new.py") is None or result.get("new.py") == []


# ---------------------------------------------------------------------------
# End-to-end test (34)
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_mixed_findings_full_pipeline(self) -> None:
        """34. Full review with narration + low-conf + empty-evidence + ungrounded + real."""
        findings = [
            # Narration -> suppressed
            _f(
                id="F-001",
                severity="MEDIUM",
                confidence=85,
                description="The code looks good. No action needed.",
                suggestion="Keep the current implementation.",
                evidence="some evidence text here",
            ),
            # Low confidence -> suppressed
            _f(
                id="F-002",
                severity="CRITICAL",
                confidence=70,
                evidence="some evidence",
            ),
            # Empty evidence -> suppressed
            _f(id="F-003", severity="HIGH", confidence=90, evidence=""),
            # Ungrounded evidence -> summary-only
            _f(
                id="F-004",
                severity="HIGH",
                confidence=90,
                evidence="completely_unrelated_fabricated_token_xyz dummy_text",
            ),
            # Real, grounded finding -> inline
            _f(
                id="F-005",
                severity="HIGH",
                confidence=90,
                evidence='query = f"SELECT * FROM {user_input}"',
            ),
        ]
        review = _review(findings)
        result = filter_review(review, mode="pr_review", diff=_DIFF_WITH_MAIN)

        # Display set: only F-005 (grounded, real)
        assert [f.id for f in result.findings] == ["F-005"]

        # Summary-only: F-004 (ungrounded but non-empty evidence)
        assert [f.id for f in result.summary_only_findings] == ["F-004"]

        # Score from scoring set (F-004 + F-005 = 2 HIGH = -30)
        assert result.score.overall == 70

        # Verdict: 70 meets pr_review threshold (70) but 2 HIGH -> FAIL
        assert result.verdict.status == VerdictStatus.FAIL
        assert result.verdict.merge_blocking is True

        # Telemetry
        assert result.meta.narration_suppressed_count == 1  # F-001
        assert result.meta.threshold_suppressed_count == 2  # F-002 (confidence) + F-003 (empty)
        assert result.meta.confidence_filter_suppressed == 3  # total
        assert result.meta.score_before_policy == 95
        assert result.meta.verdict_before_policy == "PASS"
