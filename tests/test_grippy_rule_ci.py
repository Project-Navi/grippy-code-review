# SPDX-License-Identifier: MIT
"""Tests for Rule 6: ci-script-execution-risk."""

from __future__ import annotations

import signal
from collections.abc import Generator
from contextlib import contextmanager

from grippy.rules.base import RuleSeverity
from grippy.rules.ci_script_risk import _PIPE_EXEC_RE, CiScriptRiskRule
from grippy.rules.config import ProfileConfig
from grippy.rules.context import RuleContext, parse_diff


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


class TestCiScriptRisk:
    def test_curl_pipe_bash(self) -> None:
        diff = _make_diff(
            ".github/workflows/ci.yml",
            "      run: curl -sSL https://example.com/install.sh | bash",
        )
        results = CiScriptRiskRule().run(_ctx(diff))
        assert any(
            r.severity == RuleSeverity.CRITICAL and "pipe" in r.message.lower() for r in results
        )

    def test_wget_pipe_sh(self) -> None:
        diff = _make_diff(
            ".github/workflows/ci.yml",
            "      run: wget -O- https://example.com/install.sh | sh",
        )
        results = CiScriptRiskRule().run(_ctx(diff))
        assert any(r.severity == RuleSeverity.CRITICAL for r in results)

    def test_sudo_in_workflow(self) -> None:
        diff = _make_diff(
            ".github/workflows/ci.yml",
            "      run: sudo apt-get install -y package",
        )
        results = CiScriptRiskRule().run(_ctx(diff))
        assert any(r.severity == RuleSeverity.WARN and "sudo" in r.message for r in results)

    def test_chmod_x(self) -> None:
        diff = _make_diff("scripts/deploy.sh", "chmod +x deploy.sh")
        results = CiScriptRiskRule().run(_ctx(diff))
        assert any(r.severity == RuleSeverity.WARN and "chmod" in r.message for r in results)

    def test_dockerfile(self) -> None:
        diff = _make_diff("Dockerfile", "RUN curl https://example.com/install.sh | bash")
        results = CiScriptRiskRule().run(_ctx(diff))
        assert any(r.severity == RuleSeverity.CRITICAL for r in results)

    def test_makefile(self) -> None:
        diff = _make_diff("Makefile", "\tsudo make install")
        results = CiScriptRiskRule().run(_ctx(diff))
        assert any("sudo" in r.message for r in results)

    def test_shell_script(self) -> None:
        diff = _make_diff("scripts/setup.sh", "curl https://get.example.com | bash")
        results = CiScriptRiskRule().run(_ctx(diff))
        assert any(r.severity == RuleSeverity.CRITICAL for r in results)

    def test_bash_extension(self) -> None:
        diff = _make_diff("deploy.bash", "sudo systemctl restart app")
        results = CiScriptRiskRule().run(_ctx(diff))
        assert any("sudo" in r.message for r in results)

    def test_non_ci_file_ignored(self) -> None:
        diff = _make_diff("app.py", "# curl https://example.com | bash")
        results = CiScriptRiskRule().run(_ctx(diff))
        assert results == []

    def test_context_line_not_flagged(self) -> None:
        diff = (
            "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
            "--- a/.github/workflows/ci.yml\n"
            "+++ b/.github/workflows/ci.yml\n"
            "@@ -1,2 +1,3 @@\n"
            " existing: curl https://example.com | bash\n"
            "+# new comment\n"
            " other: true\n"
        )
        results = CiScriptRiskRule().run(_ctx(diff))
        assert not any(r.severity == RuleSeverity.CRITICAL for r in results)


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


class TestCiRiskReDoS:
    def test_redos_pipe_exec_re(self) -> None:
        """100K-char adversarial input against _PIPE_EXEC_RE (has .*) completes quickly.

        Input has 'curl' match but no trailing '| sh', forcing .* to scan the entire
        100K-char string before failing.
        """
        adversarial = "curl " + "x" * 100_000
        with _timeout(5):
            _PIPE_EXEC_RE.search(adversarial)

    def test_extremely_long_line(self) -> None:
        """>1MB added line through full rule.run() produces no crash or findings."""
        long_line = "x" * 1_100_000
        diff = _make_diff(".github/workflows/ci.yml", long_line)
        results = CiScriptRiskRule().run(_ctx(diff))
        assert results == []


# -- SR-09: Specificity negatives ---------------------------------------------


class TestCiRiskNegatives:
    def test_curl_download_without_pipe(self) -> None:
        """curl downloading a file (no pipe to sh) should NOT be CRITICAL."""
        diff = _make_diff(
            ".github/workflows/ci.yml",
            "      run: curl -sSL https://example.com/file.tar.gz -o file.tar.gz",
        )
        results = CiScriptRiskRule().run(_ctx(diff))
        assert not any(r.severity == RuleSeverity.CRITICAL for r in results)

    def test_pseudo_sudo_not_flagged(self) -> None:
        """A word containing 'sudo' as substring should not match."""
        diff = _make_diff(
            ".github/workflows/ci.yml",
            "      run: echo pseudocode",
        )
        results = CiScriptRiskRule().run(_ctx(diff))
        assert results == []
