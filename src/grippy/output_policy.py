# SPDX-License-Identifier: MIT
"""Output policy — filters, scores, and gates Grippy review findings.

Three finding sets:
- **Suppressed**: narration, below-threshold, empty-evidence — discarded
- **Scoring set**: all findings surviving suppression (inline + summary-only)
- **Display set**: inline-eligible subset of scoring set, after caps

Score and verdict are computed from the scoring set. Display caps only control
what gets posted inline, not how the PR is graded.

Summary-only findings may affect score and verdict, but they must never
produce inline comments.
"""

from __future__ import annotations

import logging

from grippy.ignore import parse_nogrip
from grippy.rules.context import parse_diff
from grippy.schema import (
    Finding,
    FindingCategory,
    GrippyReview,
    Score,
    ScoreBreakdown,
    ScoreDeductions,
    Severity,
    Verdict,
    VerdictStatus,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 0a. Narration detection
# ---------------------------------------------------------------------------

_NARRATION_PHRASES = frozenset(
    {
        "no action needed",
        "no changes required",
        "no changes needed",
        "no issues found",
        "looks good",
        "properly implemented",
        "correctly implemented",
        "well-structured",
        "appropriate approach",
        "no concerns",
        "no immediate concern",
    }
)

_SUGGESTION_EMPTY_PREFIXES = ("none", "n/a", "no suggestion", "keep")


def _is_narration(finding: Finding) -> bool:
    """Detect narration — describes code without actionable advice."""
    desc_lower = finding.description.lower()
    sugg_lower = finding.suggestion.lower().strip()

    for phrase in _NARRATION_PHRASES:
        if phrase in desc_lower or phrase in sugg_lower:
            return True

    if not finding.suggestion.strip():
        return True

    for prefix in _SUGGESTION_EMPTY_PREFIXES:
        if sugg_lower.startswith(prefix):
            return True

    return False


# ---------------------------------------------------------------------------
# 0b. Confidence threshold
# ---------------------------------------------------------------------------

_CONFIDENCE_THRESHOLD: dict[Severity, int] = {
    Severity.CRITICAL: 80,
    Severity.HIGH: 75,
    Severity.MEDIUM: 75,
    Severity.LOW: 65,
}

_CATEGORY_PENALTY: dict[FindingCategory, int] = {
    FindingCategory.GOVERNANCE: 15,
    FindingCategory.OBSERVABILITY: 15,
}


def _below_confidence_threshold(finding: Finding) -> bool:
    """Check if effective confidence is below the severity-specific threshold."""
    penalty = _CATEGORY_PENALTY.get(finding.category, 0)
    effective = finding.confidence - penalty
    threshold = _CONFIDENCE_THRESHOLD[finding.severity]
    return effective < threshold


# ---------------------------------------------------------------------------
# 0c. Evidence grounding
# ---------------------------------------------------------------------------


_NoGripIndex = dict[tuple[str, int], set[str] | bool]


def _parse_diff_context(
    diff: str,
) -> tuple[dict[str, list[str]], _NoGripIndex]:
    """Parse diff once, returning added lines by file and nogrip index.

    Delegates to ``parse_diff`` from ``rules/context.py`` to avoid duplicating
    diff parsing logic. Builds the nogrip index in the same pass using
    ``parse_nogrip`` from ``ignore.py``.
    """
    files = parse_diff(diff)
    added_lines: dict[str, list[str]] = {}
    nogrip_index: _NoGripIndex = {}

    for f in files:
        added: list[str] = []
        for hunk in f.hunks:
            for line in hunk.lines:
                if line.type == "add":
                    added.append(line.content)
                    if line.new_lineno is not None:
                        ng = parse_nogrip(line.content)
                        if ng is not None:
                            nogrip_index[(f.path, line.new_lineno)] = ng
        if added:
            added_lines[f.path] = added

    return added_lines, nogrip_index


def _get_added_lines_by_file(diff: str) -> dict[str, list[str]]:
    """Extract added lines per file from a unified diff.

    Convenience wrapper around ``_parse_diff_context`` for callers that
    only need the added lines (e.g. tests).
    """
    added_lines, _ = _parse_diff_context(diff)
    return added_lines


def _evidence_is_grounded(finding: Finding, added_lines: dict[str, list[str]]) -> bool:
    """Check evidence has meaningful token overlap with the file's added lines.

    Tokenizes evidence into whitespace-separated tokens (min 3 chars each).
    Requires at least 2 evidence tokens to appear in the file's added lines.
    """
    file_lines = added_lines.get(finding.file, [])
    if not file_lines:
        return False

    tokens = [t for t in finding.evidence.split() if len(t) >= 3]
    if len(tokens) < 2:
        return True  # too few meaningful tokens — benefit of doubt

    added_text = " ".join(file_lines)
    matches = sum(1 for t in tokens if t in added_text)
    return matches >= 2


# ---------------------------------------------------------------------------
# 0c-bis. Nogrip suppression
# ---------------------------------------------------------------------------


def _is_nogrip_suppressed(finding: Finding, nogrip_index: _NoGripIndex) -> bool:
    """Check if any line in [line_start, line_end] has a ``# nogrip`` pragma.

    Bare ``# nogrip`` suppresses all findings. Targeted ``# nogrip: SEC-001``
    only suppresses findings whose ``rule_id`` matches.
    """
    for line_no in range(finding.line_start, finding.line_end + 1):
        ng = nogrip_index.get((finding.file, line_no))
        if ng is True:
            return True  # bare nogrip — suppress all
        if isinstance(ng, set) and finding.rule_id and finding.rule_id in ng:
            return True  # targeted nogrip matching finding's rule_id
    return False


# ---------------------------------------------------------------------------
# 0d. Score recomputation
# ---------------------------------------------------------------------------

_DEDUCTION: dict[Severity, int] = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 15,
    Severity.MEDIUM: 5,
    Severity.LOW: 2,
}

