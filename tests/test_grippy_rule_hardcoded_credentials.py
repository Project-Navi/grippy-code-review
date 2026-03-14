# SPDX-License-Identifier: MIT
"""Tests for Rule 9: hardcoded-credentials."""

from __future__ import annotations

import signal
from collections.abc import Generator
from contextlib import contextmanager

from grippy.rules.base import RuleSeverity
from grippy.rules.config import PROFILES
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.hardcoded_credentials import (
    _AUTH_HEADER,
    _CONN_STRING,
    _CREDENTIAL_ASSIGN,
    HardcodedCredentialsRule,
)


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


# -- Timeout helper for ReDoS tests ------------------------------------------


@contextmanager
def _timeout(seconds: int) -> Generator[None, None, None]:
    """Raise TimeoutError if block takes longer than *seconds*."""

    def _handler(signum: int, frame: object) -> None:
        msg = f"ReDoS timeout: regex took >{seconds}s"
        raise TimeoutError(msg)

    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


# -- SR-02: ReDoS safety tests -----------------------------------------------


class TestCredsReDoS:
    def test_redos_credential_assign(self) -> None:
        """100K-char adversarial input against _CREDENTIAL_ASSIGN."""
        adversarial = 'password = "' + "x" * 100_000 + '"'  # pragma: allowlist secret
        with _timeout(5):
            _CREDENTIAL_ASSIGN.search(adversarial)

    def test_redos_conn_string(self) -> None:
        """100K-char adversarial input against _CONN_STRING."""
        adversarial = "postgresql://" + "x" * 100_000 + "@"
        with _timeout(5):
            _CONN_STRING.search(adversarial)

    def test_redos_auth_header(self) -> None:
        """100K-char adversarial input against _AUTH_HEADER."""
        adversarial = '"Authorization": "Bearer ' + "x" * 100_000 + '"'
        with _timeout(5):
            _AUTH_HEADER.search(adversarial)

    def test_extremely_long_line(self) -> None:
        """>1MB added line through full rule.run() produces no crash or findings."""
        long_line = "x" * 1_100_000
        diff = _make_diff("config.py", [long_line])
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert results == []


# -- SR-07: Redaction tests ---------------------------------------------------


class TestCredsRedaction:
    def test_password_value_redacted(self) -> None:
        """SR-07: password values must be redacted in finding evidence."""
        diff = _make_diff(
            "config.py",
            ['PASSWORD = "hunter2secret"'],  # pragma: allowlist secret
        )
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 1
        assert "hunter2secret" not in results[0].evidence
        assert "****" in results[0].evidence

    def test_conn_string_value_redacted(self) -> None:
        """SR-07: connection string credentials must be redacted."""
        diff = _make_diff(
            "db.py",
            ['DSN = "postgresql://admin:s3cret@db:5432/app"'],  # pragma: allowlist secret
        )
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 1
        assert "s3cret" not in results[0].evidence
        assert "****" in results[0].evidence

    def test_auth_header_token_redacted(self) -> None:
        """SR-07: auth header tokens must not appear in finding evidence."""
        diff = _make_diff(
            "api.py",
            [
                'headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9"}'
            ],  # pragma: allowlist secret
        )
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 1
        assert "eyJhbGciOiJIUzI1NiJ9" not in results[0].evidence


# -- SR-01: Pattern coverage tests --------------------------------------------


class TestCredsPatternCoverage:
    def test_mysql_conn_string(self) -> None:
        diff = _make_diff(
            "db.py",
            ['DSN = "mysql://admin:s3cret@db:3306/app"'],  # pragma: allowlist secret
        )
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 1

    def test_basic_auth_header(self) -> None:
        diff = _make_diff(
            "api.py",
            ['headers = {"Authorization": "Basic dXNlcjpwYXNzd29yZA=="}'],
        )
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 1

    def test_secret_keyword(self) -> None:
        diff = _make_diff(
            "config.py",
            ['SECRET = "mysecretvalue123"'],  # pragma: allowlist secret
        )
        results = HardcodedCredentialsRule().run(_ctx(diff))
        assert len(results) == 1
