# SPDX-License-Identifier: MIT
"""Tests for .grippyignore and # nogrip pragma."""

from __future__ import annotations

from pathlib import Path

import pathspec

from grippy.ignore import filter_diff, load_grippyignore, parse_nogrip
from grippy.rules import check_gate, load_profile, run_rules


class TestParseNogrip:
    def test_bare_nogrip(self) -> None:
        assert parse_nogrip("x = yaml.load(data)  # nogrip") is True

    def test_single_rule_id(self) -> None:
        result = parse_nogrip("x = foo()  # nogrip: sql-injection-risk")
        assert result == {"sql-injection-risk"}

    def test_multiple_rule_ids(self) -> None:
        result = parse_nogrip("x = foo()  # nogrip: sql-injection-risk, weak-crypto")
        assert result == {"sql-injection-risk", "weak-crypto"}

    def test_no_pragma(self) -> None:
        assert parse_nogrip("x = yaml.load(data)") is None

    def test_nogrip_in_string_literal(self) -> None:
        assert parse_nogrip('msg = "use # nogrip to suppress"') is None

    def test_whitespace_variations(self) -> None:
        assert parse_nogrip("x = foo()  #nogrip") is True
        assert parse_nogrip("x = foo()  #  nogrip") is True

    def test_trailing_whitespace(self) -> None:
        assert parse_nogrip("x = foo()  # nogrip   ") is True

    def test_rule_id_with_spaces(self) -> None:
        result = parse_nogrip("x = foo()  # nogrip:  sql-injection-risk ,  weak-crypto ")
        assert result == {"sql-injection-risk", "weak-crypto"}

    def test_empty_after_colon_returns_none(self) -> None:
        """Malformed targeted pragma must NOT widen to full suppression."""
        assert parse_nogrip("x = foo()  # nogrip:") is None
        assert parse_nogrip("x = foo()  # nogrip:  ") is None
        assert parse_nogrip("x = foo()  # nogrip: ,") is None


class TestLoadGrippyignore:
    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert load_grippyignore(tmp_path) is None

    def test_valid_file_returns_spec(self, tmp_path: Path) -> None:
        (tmp_path / ".grippyignore").write_text("vendor/\n*.generated.py\n")
        spec = load_grippyignore(tmp_path)
        assert spec is not None
        assert spec.match_file("vendor/lib.py")
        assert not spec.match_file("src/app.py")

    def test_negation_pattern(self, tmp_path: Path) -> None:
        (tmp_path / ".grippyignore").write_text("tests/\n!tests/test_hostile.py\n")
        spec = load_grippyignore(tmp_path)
        assert spec is not None
        assert spec.match_file("tests/test_foo.py")
        assert not spec.match_file("tests/test_hostile.py")

    def test_comments_and_blank_lines(self, tmp_path: Path) -> None:
        (tmp_path / ".grippyignore").write_text("# comment\n\nvendor/\n")
        spec = load_grippyignore(tmp_path)
        assert spec is not None
        assert spec.match_file("vendor/x.py")
        assert not spec.match_file("src/x.py")

    def test_none_root_returns_none(self) -> None:
        assert load_grippyignore(None) is None


def _two_file_diff() -> str:
    return (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,2 +1,3 @@\n"
        " import os\n"
        "+x = 1\n"
        " pass\n"
        "diff --git a/tests/test_rule.py b/tests/test_rule.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/tests/test_rule.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+import pytest\n"
        "+def test_foo(): pass\n"
    )


class TestFilterDiff:
    def test_no_matches_returns_original(self, tmp_path: Path) -> None:
        spec = load_grippyignore(tmp_path)
        diff = _two_file_diff()
        # None spec means no filtering
        assert filter_diff(diff, spec) == (diff, 0)

    def test_filters_matching_file(self, tmp_path: Path) -> None:
        (tmp_path / ".grippyignore").write_text("tests/\n")
        spec = load_grippyignore(tmp_path)
        diff = _two_file_diff()
        filtered, count = filter_diff(diff, spec)
        assert count == 1
        assert "tests/test_rule.py" not in filtered
        assert "src/app.py" in filtered

    def test_filters_all_files_returns_empty(self, tmp_path: Path) -> None:
        (tmp_path / ".grippyignore").write_text("*\n")
        spec = load_grippyignore(tmp_path)
        diff = _two_file_diff()
        filtered, count = filter_diff(diff, spec)
        assert count == 2
        assert filtered.strip() == ""

    def test_all_excluded_with_preamble_returns_empty(self) -> None:
        """Preamble before first diff header must NOT fool empty-diff checks."""
        diff = "some preamble text\n" + _two_file_diff()
        spec = pathspec.PathSpec.from_lines("gitignore", ["*"])
        filtered, count = filter_diff(diff, spec)
        assert count == 2
        assert "diff --git" not in filtered

    def test_partial_filter_preserves_preamble(self) -> None:
        diff = "some preamble\n" + _two_file_diff()
        spec = pathspec.PathSpec.from_lines("gitignore", ["tests/"])
        filtered, count = filter_diff(diff, spec)
        assert count == 1
        assert "some preamble" in filtered
        assert "src/app.py" in filtered

    def test_empty_diff(self, tmp_path: Path) -> None:
        (tmp_path / ".grippyignore").write_text("tests/\n")
        spec = load_grippyignore(tmp_path)
        filtered, count = filter_diff("", spec)
        assert count == 0
        assert filtered == ""


class TestCIIntegration:
    def test_filter_then_rules_produces_no_findings(self) -> None:
        """End-to-end: filter diff → run rules → gate should pass."""
        diff = _two_file_diff()
        spec = pathspec.PathSpec.from_lines("gitignore", ["tests/"])
        filtered, excluded = filter_diff(diff, spec)
        assert excluded == 1

        profile = load_profile(cli_profile="security")
        findings = run_rules(filtered, profile)
        # src/app.py has "x = 1" which should not trigger rules
        assert len(findings) == 0
        assert not check_gate(findings, profile)

    def test_touched_files_after_filter(self) -> None:
        """Excluded files must not appear in touched file list."""
        diff = _two_file_diff()
        spec = pathspec.PathSpec.from_lines("gitignore", ["tests/"])
        filtered, _ = filter_diff(diff, spec)
        touched = [
            line.split(" b/", 1)[1]
            for line in filtered.splitlines()
            if line.startswith("diff --git") and " b/" in line
        ]
        assert "tests/test_rule.py" not in touched
        assert "src/app.py" in touched
