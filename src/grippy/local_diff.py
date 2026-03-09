# SPDX-License-Identifier: MIT
"""Local git diff acquisition for MCP server and CLI use.

Replaces the GitHub API diff fetcher (used in CI) with direct git subprocess
calls for local review workflows.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


class DiffError(Exception):
    """Raised when diff acquisition fails."""


_REF_PATTERN = re.compile(r"^[A-Za-z0-9\-_./~^]+$")


def _validate_ref(ref: str) -> None:
    """Validate a git ref against injection attacks.

    Raises:
        DiffError: If the ref contains unsafe characters.
    """
    if not _REF_PATTERN.match(ref):
        raise DiffError(f"Unsafe ref: {ref!r}")
    if ref.startswith("-"):
        msg = f"Invalid ref: {ref!r} — refs must not start with '-'"
        raise DiffError(msg)


def parse_scope(scope: str) -> list[str]:
    """Parse a scope string into a git command argv list.

    Supported scopes:
        - ``"staged"`` -- diff of the staging area
        - ``"commit:<ref>"`` -- show a single commit's diff
        - ``"range:<base>..<head>"`` -- diff between two refs

    Raises:
        DiffError: If the scope format is invalid or refs are unsafe.
    """
    if scope == "staged":
        return ["git", "diff", "--cached"]

    if scope.startswith("commit:"):
        ref = scope[len("commit:") :]
        _validate_ref(ref)
        return ["git", "show", "--format=", ref, "--"]

    if scope.startswith("range:"):
        range_str = scope[len("range:") :]
        if ".." not in range_str:
            raise DiffError(f"Invalid range (missing '..'): {range_str!r}")
        base, head = range_str.split("..", 1)
        _validate_ref(base)
        _validate_ref(head)
        return ["git", "diff", f"{base}..{head}"]

    raise DiffError(f"Invalid scope: {scope!r}")


def get_local_diff(scope: str = "staged") -> str:
    """Run a git diff command and return its output.

    Args:
        scope: Diff scope string (see :func:`parse_scope`).

    Returns:
        The raw unified diff text.

    Raises:
        DiffError: If the git command exits with a non-zero status.
    """
    cmd = parse_scope(scope)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        msg = "Git command timed out after 30 seconds"
        raise DiffError(msg) from None
    if result.returncode != 0:
        raise DiffError(result.stderr.strip())
    return result.stdout


def get_repo_root() -> Path | None:
    """Return the git repo root, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def diff_stats(diff: str) -> dict[str, int]:
    """Compute basic statistics from a unified diff string.

    Returns:
        A dict with keys ``files``, ``additions``, ``deletions``.
    """
    files = 0
    additions = 0
    deletions = 0
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            files += 1
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
    return {"files": files, "additions": additions, "deletions": deletions}
