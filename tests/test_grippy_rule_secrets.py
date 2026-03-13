# SPDX-License-Identifier: MIT
"""Tests for Rule 2: secrets-in-diff."""

from __future__ import annotations

import time

from grippy.rules.base import RuleSeverity
from grippy.rules.config import ProfileConfig
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.secrets_in_diff import SecretsInDiffRule


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


class TestSecretsInDiff:
    def test_aws_key(self) -> None:
        diff = _make_diff("config.py", 'AWS_KEY = "AKIAIOSFODNN7ABCDEFG"')
        results = SecretsInDiffRule().run(_ctx(diff))
        assert any(r.severity == RuleSeverity.CRITICAL and "AWS" in r.message for r in results)

    def test_github_classic_pat(self) -> None:
        diff = _make_diff("setup.py", 'token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"')
        results = SecretsInDiffRule().run(_ctx(diff))
        assert any("GitHub classic PAT" in r.message for r in results)

    def test_github_fine_grained_pat(self) -> None:
        diff = _make_diff("setup.py", 'token = "github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZab"')
        results = SecretsInDiffRule().run(_ctx(diff))
        assert any("GitHub fine-grained PAT" in r.message for r in results)

    def test_github_other_tokens(self) -> None:
        for prefix in ("gho_", "ghu_", "ghs_", "ghr_"):
            diff = _make_diff(
                "config.py", f'token = "{prefix}ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"'
            )
            results = SecretsInDiffRule().run(_ctx(diff))
            assert any(r.severity == RuleSeverity.CRITICAL for r in results), f"Failed for {prefix}"

    def test_openai_key(self) -> None:
        diff = _make_diff("config.py", 'api_key = "sk-abcdefghijklmnopqrstuvwxyz"')
        results = SecretsInDiffRule().run(_ctx(diff))
        assert any("OpenAI" in r.message for r in results)

    def test_private_key_header(self) -> None:
        diff = _make_diff("certs/key.pem", "-----BEGIN RSA PRIVATE KEY-----")
        results = SecretsInDiffRule().run(_ctx(diff))
        assert any(
            r.severity == RuleSeverity.CRITICAL and "Private key" in r.message for r in results
        )

    def test_generic_secret_assignment(self) -> None:
        diff = _make_diff("config.py", 'password = "supersecretvalue123"')
        results = SecretsInDiffRule().run(_ctx(diff))
        assert any("Generic secret" in r.message for r in results)

    def test_env_file_addition(self) -> None:
        diff = _make_diff(".env", "DB_PASSWORD=hunter2")
        results = SecretsInDiffRule().run(_ctx(diff))
        assert any(r.severity == RuleSeverity.WARN and ".env" in r.message for r in results)

    def test_comment_line_skipped(self) -> None:
        diff = _make_diff("config.py", '# token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"')
        results = SecretsInDiffRule().run(_ctx(diff))
        assert not any("GitHub" in r.message for r in results)

    def test_placeholder_skipped(self) -> None:
        diff = _make_diff("config.py", 'token = "changeme"')
        results = SecretsInDiffRule().run(_ctx(diff))
        assert not any("Generic secret" in r.message for r in results)

    def test_placeholder_your_dash_skipped(self) -> None:
        diff = _make_diff("config.py", 'api_key = "your-api-key-here"')
        results = SecretsInDiffRule().run(_ctx(diff))
        assert not any("Generic secret" in r.message for r in results)

    def test_tests_directory_skipped(self) -> None:
        diff = _make_diff("tests/test_auth.py", 'token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"')
        results = SecretsInDiffRule().run(_ctx(diff))
        assert results == []

    def test_context_line_not_flagged(self) -> None:
        diff = (
            "diff --git a/config.py b/config.py\n"
            "--- a/config.py\n"
            "+++ b/config.py\n"
            "@@ -1,2 +1,3 @@\n"
            ' token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"\n'
            "+# new comment\n"
            " other = True\n"
        )
        results = SecretsInDiffRule().run(_ctx(diff))
        assert not any("GitHub" in r.message for r in results)

    def test_evidence_is_redacted(self) -> None:
        diff = _make_diff("config.py", "AKIAIOSFODNN7EXAMPLE_LONGKEY")
        results = SecretsInDiffRule().run(_ctx(diff))
        for r in results:
            if r.evidence and "AKIA" in r.evidence:
                assert r.evidence.endswith("...")
                assert len(r.evidence) < 20


# ── SR-02: ReDoS adversarial tests (100K+ char lines) ────────────────────────

_REDOS_BUDGET_SECONDS = 1.0


def _timed_run(diff: str) -> tuple[list, float]:
    """Run rule and return (results, elapsed_seconds)."""
    rule = SecretsInDiffRule()
    ctx = _ctx(diff)
    start = time.monotonic()
    results = rule.run(ctx)
    elapsed = time.monotonic() - start
    return results, elapsed


