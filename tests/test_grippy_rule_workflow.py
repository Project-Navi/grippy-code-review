# SPDX-License-Identifier: MIT
"""Tests for Rule 1: workflow-permissions-expanded."""

from __future__ import annotations

import signal
from collections.abc import Generator
from contextlib import contextmanager

from grippy.rules.base import RuleSeverity
from grippy.rules.config import ProfileConfig
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.workflow_permissions import (
    _PERMISSIONS_RE,
    _SHA_PIN_RE,
    _USES_RE,
    WorkflowPermissionsRule,
)


def _ctx(diff: str) -> RuleContext:
    return RuleContext(
        diff=diff,
        files=parse_diff(diff),
        config=ProfileConfig(name="security", fail_on=RuleSeverity.ERROR),
    )


class TestWorkflowPermissions:
    def test_write_permission_on_added_line(self) -> None:
        diff = (
            "diff --git a/.github/workflows/deploy.yml b/.github/workflows/deploy.yml\n"
            "--- a/.github/workflows/deploy.yml\n"
            "+++ b/.github/workflows/deploy.yml\n"
            "@@ -1,3 +1,5 @@\n"
            " name: deploy\n"
            "+permissions:\n"
            "+  contents: write\n"
            " on:\n"
            "   push:\n"
        )
        rule = WorkflowPermissionsRule()
        results = rule.run(_ctx(diff))
        assert any(
            r.severity == RuleSeverity.ERROR and "write" in r.message.lower() for r in results
        )

    def test_admin_permission(self) -> None:
        diff = (
            "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
            "--- a/.github/workflows/ci.yml\n"
            "+++ b/.github/workflows/ci.yml\n"
            "@@ -1,3 +1,5 @@\n"
            " name: ci\n"
            "+permissions:\n"
            "+  packages: admin\n"
            " on:\n"
            "   push:\n"
        )
        rule = WorkflowPermissionsRule()
        results = rule.run(_ctx(diff))
        assert any(r.severity == RuleSeverity.ERROR for r in results)

    def test_read_permission_not_flagged(self) -> None:
        diff = (
            "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
            "--- a/.github/workflows/ci.yml\n"
            "+++ b/.github/workflows/ci.yml\n"
            "@@ -1,3 +1,5 @@\n"
            " name: ci\n"
            "+permissions:\n"
            "+  contents: read\n"
            " on:\n"
            "   push:\n"
        )
        rule = WorkflowPermissionsRule()
        results = rule.run(_ctx(diff))
        assert not any(
            "write" in r.message.lower() or "admin" in r.message.lower() for r in results
        )

    def test_pull_request_target(self) -> None:
        diff = (
            "diff --git a/.github/workflows/pr.yml b/.github/workflows/pr.yml\n"
            "--- a/.github/workflows/pr.yml\n"
            "+++ b/.github/workflows/pr.yml\n"
            "@@ -1,3 +1,4 @@\n"
            " name: pr\n"
            " on:\n"
            "+  pull_request_target:\n"
            "   push:\n"
        )
        rule = WorkflowPermissionsRule()
        results = rule.run(_ctx(diff))
        assert any("pull_request_target" in r.message for r in results)

    def test_unpinned_action(self) -> None:
        diff = (
            "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
            "--- a/.github/workflows/ci.yml\n"
            "+++ b/.github/workflows/ci.yml\n"
            "@@ -5,3 +5,4 @@\n"
            " jobs:\n"
            "   build:\n"
            "     steps:\n"
            "+      - uses: actions/checkout@v4\n"
        )
        rule = WorkflowPermissionsRule()
        results = rule.run(_ctx(diff))
        assert any(r.severity == RuleSeverity.WARN and "Unpinned" in r.message for r in results)

    def test_sha_pinned_action_not_flagged(self) -> None:
        diff = (
            "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
            "--- a/.github/workflows/ci.yml\n"
            "+++ b/.github/workflows/ci.yml\n"
            "@@ -5,3 +5,4 @@\n"
            " jobs:\n"
            "   build:\n"
            "     steps:\n"
            "+      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11\n"
        )
        rule = WorkflowPermissionsRule()
        results = rule.run(_ctx(diff))
        assert not any("Unpinned" in r.message for r in results)

    def test_local_action_not_flagged(self) -> None:
        diff = (
            "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
            "--- a/.github/workflows/ci.yml\n"
            "+++ b/.github/workflows/ci.yml\n"
            "@@ -5,3 +5,4 @@\n"
            " jobs:\n"
            "   build:\n"
            "     steps:\n"
            "+      - uses: ./my-action\n"
        )
        rule = WorkflowPermissionsRule()
        results = rule.run(_ctx(diff))
        assert not any("Unpinned" in r.message for r in results)

    def test_scalar_permissions_write_all(self) -> None:
        """Scalar 'permissions: write-all' on same line is detected."""
        diff = (
            "diff --git a/.github/workflows/deploy.yml b/.github/workflows/deploy.yml\n"
            "--- a/.github/workflows/deploy.yml\n"
            "+++ b/.github/workflows/deploy.yml\n"
            "@@ -1,3 +1,4 @@\n"
            " name: deploy\n"
            "+permissions: write-all\n"
            " on:\n"
            "   push:\n"
        )
        rule = WorkflowPermissionsRule()
        results = rule.run(_ctx(diff))
        assert any(
            r.severity == RuleSeverity.ERROR and "write" in r.message.lower() for r in results
        )

    def test_scalar_permissions_read_not_flagged(self) -> None:
        """Scalar 'permissions: read-all' is not flagged."""
        diff = (
            "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
            "--- a/.github/workflows/ci.yml\n"
            "+++ b/.github/workflows/ci.yml\n"
            "@@ -1,3 +1,4 @@\n"
            " name: ci\n"
            "+permissions: read-all\n"
            " on:\n"
            "   push:\n"
        )
        rule = WorkflowPermissionsRule()
        results = rule.run(_ctx(diff))
        assert not any(
            "write" in r.message.lower() or "admin" in r.message.lower() for r in results
        )

    def test_non_workflow_file_ignored(self) -> None:
        diff = (
            "diff --git a/config.yml b/config.yml\n"
            "--- a/config.yml\n"
            "+++ b/config.yml\n"
            "@@ -1,1 +1,2 @@\n"
            " key: value\n"
            "+permissions: write\n"
        )
        rule = WorkflowPermissionsRule()
        results = rule.run(_ctx(diff))
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


