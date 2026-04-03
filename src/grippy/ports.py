# SPDX-License-Identifier: MIT
"""Ports (interfaces) for grippy's hexagonal architecture.

Defines the contracts that adapters implement and consumers code against.
Trust boundary enforcement lives here — SanitizedPRContext is the TB-1 guard.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Protocol

import navi_sanitize
from pydantic import AfterValidator, BaseModel, ConfigDict

from grippy.injection_patterns import INJECTION_GUARD_PATTERNS as _INJECTION_PATTERNS

# Matches & that is NOT part of a valid XML/HTML entity reference.
# Valid entity refs: &amp; &lt; &gt; &quot; &apos; or numeric &#123; &#x1F;
_RAW_AMPERSAND = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#[0-9]+|#x[0-9a-fA-F]+);)")


def xml_escaper(text: str) -> str:
    """XML entity escaper for use as navi_sanitize.clean(text, escaper=xml_escaper).

    NOT idempotent — applying twice double-escapes &amp; to &amp;amp;.
    For idempotent escaping, use input_fence.escape_xml() which uses
    _RAW_AMPERSAND regex to skip already-escaped entities.

    This function is the navi-sanitize escaper callback. It operates on
    fresh text that clean() has already processed, so idempotency is not
    needed in that context.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _assert_already_sanitized(text: str) -> str:
    """Reject if not already sanitized. Does NOT sanitize — that's input_fence's job.

    Three-phase check matching the full production escape_xml() pipeline:
    1. navi-sanitize (invisible chars, bidi, homoglyphs) must be a no-op
    2. No raw XML delimiters remain (< > or unescaped &)
    3. No un-neutralized injection patterns remain

    Raises ValueError if any check fails — no silent double-escaping.
    (Grumpy R5 FINDING-01: original guard only checked phases 1-2, not 3.)
    """
    msg = "Content must be pre-sanitized via format_pr_context()"
    # Phase 1: navi-sanitize stability
    cleaned = navi_sanitize.clean(text)
    if text != cleaned:
        raise ValueError(msg)
    # Phase 2: no raw XML delimiters
    if "<" in text or ">" in text or _RAW_AMPERSAND.search(text):
        raise ValueError(msg)
    # Phase 3: injection patterns must already be neutralized
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            raise ValueError(msg)
    return text


class SanitizedPRContext(BaseModel):
    """Guarded wrapper — rejects content not already sanitized.

    Constructed by format_pr_context() in input_fence.py, which runs the full
    escape_xml() pipeline (navi-sanitize + injection neutralization + XML escape).
    The AfterValidator is a guard: checks idempotency, rejects if not pre-sanitized.
    """

    model_config = ConfigDict(frozen=True)
    content: Annotated[str, AfterValidator(_assert_already_sanitized)]


class ReviewResponse(Protocol):
    """Minimum response contract — matches what retry.py needs."""

    @property
    def content(self) -> str | dict[str, Any] | BaseModel | None: ...

    @property
    def reasoning_content(self) -> str | None: ...


class ReviewerPort(Protocol):
    """What grippy codes against. Any backend can implement this."""

    def run(self, message: SanitizedPRContext) -> ReviewResponse: ...

    @property
    def model_id(self) -> str | None: ...


class ReviewTransportError(Exception):
    """Non-retryable transport error from an adapter."""


class ReviewToolBudgetError(Exception):
    """Tool call budget exhausted — review cannot complete with tools."""
