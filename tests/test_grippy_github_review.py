# SPDX-License-Identifier: MIT
"""Tests for Grippy GitHub Review API integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from grippy.github_review import ThreadRef
from grippy.schema import Finding

# --- Helpers ---


def _make_finding(
    *,
    file: str = "src/app.py",
    line_start: int = 10,
    title: str = "Test finding",
    severity: str = "HIGH",
    category: str = "security",
) -> Finding:
    return Finding(
        id="F-001",
        severity=severity,
        confidence=90,
        category=category,
        file=file,
        line_start=line_start,
        line_end=line_start + 5,
        title=title,
        description="A test finding description.",
        suggestion="Fix this issue.",
        evidence="evidence here",
        grippy_note="Grippy says fix it.",
    )


# --- parse_diff_lines ---


class TestParseDiffLines:
    """parse_diff_lines extracts addressable RIGHT-side lines from unified diff."""

    def test_simple_addition(self) -> None:
        from grippy.github_review import parse_diff_lines

        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -10,3 +10,4 @@ def main():\n"
            "     existing_line\n"
            "+    new_line\n"
            "     another_existing\n"
            "+    another_new\n"
        )
        result = parse_diff_lines(diff)
        assert "src/app.py" in result
        assert 11 in result["src/app.py"]
        assert 13 in result["src/app.py"]

    def test_multiple_files(self) -> None:
        from grippy.github_review import parse_diff_lines

        diff = (
            "diff --git a/a.py b/a.py\n"
            "--- a/a.py\n"
            "+++ b/a.py\n"
            "@@ -1,2 +1,3 @@\n"
            " line1\n"
            "+added\n"
            " line2\n"
            "diff --git a/b.py b/b.py\n"
            "--- a/b.py\n"
            "+++ b/b.py\n"
            "@@ -5,2 +5,3 @@\n"
            " old\n"
            "+new\n"
            " old2\n"
        )
        result = parse_diff_lines(diff)
        assert "a.py" in result
        assert "b.py" in result
        assert 2 in result["a.py"]
        assert 6 in result["b.py"]

    def test_empty_diff(self) -> None:
        from grippy.github_review import parse_diff_lines

        result = parse_diff_lines("")
        assert result == {}

    def test_deletion_only_not_addressable(self) -> None:
        from grippy.github_review import parse_diff_lines

        diff = (
            "diff --git a/x.py b/x.py\n"
            "--- a/x.py\n"
            "+++ b/x.py\n"
            "@@ -1,3 +1,2 @@\n"
            " keep\n"
            "-removed\n"
            " keep2\n"
        )
        result = parse_diff_lines(diff)
        assert "x.py" in result
        lines = result["x.py"]
        assert 1 in lines
        assert 2 in lines

    def test_new_file(self) -> None:
        from grippy.github_review import parse_diff_lines

        diff = (
            "diff --git a/new.py b/new.py\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/new.py\n"
            "@@ -0,0 +1,3 @@\n"
            "+line1\n"
            "+line2\n"
            "+line3\n"
        )
        result = parse_diff_lines(diff)
        assert "new.py" in result
        assert result["new.py"] == {1, 2, 3}

    def test_hunk_context_lines_addressable(self) -> None:
        """Context lines (unchanged) within a hunk are also addressable."""
        from grippy.github_review import parse_diff_lines

        diff = (
            "diff --git a/f.py b/f.py\n"
            "--- a/f.py\n"
            "+++ b/f.py\n"
            "@@ -10,5 +10,6 @@ class Foo:\n"
            "     def bar(self):\n"
            "         pass\n"
            "+        new_code()\n"
            "     def baz(self):\n"
            "         pass\n"
        )
        result = parse_diff_lines(diff)
        assert 10 in result["f.py"]
        assert 12 in result["f.py"]  # the added line
        assert 14 in result["f.py"]


# --- classify_findings ---


class TestClassifyFindings:
    """classify_findings splits findings into inline-eligible and off-diff."""

    def test_finding_on_diff_line_is_inline(self) -> None:
        from grippy.github_review import classify_findings

        diff_lines = {"src/app.py": {10, 11, 12}}
        findings = [_make_finding(file="src/app.py", line_start=10)]
        inline, off_diff = classify_findings(findings, diff_lines)
        assert len(inline) == 1
        assert len(off_diff) == 0

    def test_finding_off_diff_goes_to_off_diff(self) -> None:
        from grippy.github_review import classify_findings

        diff_lines = {"src/app.py": {10, 11, 12}}
        findings = [_make_finding(file="src/app.py", line_start=99)]
        inline, off_diff = classify_findings(findings, diff_lines)
        assert len(inline) == 0
        assert len(off_diff) == 1

    def test_finding_in_unmodified_file_is_off_diff(self) -> None:
        from grippy.github_review import classify_findings

        diff_lines = {"src/other.py": {1, 2}}
        findings = [_make_finding(file="src/app.py", line_start=10)]
        inline, off_diff = classify_findings(findings, diff_lines)
        assert len(inline) == 0
        assert len(off_diff) == 1


# --- build_review_comment ---


class TestBuildReviewComment:
    """build_review_comment creates PyGithub-compatible comment dicts."""

    def test_comment_has_required_fields(self) -> None:
        from grippy.github_review import build_review_comment

        finding = _make_finding()
        comment = build_review_comment(finding)
        assert "path" in comment
        assert "body" in comment
        assert "line" in comment
        assert "side" in comment

    def test_comment_path_matches_finding_file(self) -> None:
        from grippy.github_review import build_review_comment

        finding = _make_finding(file="src/auth.py")
        comment = build_review_comment(finding)
        assert comment["path"] == "src/auth.py"

    def test_comment_line_matches_finding_line_start(self) -> None:
        from grippy.github_review import build_review_comment

        finding = _make_finding(line_start=42)
        comment = build_review_comment(finding)
        assert comment["line"] == 42

    def test_comment_body_contains_severity_and_title(self) -> None:
        from grippy.github_review import build_review_comment

        finding = _make_finding(severity="CRITICAL", title="Buffer overflow")
        comment = build_review_comment(finding)
        assert "CRITICAL" in comment["body"]
        assert "Buffer overflow" in comment["body"]

    def test_comment_body_contains_grippy_marker(self) -> None:
        from grippy.github_review import build_review_comment

        finding = _make_finding(file="src/app.py", category="security", line_start=10)
        comment = build_review_comment(finding)
        assert "<!-- grippy:src/app.py:security:10:" in comment["body"]

    def test_comment_side_is_right(self) -> None:
        from grippy.github_review import build_review_comment

        finding = _make_finding()
        comment = build_review_comment(finding)
        assert comment["side"] == "RIGHT"


# --- format_summary_comment ---


class TestFormatSummary:
    """format_summary_comment builds the compact PR dashboard."""

    def test_contains_score_and_verdict(self) -> None:
        from grippy.github_review import format_summary_comment

        result = format_summary_comment(
            score=85,
            verdict="PASS",
            finding_count=3,
            new_count=2,
            resolved_count=0,
            off_diff_findings=[],
            head_sha="abc123",
            pr_number=6,
        )
        assert "85/100" in result
        assert "PASS" in result

    def test_contains_delta_section(self) -> None:
        from grippy.github_review import format_summary_comment

        result = format_summary_comment(
            score=75,
            verdict="PASS",
            finding_count=4,
            new_count=2,
            resolved_count=3,
            off_diff_findings=[],
            head_sha="abc123",
            pr_number=6,
        )
        assert "2 new" in result
        assert "3 resolved" in result

    def test_contains_summary_marker(self) -> None:
        from grippy.github_review import format_summary_comment

        result = format_summary_comment(
            score=80,
            verdict="PASS",
            finding_count=0,
            new_count=0,
            resolved_count=0,
            off_diff_findings=[],
            head_sha="abc",
            pr_number=6,
        )
        assert "<!-- grippy-summary-6 -->" in result

    def test_off_diff_findings_in_collapsible(self) -> None:
        from grippy.github_review import format_summary_comment

        off_diff = [_make_finding(file="config.yaml", line_start=99)]
        result = format_summary_comment(
            score=70,
            verdict="PASS",
            finding_count=1,
            new_count=1,
            resolved_count=0,
            off_diff_findings=off_diff,
            head_sha="abc",
            pr_number=6,
        )
        assert "<details>" in result
        assert "config.yaml" in result
        assert "Test finding" in result

    def test_diff_truncated_notice(self) -> None:
        """diff_truncated=True adds a truncation notice to the summary."""
        from grippy.github_review import format_summary_comment

        result = format_summary_comment(
            score=85,
            verdict="PASS",
            finding_count=0,
            new_count=0,
            resolved_count=0,
            off_diff_findings=[],
            head_sha="abc",
            pr_number=7,
            diff_truncated=True,
        )
        assert "truncated" in result.lower()
        assert "Some files may not have been reviewed" in result

    def test_policy_bypassed_warning(self) -> None:
        """policy_bypassed=True adds a warning annotation to the summary."""
        from grippy.github_review import format_summary_comment

        result = format_summary_comment(
            score=80,
            verdict="PASS",
            finding_count=0,
            new_count=0,
            resolved_count=0,
            off_diff_findings=[],
            head_sha="abc",
            pr_number=8,
            policy_bypassed=True,
        )
        assert "Output policy was bypassed" in result
        assert "unfiltered" in result.lower()

    def test_display_capped_annotation(self) -> None:
        """display_capped_count > 0 adds an omission annotation."""
        from grippy.github_review import format_summary_comment

        result = format_summary_comment(
            score=70,
            verdict="FAIL",
            finding_count=5,
            new_count=5,
            resolved_count=0,
            off_diff_findings=[],
            head_sha="abc",
            pr_number=9,
            display_capped_count=3,
        )
        assert "3 additional finding(s) omitted for brevity" in result

    def test_summary_only_findings_section(self) -> None:
        """summary_only_findings renders in a collapsible details section."""
        from grippy.github_review import format_summary_comment

        summary_only = [_make_finding(file="src/utils.py", title="Weak hash usage")]
        result = format_summary_comment(
            score=70,
            verdict="FAIL",
            finding_count=1,
            new_count=1,
            resolved_count=0,
            off_diff_findings=[],
            head_sha="abc",
            pr_number=10,
            summary_only_findings=summary_only,
        )
        assert "Summary-only findings (1)" in result
        assert "scored but not inline-eligible" in result
        assert "Weak hash usage" in result
        assert "src/utils.py" in result


# --- build_review_comment snippet rendering ---


class TestBuildReviewCommentEvidence:
    """build_review_comment renders evidence as a fenced code block."""

    def test_evidence_rendered_as_code_block(self) -> None:
        from grippy.github_review import build_review_comment

        finding = _make_finding(title="SQL injection")
        comment = build_review_comment(finding)
        body = comment["body"]
        assert "```\nevidence here\n```" in body

    def test_empty_evidence_no_code_block(self) -> None:
        from grippy.github_review import build_review_comment

        finding = _make_finding(title="Missing check")
        # Finding with whitespace-only evidence
        finding_dict = finding.model_dump()
        finding_dict["evidence"] = "   "
        finding_with_empty = Finding(**finding_dict)
        comment = build_review_comment(finding_with_empty)
        body = comment["body"]
        assert "```" not in body


# --- fetch_grippy_comments ---


class TestFetchGrippyComments:
    """fetch_grippy_comments queries GraphQL reviewThreads for grippy markers."""

    @patch("grippy.github_review.subprocess.run")
    def test_parses_markers_from_thread_bodies(self, mock_run: MagicMock) -> None:
        import json

        from grippy.github_review import fetch_grippy_comments

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": [
                                        {
                                            "id": "PRRT_1",
                                            "comments": {
                                                "nodes": [
                                                    {
                                                        "body": "text\n<!-- grippy:src/app.py:security:10 -->"
                                                    }
                                                ]
                                            },
                                        },
                                        {
                                            "id": "PRRT_2",
                                            "comments": {
                                                "nodes": [
                                                    {
                                                        "body": "text\n<!-- grippy:lib/utils.py:logic:20 -->"
                                                    }
                                                ]
                                            },
                                        },
                                    ],
                                }
                            }
                        }
                    }
                }
            ),
        )
        result = fetch_grippy_comments(repo="org/repo", pr_number=1)
        assert len(result) == 2
        assert ("src/app.py", "security", 10, None) in result
        assert ("lib/utils.py", "logic", 20, None) in result
        ref1 = result[("src/app.py", "security", 10, None)]
        assert isinstance(ref1, ThreadRef)
        assert ref1.node_id == "PRRT_1"

    @patch("grippy.github_review.subprocess.run")
    def test_ignores_non_grippy_threads(self, mock_run: MagicMock) -> None:
        import json

        from grippy.github_review import fetch_grippy_comments

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": [
                                        {
                                            "id": "PRRT_other",
                                            "comments": {
                                                "nodes": [{"body": "Just a regular comment."}]
                                            },
                                        }
                                    ],
                                }
                            }
                        }
                    }
                }
            ),
        )
        result = fetch_grippy_comments(repo="org/repo", pr_number=1)
        assert len(result) == 0

    @patch("grippy.github_review.subprocess.run")
    def test_empty_threads_returns_empty(self, mock_run: MagicMock) -> None:
        import json

        from grippy.github_review import fetch_grippy_comments

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": [],
                                }
                            }
                        }
                    }
                }
            ),
        )
        result = fetch_grippy_comments(repo="org/repo", pr_number=1)
        assert len(result) == 0

    @patch("grippy.github_review.subprocess.run")
    def test_subprocess_failure_returns_empty(self, mock_run: MagicMock) -> None:
        from grippy.github_review import fetch_grippy_comments

        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        result = fetch_grippy_comments(repo="org/repo", pr_number=1)
        assert len(result) == 0

    @patch("grippy.github_review.subprocess.run")
    def test_paginates_when_has_next_page(self, mock_run: MagicMock) -> None:
        import json

        from grippy.github_review import fetch_grippy_comments

        page1 = json.dumps(
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"},
                                "nodes": [
                                    {
                                        "id": "PRRT_1",
                                        "comments": {
                                            "nodes": [
                                                {"body": "text\n<!-- grippy:a.py:security:10 -->"}
                                            ]
                                        },
                                    }
                                ],
                            }
                        }
                    }
                }
            }
        )
        page2 = json.dumps(
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                                "nodes": [
                                    {
                                        "id": "PRRT_2",
                                        "comments": {
                                            "nodes": [
                                                {"body": "text\n<!-- grippy:b.py:logic:20 -->"}
                                            ]
                                        },
                                    }
                                ],
                            }
                        }
                    }
                }
            }
        )
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=page1),
            MagicMock(returncode=0, stdout=page2),
        ]
        result = fetch_grippy_comments(repo="org/repo", pr_number=1)
        assert len(result) == 2
        assert ("a.py", "security", 10, None) in result
        assert ("b.py", "logic", 20, None) in result
        assert mock_run.call_count == 2
        # Verify cursor from page 1 was forwarded to page 2 call
        second_call_cmd = mock_run.call_args_list[1][0][0]
        assert "cursor=cursor1" in second_call_cmd

    @patch("grippy.github_review.subprocess.run")
    def test_null_nodes_skipped(self, mock_run: MagicMock) -> None:
        """Null nodes in GraphQL response are skipped without error."""
        import json

        from grippy.github_review import fetch_grippy_comments

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": [
                                        None,
                                        {
                                            "id": "PRRT_1",
                                            "comments": {
                                                "nodes": [
                                                    {
                                                        "body": "text\n<!-- grippy:a.py:security:1 -->"
                                                    }
                                                ]
                                            },
                                        },
                                    ],
                                }
                            }
                        }
                    }
                }
            ),
        )
        result = fetch_grippy_comments(repo="org/repo", pr_number=1)
        assert len(result) == 1

    @patch("grippy.github_review.subprocess.run")
    def test_empty_comments_skipped(self, mock_run: MagicMock) -> None:
        """Threads with empty comments list are skipped."""
        import json

        from grippy.github_review import fetch_grippy_comments

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": [
                                        {
                                            "id": "PRRT_empty",
                                            "comments": {"nodes": []},
                                        },
                                    ],
                                }
                            }
                        }
                    }
                }
            ),
        )
        result = fetch_grippy_comments(repo="org/repo", pr_number=1)
        assert len(result) == 0

    @patch("grippy.github_review.subprocess.run")
    def test_graphql_exception_returns_partial(self, mock_run: MagicMock) -> None:
        """Exception during GraphQL fetch returns results gathered so far."""
        from grippy.github_review import fetch_grippy_comments

        mock_run.side_effect = Exception("network error")
        result = fetch_grippy_comments(repo="org/repo", pr_number=1)
        assert result == {}


# --- post_review ---


class TestPostReview:
    """post_review creates PR review with inline comments + summary."""

    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_creates_review_with_inline_comments(
        self, mock_fetch: MagicMock, mock_github_cls: MagicMock
    ) -> None:
        from grippy.github_review import post_review

        mock_fetch.return_value = {}
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []
        mock_pr.head.repo.full_name = "org/repo"
        mock_pr.base.repo.full_name = "org/repo"

        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -8,3 +8,4 @@\n"
            " line\n"
            "+new_line\n"
            " line2\n"
        )
        findings = [_make_finding(file="src/app.py", line_start=9)]

        post_review(
            token="test-token",
            repo="org/repo",
            pr_number=1,
            findings=findings,
            head_sha="abc123",
            diff=diff,
            score=80,
            verdict="PASS",
        )

        assert mock_pr.create_review.call_count == 2
        # First call: inline COMMENT
        first_call = mock_pr.create_review.call_args_list[0]
        assert first_call.kwargs["event"] == "COMMENT"
        assert len(first_call.kwargs["comments"]) == 1
        # Second call: APPROVE verdict
        second_call = mock_pr.create_review.call_args_list[1]
        assert second_call.kwargs["event"] == "APPROVE"

    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_off_diff_findings_in_summary_only(
        self, mock_fetch: MagicMock, mock_github_cls: MagicMock
    ) -> None:
        from grippy.github_review import post_review

        mock_fetch.return_value = {}
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []
        mock_pr.head.repo.full_name = "org/repo"
        mock_pr.base.repo.full_name = "org/repo"

        diff = (
            "diff --git a/other.py b/other.py\n"
            "--- a/other.py\n+++ b/other.py\n"
            "@@ -1,2 +1,3 @@\n line\n+new\n line\n"
        )
        findings = [_make_finding(file="src/app.py", line_start=99)]  # not in diff

        post_review(
            token="test-token",
            repo="org/repo",
            pr_number=1,
            findings=findings,
            head_sha="abc123",
            diff=diff,
            score=70,
            verdict="PASS",
        )

        # No inline comments, but APPROVE verdict still posted
        mock_pr.create_review.assert_called_once()
        assert mock_pr.create_review.call_args.kwargs["event"] == "APPROVE"
        mock_pr.create_issue_comment.assert_called_once()
        body = mock_pr.create_issue_comment.call_args[0][0]
        assert "Off-diff findings" in body

    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_summary_comment_upserted(
        self, mock_fetch: MagicMock, mock_github_cls: MagicMock
    ) -> None:
        from grippy.github_review import post_review

        mock_fetch.return_value = {}
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr

        existing_comment = MagicMock()
        existing_comment.body = "old stuff\n<!-- grippy-summary-1 -->"
        mock_pr.get_issue_comments.return_value = [existing_comment]

        post_review(
            token="test-token",
            repo="org/repo",
            pr_number=1,
            findings=[],
            head_sha="abc",
            diff="",
            score=90,
            verdict="PASS",
        )

        existing_comment.edit.assert_called_once()
        mock_pr.create_issue_comment.assert_not_called()

    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_fork_pr_skips_inline_comments(
        self, mock_fetch: MagicMock, mock_github_cls: MagicMock
    ) -> None:
        """Fork PRs put all findings in summary, no inline review."""
        from grippy.github_review import post_review

        mock_fetch.return_value = {}
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []
        mock_pr.head.repo.full_name = "forker/repo"
        mock_pr.base.repo.full_name = "org/repo"

        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n+++ b/src/app.py\n"
            "@@ -8,3 +8,4 @@\n line\n+new\n line2\n"
        )
        findings = [_make_finding(file="src/app.py", line_start=9)]

        post_review(
            token="test-token",
            repo="org/repo",
            pr_number=1,
            findings=findings,
            head_sha="abc",
            diff=diff,
            score=75,
            verdict="PASS",
        )

        # No inline comments, but APPROVE verdict posted
        mock_pr.create_review.assert_called_once()
        assert mock_pr.create_review.call_args.kwargs["event"] == "APPROVE"
        mock_pr.create_issue_comment.assert_called_once()

    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_skips_existing_comment_matching_finding(
        self, mock_fetch: MagicMock, mock_github_cls: MagicMock
    ) -> None:
        """Findings matching existing grippy comments are not re-posted."""
        from grippy.github_review import post_review

        mock_fetch.return_value = {
            ("src/app.py", "security", 9, None): ThreadRef(
                node_id="PRRT_1",
                body="old\n<!-- grippy:src/app.py:security:9 -->",
            ),
        }
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []
        mock_pr.head.repo.full_name = "org/repo"
        mock_pr.base.repo.full_name = "org/repo"

        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n+++ b/src/app.py\n"
            "@@ -8,3 +8,4 @@\n line\n+new_line\n line2\n"
        )
        finding = _make_finding(file="src/app.py", line_start=9, category="security")

        post_review(
            token="test-token",
            repo="org/repo",
            pr_number=1,
            findings=[finding],
            head_sha="abc123",
            diff=diff,
            score=80,
            verdict="PASS",
        )

        # No inline comments (finding exists), but APPROVE verdict posted
        mock_pr.create_review.assert_called_once()
        assert mock_pr.create_review.call_args.kwargs["event"] == "APPROVE"

    @patch("grippy.github_review.resolve_threads")
    @patch("grippy.github_review.fetch_thread_states")
    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_resolves_absent_outdated_findings(
        self,
        mock_fetch: MagicMock,
        mock_github_cls: MagicMock,
        mock_fetch_states: MagicMock,
        mock_resolve: MagicMock,
    ) -> None:
        """Absent findings marked outdated by GitHub get their threads resolved."""
        from grippy.github_review import post_review

        mock_fetch.return_value = {
            ("old.py", "logic", 5, None): ThreadRef(
                node_id="PRRT_old",
                body="old\n<!-- grippy:old.py:logic:5 -->",
            ),
        }
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []
        mock_pr.head.repo.full_name = "org/repo"
        mock_pr.base.repo.full_name = "org/repo"
        mock_resolve.return_value = 1
        mock_fetch_states.return_value = {
            "PRRT_old": {"isOutdated": True, "isResolved": False},
        }

        post_review(
            token="test-token",
            repo="org/repo",
            pr_number=1,
            findings=[],
            head_sha="abc",
            diff="",
            score=90,
            verdict="PASS",
        )

        mock_resolve.assert_called_once()
        call_kwargs = mock_resolve.call_args[1]
        assert "PRRT_old" in call_kwargs["thread_ids"]

    @patch("grippy.github_review.resolve_threads")
    @patch("grippy.github_review.fetch_thread_states")
    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_resolves_absent_even_if_not_outdated(
        self,
        mock_fetch: MagicMock,
        mock_github_cls: MagicMock,
        mock_fetch_states: MagicMock,
        mock_resolve: MagicMock,
    ) -> None:
        """Absent findings are resolved even when GitHub hasn't marked them outdated."""
        from grippy.github_review import post_review

        mock_fetch.return_value = {
            ("old.py", "logic", 5, None): ThreadRef(
                node_id="PRRT_still_valid",
                body="old\n<!-- grippy:old.py:logic:5 -->",
            ),
        }
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []
        mock_pr.head.repo.full_name = "org/repo"
        mock_pr.base.repo.full_name = "org/repo"
        mock_fetch_states.return_value = {
            "PRRT_still_valid": {"isOutdated": False, "isResolved": False},
        }

        post_review(
            token="test-token",
            repo="org/repo",
            pr_number=1,
            findings=[],
            head_sha="abc",
            diff="",
            score=90,
            verdict="PASS",
        )

        mock_resolve.assert_called_once()

    @patch("grippy.github_review.resolve_threads")
    @patch("grippy.github_review.fetch_thread_states")
    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_skips_already_resolved_threads(
        self,
        mock_fetch: MagicMock,
        mock_github_cls: MagicMock,
        mock_fetch_states: MagicMock,
        mock_resolve: MagicMock,
    ) -> None:
        """Threads already resolved by GitHub are not re-resolved."""
        from grippy.github_review import post_review

        mock_fetch.return_value = {
            ("old.py", "logic", 5, None): ThreadRef(
                node_id="PRRT_done",
                body="old\n<!-- grippy:old.py:logic:5 -->",
            ),
        }
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []
        mock_pr.head.repo.full_name = "org/repo"
        mock_pr.base.repo.full_name = "org/repo"
        mock_fetch_states.return_value = {
            "PRRT_done": {"isOutdated": True, "isResolved": True},
        }

        post_review(
            token="test-token",
            repo="org/repo",
            pr_number=1,
            findings=[],
            head_sha="abc",
            diff="",
            score=90,
            verdict="PASS",
        )

        mock_resolve.assert_not_called()

    @patch("grippy.github_review.resolve_threads")
    @patch("grippy.github_review.fetch_thread_states")
    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_summary_only_findings_protect_threads(
        self,
        mock_fetch: MagicMock,
        mock_github_cls: MagicMock,
        mock_fetch_states: MagicMock,
        mock_resolve: MagicMock,
    ) -> None:
        """Summary-only findings are still active — their threads are NOT resolved."""
        from grippy.github_review import post_review

        summary_finding = _make_finding(file="old.py", category="logic", line_start=5)
        mock_fetch.return_value = {
            ("old.py", "logic", 5, None): ThreadRef(
                node_id="PRRT_summary",
                body="old\n<!-- grippy:old.py:logic:5 -->",
            ),
        }
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []
        mock_pr.head.repo.full_name = "org/repo"
        mock_pr.base.repo.full_name = "org/repo"

        post_review(
            token="test-token",
            repo="org/repo",
            pr_number=1,
            findings=[],
            head_sha="abc",
            diff="",
            score=85,
            verdict="PASS",
            summary_only_findings=[summary_finding],
        )

        # Thread should NOT be resolved — finding is still active (summary-only)
        mock_resolve.assert_not_called()


