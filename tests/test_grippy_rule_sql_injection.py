# SPDX-License-Identifier: MIT
"""Tests for Rule 7: sql-injection-risk."""

from __future__ import annotations

import signal
from collections.abc import Generator
from contextlib import contextmanager

from grippy.rules.base import RuleSeverity
from grippy.rules.config import PROFILES
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.sql_injection import (
    _CONCAT_SQL,
    _FSTRING_SQL,
    _PERCENT_SQL,
    SqlInjectionRule,
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


class TestSqlInjectionRule:
    def test_fstring_select(self) -> None:
        diff = _make_diff("app.py", ['query = f"SELECT * FROM users WHERE id = {user_id}"'])
        results = SqlInjectionRule().run(_ctx(diff))
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR
        assert "SQL" in results[0].message

    def test_format_string_query(self) -> None:
        diff = _make_diff("app.py", ['q = "DELETE FROM t WHERE id = %s" % uid'])
        results = SqlInjectionRule().run(_ctx(diff))
        assert len(results) == 1

    def test_concat_query(self) -> None:
        diff = _make_diff("app.py", ['q = "SELECT * FROM t WHERE name = \'" + name + "\'"'])
        results = SqlInjectionRule().run(_ctx(diff))
        assert len(results) == 1

    def test_execute_with_fstring(self) -> None:
        diff = _make_diff("app.py", ['cursor.execute(f"INSERT INTO t VALUES ({v})")'])
        results = SqlInjectionRule().run(_ctx(diff))
        assert len(results) == 1

    def test_parameterized_safe(self) -> None:
        diff = _make_diff("app.py", ['cursor.execute("SELECT * FROM t WHERE id = %s", (uid,))'])
        results = SqlInjectionRule().run(_ctx(diff))
        assert len(results) == 0

    def test_sqlalchemy_text_safe(self) -> None:
        diff = _make_diff("app.py", ['session.execute(text("SELECT 1"))'])
        results = SqlInjectionRule().run(_ctx(diff))
        assert len(results) == 0

    def test_non_python_ignored(self) -> None:
        diff = _make_diff("app.js", ["const q = `SELECT * FROM t WHERE id = ${id}`"])
        results = SqlInjectionRule().run(_ctx(diff))
        assert len(results) == 0

    def test_comment_ignored(self) -> None:
        diff = _make_diff("app.py", ['# query = f"SELECT * FROM users WHERE id = {user_id}"'])
        results = SqlInjectionRule().run(_ctx(diff))
        assert len(results) == 0

    def test_multiple_findings(self) -> None:
        diff = _make_diff(
            "app.py",
            [
                'q1 = f"SELECT * FROM a WHERE id = {x}"',
                'q2 = f"DELETE FROM b WHERE id = {y}"',
            ],
        )
        results = SqlInjectionRule().run(_ctx(diff))
        assert len(results) == 2

    def test_rule_metadata(self) -> None:
        rule = SqlInjectionRule()
        assert rule.id == "sql-injection-risk"
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


class TestSqlReDoS:
    def test_redos_percent_sql_near_miss(self) -> None:
        """Near-miss adversarial input: repeated near-keyword fragments inside quotes.

        Forces the engine to repeatedly reconsider \\bSELECT\\b boundary matches
        and fail late on the 100K-char input.
        """
        adversarial = '"' + ("sel " * 25_000) + '"'
        with _timeout(5):
            _PERCENT_SQL.search(adversarial)

    def test_redos_percent_sql_keyword_no_trail(self) -> None:
        """Real SQL keyword present early but trailing % condition never arrives.

        Forces .* after keyword to consume entire 100K-char input before failing.
        """
        adversarial = '"SELECT * FROM t WHERE id = 1' + ("x" * 100_000) + '"'
        with _timeout(5):
            _PERCENT_SQL.search(adversarial)

    def test_redos_concat_sql(self) -> None:
        """Same near-miss input against _CONCAT_SQL — same backtracking risk profile."""
        adversarial = '"' + ("sel " * 25_000) + '"'
        with _timeout(5):
            _CONCAT_SQL.search(adversarial)

    def test_redos_fstring_sql(self) -> None:
        """100K-char input against _FSTRING_SQL — lower risk but should prove safe."""
        adversarial = 'f"' + "x" * 100_000 + '"'
        with _timeout(5):
            _FSTRING_SQL.search(adversarial)

    def test_extremely_long_line(self) -> None:
        """>1MB added line through full rule.run() produces no crash or findings."""
        long_line = "x" * 1_100_000
        diff = _make_diff("app.py", [long_line])
        results = SqlInjectionRule().run(_ctx(diff))
        assert results == []
