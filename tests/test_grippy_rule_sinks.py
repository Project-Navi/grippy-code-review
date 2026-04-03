# SPDX-License-Identifier: MIT
"""Tests for Rule 3: dangerous-execution-sinks."""

from __future__ import annotations

import signal
from collections.abc import Generator
from contextlib import contextmanager

from grippy.rules.base import RuleSeverity
from grippy.rules.config import ProfileConfig
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.dangerous_sinks import _PYTHON_SINKS, DangerousSinksRule


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


class TestDangerousSinks:
    def test_python_eval(self) -> None:
        diff = _make_diff("app.py", "result = eval(user_input)")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("eval()" in r.message for r in results)

    def test_python_exec(self) -> None:
        diff = _make_diff("app.py", "exec(code)")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("exec()" in r.message for r in results)

    def test_python_os_system(self) -> None:
        diff = _make_diff("app.py", "os.system(cmd)")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("os.system()" in r.message for r in results)

    def test_python_os_popen(self) -> None:
        diff = _make_diff("app.py", "os.popen(cmd)")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("os.popen()" in r.message for r in results)

    def test_python_subprocess_shell_true(self) -> None:
        diff = _make_diff("app.py", "subprocess.run(cmd, shell=True)")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("subprocess" in r.message and "shell=True" in r.message for r in results)

    def test_python_pickle_loads(self) -> None:
        diff = _make_diff("app.py", "data = pickle.loads(raw)")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("pickle" in r.message for r in results)

    def test_python_marshal_loads(self) -> None:
        diff = _make_diff("app.py", "data = marshal.loads(raw)")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("marshal" in r.message for r in results)

    def test_python_yaml_load_unsafe(self) -> None:
        diff = _make_diff("app.py", "data = yaml.load(content)")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("yaml.load()" in r.message for r in results)

    def test_python_yaml_load_with_safe_loader(self) -> None:
        diff = _make_diff("app.py", "data = yaml.load(content, Loader=SafeLoader)")
        results = DangerousSinksRule().run(_ctx(diff))
        assert not any("yaml.load()" in r.message for r in results)

    def test_python_yaml_safe_load(self) -> None:
        diff = _make_diff("app.py", "data = yaml.safe_load(content)")
        results = DangerousSinksRule().run(_ctx(diff))
        assert not any("yaml" in r.message.lower() for r in results)

    def test_js_eval(self) -> None:
        diff = _make_diff("app.js", "const result = eval(userInput);")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("eval()" in r.message for r in results)

    def test_js_new_function(self) -> None:
        diff = _make_diff("app.ts", "const fn = new Function(code);")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("new Function()" in r.message for r in results)

    def test_js_require_child_process(self) -> None:
        diff = _make_diff("app.js", "const cp = require('child_process');")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("child_process" in r.message for r in results)

    def test_js_exec_sync(self) -> None:
        diff = _make_diff("build.ts", "execSync(command);")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("execSync()" in r.message for r in results)

    def test_jsx_file(self) -> None:
        diff = _make_diff("component.jsx", "const x = eval(input);")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("eval()" in r.message for r in results)

    def test_tsx_file(self) -> None:
        diff = _make_diff("component.tsx", "const x = eval(input);")
        results = DangerousSinksRule().run(_ctx(diff))
        assert any("eval()" in r.message for r in results)

    def test_non_code_file_ignored(self) -> None:
        diff = _make_diff("README.md", "Use eval() to execute code")
        results = DangerousSinksRule().run(_ctx(diff))
        assert results == []

    def test_context_line_not_flagged(self) -> None:
        diff = (
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,2 +1,3 @@\n"
            " result = eval(x)\n"
            "+# comment\n"
            " other = True\n"
        )
        results = DangerousSinksRule().run(_ctx(diff))
        assert not any("eval()" in r.message for r in results)

    def test_severity_is_error(self) -> None:
        diff = _make_diff("app.py", "result = eval(x)")
        results = DangerousSinksRule().run(_ctx(diff))
        assert all(r.severity == RuleSeverity.ERROR for r in results)


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