class TestReDoS:
    """SR-02: No regex pattern is vulnerable to catastrophic backtracking.

    Each test feeds a 100K+ character adversarial line designed to stress
    a specific pattern, then asserts the rule completes within budget.
    """

    def test_private_key_header_no_terminator(self) -> None:
        """BEGIN header followed by 100K chars with no END marker."""
        payload = "-----BEGIN " + "A" * 100_000
        diff = _make_diff("key.pem", payload)
        _, elapsed = _timed_run(diff)
        assert elapsed < _REDOS_BUDGET_SECONDS

    def test_private_key_header_repeated_almost_match(self) -> None:
        """Repeated near-matches for the private key pattern."""
        # Pattern: -----BEGIN.*PRIVATE KEY-----
        payload = ("-----BEGIN " + "PRIVATE KEY----" + " ") * 5000
        diff = _make_diff("key.pem", payload)
        _, elapsed = _timed_run(diff)
        assert elapsed < _REDOS_BUDGET_SECONDS

    def test_aws_key_prefix_flood(self) -> None:
        """AKIA prefix repeated without valid suffix."""
        payload = "AKIA" + "!" * 100_000  # ! is not [0-9A-Z]
        diff = _make_diff("config.py", payload)
        _, elapsed = _timed_run(diff)
        assert elapsed < _REDOS_BUDGET_SECONDS

    def test_github_pat_open_quantifier(self) -> None:
        """github_pat_ prefix with 100K alphanumeric chars ({22,} quantifier)."""
        # pragma: allowlist secret
        payload = "github_pat_" + "A" * 100_000
        diff = _make_diff("config.py", payload)
        results, elapsed = _timed_run(diff)
        assert elapsed < _REDOS_BUDGET_SECONDS
        assert any("fine-grained" in r.message for r in results)

    def test_openai_key_open_quantifier(self) -> None:
        """sk- prefix with 100K alphanumeric chars ({20,} quantifier)."""
        # pragma: allowlist secret
        payload = "sk-" + "a" * 100_000
        diff = _make_diff("config.py", payload)
        results, elapsed = _timed_run(diff)
        assert elapsed < _REDOS_BUDGET_SECONDS
        assert any("OpenAI" in r.message for r in results)

    def test_generic_secret_long_value(self) -> None:
        """Generic pattern with 100K char value after assignment."""
        payload = "token=" + "Z1a2B3c4D5e6" * 8334  # ~100K, no placeholder substrings
        diff = _make_diff("config.py", payload)
        results, elapsed = _timed_run(diff)
        assert elapsed < _REDOS_BUDGET_SECONDS
        assert any("Generic secret" in r.message for r in results)

    def test_generic_secret_whitespace_flood(self) -> None:
        r"""100K whitespace between keyword and = (stress \s* quantifier)."""
        payload = "token" + " " * 100_000 + '="valid_secret_value_here"'
        diff = _make_diff("config.py", payload)
        _, elapsed = _timed_run(diff)
        assert elapsed < _REDOS_BUDGET_SECONDS

    def test_no_match_100k_random(self) -> None:
        """100K chars with no secret patterns — pure scan overhead."""
        payload = "x" * 100_000
        diff = _make_diff("config.py", payload)
        _, elapsed = _timed_run(diff)
        assert elapsed < _REDOS_BUDGET_SECONDS

    def test_many_near_miss_lines(self) -> None:
        """1000 lines of near-miss patterns — linear not quadratic."""
        lines = []
        for i in range(1000):
            lines.append(f"+token{i} = short")  # too short for {12,}
        diff = (
            "diff --git a/config.py b/config.py\n"
            "--- a/config.py\n"
            "+++ b/config.py\n"
            f"@@ -1,1 +1,{len(lines) + 1} @@\n"
            " existing\n" + "\n".join(lines) + "\n"
        )
        _, elapsed = _timed_run(diff)
        assert elapsed < _REDOS_BUDGET_SECONDS


# ── SR-09: Fixture matrix edge cases ─────────────────────────────────────────


