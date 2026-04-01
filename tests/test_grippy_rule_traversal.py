# SPDX-License-Identifier: MIT
"""Tests for Rule 4: path-traversal-risk."""

from __future__ import annotations

import signal
from collections.abc import Generator
from contextlib import contextmanager

from grippy.rules.base import RuleSeverity
from grippy.rules.config import ProfileConfig
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.path_traversal import (
    _FILE_OPS_RE,
    _STRING_LITERAL_ONLY_RE,
    PathTraversalRule,
)


def _ctx(diff: str) -> RuleContext:
    return RuleContext(
        diff=diff,
        files=parse_diff(diff),
        config=ProfileConfig(name="security", fail_on=RuleSeverity.ERROR),
    )


def _make_diff(path: str, added_line: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1,1 +1,2 @@\n"
        " existing\n"
        f"+{added_line}\n"
    )


class TestPathTraversal:
    def test_open_with_user_input(self) -> None:
        diff = _make_diff("app.py", "f = open(user_path)")
        results = PathTraversalRule().run(_ctx(diff))
        assert any("user-controlled" in r.message for r in results)

    def test_open_with_request(self) -> None:
        diff = _make_diff("app.py", "f = open(request.form['file'])")
        results = PathTraversalRule().run(_ctx(diff))
        assert len(results) >= 1

    def test_path_join_with_input(self) -> None:
        diff = _make_diff("app.py", "p = os.path.join(base, user_input)")
        results = PathTraversalRule().run(_ctx(diff))
        assert any(r.rule_id == "path-traversal-risk" for r in results)

    def test_path_join_with_upload(self) -> None:
        diff = _make_diff("views.py", "p = path.join(upload_dir, upload_filename)")
        results = PathTraversalRule().run(_ctx(diff))
        assert len(results) >= 1

    def test_string_literal_not_flagged(self) -> None:
        diff = _make_diff("app.py", 'f = open("config.json")')
        results = PathTraversalRule().run(_ctx(diff))
        assert results == []

    def test_traversal_unix(self) -> None:
        diff = _make_diff("app.py", 'p = os.path.join(base, "../../../etc/passwd")')
        results = PathTraversalRule().run(_ctx(diff))
        assert any("traversal" in r.message.lower() for r in results)

    def test_traversal_windows(self) -> None:
        diff = _make_diff("app.py", 'p = os.path.join(base, "..\\\\..\\\\secret")')
        results = PathTraversalRule().run(_ctx(diff))
        assert any("traversal" in r.message.lower() for r in results)

    def test_non_code_file_ignored(self) -> None:
        diff = _make_diff("README.md", "open(user_path)")
        results = PathTraversalRule().run(_ctx(diff))
        assert results == []

    def test_js_file_supported(self) -> None:
        diff = _make_diff("app.js", "const f = path.join(base, user_input)")
        results = PathTraversalRule().run(_ctx(diff))
        assert len(results) >= 1

    def test_ts_file_supported(self) -> None:
        diff = _make_diff("app.ts", "const f = path.join(base, user_input)")
        results = PathTraversalRule().run(_ctx(diff))
        assert len(results) >= 1

    def test_severity_is_warn(self) -> None:
        diff = _make_diff("app.py", "f = open(user_path)")
        results = PathTraversalRule().run(_ctx(diff))
        assert all(r.severity == RuleSeverity.WARN for r in results)

    def test_no_taint_indicator_not_flagged(self) -> None:
        diff = _make_diff("app.py", "f = open(config_path)")
        results = PathTraversalRule().run(_ctx(diff))
        assert results == []


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


class TestTraversalReDoS:
    def test_redos_file_ops_re(self) -> None:
        """100K-char adversarial input against _FILE_OPS_RE completes quickly."""
        adversarial = "open(" + "x" * 100_000
        with _timeout(5):
            _FILE_OPS_RE.search(adversarial)

    def test_redos_string_literal_only_re(self) -> None:
        """100K-char input with no closing quote forces [^"']* to scan full input."""
        adversarial = 'open( "' + "x" * 100_000
        with _timeout(5):
            _STRING_LITERAL_ONLY_RE.search(adversarial)

    def test_extremely_long_line(self) -> None:
        """>1MB added line through full rule.run() produces no crash or findings."""
        long_line = "x" * 1_100_000
        diff = _make_diff("app.py", long_line)
        results = PathTraversalRule().run(_ctx(diff))
        assert results == []


class TestTraversalEdgeCaseFixtures:
    """Edge-case fixture categories for path traversal rule."""

    def test_binary_diff_no_crash(self) -> None:
        """Binary file diffs produce no results and no crash."""
        diff = (
            "diff --git a/image.png b/image.png\n"
            "new file mode 100644\n"
            "index 0000000..abcdef1\n"
            "Binary files /dev/null and b/image.png differ\n"
        )
        results = PathTraversalRule().run(_ctx(diff))
        assert results == []

    def test_renamed_file_still_scanned(self) -> None:
        """Path traversal in renamed files is still detected."""
        diff = (
            "diff --git a/old_handler.py b/new_handler.py\n"
            "similarity index 90%\n"
            "rename from old_handler.py\n"
            "rename to new_handler.py\n"
            "--- a/old_handler.py\n"
            "+++ b/new_handler.py\n"
            "@@ -1,1 +1,2 @@\n"
            " existing\n"
            "+f = open(user_path)\n"
        )
        results = PathTraversalRule().run(_ctx(diff))
        assert len(results) >= 1

    def test_deleted_line_not_flagged(self) -> None:
        """Removed lines with path traversal should not trigger findings."""
        diff = (
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,2 +1,1 @@\n"
            "-f = open(user_path)\n"
            " other = True\n"
        )
        results = PathTraversalRule().run(_ctx(diff))
        assert results == []
