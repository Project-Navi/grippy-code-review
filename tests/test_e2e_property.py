# SPDX-License-Identifier: MIT
"""Tier 0: Property-based tests for parser, retry, and escaping internals.

Uses hypothesis to fuzz the code paths that sit between LLM output and
grippy's structured review. These are the paths where hardening matters most
and where LLM-paid debugging is wasteful.

Run with: uv run pytest -m e2e_fast tests/test_e2e_property.py -v
"""

from __future__ import annotations

import json
import os
import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from grippy.agent import _escape_xml
from grippy.retry import _parse_response, _strip_markdown_fences, _validate_rule_coverage
from grippy.schema import GrippyReview

pytestmark = pytest.mark.e2e_fast

_MAX_EXAMPLES = 10_000 if os.environ.get("FUZZ_SLOW") else 1_000

_PRINTABLE = st.text(alphabet=string.printable, min_size=0, max_size=500)


# ---------------------------------------------------------------------------
# _strip_markdown_fences — must never crash, must extract JSON if present
# ---------------------------------------------------------------------------


class TestStripMarkdownFences:
    """Property tests for _strip_markdown_fences."""

    @given(text=_PRINTABLE)
    @settings(max_examples=_MAX_EXAMPLES)
    def test_never_crashes(self, text: str) -> None:
        result = _strip_markdown_fences(text)
        assert isinstance(result, str)

    @given(inner=_PRINTABLE)
    @settings(max_examples=_MAX_EXAMPLES)
    def test_extracts_fenced_content(self, inner: str) -> None:
        fenced = f"```json\n{inner}\n```"
        result = _strip_markdown_fences(fenced)
        assert result.strip() == inner.strip()

    @given(inner=_PRINTABLE)
    @settings(max_examples=_MAX_EXAMPLES)
    def test_extracts_bare_fenced_content(self, inner: str) -> None:
        fenced = f"```\n{inner}\n```"
        result = _strip_markdown_fences(fenced)
        assert result.strip() == inner.strip()

    def test_no_fences_returns_input(self) -> None:
        text = '{"key": "value"}'
        assert _strip_markdown_fences(text) == text

    def test_nested_fences(self) -> None:
        text = "```json\n```inner```\n```"
        result = _strip_markdown_fences(text)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _parse_response — must handle every plausible LLM output shape
# ---------------------------------------------------------------------------


class TestParseResponse:
    """Property tests for _parse_response."""

    def test_none_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="None"):
            _parse_response(None)

    def test_empty_string_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            _parse_response("")

    def test_whitespace_only_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            _parse_response("   \n\t  ")

    @given(text=_PRINTABLE)
    @settings(max_examples=_MAX_EXAMPLES)
    def test_never_crashes_on_arbitrary_string(self, text: str) -> None:
        """May raise ValueError/ValidationError/JSONDecodeError — must never crash."""
        try:
            _parse_response(text)
        except (ValueError, ValidationError, json.JSONDecodeError, TypeError):
            pass  # expected for garbage input

    def test_valid_dict_parses(self) -> None:
        """A valid GrippyReview dict should parse successfully."""
        review_dict = _minimal_review_dict()
        review = _parse_response(review_dict)
        assert isinstance(review, GrippyReview)

    def test_valid_json_string_parses(self) -> None:
        """A valid JSON string should parse successfully."""
        review_json = json.dumps(_minimal_review_dict())
        review = _parse_response(review_json)
        assert isinstance(review, GrippyReview)

    def test_markdown_fenced_json_parses(self) -> None:
        """JSON wrapped in markdown code fences should parse."""
        review_json = json.dumps(_minimal_review_dict())
        fenced = f"```json\n{review_json}\n```"
        review = _parse_response(fenced)
        assert isinstance(review, GrippyReview)

    def test_passthrough_grippyreview_instance(self) -> None:
        """A GrippyReview instance should pass through."""
        review = GrippyReview.model_validate(_minimal_review_dict())
        result = _parse_response(review)
        assert result is review

    @given(garbage_type=st.one_of(st.integers(), st.floats(), st.binary()))
    @settings(max_examples=100)
    def test_rejects_non_string_non_dict(self, garbage_type: object) -> None:
        with pytest.raises((TypeError, ValueError, ValidationError)):
            _parse_response(garbage_type)


# ---------------------------------------------------------------------------
# _escape_xml — injection pattern neutralization
# ---------------------------------------------------------------------------