# --- verdict review (APPROVE / REQUEST_CHANGES) ---


class TestVerdictReview:
    """post_review submits APPROVE on PASS, REQUEST_CHANGES on FAIL."""

    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_pass_submits_approve(self, mock_fetch: MagicMock, mock_github_cls: MagicMock) -> None:
        from grippy.github_review import post_review

        mock_fetch.return_value = {}
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []

        post_review(
            token="t",
            repo="o/r",
            pr_number=1,
            findings=[],
            head_sha="a",
            diff="",
            score=92,
            verdict="PASS",
        )

        mock_pr.create_review.assert_called_once()
        assert mock_pr.create_review.call_args.kwargs["event"] == "APPROVE"
        assert "92/100" in mock_pr.create_review.call_args.kwargs["body"]

    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_fail_submits_request_changes(
        self, mock_fetch: MagicMock, mock_github_cls: MagicMock
    ) -> None:
        from grippy.github_review import post_review

        mock_fetch.return_value = {}
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []

        post_review(
            token="t",
            repo="o/r",
            pr_number=1,
            findings=[],
            head_sha="a",
            diff="",
            score=45,
            verdict="FAIL",
        )

        mock_pr.create_review.assert_called_once()
        assert mock_pr.create_review.call_args.kwargs["event"] == "REQUEST_CHANGES"
        assert "45/100" in mock_pr.create_review.call_args.kwargs["body"]

    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_provisional_skips_verdict_review(
        self, mock_fetch: MagicMock, mock_github_cls: MagicMock
    ) -> None:
        from grippy.github_review import post_review

        mock_fetch.return_value = {}
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []

        post_review(
            token="t",
            repo="o/r",
            pr_number=1,
            findings=[],
            head_sha="a",
            diff="",
            score=70,
            verdict="PROVISIONAL",
        )

        mock_pr.create_review.assert_not_called()

    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_verdict_review_failure_is_non_fatal(
        self, mock_fetch: MagicMock, mock_github_cls: MagicMock
    ) -> None:
        from github import GithubException

        from grippy.github_review import post_review

        mock_fetch.return_value = {}
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []
        mock_pr.create_review.side_effect = GithubException(403, {"message": "Forbidden"}, None)

        # Should NOT raise — verdict review is non-fatal
        post_review(
            token="t",
            repo="o/r",
            pr_number=1,
            findings=[],
            head_sha="a",
            diff="",
            score=90,
            verdict="PASS",
        )

        mock_pr.create_issue_comment.assert_called_once()


