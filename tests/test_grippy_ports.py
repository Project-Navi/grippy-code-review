# SPDX-License-Identifier: MIT
"""Tests for grippy.ports — protocol definitions and SanitizedPRContext guard."""

from __future__ import annotations

import navi_sanitize
import pytest
from pydantic import ValidationError

from grippy.ports import (
    ReviewToolBudgetError,
    ReviewTransportError,
    SanitizedPRContext,
    xml_escaper,
)


class TestXmlEscaper:
    """The xml_escaper function used throughout the sanitization pipeline."""

    def test_escapes_ampersand(self) -> None:
        assert xml_escaper("a & b") == "a &amp; b"

    def test_escapes_lt(self) -> None:
        assert xml_escaper("a < b") == "a &lt; b"

    def test_escapes_gt(self) -> None:
        assert xml_escaper("a > b") == "a &gt; b"

    def test_preserves_clean_text(self) -> None:
        assert xml_escaper("clean text") == "clean text"


def _sanitize_like_production(text: str) -> str:
    """Mimic the production _escape_xml pipeline: navi-sanitize then XML escape."""
    return xml_escaper(navi_sanitize.clean(text))


class TestSanitizedPRContext:
    """TB-1 structural enforcement tests."""

    def test_accepts_already_sanitized_content(self) -> None:
        """Content that is already clean passes the idempotent guard."""
        clean = _sanitize_like_production("clean text with entities")
        ctx = SanitizedPRContext(content=clean)
        assert ctx.content == clean

    def test_accepts_pre_escaped_xml(self) -> None:
        """Pre-escaped XML entities pass (they're already sanitized)."""
        clean = _sanitize_like_production("text with & and <tag>")
        ctx = SanitizedPRContext(content=clean)
        assert "&amp;" in ctx.content

    def test_rejects_raw_xml_chars(self) -> None:
        """Raw XML chars that would change under sanitization are rejected."""
        with pytest.raises(ValidationError, match="pre-sanitized"):
            SanitizedPRContext(content="text with <script> tags")

    def test_rejects_raw_ampersand(self) -> None:
        """Raw & that would become &amp; is rejected."""
        with pytest.raises(ValidationError, match="pre-sanitized"):
            SanitizedPRContext(content="a & b")

    def test_rejects_invisible_unicode(self) -> None:
        """Content with invisible Unicode chars is rejected."""
        with pytest.raises(ValidationError, match="pre-sanitized"):
            SanitizedPRContext(content="text\u200bwith\u200bzero-width")

    def test_frozen(self) -> None:
        """SanitizedPRContext is immutable."""
        clean = _sanitize_like_production("test")
        ctx = SanitizedPRContext(content=clean)
        with pytest.raises(ValidationError):
            ctx.content = "mutated"  # type: ignore[misc]

    def test_no_double_escape(self) -> None:
        """Already-escaped content is not double-escaped.

        This is the key property: &amp; stays as &amp;, not &amp;amp;.
        """
        content = _sanitize_like_production("text & more <stuff>")
        ctx = SanitizedPRContext(content=content)
        assert ctx.content == content  # unchanged, not double-escaped
        assert "&amp;" in ctx.content  # confirm escaping is present


class TestExceptionTypes:
    """Transport and tool budget exceptions are importable and correct."""

    def test_transport_error_is_exception(self) -> None:
        assert issubclass(ReviewTransportError, Exception)

    def test_tool_budget_error_is_exception(self) -> None:
        assert issubclass(ReviewToolBudgetError, Exception)

    def test_transport_error_message(self) -> None:
        e = ReviewTransportError("rate limited")
        assert str(e) == "rate limited"

    def test_tool_budget_error_message(self) -> None:
        e = ReviewToolBudgetError("budget exhausted")
        assert str(e) == "budget exhausted"