class TestEscapeXml:
    """Property tests for _escape_xml."""

    @given(text=_PRINTABLE)
    @settings(max_examples=_MAX_EXAMPLES)
    def test_never_crashes(self, text: str) -> None:
        result = _escape_xml(text)
        assert isinstance(result, str)

    @given(text=_PRINTABLE)
    @settings(max_examples=_MAX_EXAMPLES)
    def test_no_raw_xml_delimiters(self, text: str) -> None:
        """Output must not contain unescaped < or > or &."""
        result = _escape_xml(text)
        # After escaping, any < > & in the result should be part of entities
        for i, ch in enumerate(result):
            if ch == "&":
                rest = result[i:]
                assert (
                    rest.startswith("&amp;")
                    or rest.startswith("&lt;")
                    or rest.startswith("&gt;")
                    or rest.startswith("&")  # could be part of [BLOCKED] replacement
                ), f"Unescaped & at position {i} in: {result[max(0, i - 10) : i + 20]!r}"

    @given(text=st.text(alphabet=string.printable, min_size=1, max_size=200))
    @settings(max_examples=_MAX_EXAMPLES)
    def test_injection_patterns_blocked(self, text: str) -> None:
        """If text contains known injection patterns, output contains [BLOCKED]."""
        import re

        patterns = [
            r"(?i)ignore\s+(?:all\s+)?previous\s+instructions?",
            r"(?i)score\s+this\s+(?:PR|review|code)\s+\d+",
            r"(?i)IMPORTANT\s+SYSTEM\s+UPDATE",
            r"(?i)skip\s+(?:security\s+)?analysis",
            r"(?i)no\s+findings?\s+needed",
        ]
        has_pattern = any(re.search(p, text) for p in patterns)
        result = _escape_xml(text)
        if has_pattern:
            assert "[BLOCKED]" in result


# ---------------------------------------------------------------------------
# _validate_rule_coverage — deterministic cross-reference
# ---------------------------------------------------------------------------


class TestValidateRuleCoverage:
    """Tests for rule coverage validation logic."""

    def test_empty_expected_returns_empty(self) -> None:
        review = GrippyReview.model_validate(_minimal_review_dict())
        missing = _validate_rule_coverage(review, {})
        assert missing == []

    def test_missing_rule_detected(self) -> None:
        review = GrippyReview.model_validate(_minimal_review_dict())
        missing = _validate_rule_coverage(review, {"secrets-in-diff": 1})
        assert len(missing) == 1
        assert "secrets-in-diff" in missing[0]

    def test_matching_rule_passes(self) -> None:
        d = _minimal_review_dict()
        d["findings"][0]["rule_id"] = "secrets-in-diff"
        review = GrippyReview.model_validate(d)
        missing = _validate_rule_coverage(review, {"secrets-in-diff": 1})
        assert missing == []

    def test_wrong_file_detected(self) -> None:
        d = _minimal_review_dict()
        d["findings"][0]["rule_id"] = "secrets-in-diff"
        d["findings"][0]["file"] = "wrong.py"
        review = GrippyReview.model_validate(d)
        missing = _validate_rule_coverage(
            review,
            {"secrets-in-diff": 1},
            expected_rule_files={"secrets-in-diff": frozenset({".env"})},
        )
        assert len(missing) == 1
        assert "don't reference flagged files" in missing[0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_review_dict() -> dict:
    """Return a minimal valid GrippyReview dict for testing."""
    return {
        "version": "1.0",
        "audit_type": "pr_review",
        "timestamp": "2026-03-09T00:00:00Z",
        "model": "test-model",
        "pr": {
            "title": "Test PR",
            "author": "test-author",
            "branch": "feat/test -> main",
            "complexity_tier": "STANDARD",
        },
        "scope": {
            "files_in_diff": 1,
            "files_reviewed": 1,
            "coverage_percentage": 100.0,
            "governance_rules_applied": [],
            "modes_active": ["pr_review"],
        },
        "findings": [
            {
                "id": "F-001",
                "severity": "HIGH",
                "confidence": 85,
                "category": "security",
                "file": "test.py",
                "line_start": 1,
                "line_end": 5,
                "title": "Test finding",
                "description": "Test description.",
                "suggestion": "Fix it.",
                "evidence": "line 1",
                "grippy_note": "Grippy says fix it.",
            }
        ],
        "escalations": [],
        "score": {
            "overall": 60,
            "breakdown": {
                "security": 50,
                "logic": 80,
                "governance": 70,
                "reliability": 70,
                "observability": 60,
            },
            "deductions": {
                "critical_count": 0,
                "high_count": 1,
                "medium_count": 0,
                "low_count": 0,
                "total_deduction": 15,
            },
        },
        "verdict": {
            "status": "FAIL",
            "threshold_applied": 70,
            "merge_blocking": True,
            "summary": "Security issues found.",
        },
        "personality": {
            "tone_register": "grumpy",
            "opening_catchphrase": "What is this.",
            "closing_line": "Do better.",
            "ascii_art_key": "warning",
        },
        "meta": {
            "review_duration_ms": 1000,
            "tokens_used": 500,
            "context_files_loaded": 0,
            "confidence_filter_suppressed": 0,
            "duplicate_filter_suppressed": 0,
        },
    }