# --- fetch_thread_states ---


class TestFetchThreadStates:
    """fetch_thread_states queries GitHub GraphQL for thread metadata."""

    @patch("grippy.github_review.subprocess.run")
    def test_returns_thread_states(self, mock_run: MagicMock) -> None:
        import json

        from grippy.github_review import fetch_thread_states

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "data": {
                        "nodes": [
                            {"id": "PRRT_1", "isOutdated": True, "isResolved": False},
                            {"id": "PRRT_2", "isOutdated": False, "isResolved": True},
                        ]
                    }
                }
            ),
        )
        result = fetch_thread_states(["PRRT_1", "PRRT_2"])
        assert result["PRRT_1"]["isOutdated"] is True
        assert result["PRRT_1"]["isResolved"] is False
        assert result["PRRT_2"]["isOutdated"] is False
        assert result["PRRT_2"]["isResolved"] is True

    @patch("grippy.github_review.subprocess.run")
    def test_empty_ids_no_call(self, mock_run: MagicMock) -> None:
        from grippy.github_review import fetch_thread_states

        result = fetch_thread_states([])
        assert result == {}
        mock_run.assert_not_called()

    @patch("grippy.github_review.subprocess.run")
    def test_failure_returns_empty(self, mock_run: MagicMock) -> None:
        from grippy.github_review import fetch_thread_states

        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        result = fetch_thread_states(["PRRT_1"])
        assert result == {}

    @patch("grippy.github_review.subprocess.run")
    def test_null_nodes_skipped(self, mock_run: MagicMock) -> None:
        """Null nodes (e.g. deleted threads) are skipped gracefully."""
        import json

        from grippy.github_review import fetch_thread_states

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "data": {
                        "nodes": [
                            None,
                            {"id": "PRRT_2", "isOutdated": True, "isResolved": False},
                        ]
                    }
                }
            ),
        )
        result = fetch_thread_states(["PRRT_bad", "PRRT_2"])
        assert "PRRT_bad" not in result
        assert result["PRRT_2"]["isOutdated"] is True

    @patch("grippy.github_review.subprocess.run")
    def test_uses_graphql_variables(self, mock_run: MagicMock) -> None:
        """Thread IDs are passed as GraphQL variables via stdin, not interpolated."""
        import json

        from grippy.github_review import fetch_thread_states

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"data": {"nodes": []}}),
        )
        fetch_thread_states(["PRRT_1"])
        input_data = json.loads(mock_run.call_args[1]["input"])
        assert "$ids" in input_data["query"]
        assert "PRRT_1" not in input_data["query"]
        assert input_data["variables"]["ids"] == ["PRRT_1"]

    @patch("grippy.github_review.subprocess.run")
    def test_exception_returns_empty(self, mock_run: MagicMock) -> None:
        """Exception during fetch returns empty dict (non-fatal)."""
        from grippy.github_review import fetch_thread_states

        mock_run.side_effect = Exception("network failure")
        result = fetch_thread_states(["PRRT_1"])
        assert result == {}


