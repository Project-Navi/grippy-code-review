# SPDX-License-Identifier: MIT
"""Rule 10: insecure-deserialization -- detect unsafe deserialization of untrusted data."""

from __future__ import annotations

import re

from grippy.rules.base import RuleResult, RuleSeverity
from grippy.rules.context import RuleContext

# NOTE: pickle/marshal are already covered by dangerous_sinks.py (Rule 3).
# This rule covers ADDITIONAL deserialization sinks not in that rule.

_DESER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("shelve.open — uses pickle internally", re.compile(r"\bshelve\.open\s*\(")),
    (
        "jsonpickle.decode — arbitrary object instantiation",
        re.compile(r"\bjsonpickle\.decode\s*\("),
    ),
    ("dill.loads — superset of pickle", re.compile(r"\bdill\.loads?\s*\(")),
    ("cloudpickle.loads — arbitrary code execution", re.compile(r"\bcloudpickle\.loads?\s*\(")),
]

# torch.load without weights_only=True
# NOTE: yaml.load is handled by dangerous_sinks.py (Rule 3)
_TORCH_LOAD_RE = re.compile(r"\btorch\.load\s*\(")
_TORCH_SAFE_RE = re.compile(r"\bweights_only\s*=\s*True\b")

_PYTHON_EXTENSIONS = frozenset({".py"})


def _file_ext(path: str) -> str:
    """Get file extension including the dot."""
    dot = path.rfind(".")
    return path[dot:] if dot >= 0 else ""


def _is_comment(content: str) -> bool:
    """Check if a line is a Python comment."""
    return content.strip().startswith("#")


class InsecureDeserializationRule:
    """Detect unsafe deserialization of untrusted data."""

    id = "insecure-deserialization"
    description = "Flag shelve, jsonpickle, dill, cloudpickle, and torch.load"
    default_severity = RuleSeverity.ERROR

    def run(self, ctx: RuleContext) -> list[RuleResult]:
        results: list[RuleResult] = []
        for f in ctx.files:
            if _file_ext(f.path) not in _PYTHON_EXTENSIONS:
                continue
            for path, lineno, content in ctx.added_lines_for(f.path):
                if _is_comment(content):
                    continue

                # Standard deserialization sinks
                matched = False
                for message, pattern in _DESER_PATTERNS:
                    if pattern.search(content):
                        results.append(
                            RuleResult(
                                rule_id=self.id,
                                severity=self.default_severity,
                                message=f"Insecure deserialization: {message}",
                                file=path,
                                line=lineno,
                                evidence=content.strip()[:120],
                            )
                        )
                        matched = True
                        break

                if matched:
                    continue

                # torch.load without weights_only=True
                # NOTE: yaml.load is handled by dangerous_sinks.py (Rule 3)
                if _TORCH_LOAD_RE.search(content) and not _TORCH_SAFE_RE.search(content):
                    results.append(
                        RuleResult(
                            rule_id=self.id,
                            severity=self.default_severity,
                            message=(
                                "Insecure deserialization: torch.load without weights_only=True"
                            ),
                            file=path,
                            line=lineno,
                            evidence=content.strip()[:120],
                        )
                    )
        return results
