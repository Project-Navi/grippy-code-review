# SPDX-License-Identifier: MIT
"""Tests for Grippy local git diff acquisition."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from grippy.local_diff import (
    DiffError,
    diff_stats,
    get_local_diff,
    get_repo_root,
    parse_scope,
)

# ---------------------------------------------------------------------------
# parse_scope — valid scopes
# ---------------------------------------------------------------------------


class TestParseScope:
    """Tests for parse_scope()."""

    def test_staged(self) -> None:
        assert parse_scope("staged") == ["git", "diff", "--cached"]

    def test_commit_head(self) -> None:
        assert parse_scope("commit:HEAD") == ["git", "show", "--format=", "HEAD", "--"]

    def test_commit_sha(self) -> None:
        assert parse_scope("commit:abc123def") == [
            "git",
            "show",
            "--format=",
            "abc123def",
            "--",
        ]

    def test_commit_head_tilde(self) -> None:
        assert parse_scope("commit:HEAD~3") == ["git", "show", "--format=", "HEAD~3", "--"]

    def test_range_main_head(self) -> None:
        assert parse_scope("range:main..HEAD") == ["git", "diff", "main..HEAD"]

    def test_range_head_tilde(self) -> None:
        assert parse_scope("range:HEAD~3..HEAD") == ["git", "diff", "HEAD~3..HEAD"]


# ---------------------------------------------------------------------------
# parse_scope — error cases
# ---------------------------------------------------------------------------


class TestParseScopeErrors:
    """Tests for parse_scope() error handling."""

    def test_invalid_scope(self) -> None:
        with pytest.raises(DiffError, match="Invalid scope"):
            parse_scope("something_wrong")

    def test_empty_scope(self) -> None:
        with pytest.raises(DiffError, match="Invalid scope"):
            parse_scope("")

    def test_range_missing_dotdot(self) -> None:
        with pytest.raises(DiffError, match="Invalid range"):
            parse_scope("range:mainHEAD")


# ---------------------------------------------------------------------------
# parse_scope — injection attempts
# ---------------------------------------------------------------------------


class TestParseScopeInjection:
    """Tests for parse_scope() injection prevention."""

    def test_semicolon_in_commit_ref(self) -> None:
        with pytest.raises(DiffError, match="Unsafe ref"):
            parse_scope("commit:HEAD;rm -rf /")

    def test_backtick_in_commit_ref(self) -> None:
        with pytest.raises(DiffError, match="Unsafe ref"):
            parse_scope("commit:`whoami`")

    def test_dollar_paren_in_commit_ref(self) -> None:
        with pytest.raises(DiffError, match="Unsafe ref"):
            parse_scope("commit:$(cat /etc/passwd)")

    def test_semicolon_in_range_ref(self) -> None:
        with pytest.raises(DiffError, match="Unsafe ref"):
            parse_scope("range:main;evil..HEAD")

    def test_backtick_in_range_ref(self) -> None:
        with pytest.raises(DiffError, match="Unsafe ref"):
            parse_scope("range:main..`evil`")

    def test_dollar_paren_in_range_ref(self) -> None:
        with pytest.raises(DiffError, match="Unsafe ref"):
            parse_scope("range:$(evil)..HEAD")

    def test_space_in_ref(self) -> None:
        with pytest.raises(DiffError, match="Unsafe ref"):
            parse_scope("commit:HEAD --evil")

    def test_flag_injection_commit(self) -> None:
        with pytest.raises(DiffError, match="must not start with"):
            parse_scope("commit:--no-patch")

    def test_flag_injection_single_dash(self) -> None:
        with pytest.raises(DiffError, match="must not start with"):
            parse_scope("commit:-p")

    def test_flag_injection_range(self) -> None:
        with pytest.raises(DiffError, match="must not start with"):
            parse_scope("range:--stat..HEAD")


# ---------------------------------------------------------------------------
# get_local_diff
# ---------------------------------------------------------------------------


class TestGetLocalDiff:
    """Tests for get_local_diff()."""

    def test_returns_diff_output(self) -> None:
        fake_diff = "diff --git a/foo.py b/foo.py\n+hello\n"
        result = subprocess.CompletedProcess(
            args=["git", "diff", "--cached"],
            returncode=0,
            stdout=fake_diff,
            stderr="",
        )
        with patch("grippy.local_diff.subprocess.run", return_value=result) as mock_run:
            output = get_local_diff("staged")
            assert output == fake_diff
            mock_run.assert_called_once_with(
                ["git", "diff", "--cached"],
                capture_output=True,
                text=True,
                timeout=30,
                shell=False,
            )

    def test_default_scope_is_staged(self) -> None:
        result = subprocess.CompletedProcess(
            args=["git", "diff", "--cached"],
            returncode=0,
            stdout="",
            stderr="",
        )
        with patch("grippy.local_diff.subprocess.run", return_value=result) as mock_run:
            get_local_diff()
            mock_run.assert_called_once_with(
                ["git", "diff", "--cached"],
                capture_output=True,
                text=True,
                timeout=30,
                shell=False,
            )

    def test_git_failure_raises_diff_error(self) -> None:
        result = subprocess.CompletedProcess(
            args=["git", "diff", "--cached"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )
        with patch("grippy.local_diff.subprocess.run", return_value=result):
            with pytest.raises(DiffError, match="fatal: not a git repository"):
                get_local_diff("staged")

    def test_git_timeout_raises_diff_error(self) -> None:
        with patch(
            "grippy.local_diff.subprocess.run",
            side_effect=subprocess.TimeoutExpired("git", 30),
        ):
            with pytest.raises(DiffError, match="timed out"):
                get_local_diff("staged")

    def test_empty_diff_returns_empty_string(self) -> None:
        result = subprocess.CompletedProcess(
            args=["git", "diff", "--cached"],
            returncode=0,
            stdout="",
            stderr="",
        )
        with patch("grippy.local_diff.subprocess.run", return_value=result):
            assert get_local_diff("staged") == ""


# ---------------------------------------------------------------------------
# diff_stats
# ---------------------------------------------------------------------------


class TestDiffStats:
    """Tests for diff_stats()."""

    def test_basic_counting(self) -> None:
        diff = (
            "diff --git a/foo.py b/foo.py\n"
            "index 1234567..abcdefg 100644\n"
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,3 +1,4 @@\n"
            " unchanged\n"
            "+added line 1\n"
            "+added line 2\n"
            "-removed line\n"
            " unchanged\n"
            "diff --git a/bar.py b/bar.py\n"
            "index 1234567..abcdefg 100644\n"
            "--- a/bar.py\n"
            "+++ b/bar.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-old\n"
            "+new\n"
        )
        stats = diff_stats(diff)
        assert stats == {"files": 2, "additions": 3, "deletions": 2}

    def test_empty_diff(self) -> None:
        stats = diff_stats("")
        assert stats == {"files": 0, "additions": 0, "deletions": 0}


# ---------------------------------------------------------------------------
# get_repo_root
# ---------------------------------------------------------------------------


class TestGetRepoRoot:
    """Tests for get_repo_root()."""

    def test_returns_path_in_git_repo(self) -> None:
        root = get_repo_root()
        assert root is not None
        assert (root / ".git").exists() or (root / ".git").is_file()

    def test_returns_none_outside_git(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        assert get_repo_root() is None

    def test_returns_none_on_timeout(self) -> None:
        """TimeoutExpired is caught and returns None."""
        with patch(
            "grippy.local_diff.subprocess.run",
            side_effect=subprocess.TimeoutExpired("git", 5),
        ):
            assert get_repo_root() is None

    def test_returns_none_on_os_error(self) -> None:
        """OSError (e.g. git not installed) is caught and returns None."""
        with patch(
            "grippy.local_diff.subprocess.run",
            side_effect=OSError("No such file or directory"),
        ):
            assert get_repo_root() is None