# --- resolve_threads ---


class TestResolveThreads:
    """resolve_threads auto-resolves GitHub review threads via batch mutation."""

    @patch("grippy.github_review.subprocess.run")
    def test_single_thread_single_call(self, mock_run: MagicMock) -> None:
        from grippy.github_review import resolve_threads

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"data": {"t0": {"thread": {"id": "PRRT_1", "isResolved": true}}}}',
        )
        count = resolve_threads(repo="org/repo", pr_number=1, thread_ids=["PRRT_1"])
        assert count == 1
        mock_run.assert_called_once()

    @patch("grippy.github_review.subprocess.run")
    def test_batch_multiple_threads_single_call(self, mock_run: MagicMock) -> None:
        """Multiple threads resolved in a single GraphQL call via aliases."""
        import json

        from grippy.github_review import resolve_threads

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "data": {
                        "t0": {"thread": {"id": "PRRT_1", "isResolved": True}},
                        "t1": {"thread": {"id": "PRRT_2", "isResolved": True}},
                        "t2": {"thread": {"id": "PRRT_3", "isResolved": True}},
                    }
                }
            ),
        )
        count = resolve_threads(
            repo="org/repo", pr_number=1, thread_ids=["PRRT_1", "PRRT_2", "PRRT_3"]
        )
        assert count == 3
        mock_run.assert_called_once()

    @patch("grippy.github_review.subprocess.run")
    def test_empty_thread_ids_no_calls(self, mock_run: MagicMock) -> None:
        from grippy.github_review import resolve_threads

        count = resolve_threads(repo="org/repo", pr_number=1, thread_ids=[])
        assert count == 0
        mock_run.assert_not_called()

    @patch("grippy.github_review.subprocess.run")
    def test_subprocess_failure_returns_zero(self, mock_run: MagicMock) -> None:
        from grippy.github_review import resolve_threads

        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        count = resolve_threads(repo="org/repo", pr_number=1, thread_ids=["PRRT_1"])
        assert count == 0

    @patch("grippy.github_review.subprocess.run")
    def test_partial_failure_counts_successes(self, mock_run: MagicMock) -> None:
        """If some aliases fail in the response, only count successful ones."""
        import json

        from grippy.github_review import resolve_threads

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "data": {
                        "t0": {"thread": {"id": "PRRT_1", "isResolved": True}},
                        "t1": None,
                    }
                }
            ),
        )
        count = resolve_threads(repo="org/repo", pr_number=1, thread_ids=["PRRT_1", "PRRT_2"])
        assert count == 1

    @patch("grippy.github_review.subprocess.run")
    def test_exception_returns_zero(self, mock_run: MagicMock) -> None:
        from grippy.github_review import resolve_threads

        mock_run.side_effect = OSError("gh not found")
        count = resolve_threads(repo="org/repo", pr_number=1, thread_ids=["PRRT_1"])
        assert count == 0


