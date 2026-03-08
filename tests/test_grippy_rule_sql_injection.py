# SPDX-License-Identifier: MIT
"""Tests for Rule 7: sql-injection-risk."""

from __future__ import annotations

from grippy.rules.base import RuleSeverity
from grippy.rules.config import PROFILES
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.sql_injection import SqlInjectionRule


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
