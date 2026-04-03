# SPDX-License-Identifier: MIT
"""Rule 7: sql-injection-risk -- detect SQL queries built from untrusted input."""

from __future__ import annotations

import re

from grippy.rules.base import RuleResult, RuleSeverity
from grippy.rules.context import RuleContext

_SQL_KEYWORDS = r"(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|MERGE)"

# f-string or .format() with SQL keyword
# Uses [^\n]*? (lazy, newline-bounded) instead of .* to prevent cross-line
# backtracking while still matching quotes within the line.
_FSTRING_SQL = re.compile(
    rf"""(?:f['"]|\.format\s*\()[^\n]*?\b{_SQL_KEYWORDS}\b""",
    re.IGNORECASE,
)

# %-formatting with SQL keyword: % operator must follow a closing quote
# Uses [^\n]*? (lazy, newline-bounded) instead of .* to prevent cross-line
# backtracking while still matching mixed quote characters.
_PERCENT_SQL = re.compile(
    rf"""['"][^\n]*?\b{_SQL_KEYWORDS}\b[^\n]*?['"]\s*%\s*(?:\(|[a-zA-Z_])""",
    re.IGNORECASE,
)

# String concatenation with SQL keyword (both directions)
# Uses [^\n]*? (lazy, newline-bounded) instead of .* to prevent cross-line
# backtracking while still matching mixed quote characters.
_CONCAT_SQL = re.compile(
    rf"""(?:['"][^\n]*?\b{_SQL_KEYWORDS}\b[^\n]*?['"]\s*\+|\+\s*['"][^\n]*?\b{_SQL_KEYWORDS}\b)""",
    re.IGNORECASE,
)

# cursor.execute/executemany with f-string
_EXECUTE_FSTRING = re.compile(
    r"""\.\s*(?:execute|executemany)\s*\(\s*f['"]""",
)

_PYTHON_EXTENSIONS = frozenset({".py"})


def _file_ext(path: str) -> str:
    """Get file extension including the dot."""
    dot = path.rfind(".")
    return path[dot:] if dot >= 0 else ""


def _is_comment(content: str) -> bool:
    """Check if a line is a Python comment."""
    return content.strip().startswith("#")


class SqlInjectionRule:
    """Detect SQL queries built via string interpolation."""

    id = "sql-injection-risk"
    description = "Flag SQL queries built with f-strings, %-formatting, or concatenation"
    default_severity = RuleSeverity.ERROR

    def run(self, ctx: RuleContext) -> list[RuleResult]:
        results: list[RuleResult] = []
        for f in ctx.files:
            if _file_ext(f.path) not in _PYTHON_EXTENSIONS:
                continue
            for path, lineno, content in ctx.added_lines_for(f.path):
                if _is_comment(content):
                    continue
                for pattern in (_FSTRING_SQL, _PERCENT_SQL, _CONCAT_SQL, _EXECUTE_FSTRING):
                    if pattern.search(content):
                        results.append(
                            RuleResult(
                                rule_id=self.id,
                                severity=self.default_severity,
                                message="SQL injection risk: query built from interpolated input",
                                file=path,
                                line=lineno,
                                evidence=content.strip()[:120],
                            )
                        )
                        break  # one finding per line
        return results