# --- parse_diff_lines edge cases ---


class TestParseDiffLinesEdgeCases:
    """Edge cases for parse_diff_lines context line handling."""

    def test_no_newline_marker_not_in_result(self) -> None:
        """'\\No newline at end of file' marker must NOT appear in result set."""
        from grippy.github_review import parse_diff_lines

        diff = (
            "diff --git a/f.py b/f.py\n"
            "--- a/f.py\n"
            "+++ b/f.py\n"
            "@@ -1,3 +1,3 @@\n"
            " line1\n"
            "-old_line2\n"
            "+new_line2\n"
            "\\ No newline at end of file\n"
        )
        result = parse_diff_lines(diff)
        assert "f.py" in result
        assert 1 in result["f.py"]
        assert 2 in result["f.py"]
        assert len(result["f.py"]) == 2

    def test_binary_metadata_no_crash(self) -> None:
        """Diff with 'Binary files differ' should not crash or over-include."""
        from grippy.github_review import parse_diff_lines

        diff = "diff --git a/img.png b/img.png\nBinary files a/img.png and b/img.png differ\n"
        result = parse_diff_lines(diff)
        assert result.get("img.png", set()) == set()

    def test_only_space_prefix_is_context(self) -> None:
        """Only lines starting with ' ' are context — random chars are ignored."""
        from grippy.github_review import parse_diff_lines

        diff = (
            "diff --git a/f.py b/f.py\n"
            "--- a/f.py\n"
            "+++ b/f.py\n"
            "@@ -1,3 +1,4 @@\n"
            " context_line\n"
            "+added_line\n"
            "~unexpected_tilde_line\n"
            " more_context\n"
        )
        result = parse_diff_lines(diff)
        assert 1 in result["f.py"]
        assert 2 in result["f.py"]
        assert 3 in result["f.py"]
        assert len(result["f.py"]) == 3


# --- post_review 422 fallback ---


class TestPostReview422Fallback:
    """post_review handles GitHub 422 errors by moving findings to summary."""

    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_422_fallback_to_summary(
        self, mock_fetch: MagicMock, mock_github_cls: MagicMock
    ) -> None:
        """422 on create_review moves findings to off-diff in summary, no crash."""
        from github import GithubException

        from grippy.github_review import post_review

        mock_fetch.return_value = {}
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []
        mock_pr.head.repo.full_name = "org/repo"
        mock_pr.base.repo.full_name = "org/repo"
        mock_pr.create_review.side_effect = GithubException(
            422, {"message": "Validation Failed"}, None
        )

        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n+++ b/src/app.py\n"
            "@@ -8,3 +8,4 @@\n line\n+new_line\n line2\n"
        )
        findings = [_make_finding(file="src/app.py", line_start=9)]

        # Should NOT raise
        post_review(
            token="test-token",
            repo="org/repo",
            pr_number=1,
            findings=findings,
            head_sha="abc123",
            diff=diff,
            score=80,
            verdict="PASS",
        )

        # Summary should include the finding as off-diff
        mock_pr.create_issue_comment.assert_called_once()
        body = mock_pr.create_issue_comment.call_args[0][0]
        assert "Off-diff findings" in body

    @patch("grippy.github_review.Github")
    @patch("grippy.github_review.fetch_grippy_comments")
    def test_non_422_propagates(self, mock_fetch: MagicMock, mock_github_cls: MagicMock) -> None:
        """GithubException(500) is re-raised, not swallowed."""
        from github import GithubException

        from grippy.github_review import post_review

        mock_fetch.return_value = {}
        mock_pr = MagicMock()
        mock_github_cls.return_value.get_repo.return_value.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []
        mock_pr.head.repo.full_name = "org/repo"
        mock_pr.base.repo.full_name = "org/repo"
        mock_pr.create_review.side_effect = GithubException(
            500, {"message": "Internal Server Error"}, None
        )

        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n+++ b/src/app.py\n"
            "@@ -8,3 +8,4 @@\n line\n+new_line\n line2\n"
        )
        findings = [_make_finding(file="src/app.py", line_start=9)]

        with pytest.raises(GithubException):
            post_review(
                token="test-token",
                repo="org/repo",
                pr_number=1,
                findings=findings,
                head_sha="abc123",
                diff=diff,
                score=80,
                verdict="PASS",
            )


