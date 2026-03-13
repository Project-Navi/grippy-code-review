# SPDX-License-Identifier: MIT
"""Tests for benchmarks/martian/run_grippy.py."""

from benchmarks.martian.run_grippy import (
    format_finding_as_comment,
    is_inline_finding,
)


def _make_finding(**overrides):
    """Create a minimal Finding-like dict."""
    base = {
        "id": "F-001",
        "severity": "HIGH",
        "confidence": 85,
        "category": "security",
        "file": "src/auth.py",
        "line_start": 42,
        "line_end": 42,
        "title": "SQL injection risk",
        "description": "Query concatenates user input without parameterization.",
        "suggestion": "Use parameterized queries.",
        "evidence": "line 42: query = f'SELECT * FROM users WHERE id={user_id}'",
        "grippy_note": "Watch out!",
    }
    base.update(overrides)
    return base


def test_is_inline_finding():
    assert is_inline_finding(_make_finding()) is True
    assert is_inline_finding(_make_finding(file="", line_start=0)) is False
    assert is_inline_finding(_make_finding(file="src/a.py", line_start=0)) is False


def test_format_finding_as_comment_inline():
    finding = _make_finding()
    comment = format_finding_as_comment(finding)
    assert "SQL injection risk" in comment
    assert "concatenates user input" in comment
    # Must NOT contain severity tags, suggestions, evidence, confidence
    assert "[HIGH]" not in comment
    assert "Suggestion:" not in comment
    assert "Evidence:" not in comment
    assert "85" not in comment


def test_format_finding_as_comment_is_concise():
    finding = _make_finding()
    comment = format_finding_as_comment(finding)
    # Should be markdown heading + description, nothing else
    lines = [line for line in comment.strip().split("\n") if line.strip()]
    assert len(lines) <= 4  # heading + description (possibly wrapped)


def test_format_finding_parity_with_production():
    """Verify benchmark formatter output is structurally consistent
    with production build_review_comment() — same substance, less metadata."""
    from grippy.github_review import build_review_comment
    from grippy.schema import Finding, FindingCategory, Severity

    prod_finding = Finding(
        id="F-001",
        severity=Severity.HIGH,
        confidence=85,
        category=FindingCategory.SECURITY,
        file="src/auth.py",
        line_start=42,
        line_end=42,
        title="SQL injection risk",
        description="Query concatenates user input without parameterization.",
        suggestion="Use parameterized queries.",
        evidence="line 42",
        grippy_note="Watch out!",
    )

    prod_comment = build_review_comment(prod_finding)
    bench_finding = _make_finding()
    bench_comment = format_finding_as_comment(bench_finding)

    # Both must contain the title and description
    assert "SQL injection risk" in prod_comment["body"]
    assert "SQL injection risk" in bench_comment
    assert "concatenates user input" in prod_comment["body"]
    assert "concatenates user input" in bench_comment

    # Bench version must NOT contain metadata that production includes
    assert "Confidence:" in prod_comment["body"]  # production has it
    assert "Confidence" not in bench_comment  # bench strips it
    assert "Suggestion:" in prod_comment["body"]  # production has it
    assert "Suggestion" not in bench_comment  # bench strips it
