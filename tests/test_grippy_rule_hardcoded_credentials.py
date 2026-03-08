# SPDX-License-Identifier: MIT
"""Tests for Rule 9: hardcoded-credentials."""

from __future__ import annotations

from grippy.rules.base import RuleSeverity
from grippy.rules.config import PROFILES
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.hardcoded_credentials import HardcodedCredentialsRule


def _make_diff(filename: str, added_lines: list[str]) -> str:
    body = "\n".join(f"+{line}" for line in added_lines)
    return (
        f"diff --git a/{filename} b/{filename}\n"
        f"new file mode 100644\n"
        f"--- /dev/null\n"
        f"+++ b/{filename}\n"
        f"@@ -0,0 +1,{len(added_lines)} @@\n"
        f"{body}\n"
    )


def _ctx(diff: str) -> RuleContext:
    return RuleContext(diff=diff, files=parse_diff(diff), config=PROFILES["security"])


class TestHardcodedCredentialsRule:
    def test_password_string(self) -> None:
        diff = _make_diff("config.py", ['PASSWORD = "hunter2"'])  # pragma: allowlist secret
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR

    def test_db_connection_string(self) -> None:
        diff = _make_diff(
            "db.py",
            ['DSN = "postgresql://admin:s3cret@db:5432/app"'],  # pragma: allowlist secret
        )
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 1

    def test_auth_header(self) -> None:
        diff = _make_diff(
            "api.py",
            ['headers = {"Authorization": "Bearer eyJhbGciOi..."}'],
        )
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 1

    def test_env_var_safe(self) -> None:
        diff = _make_diff("config.py", ['PASSWORD = os.environ["DB_PASSWORD"]'])
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 0

    def test_getenv_safe(self) -> None:
        diff = _make_diff("config.py", ['PASSWORD = os.getenv("DB_PASSWORD")'])
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 0

    def test_placeholder_safe(self) -> None:
        diff = _make_diff("config.py", ['PASSWORD = "changeme"'])
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 0

    def test_empty_string_safe(self) -> None:
        diff = _make_diff("config.py", ['PASSWORD = ""'])
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 0

    def test_test_dir_skipped(self) -> None:
        diff = _make_diff(
            "tests/conftest.py",
            ['PASSWORD = "testpass123"'],  # pragma: allowlist secret
        )
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 0

    def test_comment_ignored(self) -> None:
        diff = _make_diff("config.py", ['# PASSWORD = "hunter2"'])  # pragma: allowlist secret
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 0

    def test_rule_metadata(self) -> None:
        rule = HardcodedCredentialsRule()
        assert rule.id == "hardcoded-credentials"
        assert rule.default_severity == RuleSeverity.ERROR