# --- resolve_threads GraphQL variables ---


class TestResolveThreadsBatchSafety:
    """Batch mutation uses GraphQL variables — no string interpolation of IDs."""

    @patch("grippy.github_review.subprocess.run")
    def test_uses_graphql_variables_not_interpolation(self, mock_run: MagicMock) -> None:
        """Thread IDs are passed as $id0, $id1 variables, not embedded in query."""
        import json

        from grippy.github_review import resolve_threads

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {"data": {"t0": {"thread": {"id": "PRRT_test", "isResolved": True}}}}
            ),
        )
        resolve_threads(repo="org/repo", pr_number=1, thread_ids=["PRRT_test"])
        cmd = mock_run.call_args[0][0]
        query_args = [a for a in cmd if a.startswith("query=")]
        assert len(query_args) == 1
        assert "resolveReviewThread" in query_args[0]
        # Thread ID must NOT appear in the query string — it's a variable
        assert "PRRT_test" not in query_args[0]
        assert "$id0" in query_args[0]
        # Thread ID passed as separate -f variable arg
        var_args = [a for a in cmd if a.startswith("id0=")]
        assert len(var_args) == 1
        assert var_args[0] == "id0=PRRT_test"

    @patch("grippy.github_review.subprocess.run")
    def test_injection_attempt_in_thread_id_is_variable_only(self, mock_run: MagicMock) -> None:
        """Malicious thread ID cannot break GraphQL structure — passed as variable."""
        import json

        from grippy.github_review import resolve_threads

        malicious = 'PRRT_abc"}}mutation BadActor{}'
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"data": {"t0": {"thread": {"id": malicious, "isResolved": True}}}}),
        )
        resolve_threads(repo="org/repo", pr_number=1, thread_ids=[malicious])
        cmd = mock_run.call_args[0][0]
        query_args = [a for a in cmd if a.startswith("query=")]
        # Malicious payload must NOT appear in the query string
        assert malicious not in query_args[0]
        assert "BadActor" not in query_args[0]
        # It's safely in the variable arg
        var_args = [a for a in cmd if a.startswith("id0=")]
        assert var_args[0] == f"id0={malicious}"


# --- Comment sanitization ---


class TestCommentSanitization:
    """LLM output must be sanitized before posting to GitHub comments."""

    def test_script_tag_stripped_from_inline_comment(self) -> None:
        """<script> tags in finding description are stripped from review comment body."""
        from grippy.github_review import build_review_comment

        finding = _make_finding()
        # Rebuild with malicious description — Finding is frozen, so create fresh
        finding = Finding(
            id="F-001",
            severity="HIGH",
            confidence=90,
            category="security",
            file="src/app.py",
            line_start=10,
            line_end=15,
            title="XSS <script>alert('title')</script> risk",
            description="Vuln here <script>alert(1)</script> in code.",
            suggestion="Fix <script>alert('sug')</script> this.",
            evidence="evidence here",
            grippy_note="<script>alert('note')</script> Grippy says.",
        )
        comment = build_review_comment(finding)
        body = comment["body"]
        assert "<script>" not in body
        assert "alert(1)" not in body
        assert "alert('title')" not in body
        assert "alert('sug')" not in body
        assert "alert('note')" not in body

    def test_iframe_tag_stripped(self) -> None:
        from grippy.github_review import build_review_comment

        finding = Finding(
            id="F-001",
            severity="HIGH",
            confidence=90,
            category="security",
            file="src/app.py",
            line_start=10,
            line_end=15,
            title="Test finding",
            description='Check <iframe src="https://evil.com"></iframe> this.',
            suggestion="Fix this.",
            evidence="evidence",
            grippy_note="Grippy note.",
        )
        comment = build_review_comment(finding)
        assert "<iframe" not in comment["body"]

    def test_event_handler_stripped(self) -> None:
        from grippy.github_review import build_review_comment

        finding = Finding(
            id="F-001",
            severity="HIGH",
            confidence=90,
            category="security",
            file="src/app.py",
            line_start=10,
            line_end=15,
            title="Test finding",
            description='<img onerror="alert(1)" src="x">',
            suggestion="Fix this.",
            evidence="evidence",
            grippy_note="Grippy note.",
        )
        comment = build_review_comment(finding)
        assert "onerror" not in comment["body"]

    def test_javascript_scheme_stripped(self) -> None:
        from grippy.github_review import build_review_comment

        finding = Finding(
            id="F-001",
            severity="HIGH",
            confidence=90,
            category="security",
            file="src/app.py",
            line_start=10,
            line_end=15,
            title="Test finding",
            description="Click [here](javascript:alert(1)) for details.",
            suggestion="Fix this.",
            evidence="evidence",
            grippy_note="Grippy note.",
        )
        comment = build_review_comment(finding)
        assert "javascript:" not in comment["body"]

    def test_sanitization_applied_in_summary_off_diff(self) -> None:
        """Off-diff findings in format_summary_comment are also sanitized."""
        from grippy.github_review import format_summary_comment

        finding = Finding(
            id="F-001",
            severity="HIGH",
            confidence=90,
            category="security",
            file="src/app.py",
            line_start=10,
            line_end=15,
            title="<script>alert('t')</script> Bad title",
            description="<script>alert('d')</script> Bad desc.",
            suggestion="<script>alert('s')</script> Bad suggestion.",
            evidence="evidence",
            grippy_note="Grippy note.",
        )
        result = format_summary_comment(
            score=70,
            verdict="FAIL",
            finding_count=1,
            new_count=1,
            resolved_count=0,
            off_diff_findings=[finding],
            head_sha="abc123",
            pr_number=6,
        )
        assert "<script>" not in result
        assert "alert('t')" not in result
        assert "alert('d')" not in result
        assert "alert('s')" not in result

    def test_sanitize_preserves_safe_content(self) -> None:
        """Sanitization does not mangle safe markdown content."""
        from grippy.github_review import _sanitize_comment_text

        safe = "Use `parameterized_query()` instead of **string concat**."
        assert _sanitize_comment_text(safe) == safe

    def test_data_scheme_stripped(self) -> None:
        from grippy.github_review import _sanitize_comment_text

        text = "See data:text/html,<h1>pwned</h1>"
        result = _sanitize_comment_text(text)
        assert "data:" not in result

    def test_case_insensitive_stripping(self) -> None:
        from grippy.github_review import _sanitize_comment_text

        text = "<SCRIPT>alert(1)</SCRIPT>"
        result = _sanitize_comment_text(text)
        assert "<SCRIPT>" not in result
        assert "<script>" not in result.lower()

    def test_unquote_loop_decodes_fully(self) -> None:
        """Verify that _sanitize_comment_text fully decodes URL-encoded content.

        The dangerous scheme regex must run against fully decoded text.
        The unquote() call must loop until stable to prevent multi-layer
        encoding bypass (e.g., %2561 -> %61 -> a).
        """
        from urllib.parse import unquote

        from grippy.github_review import _sanitize_comment_text

        # Prove the vulnerability: single unquote leaves %61 intact
        assert unquote("jav%2561script:") == "jav%61script:"
        # Double unquote resolves to the dangerous scheme
        assert unquote(unquote("jav%2561script:")) == "javascript:"

        # The sanitizer must block this regardless
        text = "jav%2561script:alert(1)"
        result = _sanitize_comment_text(text)
        assert "javascript:" not in result.lower()

    def test_single_url_encoding_blocked(self) -> None:
        """Single-encoded javascript: scheme (jav%61script:) must be blocked."""
        from grippy.github_review import _sanitize_comment_text

        text = "jav%61script:alert(1)"
        result = _sanitize_comment_text(text)
        assert "javascript:" not in result.lower()

    def test_triple_url_encoding_blocked(self) -> None:
        """Triple-encoded javascript: scheme must also be blocked."""
        from grippy.github_review import _sanitize_comment_text

        text = "jav%25252561script:alert(1)"
        result = _sanitize_comment_text(text)
        assert "javascript:" not in result.lower()

    def test_plain_javascript_still_blocked(self) -> None:
        """Unencoded javascript: scheme must still be blocked."""
        from grippy.github_review import _sanitize_comment_text

        text = "javascript:alert(1)"
        result = _sanitize_comment_text(text)
        assert "javascript:" not in result.lower()

    def test_double_encoded_data_scheme_blocked(self) -> None:
        """Double-encoded data: scheme must be blocked."""
        from grippy.github_review import _sanitize_comment_text

        text = "d%2561ta:text/html,pwned"
        result = _sanitize_comment_text(text)
        assert "data:" not in result.lower()

    def test_vbscript_double_encoded_blocked(self) -> None:
        """Double-encoded vbscript: scheme must be blocked."""
        from grippy.github_review import _sanitize_comment_text

        text = "vb%2573cript:msgbox"
        result = _sanitize_comment_text(text)
        assert "vbscript:" not in result.lower()


