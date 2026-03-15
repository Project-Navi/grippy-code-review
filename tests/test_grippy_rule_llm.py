# SPDX-License-Identifier: MIT
"""Tests for Rule 5: llm-output-unsanitized."""

from __future__ import annotations

import signal
from collections.abc import Generator
from contextlib import contextmanager

from grippy.rules.base import RuleSeverity
from grippy.rules.config import ProfileConfig
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.llm_output_sinks import (
    _MODEL_OUTPUT_RE,
    _SINK_RE,
    SANITIZERS,
    LlmOutputSinksRule,
)


def _ctx(diff: str) -> RuleContext:
    return RuleContext(
        diff=diff,
        files=parse_diff(diff),
        config=ProfileConfig(name="security", fail_on=RuleSeverity.ERROR),
    )


def _make_diff(path: str, *added_lines: str) -> str:
    lines = [
        f"diff --git a/{path} b/{path}\n",
        f"--- a/{path}\n",
        f"+++ b/{path}\n",
        f"@@ -1,1 +1,{len(added_lines) + 1} @@\n",
        " existing\n",
    ]
    for line in added_lines:
        lines.append(f"+{line}\n")
    return "".join(lines)


class TestLlmOutputSinks:
    def test_direct_pipe_to_comment(self) -> None:
        diff = _make_diff(
            "bot.py",
            "    result = agent.run(prompt)",
            "    pr.create_issue_comment(result.content)",
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert any(r.rule_id == "llm-output-unsanitized" for r in results)

    def test_sanitized_output_not_flagged(self) -> None:
        diff = _make_diff(
            "bot.py",
            "    result = agent.run(prompt)",
            "    safe = sanitize(result.content)",
            "    pr.create_issue_comment(safe)",
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert not any(r.rule_id == "llm-output-unsanitized" for r in results)

    def test_html_escape_suppresses(self) -> None:
        diff = _make_diff(
            "bot.py",
            "    result = agent.run(prompt)",
            "    safe = html.escape(result.content)",
            "    pr.create_issue_comment(safe)",
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert not any(r.rule_id == "llm-output-unsanitized" for r in results)

    def test_completion_to_post(self) -> None:
        diff = _make_diff(
            "handler.py",
            "    completion = model.generate(prompt)",
            "    post(completion)",
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert any(r.rule_id == "llm-output-unsanitized" for r in results)

    def test_choices_to_body(self) -> None:
        diff = _make_diff(
            "handler.py",
            "    text = response.choices[0].text",
            "    comment.body = text",
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert any(r.rule_id == "llm-output-unsanitized" for r in results)

    def test_no_model_output_not_flagged(self) -> None:
        diff = _make_diff(
            "handler.py",
            "    text = 'hello world'",
            "    pr.create_issue_comment(text)",
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert results == []

    def test_non_python_file_ignored(self) -> None:
        diff = _make_diff(
            "handler.js",
            "    const result = agent.run(prompt);",
            "    pr.create_issue_comment(result.content);",
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert results == []

    def test_severity_is_error(self) -> None:
        diff = _make_diff(
            "bot.py",
            "    result = agent.run(prompt)",
            "    pr.create_issue_comment(result.content)",
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert all(r.severity == RuleSeverity.ERROR for r in results)

    def test_sanitizers_frozenset(self) -> None:
        assert isinstance(SANITIZERS, frozenset)
        assert "sanitize" in SANITIZERS
        assert "html.escape" in SANITIZERS
        assert "_sanitize_comment_text" in SANITIZERS


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


class TestLlmSinksReDoS:
    def test_redos_model_output_re(self) -> None:
        """100K-char adversarial input against _MODEL_OUTPUT_RE completes quickly."""
        adversarial = "content" + "x" * 100_000
        with _timeout(5):
            _MODEL_OUTPUT_RE.search(adversarial)

    def test_redos_sink_re(self) -> None:
        """100K-char adversarial input against _SINK_RE completes quickly."""
        adversarial = "create_comment(" + "x" * 100_000
        with _timeout(5):
            _SINK_RE.search(adversarial)

    def test_extremely_long_line(self) -> None:
        """>1MB added line through full rule.run() produces no crash or findings."""
        long_line = "x" * 1_100_000
        diff = _make_diff("bot.py", long_line)
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert results == []


# -- SR-01: Pattern coverage tests (closes untested entries) ------------------


class TestLlmSinksPatternCoverage:
    def test_chat_to_comment(self) -> None:
        """'.chat(' model output token → create_issue_comment sink."""
        diff = _make_diff(
            "bot.py",
            "    result = client.chat(messages)",
            "    pr.create_issue_comment(result.content)",
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert any(r.rule_id == "llm-output-unsanitized" for r in results)

    def test_sink_create_comment(self) -> None:
        """'.run(' model output → 'create_comment(' sink."""
        diff = _make_diff(
            "bot.py",
            "    result = agent.run(prompt)",
            "    pr.create_comment(body=result.content)",
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert any(r.rule_id == "llm-output-unsanitized" for r in results)

    def test_sink_render(self) -> None:
        """'.generate(' model output → 'render(' sink."""
        diff = _make_diff(
            "handler.py",
            "    text = model.generate(prompt)",
            "    return render(text)",
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert any(r.rule_id == "llm-output-unsanitized" for r in results)

    def test_sink_fstring_html(self) -> None:
        """'.content' model output → 'f\"<' sink."""
        diff = _make_diff(
            "render.py",
            "    result = agent.run(prompt)",
            '    html = f"<div>{result.content}</div>"',
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert any(r.rule_id == "llm-output-unsanitized" for r in results)


class TestLlmSinksEdgeCaseFixtures:
    """Edge-case fixture categories for LLM output sinks rule."""

    def test_binary_diff_no_crash(self) -> None:
        """Binary file diffs produce no results and no crash."""
        diff = (
            "diff --git a/image.png b/image.png\n"
            "new file mode 100644\n"
            "index 0000000..abcdef1\n"
            "Binary files /dev/null and b/image.png differ\n"
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert results == []

    def test_renamed_file_still_scanned(self) -> None:
        """LLM sinks in renamed files are still detected."""
        diff = (
            "diff --git a/old_bot.py b/new_bot.py\n"
            "similarity index 90%\n"
            "rename from old_bot.py\n"
            "rename to new_bot.py\n"
            "--- a/old_bot.py\n"
            "+++ b/new_bot.py\n"
            "@@ -1,1 +1,3 @@\n"
            " existing\n"
            "+    result = agent.run(prompt)\n"
            "+    pr.create_issue_comment(result.content)\n"
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert any(r.rule_id == "llm-output-unsanitized" for r in results)

    def test_deleted_line_not_flagged(self) -> None:
        """Removed lines with LLM sinks should not trigger findings."""
        diff = (
            "diff --git a/bot.py b/bot.py\n"
            "--- a/bot.py\n"
            "+++ b/bot.py\n"
            "@@ -1,3 +1,1 @@\n"
            "-    result = agent.run(prompt)\n"
            "-    pr.create_issue_comment(result.content)\n"
            " other = True\n"
        )
        results = LlmOutputSinksRule().run(_ctx(diff))
        assert results == []