class TestFixtureMatrixEdgeCases:
    """SR-09: Additional fixture categories beyond positive/negative basics."""

    def test_renamed_file_still_scanned(self) -> None:
        """Secrets in renamed files are still detected."""
        diff = (
            "diff --git a/old_config.py b/new_config.py\n"
            "similarity index 90%\n"
            "rename from old_config.py\n"
            "rename to new_config.py\n"
            "--- a/old_config.py\n"
            "+++ b/new_config.py\n"
            "@@ -1,1 +1,2 @@\n"
            " existing\n"
            '+token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"\n'  # pragma: allowlist secret
        )
        results = SecretsInDiffRule().run(_ctx(diff))
        assert any("GitHub classic PAT" in r.message for r in results)

    def test_binary_diff_no_crash(self) -> None:
        """Binary file diffs produce no results and no crash."""
        diff = (
            "diff --git a/image.png b/image.png\n"
            "new file mode 100644\n"
            "index 0000000..abcdef1\n"
            "Binary files /dev/null and b/image.png differ\n"
        )
        results = SecretsInDiffRule().run(_ctx(diff))
        assert results == []

    def test_submodule_diff_no_crash(self) -> None:
        """Submodule pointer change produces no results."""
        diff = (
            "diff --git a/vendor/lib b/vendor/lib\n"
            "index abc1234..def5678 160000\n"
            "--- a/vendor/lib\n"
            "+++ b/vendor/lib\n"
            "@@ -1 +1 @@\n"
            "-Subproject commit abc1234abc1234abc1234abc1234abc1234abc123\n"
            "+Subproject commit def5678def5678def5678def5678def5678def567\n"
        )
        results = SecretsInDiffRule().run(_ctx(diff))
        assert results == []

    def test_multiple_secrets_same_line_first_wins(self) -> None:
        """Only one finding per line (break after first match)."""
        line = "AKIAIOSFODNN7ABCDEFG sk-abcdefghijklmnopqrstuvwxyz"  # pragma: allowlist secret
        diff = _make_diff("config.py", line)
        results = SecretsInDiffRule().run(_ctx(diff))
        assert len(results) == 1

    def test_near_miss_aws_key_wrong_length(self) -> None:
        """AKIA prefix with only 15 chars (needs 16) should not match."""
        diff = _make_diff("config.py", 'key = "AKIAIOSFODNN7ABC"')  # 15 after AKIA
        results = SecretsInDiffRule().run(_ctx(diff))
        assert not any("AWS" in r.message for r in results)

    def test_near_miss_ghp_wrong_length(self) -> None:
        """ghp_ prefix with 35 chars (needs 36) should not match."""
        # pragma: allowlist secret
        diff = _make_diff("config.py", 'token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"')  # 35
        results = SecretsInDiffRule().run(_ctx(diff))
        assert not any("GitHub classic PAT" in r.message for r in results)

    def test_deleted_line_not_flagged(self) -> None:
        """Removed lines with secrets should not trigger findings."""
        diff = (
            "diff --git a/config.py b/config.py\n"
            "--- a/config.py\n"
            "+++ b/config.py\n"
            "@@ -1,2 +1,1 @@\n"
            '-token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"\n'
            " other = True\n"
        )
        results = SecretsInDiffRule().run(_ctx(diff))
        assert results == []

    def test_nested_tests_dir_skipped(self) -> None:
        """Deeply nested tests/ path is still skipped."""
        diff = _make_diff(
            "src/myapp/tests/integration/test_auth.py",
            'token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"',
        )
        results = SecretsInDiffRule().run(_ctx(diff))
        assert results == []

    def test_env_file_nested_path(self) -> None:
        """Nested .env file (deploy/.env) is detected."""
        diff = _make_diff("deploy/.env", "SECRET_KEY=longsecretvalue123456")
        results = SecretsInDiffRule().run(_ctx(diff))
        assert any(".env" in r.message for r in results)

    def test_slash_slash_comment_skipped(self) -> None:
        """C-style // comments are skipped."""
        diff = _make_diff("config.js", '// token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"')
        results = SecretsInDiffRule().run(_ctx(diff))
        assert results == []

    def test_star_comment_skipped(self) -> None:
        """Block comment * lines are skipped."""
        diff = _make_diff("config.java", '* token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"')
        results = SecretsInDiffRule().run(_ctx(diff))
        assert results == []

    def test_all_placeholders_suppressed(self) -> None:
        """Each placeholder keyword in _PLACEHOLDERS is actually suppressed."""
        placeholders = [
            "changeme",
            "xxxx_placeholder",
            "example_value_long",
            "placeholder_value_x",
            "your-api-key-value",
            "your_api_key_value",
            "test_dummy_secret_x",
            "dummy_value_xxxxxx",
            "fake_credential_xx",
            "mock_secret_valuex",
            "sample_token_value",
            "todo_replace_this_",
            "fixme_secret_value",
            "replace_me_xxxxxxx",
        ]
        for placeholder in placeholders:
            diff = _make_diff("config.py", f'token = "{placeholder}"')
            results = SecretsInDiffRule().run(_ctx(diff))
            assert not any("Generic secret" in r.message for r in results), (
                f"Placeholder not suppressed: {placeholder}"
            )

    def test_short_redaction(self) -> None:
        """Values <= 8 chars are redacted to first 4 chars."""
        assert SecretsInDiffRule._redact("AKIA1234") == "AKIA..."

    def test_long_redaction(self) -> None:
        """Values > 8 chars show first 8 chars."""
        assert SecretsInDiffRule._redact("AKIAIOSFODNN7") == "AKIAIOSF..."