# --- Verdict markers ---


class TestVerdictMarkers:
    """Grippy verdict markers identify bot reviews and store machine-readable metadata."""

    def test_build_verdict_body_contains_marker(self) -> None:
        from grippy.github_review import build_verdict_body

        body = build_verdict_body(
            score=85,
            verdict="PASS",
            head_sha="abc1234def5678",  # pragma: allowlist secret
            base_text="Grippy approves",
        )
        assert "<!-- grippy-verdict abc1234def5678 -->" in body

    def test_build_verdict_body_contains_meta(self) -> None:
        from grippy.github_review import build_verdict_body

        body = build_verdict_body(
            score=42,
            verdict="FAIL",
            head_sha="deadbeef12345678",  # pragma: allowlist secret
            base_text="Grippy rejects",
        )
        assert '<!-- grippy-meta {"score": 42, "verdict": "FAIL"} -->' in body

    def test_build_verdict_body_preserves_base_text(self) -> None:
        from grippy.github_review import build_verdict_body

        body = build_verdict_body(
            score=85,
            verdict="PASS",
            head_sha="abc1234",
            base_text="Grippy approves — **PASS** (85/100)",
        )
        assert "Grippy approves — **PASS** (85/100)" in body

    def test_parse_grippy_meta_extracts_score_and_verdict(self) -> None:
        from grippy.github_review import parse_grippy_meta

        body = 'Some text\n<!-- grippy-meta {"score": 85, "verdict": "PASS"} -->\nmore'
        result = parse_grippy_meta(body)
        assert result == {"score": 85, "verdict": "PASS"}

    def test_parse_grippy_meta_returns_none_for_missing(self) -> None:
        from grippy.github_review import parse_grippy_meta

        assert parse_grippy_meta("no markers here") is None

    def test_parse_grippy_meta_returns_none_for_malformed_json(self) -> None:
        from grippy.github_review import parse_grippy_meta

        body = "<!-- grippy-meta {bad json} -->"
        assert parse_grippy_meta(body) is None


# --- _dismiss_prior_verdicts ---


class TestDismissPriorVerdicts:
    """_dismiss_prior_verdicts manages verdict lifecycle with marker-based identity."""

    def _make_review(
        self,
        *,
        review_id: int = 1,
        state: str = "APPROVED",
        body: str = "<!-- grippy-verdict abc123 -->",
        commit_id: str = "old_sha",
        dismiss_ok: bool = True,
    ) -> MagicMock:
        review = MagicMock()
        review.id = review_id
        review.state = state
        review.body = body
        review.commit_id = commit_id
        if not dismiss_ok:
            from github import GithubException

            review.dismiss.side_effect = GithubException(403, {}, {})
        return review

    def test_dismisses_old_sha_grippy_verdicts(self) -> None:
        from grippy.github_review import _dismiss_prior_verdicts

        pr = MagicMock()
        old = self._make_review(review_id=1, commit_id="old_sha")
        pr.get_reviews.return_value = [old]
        count = _dismiss_prior_verdicts(pr, "new_sha")
        assert count == 1
        old.dismiss.assert_called_once()

    def test_skips_same_sha_in_normal_mode(self) -> None:
        from grippy.github_review import _dismiss_prior_verdicts

        pr = MagicMock()
        same = self._make_review(review_id=1, commit_id="new_sha")
        pr.get_reviews.return_value = [same]
        count = _dismiss_prior_verdicts(pr, "new_sha")
        assert count == 0
        same.dismiss.assert_not_called()

    def test_dismisses_same_sha_in_force_mode(self) -> None:
        from grippy.github_review import _dismiss_prior_verdicts

        pr = MagicMock()
        same = self._make_review(review_id=1, commit_id="new_sha")
        pr.get_reviews.return_value = [same]
        count = _dismiss_prior_verdicts(pr, "new_sha", force=True)
        assert count == 1
        same.dismiss.assert_called_once()

    def test_excludes_review_id(self) -> None:
        from grippy.github_review import _dismiss_prior_verdicts

        pr = MagicMock()
        fresh = self._make_review(review_id=99, commit_id="new_sha")
        old = self._make_review(review_id=50, commit_id="new_sha")
        pr.get_reviews.return_value = [fresh, old]
        count = _dismiss_prior_verdicts(pr, "new_sha", force=True, exclude_review_id=99)
        assert count == 1
        fresh.dismiss.assert_not_called()
        old.dismiss.assert_called_once()

    def test_skips_human_reviews(self) -> None:
        from grippy.github_review import _dismiss_prior_verdicts

        pr = MagicMock()
        human = self._make_review(review_id=1, body="LGTM", commit_id="old_sha")
        pr.get_reviews.return_value = [human]
        count = _dismiss_prior_verdicts(pr, "new_sha")
        assert count == 0
        human.dismiss.assert_not_called()

    def test_skips_non_verdict_states(self) -> None:
        from grippy.github_review import _dismiss_prior_verdicts

        pr = MagicMock()
        comment = self._make_review(review_id=1, state="COMMENTED", commit_id="old_sha")
        pr.get_reviews.return_value = [comment]
        count = _dismiss_prior_verdicts(pr, "new_sha")
        assert count == 0

    def test_dismiss_exception_is_non_fatal(self) -> None:
        from grippy.github_review import _dismiss_prior_verdicts

        pr = MagicMock()
        failing = self._make_review(review_id=1, commit_id="old_sha", dismiss_ok=False)
        ok = self._make_review(review_id=2, commit_id="old_sha2")
        pr.get_reviews.return_value = [failing, ok]
        count = _dismiss_prior_verdicts(pr, "new_sha")
        assert count == 1

    def test_multiple_stacked_verdicts_all_dismissed(self) -> None:
        from grippy.github_review import _dismiss_prior_verdicts

        pr = MagicMock()
        reviews = [self._make_review(review_id=i, commit_id=f"sha_{i}") for i in range(5)]
        pr.get_reviews.return_value = reviews
        count = _dismiss_prior_verdicts(pr, "new_sha")
        assert count == 5
        for r in reviews:
            r.dismiss.assert_called_once()

    def test_mixed_actors_only_grippy_dismissed(self) -> None:
        from grippy.github_review import _dismiss_prior_verdicts

        pr = MagicMock()
        grippy = self._make_review(review_id=1, commit_id="old_sha")
        human = self._make_review(review_id=2, body="Looks good", commit_id="old_sha")
        changes = self._make_review(
            review_id=3,
            state="CHANGES_REQUESTED",
            body="<!-- grippy-verdict old_sha -->\nFail",
            commit_id="old_sha",
        )
        pr.get_reviews.return_value = [grippy, human, changes]
        count = _dismiss_prior_verdicts(pr, "new_sha")
        assert count == 2
        human.dismiss.assert_not_called()


