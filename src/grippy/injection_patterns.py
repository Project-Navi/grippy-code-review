# SPDX-License-Identifier: MIT
"""Shared injection pattern definitions — single source of truth.

This is a leaf module with ZERO imports from other grippy modules to avoid
circular imports. Both input_fence.py (escape pipeline) and ports.py
(guard validator) import from here.

Patterns adapted from navi-os's sanitize_for_llm() pattern. Matched text
is replaced with [BLOCKED] so attacker-controlled PR content cannot
manipulate review scoring, confidence calibration, or analysis behavior.
"""

from __future__ import annotations

import re

# Full patterns with replacement strings — used by escape_xml() pipeline.
INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)ignore\s+(?:all\s+)?previous\s+instructions?"), "[BLOCKED]"),
    (re.compile(r"(?i)score\s+this\s+(?:PR|review|code)\s+\d+"), "[BLOCKED]"),
    (
        re.compile(r"(?i)(?:confidence|severity)\s+(?:below|under|above|less\s+than)\s+\d+"),
        "[BLOCKED]",
    ),
    (
        re.compile(
            r"(?i)set\s+(?:the\s+)?confidence\s+of\s+all\s+(?:the\s+)?findings?\s+to\s+\d+"
        ),
        "[BLOCKED]",
    ),
    (re.compile(r"(?i)low\s+confidence\s+only"), "[BLOCKED]"),
    (re.compile(r"(?i)IMPORTANT\s+SYSTEM\s+UPDATE"), "[BLOCKED]"),
    (re.compile(r"(?i)bypass\s+(?:all\s+)?security\s+checks?"), "[BLOCKED]"),
    (re.compile(r"(?i)you\s+are\s+now\s+"), "[BLOCKED] "),
    (re.compile(r"(?i)skip\s+(?:security\s+)?analysis"), "[BLOCKED]"),
    (re.compile(r"(?i)no\s+findings?\s+needed"), "[BLOCKED]"),
]

# Guard-only patterns (no replacement) — used by _assert_already_sanitized()
# to verify content has already been neutralized.
INJECTION_GUARD_PATTERNS: list[re.Pattern[str]] = [pat for pat, _repl in INJECTION_PATTERNS]