class TestWorkflowReDoS:
    """Adversarial long-input tests for all compiled regexes (SR-02)."""

    def test_redos_permissions_re(self) -> None:
        """100K-char adversarial input against _PERMISSIONS_RE completes quickly."""
        adversarial = "permissions" + " " * 100_000 + ":"
        with _timeout(5):
            _PERMISSIONS_RE.match(adversarial)

    def test_redos_uses_re(self) -> None:
        """100K-char adversarial input against _USES_RE completes quickly."""
        adversarial = "  - uses: " + "a" * 100_000
        with _timeout(5):
            _USES_RE.match(adversarial)

    def test_redos_sha_pin_re(self) -> None:
        """100K-char non-matching input against _SHA_PIN_RE completes quickly.

        _SHA_PIN_RE uses search() not match(), so exercise with a long
        non-matching string to stress the search path.
        """
        adversarial = "x" * 100_000
        with _timeout(5):
            _SHA_PIN_RE.search(adversarial)


# -- SR-04: Proximity window tests -------------------------------------------


class TestProximityWindow:
    """Prove the ±2 proximity window design for permissions/pull_request_target."""

    def test_proximity_window_inside(self) -> None:
        """Context line with 'write' permission within ±2 of an added line IS detected."""
        diff = (
            "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
            "--- a/.github/workflows/ci.yml\n"
            "+++ b/.github/workflows/ci.yml\n"
            "@@ -1,5 +1,6 @@\n"
            " name: ci\n"
            " permissions:\n"
            "   contents: write\n"  # context line, idx=2
            "+  issues: read\n"  # added line, idx=3 — within ±2 of idx=2
            " on:\n"
            "   push:\n"
        )
        rule = WorkflowPermissionsRule()
        results = rule.run(_ctx(diff))
        assert any(
            "write" in r.message.lower() and r.severity == RuleSeverity.ERROR for r in results
        ), "Context 'write' permission within ±2 of added line should be detected"

    def test_proximity_window_outside(self) -> None:
        """Context line with 'write' permission >2 lines from any added line is NOT detected."""
        diff = (
            "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
            "--- a/.github/workflows/ci.yml\n"
            "+++ b/.github/workflows/ci.yml\n"
            "@@ -1,8 +1,9 @@\n"
            " name: ci\n"
            " permissions:\n"
            "   contents: write\n"  # context, idx=2
            "   packages: read\n"  # context, idx=3
            "   pages: read\n"  # context, idx=4
            "   actions: read\n"  # context, idx=5
            "+  id-token: read\n"  # added, idx=6 — >2 away from idx=2
            " on:\n"
            "   push:\n"
        )
        rule = WorkflowPermissionsRule()
        results = rule.run(_ctx(diff))
        assert not any("write" in r.message.lower() for r in results), (
            "Context 'write' permission >2 lines from added line should NOT be detected"
        )
