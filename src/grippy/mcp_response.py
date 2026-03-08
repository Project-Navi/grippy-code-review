# SPDX-License-Identifier: MIT
"""AI-facing response serializers for MCP tools.

Strips personality fields from GrippyReview and produces dense JSON
output suitable for programmatic consumption by AI agents.
"""

from __future__ import annotations

from typing import Any

from grippy.rules.base import RuleResult
from grippy.schema import GrippyReview

_SEVERITY_NAMES: dict[int, str] = {0: "INFO", 1: "WARN", 2: "ERROR", 3: "CRITICAL"}


def _serialize_rule_finding(r: RuleResult) -> dict[str, Any]:
    """Serialize a single deterministic rule finding."""
    d: dict[str, Any] = {
        "rule_id": r.rule_id,
        "severity": _SEVERITY_NAMES.get(int(r.severity), r.severity.name),
        "message": r.message,
        "file": r.file,
        "line": r.line,
    }
    if r.evidence is not None:
        d["evidence"] = r.evidence
    if r.enrichment is not None:
        d["enrichment"] = {
            "blast_radius": r.enrichment.blast_radius,
            "is_recurring": r.enrichment.is_recurring,
            "prior_count": r.enrichment.prior_count,
            "suppressed": r.enrichment.suppressed,
            "suppression_reason": r.enrichment.suppression_reason,
            "velocity": r.enrichment.velocity,
        }
    return d


def serialize_scan(
    findings: list[RuleResult],
    *,
    gate: bool,
    profile: str,
    diff_stats: dict[str, Any],
) -> dict[str, Any]:
    """Serialize ``scan_diff`` output (deterministic rule engine results)."""
    return {
        "findings": [_serialize_rule_finding(r) for r in findings],
        "gate": "failed" if gate else "passed",
        "profile": profile,
        "diff_stats": diff_stats,
    }


def serialize_audit(
    review: GrippyReview,
    *,
    profile: str,
    diff_stats: dict[str, Any],
    rule_findings: list[RuleResult] | None = None,
    diff_truncated: bool = False,
) -> dict[str, Any]:
    """Serialize ``audit_diff`` output, stripping personality fields."""
    return {
        "findings": [
            {
                "id": f.id,
                "file": f.file,
                "line": f.line_start,
                "severity": f.severity.value,
                "category": f.category.value,
                "title": f.title,
                "description": f.description,
                "confidence": f.confidence,
            }
            for f in review.findings
        ],
        "score": {
            "overall": review.score.overall,
            "security": review.score.breakdown.security,
            "logic": review.score.breakdown.logic,
            "governance": review.score.breakdown.governance,
            "reliability": review.score.breakdown.reliability,
            "observability": review.score.breakdown.observability,
        },
        "verdict": {
            "status": review.verdict.status.value,
            "merge_blocking": review.verdict.merge_blocking,
        },
        "rule_findings": [_serialize_rule_finding(r) for r in (rule_findings or [])],
        "metadata": {
            "model": review.model,
            "profile": profile,
            "files_reviewed": review.scope.files_reviewed,
            "diff_stats": diff_stats,
            "diff_truncated": diff_truncated,
        },
    }