class TestSinksReDoS:
    """Adversarial long-input tests for compiled regexes (SR-02)."""

    def test_redos_subprocess_pattern(self) -> None:
        r"""100K-char adversarial input against subprocess `.*` pattern.

        The subprocess pattern \bsubprocess\.\w+\(.*shell\s*=\s*True has `.*`
        in the middle which could theoretically cause backtracking on non-matching
        long inputs. This test proves it completes quickly.
        """
        # Get the subprocess pattern from _PYTHON_SINKS
        subprocess_pattern = next(p for name, p in _PYTHON_SINKS if "subprocess" in name)
        # Adversarial: starts matching but never completes — forces backtracking attempt
        adversarial = "subprocess.run(" + "x" * 100_000 + ")"
        with _timeout(5):
            subprocess_pattern.search(adversarial)

    def test_extremely_long_line(self) -> None:
        """>1MB added line doesn't crash the scanner."""
        long_content = "x = " + "a" * 1_100_000
        diff = _make_diff("app.py", long_content)
        results = DangerousSinksRule().run(_ctx(diff))
        assert results == []


class TestSinksReDoSStrict:
    """Strict sub-100ms timing tests for bounded subprocess shell pattern.

    Verifies that replacing .* with [^\\n]*? in the subprocess pattern
    eliminates quadratic backtracking on 50K-char adversarial lines.
    """

    def test_subprocess_pattern_50k_under_100ms(self) -> None:
        """subprocess pattern with 50K chars between ( and ) must complete in <100ms."""
        import time

        subprocess_pattern = next(p for name, p in _PYTHON_SINKS if "subprocess" in name)
        adversarial = "subprocess.run(" + "x" * 50_000 + ")"
        start = time.monotonic()
        subprocess_pattern.search(adversarial)
        elapsed_ms = (time.monotonic() - start) * 1000
        assert elapsed_ms < 100, (
            f"subprocess pattern took {elapsed_ms:.1f}ms on 50K adversarial input"
        )

    def test_subprocess_positive_still_matches(self) -> None:
        """Bounded pattern still detects subprocess with shell=True."""
        subprocess_pattern = next(p for name, p in _PYTHON_SINKS if "subprocess" in name)
        assert subprocess_pattern.search("subprocess.run(cmd, shell=True)")
        assert subprocess_pattern.search("subprocess.call(cmd, shell = True)")
        assert subprocess_pattern.search("subprocess.Popen(cmd, shell=True)")

    def test_subprocess_negative_no_shell(self) -> None:
        """subprocess without shell=True should not match."""
        subprocess_pattern = next(p for name, p in _PYTHON_SINKS if "subprocess" in name)
        assert not subprocess_pattern.search("subprocess.run(cmd)")
        assert not subprocess_pattern.search("subprocess.call(cmd, check=True)")


class TestSinksEdgeCaseFixtures:
    """Edge-case fixture categories for sinks rule."""

    def test_binary_diff_no_crash(self) -> None:
        """Binary file diffs produce no results and no crash."""
        diff = (
            "diff --git a/image.png b/image.png\n"
            "new file mode 100644\n"
            "index 0000000..abcdef1\n"
            "Binary files /dev/null and b/image.png differ\n"
        )
        results = DangerousSinksRule().run(_ctx(diff))
        assert results == []

    def test_renamed_file_still_scanned(self) -> None:
        """Dangerous sinks in renamed files are still detected."""
        diff = (
            "diff --git a/old_util.py b/new_util.py\n"
            "similarity index 90%\n"
            "rename from old_util.py\n"
            "rename to new_util.py\n"
            "--- a/old_util.py\n"
            "+++ b/new_util.py\n"
            "@@ -1,1 +1,2 @@\n"
            " existing\n"
            "+exec(code)\n"
        )
        results = DangerousSinksRule().run(_ctx(diff))
        assert len(results) >= 1

    def test_deleted_line_not_flagged(self) -> None:
        """Removed lines with dangerous sinks should not trigger findings."""
        diff = (
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,2 +1,1 @@\n"
            "-exec(code)\n"
            " other = True\n"
        )
        results = DangerousSinksRule().run(_ctx(diff))
        assert results == []
