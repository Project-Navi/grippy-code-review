# SPDX-License-Identifier: MIT
"""Rule 8: weak-crypto -- detect weak hash algorithms, broken ciphers, and insecure RNG."""

from __future__ import annotations

import re

from grippy.rules.base import RuleResult, RuleSeverity
from grippy.rules.context import RuleContext

_WEAK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("MD5 hash — use SHA-256+", re.compile(r"\bhashlib\.md5\b")),
    ("SHA1 hash — use SHA-256+", re.compile(r"\bhashlib\.sha1\b")),
    ("DES cipher — use AES", re.compile(r"\bDES\.new\b")),
    ("RC4/ARC4 cipher — use AES", re.compile(r"\b(?:RC4|ARC4)\.new\b")),
    ("Blowfish cipher — use AES", re.compile(r"\bBlowfish\.new\b")),
    ("ECB mode — use CBC/GCM", re.compile(r"\bMODE_ECB\b")),
    (
        "random module for security — use secrets",
        re.compile(r"\brandom\.(?:randint|random|choice|getrandbits|sample|shuffle)\s*\("),
    ),
]

_PYTHON_EXTENSIONS = frozenset({".py"})


def _file_ext(path: str) -> str:
    """Get file extension including the dot."""
    dot = path.rfind(".")
    return path[dot:] if dot >= 0 else ""


def _in_tests_dir(path: str) -> bool:
    """Check if path is under a tests directory."""
    return path.startswith("tests/") or "/tests/" in path


def _is_comment(content: str) -> bool:
    """Check if a line is a Python comment."""
    return content.strip().startswith("#")


class WeakCryptoRule:
    """Detect usage of weak hash algorithms, broken ciphers, and insecure RNG."""

    id = "weak-crypto"
    description = "Flag MD5, SHA1, DES, ECB mode, and random module for security contexts"
    default_severity = RuleSeverity.WARN

    def run(self, ctx: RuleContext) -> list[RuleResult]:
        results: list[RuleResult] = []
        for f in ctx.files:
            if _file_ext(f.path) not in _PYTHON_EXTENSIONS:
                continue
            if _in_tests_dir(f.path):
                continue
            for path, lineno, content in ctx.added_lines_for(f.path):
                if _is_comment(content):
                    continue
                for message, pattern in _WEAK_PATTERNS:
                    if pattern.search(content):
                        results.append(
                            RuleResult(
                                rule_id=self.id,
                                severity=self.default_severity,
                                message=f"Weak cryptography: {message}",
                                file=path,
                                line=lineno,
                                evidence=content.strip()[:120],
                            )
                        )
                        break  # one finding per line
        return results
