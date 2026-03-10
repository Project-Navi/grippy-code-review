# SPDX-License-Identifier: MIT
"""Tier 3: LLM model characterization tests.

These tests log and trend model behavior under the e2e_stress marker.
Assertions are intentionally loose — they characterize the model's
tendencies, not enforce strict product guarantees. Use these to detect
model regressions across versions, not as CI gates.

Run with: uv run pytest -m e2e_stress tests/test_e2e_llm_characterization.py -v
"""

from __future__ import annotations

import statistics

import pytest

from tests.e2e_fixtures import (
    DIFFS,
    assert_valid_review,
    generate_massive_diff,
    run_pipeline,
    skip_no_llm,
)

pytestmark = [pytest.mark.e2e_stress]


@skip_no_llm
class TestScoreCharacterization:
    """Characterize score distributions. Loose bounds — log, don't gate."""

    @pytest.mark.timeout(600)
    def test_score_variance_across_runs(self) -> None:
        """Same diff 3x — log score spread. Warn if > 30, fail if > 50."""
        scores: list[int] = []
        for i in range(3):
            review = run_pipeline(
                DIFFS["multi_vuln_auth"],
                title=f"Auth module (run {i + 1})",
                description="SQL injection, secrets, weak crypto.",
                max_retries=2,
            )
            assert_valid_review(review)
            scores.append(review.score.overall)
            print(f"  Run {i + 1}: score={review.score.overall}")

        spread = max(scores) - min(scores)
        mean = statistics.mean(scores)
        print(f"  Scores: {scores}, spread={spread}, mean={mean:.1f}")

        # Loose gate: > 50 point spread is unreliable
        assert spread <= 50, f"Score spread {spread} exceeds 50: {scores}"

    @pytest.mark.timeout(180)
    def test_clean_code_scores_above_70(self) -> None:
        """Clean code should score well. Warn below 70, fail below 50."""
        review = run_pipeline(
            DIFFS["clean_python"],
            title="Clean math utils",
            description="Simple math helpers, no security issues.",
        )
        assert_valid_review(review)
        print(f"  Clean code score: {review.score.overall}")
        assert review.score.overall >= 50, (
            f"Clean code scored {review.score.overall} — below 50 is alarm territory"
        )

    @pytest.mark.timeout(180)
    def test_vulnerable_code_scores_below_70(self) -> None:
        """Multi-vuln code should score poorly. Warn above 60, fail above 80."""
        review = run_pipeline(
            DIFFS["payment_multi_vuln"],
            title="Payment service",
            description="SQL injection x3, hardcoded secrets x2, weak crypto.",
            max_retries=3,
        )
        assert_valid_review(review)
        print(f"  Vuln code score: {review.score.overall}")
        assert review.score.overall <= 80, (
            f"Multi-vuln code scored {review.score.overall} — above 80 means under-penalizing"
        )


@skip_no_llm
class TestFindingQuality:
    """Characterize finding quality — are findings grounded in the diff?"""

    @pytest.mark.timeout(300)
    def test_multi_vuln_finding_count(self) -> None:
        """Payment diff should produce multiple findings. Log actual count."""
        review = run_pipeline(
            DIFFS["payment_multi_vuln"],
            title="Payment service",
            description="SQL injection x3, hardcoded secrets x2, weak crypto.",
            max_retries=3,
        )
        assert_valid_review(review)
        print(f"  Finding count: {len(review.findings)}")
        for f in review.findings:
            print(f"    {f.id}: [{f.severity}] {f.file}:{f.line_start} — {f.title}")

        # Loose: at least 2 findings for a diff with 6+ real issues
        assert len(review.findings) >= 2, f"Expected >=2 findings, got {len(review.findings)}"

    @pytest.mark.timeout(300)
    def test_findings_reference_correct_files(self) -> None:
        """Findings should reference files from the actual diff, not hallucinated paths."""
        review = run_pipeline(
            DIFFS["multi_vuln_auth"],
            title="Auth module",
            max_retries=3,
        )
        assert_valid_review(review)

        # Files in the diff
        diff_files = {"auth/login.py", "api/views.py"}
        finding_files = {f.file for f in review.findings}
        print(f"  Diff files: {diff_files}")
        print(f"  Finding files: {finding_files}")

        # At least one finding should reference a real diff file
        grounded = finding_files & diff_files
        assert len(grounded) >= 1, (
            f"No findings reference diff files. Finding files: {finding_files}, "
            f"diff files: {diff_files}"
        )


@skip_no_llm
class TestPersonalityCharacterization:
    """Characterize personality field population. Model-dependent, loosely gated."""

    @pytest.mark.timeout(180)
    def test_personality_fields_populated(self) -> None:
        """Personality fields should be non-empty strings."""
        review = run_pipeline(DIFFS["clean_python"], title="Clean code")
        assert_valid_review(review)

        p = review.personality
        print(f"  tone_register: {p.tone_register}")
        print(f"  opening: {p.opening_catchphrase!r}")
        print(f"  closing: {p.closing_line!r}")
        print(f"  ascii_art_key: {p.ascii_art_key}")

        # These are schema fields — they should be populated, but content is model-dependent
        assert len(p.opening_catchphrase) > 0, "opening_catchphrase is empty"
        assert len(p.closing_line) > 0, "closing_line is empty"


@skip_no_llm
class TestTruncationCharacterization:
    """Characterize behavior on large diffs."""

    @pytest.mark.timeout(300)
    def test_massive_diff_completes(self) -> None:
        """120K char diff — verify review completes. Log truncation behavior."""
        review = run_pipeline(
            DIFFS["massive"],
            title="Add 100 modules",
            description="Large refactor.",
            max_retries=3,
        )
        assert_valid_review(review)
        print(f"  Files in diff: {review.scope.files_in_diff}")
        print(f"  Files reviewed: {review.scope.files_reviewed}")
        print(f"  Coverage: {review.scope.coverage_percentage}%")

    @pytest.mark.timeout(300)
    def test_500k_diff_completes(self) -> None:
        """500K char diff — beyond normal limits. Should truncate and review."""
        huge = generate_massive_diff(500_000)
        review = run_pipeline(
            huge,
            title="Massive refactor",
            description="Very large change.",
            max_retries=3,
        )
        assert_valid_review(review)
        print(f"  500K diff: score={review.score.overall}, findings={len(review.findings)}")
