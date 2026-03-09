# SPDX-License-Identifier: MIT
"""Rule 9: hardcoded-credentials -- detect passwords, connection strings, and auth tokens."""

from __future__ import annotations

import re

from grippy.rules.base import RuleResult, RuleSeverity
from grippy.rules.context import RuleContext

# password/secret = "literal" (not env var, not placeholder)  # pragma: allowlist secret
_CREDENTIAL_ASSIGN = re.compile(
    r"""(?:password|passwd|pwd|secret|credential|auth_token|db_pass)\s*=\s*["'][^"']{4,}["']""",
    re.IGNORECASE,
)

# Connection strings with embedded credentials
_CONN_STRING = re.compile(
    r"""(?:postgresql|mysql|mongodb|redis|amqp|mssql)://[^:]+:[^@]+@""",
    re.IGNORECASE,
)

# Authorization header with literal token
_AUTH_HEADER = re.compile(
    r"""["']Authorization["']\s*:\s*["'](?:Bearer|Basic|Token)\s+[a-zA-Z0-9_.+/=-]{8,}""",
    re.IGNORECASE,
)

# Safe patterns — env var lookups
_ENV_VAR_RE = re.compile(r"""os\.(?:environ|getenv)\s*[(\[]""")

_PLACEHOLDERS = frozenset(
    {
        "changeme",
        "xxxx",
        "placeholder",
        "your-",
        "your_",
        "test",
        "dummy",
        "fake",
        "example",
        "todo",
        "replace",
    }
)

_PYTHON_EXTENSIONS = frozenset({".py"})


def _file_ext(path: str) -> str:
    dot = path.rfind(".")
    return path[dot:] if dot >= 0 else ""


def _is_comment(content: str) -> bool:
    return content.strip().startswith("#")


def _in_tests_dir(path: str) -> bool:
    return path.startswith("tests/") or "/tests/" in path


def _is_placeholder(content: str) -> bool:
    lower = content.lower()
    return any(p in lower for p in _PLACEHOLDERS)


def _is_empty_string(content: str) -> bool:
    return bool(re.search(r"""=\s*["']\s*["']""", content))


class HardcodedCredentialsRule:
    """Detect hardcoded passwords, connection strings, and auth tokens."""

    id = "hardcoded-credentials"
    description = "Flag hardcoded passwords, DB connection strings, and auth headers"
    default_severity = RuleSeverity.ERROR

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
                if _ENV_VAR_RE.search(content):
                    continue
                if _is_placeholder(content) or _is_empty_string(content):
                    continue
                for pattern in (_CREDENTIAL_ASSIGN, _CONN_STRING, _AUTH_HEADER):
                    if pattern.search(content):
                        results.append(
                            RuleResult(
                                rule_id=self.id,
                                severity=self.default_severity,
                                message=(
                                    "Hardcoded credential"
                                    " — use environment variables or a secrets manager"
                                ),
                                file=path,
                                line=lineno,
                                evidence=self._redact(content.strip()),
                            )
                        )
                        break
        return results

    @staticmethod
    def _redact(line: str) -> str:
        """Redact credential values from evidence."""
        return re.sub(r"""(=\s*["'])[^"']{4,}(["'])""", r"\1****\2", line)[:120]