_CATEGORY_CAP: dict[FindingCategory, int] = {
    FindingCategory.SECURITY: 50,
    FindingCategory.LOGIC: 30,
    FindingCategory.GOVERNANCE: 30,
    FindingCategory.RELIABILITY: 20,
    FindingCategory.OBSERVABILITY: 15,
}


def _recompute_score(findings: list[Finding]) -> Score:
    """Recompute score from the scoring set using the deduction rubric."""
    category_deductions: dict[FindingCategory, int] = {}
    severity_counts = dict.fromkeys(Severity, 0)

    for f in findings:
        category_deductions[f.category] = category_deductions.get(f.category, 0) + _DEDUCTION.get(
            f.severity, 0
        )
        severity_counts[f.severity] += 1

    total = 0
    capped: dict[FindingCategory, int] = {}
    for cat, ded in category_deductions.items():
        cap = _CATEGORY_CAP.get(cat, 30)
        c = min(ded, cap)
        capped[cat] = c
        total += c

    return Score(
        overall=max(0, 100 - total),
        breakdown=ScoreBreakdown(
            security=100 - capped.get(FindingCategory.SECURITY, 0),
            logic=100 - capped.get(FindingCategory.LOGIC, 0),
            governance=100 - capped.get(FindingCategory.GOVERNANCE, 0),
            reliability=100 - capped.get(FindingCategory.RELIABILITY, 0),
            observability=100 - capped.get(FindingCategory.OBSERVABILITY, 0),
        ),
        deductions=ScoreDeductions(
            critical_count=severity_counts[Severity.CRITICAL],
            high_count=severity_counts[Severity.HIGH],
            medium_count=severity_counts[Severity.MEDIUM],
            low_count=severity_counts[Severity.LOW],
            total_deduction=total,
        ),
    )


# ---------------------------------------------------------------------------
# 0e. Verdict derivation
# ---------------------------------------------------------------------------

_THRESHOLD: dict[str, int] = {
    "pr_review": 70,
    "security_audit": 85,
    "governance_check": 70,
    "surprise_audit": 85,
}


def _derive_verdict(score: int, findings: list[Finding], mode: str) -> Verdict:
    """Derive verdict from recomputed score and mode (call-site authority)."""
    threshold = _THRESHOLD.get(mode, 70)

    has_critical = any(f.severity == Severity.CRITICAL for f in findings)
    high_count = sum(1 for f in findings if f.severity == Severity.HIGH)

    if has_critical:
        status, blocking = VerdictStatus.FAIL, True
    elif high_count >= 2:
        status, blocking = VerdictStatus.FAIL, True
    elif score < threshold:
        status, blocking = VerdictStatus.FAIL, True
    elif high_count > 0:
        status, blocking = VerdictStatus.PROVISIONAL, False
    else:
        status, blocking = VerdictStatus.PASS, False

    return Verdict(
        status=status,
        threshold_applied=threshold,
        merge_blocking=blocking,
        summary=f"Score {score}/100 (threshold {threshold}, mode {mode})",
    )


