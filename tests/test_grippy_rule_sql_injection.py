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

    def test_hyphenated_keyword_not_sql(self) -> None:
        """Hyphenated compound words containing SQL keywords are not SQL."""
        diff = _make_diff(
            "review.py",
            [
                'f.write(f"merge-blocking={str(val).lower()}\\n")',
                'f.write(f"create-date={date}\\n")',
                'f.write(f"drop-down-menu={menu}\\n")',
            ],
        )
        results = SqlInjectionRule().run(_ctx(diff))
        assert len(results) == 0

    def test_real_merge_still_detected(self) -> None:
        """Actual SQL MERGE statement is still flagged."""
        diff = _make_diff("app.py", ['q = f"MERGE INTO target USING source ON {cond}"'])
        results = SqlInjectionRule().run(_ctx(diff))
        assert len(results) == 1

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


class TestSqlReDoSStrict:
    """Strict sub-100ms timing tests for bounded SQL regex patterns.

    These verify that replacing .* with [^'\"\\n]* eliminates quadratic
    backtracking on 50K-char adversarial lines.
    """

    def test_fstring_sql_50k_under_100ms(self) -> None:
        """_FSTRING_SQL with .format( prefix and 50K chars must complete in <100ms."""
        import time

        adversarial = ".format(" + "x" * 50_000
        start = time.monotonic()
        _FSTRING_SQL.search(adversarial)
        elapsed_ms = (time.monotonic() - start) * 1000
        assert elapsed_ms < 100, f"_FSTRING_SQL took {elapsed_ms:.1f}ms on 50K adversarial input"

    def test_percent_sql_50k_under_100ms(self) -> None:
        """_PERCENT_SQL with SQL keyword + 50K padding must complete in <100ms."""
        import time

        adversarial = '"SELECT ' + "x" * 50_000 + '"'
        start = time.monotonic()
        _PERCENT_SQL.search(adversarial)
        elapsed_ms = (time.monotonic() - start) * 1000
        assert elapsed_ms < 100, f"_PERCENT_SQL took {elapsed_ms:.1f}ms on 50K adversarial input"

    def test_concat_sql_50k_under_100ms(self) -> None:
        """_CONCAT_SQL with SQL keyword + 50K padding must complete in <100ms."""
        import time

        adversarial = '"SELECT ' + "x" * 50_000 + '" +'
        start = time.monotonic()
        _CONCAT_SQL.search(adversarial)
        elapsed_ms = (time.monotonic() - start) * 1000
        assert elapsed_ms < 100, f"_CONCAT_SQL took {elapsed_ms:.1f}ms on 50K adversarial input"

    def test_positive_fstring_still_matches(self) -> None:
        """Bounded patterns still detect f-string SQL injection."""
        assert _FSTRING_SQL.search('query = f"SELECT * FROM users WHERE id = {uid}"')
        assert _FSTRING_SQL.search("q = f'INSERT INTO t VALUES ({v})'")
        assert _FSTRING_SQL.search('.format( "SELECT * FROM t" )')

    def test_positive_percent_still_matches(self) -> None:
        """Bounded patterns still detect %-format SQL injection."""
        assert _PERCENT_SQL.search('"SELECT * FROM users WHERE id = %s" % uid')

    def test_positive_concat_still_matches(self) -> None:
        """Bounded patterns still detect concatenation SQL injection."""
        assert _CONCAT_SQL.search('"SELECT * FROM t WHERE name = " + name')
        assert _CONCAT_SQL.search('+ "SELECT * FROM t"')


class TestSqlEdgeCaseFixtures:
    """Edge-case fixture categories for SQL injection rule."""

    def test_binary_diff_no_crash(self) -> None:
        """Binary file diffs produce no results and no crash."""
        diff = (
            "diff --git a/image.png b/image.png\n"
            "new file mode 100644\n"
            "index 0000000..abcdef1\n"
            "Binary files /dev/null and b/image.png differ\n"
        )
        results = SqlInjectionRule().run(_ctx(diff))
        assert results == []

    def test_renamed_file_still_scanned(self) -> None:
        """SQL injection in renamed files is still detected."""
        diff = (
            "diff --git a/old_db.py b/new_db.py\n"
            "similarity index 90%\n"
            "rename from old_db.py\n"
            "rename to new_db.py\n"
            "--- a/old_db.py\n"
            "+++ b/new_db.py\n"
            "@@ -1,1 +1,2 @@\n"
            " existing\n"
            '+query = f"SELECT * FROM users WHERE id = {user_id}"\n'
        )
        results = SqlInjectionRule().run(_ctx(diff))
        assert len(results) >= 1

    def test_deleted_line_not_flagged(self) -> None:
        """Removed SQL injection lines should not trigger findings."""
        diff = (
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,2 +1,1 @@\n"
            '-query = f"SELECT * FROM users WHERE id = {user_id}"\n'
            " other = True\n"
        )
        results = SqlInjectionRule().run(_ctx(diff))
        assert results == []