# --- post_review verdict lifecycle ---


class TestPostReviewVerdictLifecycle:
    """post_review uses markers and dismiss-after-post ordering."""

    def _setup_mocks(self) -> tuple[MagicMock, MagicMock, MagicMock]:
        """Create mock Github, repository, and PR objects."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr
        mock_pr.get_issue_comments.return_value = []
        mock_pr.get_reviews.return_value = []
        mock_review = MagicMock()
        mock_review.id = 999
        mock_pr.create_review.return_value = mock_review
        return mock_gh, mock_repo, mock_pr

    @patch("grippy.github_review.fetch_grippy_comments", return_value={})
    @patch("grippy.github_review.Github")
    def test_verdict_body_contains_markers(self, mock_gh_cls, mock_fetch) -> None:
        mock_gh, _, mock_pr = self._setup_mocks()
        mock_gh_cls.return_value = mock_gh

        from grippy.github_review import post_review

        post_review(
            token="fake",
            repo="owner/repo",
            pr_number=1,
            findings=[],
            head_sha="abc1234def",  # pragma: allowlist secret
            diff="",
            score=85,
            verdict="PASS",
        )
        # Find the APPROVE call (not COMMENT)
        approve_calls = [
            c for c in mock_pr.create_review.call_args_list if c.kwargs.get("event") == "APPROVE"
        ]
        assert len(approve_calls) >= 1
        body = approve_calls[0].kwargs.get("body", "")
        assert "<!-- grippy-verdict abc1234def -->" in body
        assert "grippy-meta" in body

    @patch("grippy.github_review.fetch_grippy_comments", return_value={})
    @patch("grippy.github_review._dismiss_prior_verdicts", return_value=0)
    @patch("grippy.github_review.Github")
    def test_dismiss_called_after_verdict_post(self, mock_gh_cls, mock_dismiss, mock_fetch) -> None:
        mock_gh, _, _mock_pr = self._setup_mocks()
        mock_gh_cls.return_value = mock_gh

        from grippy.github_review import post_review

        post_review(
            token="fake",
            repo="owner/repo",
            pr_number=1,
            findings=[],
            head_sha="abc1234",
            diff="",
            score=85,
            verdict="PASS",
        )
        mock_dismiss.assert_called_once()
        call_kwargs = mock_dismiss.call_args.kwargs
        assert "exclude_review_id" in call_kwargs
        assert call_kwargs["exclude_review_id"] == 999

    @patch("grippy.github_review.fetch_grippy_comments", return_value={})
    @patch("grippy.github_review._dismiss_prior_verdicts", return_value=0)
    @patch("grippy.github_review.Github")
    def test_verdict_failure_skips_dismiss(self, mock_gh_cls, mock_dismiss, mock_fetch) -> None:
        mock_gh, _, mock_pr = self._setup_mocks()
        mock_gh_cls.return_value = mock_gh
        from github import GithubException

        def selective_fail(**kwargs):
            event = kwargs.get("event", "")
            if event in ("APPROVE", "REQUEST_CHANGES"):
                raise GithubException(500, {}, {})
            mock_result = MagicMock()
            mock_result.id = 999
            return mock_result

        mock_pr.create_review.side_effect = selective_fail

        from grippy.github_review import post_review

        post_review(
            token="fake",
            repo="owner/repo",
            pr_number=1,
            findings=[],
            head_sha="abc1234",
            diff="",
            score=85,
            verdict="PASS",
        )
        mock_dismiss.assert_not_called()


# --- fetch_thread_states -F fix ---


class TestFetchThreadStatesFix:
    """fetch_thread_states must pass ids array via --input stdin (not -F which doesn't parse arrays)."""

    @patch("subprocess.run")
    def test_uses_stdin_input_for_ids(self, mock_run) -> None:
        import json

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"data":{"nodes":[]}}',
            stderr="",
        )
        from grippy.github_review import fetch_thread_states

        fetch_thread_states(["PRRT_abc123", "PRRT_def456"])
        args = mock_run.call_args[0][0]
        assert "--input" in args, "Expected --input flag for stdin JSON"
        # Verify ids passed as JSON array in stdin
        input_data = json.loads(mock_run.call_args[1]["input"])
        assert input_data["variables"]["ids"] == ["PRRT_abc123", "PRRT_def456"]

    @patch("subprocess.run")
    def test_empty_thread_ids_skips_call(self, mock_run) -> None:
        from grippy.github_review import fetch_thread_states

        result = fetch_thread_states([])
        assert result == {}
        mock_run.assert_not_called()


# --- Reference-style markdown link stripping ---


class TestReferenceStyleLinkStripping:
    """_sanitize_comment_text strips reference-style links, collapsed refs, and autolinks."""

    def test_reference_link_with_definition_stripped(self) -> None:
        """[text][id] + definition line -> plain text only."""
        from grippy.github_review import _sanitize_comment_text

        text = "[click here][1]\n\n[1]: https://evil.com"
        result = _sanitize_comment_text(text)
        assert "click here" in result
        assert "https://evil.com" not in result
        assert "[1]" not in result

    def test_collapsed_reference_stripped(self) -> None:
        """[text][] + definition -> plain text only."""
        from grippy.github_review import _sanitize_comment_text

        text = "[click here][]\n\n[click here]: https://evil.com"
        result = _sanitize_comment_text(text)
        assert "click here" in result
        assert "https://evil.com" not in result

    def test_bare_autolink_stripped(self) -> None:
        """<https://evil.com> -> plain URL text without angle brackets."""
        from grippy.github_review import _sanitize_comment_text

        text = "Visit <https://evil.com> for details"
        result = _sanitize_comment_text(text)
        assert "<https://" not in result
        # The URL text itself may remain (safe — not a clickable link)
        assert ">" not in result or "evil.com>" not in result

    def test_inline_links_still_stripped(self) -> None:
        """Regression: existing inline link stripping still works."""
        from grippy.github_review import _sanitize_comment_text

        text = "[click](https://evil.com)"
        result = _sanitize_comment_text(text)
        assert "https://evil.com" not in result
        assert "click" in result

    def test_reference_without_definition_inert(self) -> None:
        """[text][id] without a definition is harmless (renders as literal text)."""
        from grippy.github_review import _sanitize_comment_text

        text = "[text][undefined-id]"
        result = _sanitize_comment_text(text)
        # Should be stripped to plain text (defense-in-depth)
        assert "text" in result

    def test_multiple_reference_definitions_stripped(self) -> None:
        """Multiple definitions are all removed."""
        from grippy.github_review import _sanitize_comment_text

        text = "[a][1] and [b][2]\n\n[1]: https://evil1.com\n[2]: https://evil2.com 'title'"
        result = _sanitize_comment_text(text)
        assert "https://evil1.com" not in result
        assert "https://evil2.com" not in result
        assert "a" in result
        assert "b" in result

    def test_indented_definition_stripped(self) -> None:
        """Definitions with up to 3 spaces of indentation are stripped."""
        from grippy.github_review import _sanitize_comment_text

        text = "[ref][1]\n   [1]: https://evil.com"
        result = _sanitize_comment_text(text)
        assert "https://evil.com" not in result

    def test_http_autolink_stripped(self) -> None:
        """<http://...> autolinks are stripped too."""
        from grippy.github_review import _sanitize_comment_text

        text = "See <http://evil.com/path>"
        result = _sanitize_comment_text(text)
        assert "<http://" not in result