# ---------------------------------------------------------------------------
# 0f. Display caps
# ---------------------------------------------------------------------------


def _apply_display_caps(findings: list[Finding]) -> tuple[list[Finding], int]:
    """Apply per-file, per-review, and LOW caps. Returns (display, capped_count)."""
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
    }
    ranked = sorted(findings, key=lambda f: (severity_order.get(f.severity, 4), -f.confidence))

    # Per-file cap: 5
    file_counts: dict[str, int] = {}
    after_file: list[Finding] = []
    file_capped = 0
    for f in ranked:
        c = file_counts.get(f.file, 0)
        if c >= 5:
            file_capped += 1
            continue
        file_counts[f.file] = c + 1
        after_file.append(f)

    # LOW cap: 3
    low_seen = 0
    after_low: list[Finding] = []
    low_capped = 0
    for f in after_file:
        if f.severity == Severity.LOW:
            if low_seen >= 3:
                low_capped += 1
                continue
            low_seen += 1
        after_low.append(f)

    # Per-review cap: 20
    review_capped = max(0, len(after_low) - 20)
    display = after_low[:20]

    return display, file_capped + low_capped + review_capped


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def filter_review(
    review: GrippyReview,
    *,
    mode: str = "pr_review",
    diff: str | None = None,
) -> GrippyReview:
    """Apply output policy to a GrippyReview.

    Returns the mutated review with:
    - ``findings`` = display set (inline-eligible, capped)
    - ``summary_only_findings`` = scored but not inline-eligible
    - ``score`` = recomputed from scoring set
    - ``verdict`` = derived from recomputed score + mode
    - ``meta`` = updated telemetry

    Raises on error — caller (retry.py) owns fail-open.
    """
    score_before = review.score.overall
    verdict_before = review.verdict.status.value

    if review.audit_type != mode:
        log.warning(
            "audit_type drift: review.audit_type=%r, mode=%r — using mode",
            review.audit_type,
            mode,
        )

    if diff:
        added_lines, nogrip_index = _parse_diff_context(diff)
    else:
        added_lines, nogrip_index = None, {}

    # --- Phase 1: Suppression ---
    surviving: list[Finding] = []
    narration_count = 0
    threshold_count = 0
    nogrip_count = 0

    for finding in review.findings:
        if nogrip_index and _is_nogrip_suppressed(finding, nogrip_index):
            nogrip_count += 1
            continue
        if _is_narration(finding):
            narration_count += 1
            continue
        if _below_confidence_threshold(finding):
            threshold_count += 1
            continue
        surviving.append(finding)

    # --- Phase 2: Evidence grounding → inline vs summary-only ---
    inline_eligible: list[Finding] = []
    summary_only: list[Finding] = []

    for finding in surviving:
        evidence_text = finding.evidence.strip() if finding.evidence else ""

        if not evidence_text:
            # Empty evidence → suppress (no proof)
            threshold_count += 1
            continue

        if added_lines is not None:
            if _evidence_is_grounded(finding, added_lines):
                inline_eligible.append(finding)
            else:
                # Non-empty but ungrounded → summary-only (still scored)
                summary_only.append(finding)
        else:
            # No diff provided — all inline-eligible
            inline_eligible.append(finding)

    # --- Phase 3: Score from scoring set (inline + summary-only, uncapped) ---
    scoring_set = inline_eligible + summary_only
    new_score = _recompute_score(scoring_set)

    # --- Phase 4: Verdict from score + mode ---
    new_verdict = _derive_verdict(new_score.overall, scoring_set, mode)

    # --- Phase 5: Display caps (inline-eligible only) ---
    display, capped_count = _apply_display_caps(inline_eligible)

    # --- Phase 6: Mutate review ---
    review.findings = display
    review.summary_only_findings = summary_only
    review.score = new_score
    review.verdict = new_verdict

    # --- Phase 7: Telemetry ---
    review.meta.score_before_policy = score_before
    review.meta.verdict_before_policy = verdict_before
    review.meta.narration_suppressed_count = narration_count
    review.meta.threshold_suppressed_count = threshold_count
    review.meta.nogrip_suppressed_count = nogrip_count
    review.meta.confidence_filter_suppressed = narration_count + threshold_count + nogrip_count
    review.meta.display_capped_count = capped_count

    return review
